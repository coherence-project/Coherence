# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import re

from twisted.spread import pb
from twisted.internet import reactor

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement
from coherence.upnp.core.soap_service import errorCode

class ElisaMediaStore:

    """ this is a backend to the Elisa Media DB

        Elisa needs to expose two methods

        get_root_id(media_type)
            if media_type == '*'
                this returns the root id of the media collection
            if media_type == 'audio'
                this returns the root id of the audio collection

        get_item_by_id(id)
            this returns a dict with the following keys:
            id = id in the media db
            parent_id = parent_id in the media db
            name = title, album name or basename
            mimetype = 'directory' or real mimetype
            children = list of objects for which this item is the parent
            location = filesystem path if item is a file
            size = in bytes (OPTIONAL)
    """

    def __init__(self, name, host, urlbase, ignore_patterns, server):
        self.name = name
        self.host = host
        if urlbase[len(urlbase)-1] != '/':
            urlbase += '/'
        self.urlbase = urlbase
        self.server = server
        self.update_id = 0
        self.root_id = 0
        self.get_root_id()

    def get_store(self):
        factory = pb.PBClientFactory()
        reactor.connectTCP(self.host, 8789, factory)
        return factory.getRootObject()
        
    def set_root_id( self, id):
        self.root_id = id

    def get_root_id( self, media_type='audio'):
        """ ask Elisa to tell us the id of the top item
            representing the media_type == 'something' collection """
        store = self.get_store()
        dfr = store.addCallback(lambda object:
                                object.callRemote('get_cache_manager'))
        dfr.addCallback(lambda cache_mgr:
                        cache_mgr.callRemote("get_media_root_id", media_type))
        dfr.addCallback(self.set_root_id)


    def upnp_init(self):
        self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo', 'http-get:*:audio/mpeg:*')

    def upnp_Browse(self, *args, **kwargs):
        ObjectID = int(kwargs['ObjectID'])
        BrowseFlag = kwargs['BrowseFlag']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']
        
        def build_upnp_item(elisa_item):
            UPnPClass = classChooser(elisa_item['mimetype'])
            upnp_item = UPnPClass(elisa_item['id'],
                                  elisa_item['parent_id'],
                                  elisa_item['name'])
            if isinstance(upnp_item, Container):
                upnp_item.childCount = len(elisa_item.get('children',[]))
            else:
                url = self.urlbase + elisa_item['location'] # FIXME
                upnp_item.res = Resource(url,
                                         'http-get:*:%s:*' % elisa_item['mimetype'])
                try:
                    upnp_item.res.size = elisa_item['size']
                except:
                    upnp_item.res.size = None
                upnp_item.res = [ upnp_item.res ]

            return upnp_item
        
        def got_result(elisa_item):
            didl = DIDLElement()
            children = elisa_item.get('children',[])
            if BrowseFlag == 'BrowseDirectChildren':
                if RequestedCount == 0:
                    childs = children[StartingIndex:]
                else:
                    childs = children[StartingIndex:StartingIndex+RequestedCount]
                for child in childs:
                    didl.addItem(build_upnp_item(child))
                total = len(children)
            else:
                didl.addItem(build_upnp_item(elisa_item))
                total = 1

            r = { 'Result': didl.toString(), 'TotalMatches': total,
                  'NumberReturned': didl.numItems()}

            if hasattr(elisa_item, 'update_id'):
                r['UpdateID'] = item.update_id
            else:
                r['UpdateID'] = self.update_id

            return r
    
        def errback(r):
            raise errorCode(701)

        id = ObjectID
        if id == 0:
            id = self.root_id

        store = self.get_store()
        dfr = store.addCallback(lambda object:
                                object.callRemote('get_cache_manager'))
        dfr.addErrback(errback)
        dfr.addCallback(lambda cache_mgr:
                        cache_mgr.callRemote("get_media_node_with_id", id))
        dfr.addCallback(got_result)
        return dfr
            


if __name__ == '__main__':
    def main():

        p = 'localhost'

        def got_result(result):
            print result

        f = MediaStore('my media',p, 'http://localhost/',())

        dfr = f.upnp_Browse(BrowseFlag='BrowseDirectChildren',
                            RequestedCount=0,
                            StartingIndex=0,
                            ObjectID=23,
                            SortCriteria='*',
                            Filter='')
        dfr.addCallback(got_result)
        dfr.addCallback(lambda _: reactor.stop())
        
    reactor.callLater(0.1, main)
    reactor.run()
        
