# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import re

from twisted.spread import pb
from twisted.internet import reactor
from twisted.python import failure

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement
from coherence.upnp.core.soap_service import errorCode

import coherence.extern.louie as louie

from coherence.extern.simple_plugin import Plugin

class ElisaMediaStore(Plugin):

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
            cover = url by which the cover image can be retrieved  (OPTIONAL)
            size = in bytes (OPTIONAL)
    """

    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        self.name = kwargs.get('name','Elisa')
        self.host = kwargs.get('host','127.0.0.1')
        self.urlbase = kwargs.get('urlbase','')
        ignore_patterns = kwargs.get('ignore_patterns',[])

        if self.urlbase[len(self.urlbase)-1] != '/':
            self.urlbase += '/'
        self.server = server
        self.update_id = 0
        self.root_id = 0
        self.get_root_id()

    def __repr__(self):
        return "Elisa storage"

    def get_store(self):
        factory = pb.PBClientFactory()
        factory.noisy = False
        reactor.connectTCP(self.host, 8789, factory)
        return factory.getRootObject()

    def get_by_id(self,id):
        try:
            return self.store[int(id)]
        except:
            return None

    def set_root_id( self, id):
        self.root_id = id
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

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
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                            ['internal:%s:*:*' % self.host,
                             'http-get:*:audio/mpeg:*'])

    def upnp_Browse(self, *args, **kwargs):
        ObjectID = kwargs['ObjectID']
        BrowseFlag = kwargs['BrowseFlag']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']

        def build_upnp_item(elisa_item):
            UPnPClass = classChooser(elisa_item['mimetype'])
            upnp_item = None
            if UPnPClass:
                upnp_item = UPnPClass(elisa_item['id'],
                                      elisa_item['parent_id'],
                                      elisa_item['name'])
                if isinstance(upnp_item, Container):
                    upnp_item.childCount = len(elisa_item.get('children',[]))
                    if len(Filter) > 0:
                        upnp_item.searchable = True
                        upnp_item.searchClass = ('object',)
                else:
                    internal_url = elisa_item['location'].get('internal')
                    external_url = elisa_item['location'].get('external')
                    try:
                        size = elisa_item['size']
                    except:
                        size = None
                    try:
                        cover = elisa_item['cover']
                        if cover != '':
                            upnp_item.albumArtURI = cover
                    except:
                        pass

                    res = Resource(internal_url,
                                   'internal:%s:*:*' %self.host)
                    res.size = size
                    upnp_item.res.append(res)
                    res = Resource(external_url,
                                   'http-get:*:%s:*' % elisa_item['mimetype'])
                    res.size = size
                    upnp_item.res.append(res)

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
                    if child is not None:
                        item = build_upnp_item(child)
                        if item:
                            didl.addItem(item)
                total = len(children)
            elif elisa_item:
                item = build_upnp_item(elisa_item)
                if item:
                    didl.addItem(item)
                total = 1

            r = { 'Result': didl.toString(), 'TotalMatches': total,
                  'NumberReturned': didl.numItems()}

            if hasattr(elisa_item, 'update_id'):
                r['UpdateID'] = item.update_id
            else:
                r['UpdateID'] = self.update_id

            return r

        def errback(r):
            return failure.Failure(errorCode(701))

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

        f = MediaStore(None,'my media',p, 'http://localhost/',())

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
