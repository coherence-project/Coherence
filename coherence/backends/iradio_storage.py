# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

from twisted.internet import defer

from coherence.upnp.core import utils

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement

from coherence import log
from coherence.backend import BackendItem, BackendStore

from urlparse import urlsplit

class ProxyStream(utils.ReverseProxyResource, log.Loggable):
    logCategory = 'iradio'
    
    def __init__(self, uri):
        self.uri = uri
        _,host_port,path,_,_ = urlsplit(uri)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
            port = int(port)
        else:
            host = host_port
            port = 80

        if path == '':
            path = '/'

        #print "ProxyStream init", host, port, path
        utils.ReverseProxyResource.__init__(self, host, port, path)

    def requestFinished(self, result):
        """ self.connection is set in utils.ReverseProxyResource.render """
        self.info("ProxyStream requestFinished")
        self.connection.transport.loseConnection()

    def render(self, request):
        self.info("this is our render method",request.method, request.uri, request.client, request.clientproto)
        self.info("render", request.getAllHeaders())
        if request.clientproto == 'HTTP/1.1':
            self.connection = request.getHeader('connection')
            if self.connection:
                tokens = map(str.lower, connection.split(' '))
                if 'close' in tokens:
                    d = request.notifyFinish()
                    d.addBoth(self.requestFinished)
        else:
            d = request.notifyFinish()
            d.addBoth(self.requestFinished)
        return utils.ReverseProxyResource.render(self, request)

class IRadioItem(log.Loggable):
    logCategory = 'iradio'

    def __init__(self, id, obj, parent, mimetype, urlbase, UPnPClass,update=False):
        self.id = id

        self.name = obj.get('name')
        self.mimetype = mimetype

        self.parent = parent
        if parent:
            parent.add_child(self,update=update)

        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(id, parent_id, self.name)
        if isinstance(self.item, Container):
            self.item.childCount = 0
        self.child_count = 0
        self.children = None

        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'

        if self.mimetype == 'directory':
            self.url = urlbase + str(self.id)
        else:
            self.url = urlbase + str(self.id)
            self.location = ProxyStream(obj.get('url'))
            #self.url = obj.get('url')

        if self.mimetype == 'directory':
            self.update_id = 0
        else:
            res = Resource(self.url, 'http-get:*:%s:%s' % (obj.get('mimetype'),
                                                                     ';'.join(('DLNA.ORG_PN=MP3',
                                                                               'DLNA.ORG_CI=0',
                                                                               'DLNA.ORG_OP=01',
                                                                               'DLNA.ORG_FLAGS=01700000000000000000000000000000'))))
            res.size = 0 #None
            self.item.res.append(res)


    def remove(self):
        if self.parent:
            self.parent.remove_child(self)
        del self.item

    def add_child(self, child, update=False):
        if self.children == None:
            self.children = []
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
        if self.children == None:
            def got_page(result):
                result = utils.parse_xml(result, encoding='utf-8')
                tunein = result.find('tunein')
                if tunein != None:
                    tunein = tunein.get('base','/sbin/tunein-station.pls')
                prot,host_port,path,_,_ = urlsplit(self.store.config.get('genrelist','http://www.shoutcast.com/sbin/newxml.phtml'))
                tunein = prot + '://' + host_port + tunein

                def append_new(result, s):
                    result = result[0].split('\n')
                    for line in result:
                        if line.startswith('File1='):
                            s['url'] = line[6:]
                            self.store.append(s,self)
                            break

                l = []
                for station in result.findall('station'):
                    if station.get('mt') == 'audio/mpeg':
                        d2 = utils.getPage('%s?id=%s' % (tunein, station.get('id')), timeout=20)
                        d2.addCallback(append_new, {'name':station.get('name').encode('utf-8'),
                                                    'mimetype':station.get('mt'),
                                                    'id':station.get('id'),
                                                    'url':None})
                        d2.addErrback(got_error)
                        l.append(d2)
                dl = defer.DeferredList(l)

                def process_items(result):
                    self.info("process_item", result, self.children)
                    if self.children == None:
                        return  []
                    if request_count == 0:
                        return self.children[start:]
                    else:
                        return self.children[start:request_count]

                dl.addCallback(process_items)
                return dl

            def got_error(error):
                self.warning("connection to ShoutCast service failed! %r", error)
                self.debug("%r", error.getTraceback())

            d = utils.getPage('%s?genre=%s' % (self.store.config.get('genrelist','http://www.shoutcast.com/sbin/newxml.phtml'),self.name))
            d.addCallbacks(got_page, got_error, None, None, None, None)
            return d
        else:
            if request_count == 0:
                return self.children[start:]
            else:
                return self.children[start:request_count]

    def get_child_count(self):
        return self.child_count

    def get_id(self):
        return self.id

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
        return 'id: ' + str(self.id) + ' @ ' + self.url + ' ' + self.name

class IRadioStore(BackendStore):

    logCategory = 'iradio'

    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)
        self.next_id = 1000
        self.config = kwargs
        self.name = kwargs.get('name','iRadioStore')

        self.update_id = 0

        self.wmc_mapping = {'4': 1000}


        self.store = {}

        self.init_completed()


    def __repr__(self):
        return self.__class__.__name__

    def append( self, obj, parent):
        if isinstance(obj, basestring):
            mimetype = 'directory'
        else:
            mimetype = obj['mimetype']

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = IRadioItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass, update=update)
        self.store[id].store = self
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

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        try:
            id = int(id)
        except ValueError:
            id = 1000

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

    def upnp_init(self):
        self.current_connection_id = None
        #parent = self.append('iRadio', None)

        #self.append({'name':'GrooveFM','mimetype':'audio/mpeg','url':'http://80.252.111.34:10028/'}, parent)
        #self.append({'name':'Dancing Queen','mimetype':'audio/mpeg','url':'http://netzflocken.de/files/dq.mp3'}, parent)

        parent = self.append({'name':'iRadio','mimetype':'directory'}, None)

        def got_page(result):
            result = utils.parse_xml(result, encoding='utf-8')
            for genre in result.findall('genre'):
                self.append({'name':genre.get('name').encode('utf-8'),
                             'mimetype':'directory',
                             'url':'%s?genre=%s' % (self.config.get('genrelist','http://www.shoutcast.com/sbin/newxml.phtml'),genre.get('name'))},parent)

        def got_error(error):
            self.warning("connection to ShoutCast service failed! %r", error)
            self.debug("%r", error.getTraceback())

        utils.getPage(self.config.get('genrelist','http://www.shoutcast.com/sbin/newxml.phtml')).addCallbacks(got_page, got_error, None, None, None, None)

        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    ['http-get:*:audio/mpeg:*',
                                                                     'http-get:*:audio/x-scpls:*'],
                                                                    default=True)

def main():

    f = IRadioStore(None)

    def got_upnp_result(result):
        print "upnp", result

    f.upnp_init()
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
