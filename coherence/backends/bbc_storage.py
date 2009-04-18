# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008 Frank Scholz <coherence@beebits.net>

from coherence.backend import BackendStore
from coherence.backend import BackendItem
from coherence.upnp.core import DIDLLite
from coherence.upnp.core.utils import getPage

from twisted.internet import reactor
from twisted.python.util import OrderedDict

from coherence.extern.et import parse_xml

ROOT_CONTAINER_ID = 0
SERIES_CONTAINER_ID = 100


class BBCItem(BackendItem):

    def __init__(self, parent_id, id, title, url):
        self.parent_id = parent_id
        self.id = id
        self.location = url
        self.name = title
        self.duration = None
        self.size = None
        self.mimetype = 'audio/mpeg'
        self.description = None

        self.item = None

    def get_item(self):
        if self.item == None:
            self.item = DIDLLite.AudioItem(self.id, self.parent_id, self.name)
            self.item.description = self.description

            res = DIDLLite.Resource(self.location, 'http-get:*:%s:*' % self.mimetype)
            res.duration = self.duration
            res.size = self.size
            self.item.res.append(res)
        return self.item

class Container(BackendItem):

    def __init__(self, id, store, parent_id, title):
        self.url = store.urlbase+str(id)
        self.parent_id = parent_id
        self.id = id
        self.name = title
        self.mimetype = 'directory'
        self.update_id = 0
        self.children = []

        self.item = DIDLLite.Container(self.id, self.parent_id, self.name)
        self.item.childCount = 0

        self.sorted = False

    def add_child(self, child):
        id = child.id
        if isinstance(child.id, basestring):
            _,id = child.id.split('.')
        self.children.append(child)
        self.item.childCount += 1
        self.sorted = False

    def get_children(self, start=0, end=0):
        if self.sorted == False:
            def childs_sort(x,y):
                r = cmp(x.name,y.name)
                return r

            self.children.sort(cmp=childs_sort)
            self.sorted = True
        if end != 0:
            return self.children[start:end]
        return self.children[start:]

    def get_child_count(self):
        return len(self.children)

    def get_path(self):
        return self.url

    def get_item(self):
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id


class BBCStore(BackendStore):

    implements = ['MediaServer']
    rss_url = "http://open.bbc.co.uk/rad/uriplay/availablecontent"

    def __init__(self, server, *args, **kwargs):
        BackendStore.__init__(self,server,**kwargs)

        self.name = kwargs.get('name', 'BBC')
        self.refresh = int(kwargs.get('refresh', 1)) * (60 *60)

        self.next_id = 1000
        self.update_id = 0
        self.last_updated = None
        self.store = {}
        d = self.update_data()
        d.addCallback(self.init_completed)

    def get_next_id(self):
        self.next_id += 1
        return self.next_id

    def get_by_id(self,id):
        #print "looking for id %r" % id
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        try:
            return self.store[int(id)]
        except (ValueError,KeyError):
            pass
        return None

    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable( \
                0, 'SourceProtocolInfo', ['http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=11;DLNA.ORG_FLAGS=01700000000000000000000000000000',
                                          'http-get:*:audio/mpeg:*'])

    def update_data(self):

        def fail(f):
            print "fail", f
            return f

        dfr = getPage(self.rss_url)
        dfr.addCallback(parse_xml)
        dfr.addErrback(fail)
        dfr.addCallback(self.parse_data)
        dfr.addErrback(fail)
        dfr.addBoth(self.queue_update)
        return dfr

    def parse_data(self, xml_data):
        root = xml_data.getroot()

        self.store = {}

        self.store[ROOT_CONTAINER_ID] = \
                        Container(ROOT_CONTAINER_ID,self,-1, self.name)
        self.store[SERIES_CONTAINER_ID] = \
                        Container(SERIES_CONTAINER_ID,self,ROOT_CONTAINER_ID, 'Series')
        self.store[ROOT_CONTAINER_ID].add_child(self.store[SERIES_CONTAINER_ID])


        for brand in root.findall('./{http://purl.org/ontology/po/}Brand'):
            first = None
            for episode in brand.findall('*/{http://purl.org/ontology/po/}Episode'):
                for version in episode.findall('*/{http://purl.org/ontology/po/}Version'):
                    seconds = int(version.find('./{http://uriplay.org/elements/}publishedDuration').text)
                    hours = seconds / 3600
                    seconds = seconds - hours * 3600
                    minutes = seconds / 60
                    seconds = seconds - minutes * 60
                    duration = ("%d:%02d:%02d") % (hours, minutes, seconds)
                    for manifestation in version.findall('./{http://uriplay.org/elements/}manifestedAs'):
                        encoding = manifestation.find('*/{http://uriplay.org/elements/}dataContainerFormat')
                        size = manifestation.find('*/{http://uriplay.org/elements/}dataSize')
                        for location in manifestation.findall('*/*/{http://uriplay.org/elements/}Location'):
                            uri = location.find('./{http://uriplay.org/elements/}uri')
                            uri = uri.attrib['{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource']
                            if first == None:
                                id = self.get_next_id()
                                self.store[id] = \
                                        Container(id,self,SERIES_CONTAINER_ID,brand.find('./{http://purl.org/dc/elements/1.1/}title').text)
                                self.store[SERIES_CONTAINER_ID].add_child(self.store[id])
                                first = self.store[id]

                            item = BBCItem(first.id, self.get_next_id(), episode.find('./{http://purl.org/dc/elements/1.1/}title').text, uri)
                            first.add_child(item)
                            item.mimetype = encoding.text
                            item.duration = duration
                            item.size = int(size.text)*1024
                            item.description = episode.find('./{http://purl.org/dc/elements/1.1/}description').text



        self.update_id += 1
        #if self.server:
        #    self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
        #    value = (ROOT_CONTAINER_ID,self.container.update_id)
        #    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

    def queue_update(self, error_or_failure):
        reactor.callLater(self.refresh, self.update_data)
