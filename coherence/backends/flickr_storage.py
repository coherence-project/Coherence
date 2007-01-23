# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

import time
import re

from twisted.python import failure
from twisted.web.xmlrpc import Proxy

from elementtree.ElementTree import fromstring

from coherence.upnp.core.utils import parse_xml

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement
from coherence.upnp.core.soap_proxy import SOAPProxy
from coherence.upnp.core.soap_service import errorCode

from coherence.extern.logger import Logger
log = Logger('FlickrStore')

class FlickrItem:

    def __init__(self, id, obj, parent, mimetype, urlbase, UPnPClass,update=False):
        self.id = id
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
  
        if self.mimetype == 'directory':
            if( len(urlbase) and urlbase[-1] != '/'):
                urlbase += '/'
            self.url = urlbase + str(self.id)
        else:
            self.url = u"http://farm%s.static.flickr.com/%s/%s_%s_o.jpg" % (
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
            
    def __del__(self):
        #print "FSItem __del__", self.id, self.get_name()
        pass

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
        #print "remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name())
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

    wmc_mapping = {'B': 1000}
    
    def __init__(self, server, **kwargs):
        self.next_id = 1000
        self.name = kwargs.get('name','Flickr')
        
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

        self.store[id] = FlickrItem( id, obj, parent, mimetype, self.urlbase, UPnPClass, update=update)
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
            
        return None
        
    def append_flickr_result(self, result, parent):
        for photo in result.getiterator('photo'):
            self.append(photo, parent)

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

    def flickr_call(self, method, **kwargs):
        def got_result(result):
            #print 'flickr_call result', result.encode('utf-8')
            result = parse_xml(result, encoding='utf-8')
            return result

        def got_error(error):
            log.info(error)
            log.error("connection to Flickr service failed!")
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
        parent = self.append( 'Most Wanted', parent)
        d = self.flickr_interestingness()
        d.addCallback(self.append_flickr_result, parent)

def main():

    f = FlickrStore(None)
    
    def got_flickr_result(result):
        print "flickr", result
        for photo in result.getiterator('photo'):
            title = photo.get('title').encode('utf-8')
            if len(title) == 0:
                title = u'untitled'
                
            url = "http://farm%s.static.flickr.com/%s/%s_%s_o.jpg" % (
                        photo.get('farm').encode('utf-8'),
                        photo.get('server').encode('utf-8'),
                        photo.get('id').encode('utf-8'),
                        photo.get('secret').encode('utf-8'))
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
