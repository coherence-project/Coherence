# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

# this is a backend to the Elisa Media DB
#
# Elisa needs to expose two methods
#
#   get_root_id(media_type)
#       if media_type == '*'
#       this returns the root id of the media collection
#       if media_type == 'audio'
#       this returns the root id of the audio collection
#
#   get_item_by_id(id)
#       this returns an object with the following attributes
#       (or a dict with the keys)
#       id = id in the media db
#       parent_id = parent_id in the media db
#       name = title, album name or basename
#       mimetype = 'directory' or real mimetype
#      size = in bytes
#      children = list of objects for which this item is the parent
#       location = filesystem path if item is a file
#

import re

from twisted.spread import pb
from twisted.internet import reactor

from DIDLLite import classChooser, Container, Resource, DIDLElement
from soap_service import errorCode

class MediaStore:

    def __init__(self, name, path, urlbase, ignore_patterns):
        self.name = name
        if urlbase[len(urlbase)-1] != '/':
            urlbase += '/'
        self.urlbase = urlbase
        self.update_id = 0
        self.root_id = 0
        factory = pb.PBClientFactory()
        reactor.connectTCP(path, 8789, pb.PBClientFactory())
        self.store = factory.getRootObject()
        self.get_root_id()
        
    def set_root_id( self, id):
        self.root_id = id

    def get_root_id( self, media_type='audio'):
        """ ask Elisa to tell us the id of the top item
            representing the media_type == 'something' collection """
        dfr = self.store.callRemote("get_root_id", type)
        dfr.addCallback(self.set_root_id)

    def upnp_Browse(self, *args, **kwargs):
        ObjectID = int(kwargs['ObjectID'])
        BrowseFlag = kwargs['BrowseFlag']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']
        
        def build_upnp_item(elisa_item):
            UPnPClass = classChooser(elisa_item.mimetype)
            upnp_item = UPnPClass(elisa_item.id, elisa_item.parent_id, elisa_item.name)
            if isinstance(upnp_item, Container):
                upnp_item.childCount = len(elisa_item.children)
            else:
                url = self.urlbase + elisa_item.location # FIXME
                upnp_item.res = Resource(elisa_item.url, 'http-get:*:%s:*' % elisa_item.mimetype)
                upnp_item.res.size = elisa_item.size
                upnp_item.res = [ upnp_item.res ]


        def got_result(elisa_item):
            didl = DIDLElement()
            if BrowseFlag == 'BrowseDirectChildren':
                if RequestedCount == 0:
                    childs = elisa_item.children[StartingIndex:]
                else:
                    childs = elisa_item.children[StartingIndex:StartingIndex+RequestedCount]
                for child in childs:
                    didl.addItem(build_upnp_item(child))
                total = len(elisa_item.children)
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

        id = ObjectID
        if id == 0:
            id = self.root_id
        dfr = self.store.callRemote("get_item_by_id", id)
        dfr.addCallback(self.got_result)
        dfr.addErrback(lambda _:raise errorCode(701))
            


if __name__ == '__main__':
    
    print 'test me'
    