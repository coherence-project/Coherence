# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

import time
import re
from datetime import datetime
from email.Utils import parsedate_tz

from twisted.python import failure
from twisted.web import proxy
from twisted.web.xmlrpc import Proxy
from twisted.internet import task

from coherence.upnp.core.utils import parse_xml

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement
from coherence.upnp.core.soap_proxy import SOAPProxy
from coherence.upnp.core.soap_service import errorCode

import louie

from coherence import log

from urlparse import urlsplit

def myGetPage(url, contextFactory=None, *args, **kwargs):
    scheme, host, port, path = _parse(url)
    factory = HTTPClientFactory(url, *args, **kwargs)
    reactor.connectTCP(host, port, factory)
    return factory

class ProxyImage(proxy.ReverseProxyResource):

    def __init__(self, uri):
        self.uri = uri
        _,host_port,path,_,_ = urlsplit(uri)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
            port = int(port)
        else:
            host = host_port
            port = 80

        proxy.ReverseProxyResource.__init__(self, host, port, path)

class FlickrItem(log.Loggable):
    logCategory = 'flickr_storage'
    
    def __init__(self, id, obj, parent, mimetype, urlbase, UPnPClass,update=False,proxy=False):
        self.id = id
        self.real_url = None
        if mimetype == 'directory':
            self.name = obj
            self.mimetype = mimetype
        else:
            self.name = obj.get('title').encode('utf-8')
            if len(self.name) == 0:
                self.name = 'untitled'
            self.mimetype = 'image/jpeg'

        self.parent = parent
        if parent:
            parent.add_child(self,update=update)

        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'

        if self.mimetype == 'directory':
            self.flickr_id = None
            self.url = urlbase + str(self.id)
        else:
            self.flickr_id = obj.get('id')
            self.real_url = "http://farm%s.static.flickr.com/%s/%s_%s.jpg" % (
                            obj.get('farm'),
                            obj.get('server'),
                            obj.get('id'),
                            obj.get('secret'))

            if proxy == True:
                self.url = urlbase + str(self.id)
                self.location = ProxyImage(self.real_url)
            else:
                self.url = u"http://farm%s.static.flickr.com/%s/%s_%s.jpg" % (
                        obj.get('farm').encode('utf-8'),
                        obj.get('server').encode('utf-8'),
                        obj.get('id').encode('utf-8'),
                        obj.get('secret').encode('utf-8'))

        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(id, parent_id, self.get_name())
        self.child_count = 0
        self.children = []

        if self.mimetype == 'directory':
            self.update_id = 0
        else:
            self.item.res = Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            self.item.res.size = None
            self.item.res = [ self.item.res ]
            self.set_item_size_and_date()

    def __del__(self):
        #print "FSItem __del__", self.id, self.get_name()
        pass

    def set_item_size_and_date(self):
        from coherence.upnp.core.utils import getPage

        def gotPhoto(result):
            self.debug("gotPhoto", result)
            _, headers = result
            length = headers.get('content-length',None)
            modified = headers.get('last-modified',None)
            if length != None:
                self.item.res[0].size = int(length[0])
            if modified != None:
                """ Tue, 06 Feb 2007 15:56:32 GMT """
                self.item.date = datetime(*parsedate_tz(modified[0])[0:6])

        def gotError(failure, url):
            self.warning("error requesting", failure, url)
            self.info(failure)

        getPage(self.real_url,method='HEAD').addCallbacks(gotPhoto, gotError, None, None, [self.real_url], None)

    def remove(self):
        #print "FSItem remove", self.id, self.get_name(), self.parent
        if self.parent:
            self.parent.remove_child(self)
        del self.item

    def add_child(self, child, update=False):
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update == True:
            self.update_id += 1


    def remove_child(self, child):
        self.info("remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name()))
        if child in self.children:
            self.child_count -= 1
            if isinstance(self.item, Container):
                self.item.childCount -= 1
            self.children.remove(child)
            self.update_id += 1

    def get_children(self,start=0,request_count=0):
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]

    def get_child_count(self):
        return self.child_count

    def get_id(self):
        return self.id

    def get_location(self):
        return self.location

    def get_update_id(self):
        if hasattr(self, 'update_id'):
            return self.update_id
        else:
            return None

    def get_path(self):
        return self.url

    def get_name(self):
        return self.name

    def get_flickr_id(self):
        return self.flickr_id

    def get_child_by_flickr_id(self, flickr_id):
        for c in self.children:
            if flickr_id == c.flickr_id:
                return c
        return None

    def get_parent(self):
        return self.parent

    def get_item(self):
        return self.item

    def get_xml(self):
        return self.item.toString()

    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + self.url

class FlickrStore:

    implements = ['MediaServer']

    wmc_mapping = {'16': 1000}

    def __init__(self, server, **kwargs):
        self.next_id = 1000
        self.name = kwargs.get('name','Flickr')
        self.proxy = kwargs.get('proxy','false')
        self.refresh = int(kwargs.get('refresh',60))*60
        if self.proxy in [1,'Yes','yes','True','true']:
            self.proxy = True
        else:
            self.proxy = False

        self.urlbase = kwargs.get('urlbase','')
        if( len(self.urlbase)>0 and
            self.urlbase[len(self.urlbase)-1] != '/'):
            self.urlbase += '/'

        ignore_patterns = kwargs.get('ignore_patterns',[])
        ignore_file_pattern = re.compile('|'.join(['^\..*'] + list(ignore_patterns)))

        self.server = server
        self.update_id = 0
        self.flickr = Proxy('http://api.flickr.com/services/xmlrpc/')
        self.flickr_api_key = '837718c8a622c699edab0ea55fcec224'
        self.store = {}

        self.refresh_store_loop = task.LoopingCall(self.refresh_store)
        self.refresh_store_loop.start(self.refresh, now=False)

        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def append( self, obj, parent):
        if isinstance(obj, str):
            mimetype = 'directory'
        else:
            mimetype = 'image/'

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FlickrItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass, update=update, proxy=self.proxy)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent:
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        if mimetype == 'directory':
            return self.store[id]


        def update_photo_details(result, photo):
            dates = result.find('dates')
            self.info("update_photo_details", dates.get('posted'), dates.get('taken'))
            photo.item.date = datetime(*time.strptime(dates.get('taken'),
                                               "%Y-%m-%d %H:%M:%S")[0:6])

        #d = self.flickr_photos_getInfo(obj.get('id'),obj.get('secret'))
        #d.addCallback(update_photo_details, self.store[id])

        return None

    def remove(self, id):
        #print 'FlickrStore remove id', id
        try:
            item = self.store[int(id)]
            parent = item.get_parent()
            item.remove()
            del self.store[int(id)]
            if hasattr(self, 'update_id'):
                self.update_id += 1
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)
        except:
            pass

    def append_flickr_result(self, result, parent):
        count = 0
        for photo in result.getiterator('photo'):
            self.append(photo, parent)
            count += 1
        self.warning("initialized photo set %s with %d images" % (parent.get_name(), count))

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
        id = int(id)
        if id == 0:
            id = 1000
        try:
            return self.store[id]
        except:
            return None

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def refresh_store(self):
        self.info("refresh_store")

        def update_flickr_result(result, parent):
            """ - is in in the store, but not in the update,
                  remove it from the store
                - the photo is already in the store, skip it
                - if in the update, but not in the store,
                  append it to the store
            """
            old_ones = {}
            new_ones = {}
            for child in parent.get_children():
                old_ones[child.get_flickr_id()] = child
            for photo in result.findall('photo'):
                new_ones[photo.get('id')] = photo
            for id,child in old_ones.items():
                if new_ones.has_key(id):
                    self.debug(id, "already there")
                    del new_ones[id]
                else:
                    self.debug(child.get_flickr_id(), "needs removal")
                    del old_ones[id]
                    self.remove(child.get_id())
            self.info("refresh pass 1:", "old", len(old_ones), "new", len(new_ones), "store", len(self.store))
            for photo in new_ones.values():
                self.append(photo, parent)

            self.info("refresh pass 2:", "old", len(old_ones), "new", len(new_ones), "store", len(self.store))
            if len(new_ones) > 0:
                self.warning("updated photo set %s with %d new images" % (parent.get_name(), len(new_ones)))

        d = self.flickr_interestingness()
        d.addCallback(update_flickr_result, self.most_wanted)

    def flickr_call(self, method, **kwargs):
        def got_result(result):
            #print 'flickr_call result', result.encode('utf-8')
            result = parse_xml(result, encoding='utf-8')
            return result

        def got_error(error):
            self.info(error)
            self.error("connection to Flickr service failed!")
            return error

        args = {}
        args.update(kwargs)
        args['api_key'] = self.flickr_api_key

        d = self.flickr.callRemote(method, args)
        d.addCallback(got_result)
        d.addErrback(got_error)
        return d

    def flickr_test_echo(self, name='Test'):
        d = self.flickr_call('flickr.test.echo', **kwargs)
        return d

    def flickr_photos_getInfo(self, photo_id=None, secret=None):
        d = self.flickr_call('flickr.photos.getInfo', photo_id=photo_id, secret=secret)
        return d

    def flickr_interestingness(self, date=None, per_page=100):
        if date == None:
            date = time.strftime( "%Y-%m-%d", time.localtime(time.time()-86400))
        if per_page > 500:
            per_page = 500
        #d = self.flickr_call('flickr.interestingness.getList', date=date, per_page=per_page)
        d = self.flickr_call('flickr.interestingness.getList', per_page=per_page)
        return d

    def soap_flickr_test_echo(self, value):
        client = SOAPProxy("http://api.flickr.com/services/soap/",
                            namespace=("x","urn:flickr"),
                            envelope_attrib=[("xmlns:s", "http://www.w3.org/2003/05/soap-envelope"),
                                            ("xmlns:xsi", "http://www.w3.org/1999/XMLSchema-instance"),
                                            ("xmlns:xsd", "http://www.w3.org/1999/XMLSchema")],
                            soapaction="FlickrRequest")
        d = client.callRemote( "FlickrRequest",
                                method='flickr.test.echo',
                                name=value,
                                api_key='837718c8a622c699edab0ea55fcec224')
        def got_results(result):
            print result

        d.addCallback(got_results)
        return d

    def upnp_init(self):
        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    'http-get:*:image/jpeg:*,'
                                                                    'http-get:*:image/gif:*,'
                                                                    'http-get:*:image/png:*',
                                                                    default=True)
        parent = self.append( 'Flickr', None)
        self.most_wanted = self.append( 'Most Wanted', parent)
        d = self.flickr_interestingness()
        d.addCallback(self.append_flickr_result, self.most_wanted)

def main():

    f = FlickrStore(None)

    def got_flickr_result(result):
        print "flickr", result
        for photo in result.getiterator('photo'):
            title = photo.get('title').encode('utf-8')
            if len(title) == 0:
                title = u'untitled'

            for k,item in photo.items():
                print k, item

            url = "http://farm%s.static.flickr.com/%s/%s_%s.jpg" % (
                        photo.get('farm').encode('utf-8'),
                        photo.get('server').encode('utf-8'),
                        photo.get('id').encode('utf-8'),
                        photo.get('secret').encode('utf-8'))
            #orginal_url = "http://farm%s.static.flickr.com/%s/%s_%s_o.jpg" % (
            #            photo.get('farm').encode('utf-8'),
            #            photo.get('server').encode('utf-8'),
            #            photo.get('id').encode('utf-8'),
            #            photo.get('originalsecret').encode('utf-8'))
            print photo.get('id').encode('utf-8'), title, url

    def got_upnp_result(result):
        print "upnp", result

    #d = f.flickr_test_echo(name='Coherence')
    d = f.flickr_interestingness()
    d.addCallback(got_flickr_result)

    #f.upnp_init()
    #print f.store
    #r = f.upnp_Browse(BrowseFlag='BrowseDirectChildren',
    #                    RequestedCount=0,
    #                    StartingIndex=0,
    #                    ObjectID=0,
    #                    SortCriteria='*',
    #                    Filter='')
    #got_upnp_result(r)


if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
