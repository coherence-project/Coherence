# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008 Frank Scholz <coherence@beebits.net>

from datetime import datetime
from email.Utils import parsedate_tz

from coherence.backend import BackendStore,BackendRssMixin
from coherence.backend import BackendItem
from coherence.upnp.core import DIDLLite

from twisted.python.util import OrderedDict

ROOT_CONTAINER_ID = 0

class Item(BackendItem):

    def __init__(self, parent, id, title, url):
        self.parent = parent
        self.id = id
        self.location = url
        self.name = title
        self.duration = None
        self.size = None
        self.mimetype = 'audio/mpeg'
        self.description = None
        self.date = None

        self.item = None

    def get_item(self):
        if self.item == None:
            self.item = DIDLLite.AudioItem(self.id, self.parent.id, self.name)
            self.item.description = self.description
            self.item.date = self.date

            if hasattr(self.parent, 'cover'):
                self.item.albumArtURI = self.parent.cover

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


class SWR3Store(BackendStore,BackendRssMixin):

    implements = ['MediaServer']

    def __init__(self, server, *args, **kwargs):
        self.name = kwargs.get('name', 'SWR3')
        self.refresh = int(kwargs.get('refresh', 1)) * (60 *60)
        self.urlbase = kwargs.get('urlbase','')
        if( len(self.urlbase)>0 and
            self.urlbase[len(self.urlbase)-1] != '/'):
            self.urlbase += '/'
        self.server = server
        self.next_id = 1000
        self.update_id = 0
        self.last_updated = None
        self.store = {}

        self.store[ROOT_CONTAINER_ID] = \
                        Container(ROOT_CONTAINER_ID,self,-1, self.name)

        self.init_completed()

        self.update_data("http://www.swr3.de/rdf-feed/podcast/marianne014.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/gedoens.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/bescheid.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/timtom.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/wwdtl.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/boersenman.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/gag.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/tt.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/evishow.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/reusch.xml.php",self.get_next_id(),encoding="ISO-8859-1")
        self.update_data("http://www.swr3.de/rdf-feed/podcast/taepo.xml.php",self.get_next_id(),encoding="ISO-8859-1")

    def get_next_id(self):
        self.next_id += 1
        return self.next_id

    def get_by_id(self,id):
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
                0, 'SourceProtocolInfo', ['http-get:*:audio/mpeg:*'])

    def parse_data(self,xml_data,container):
        root = xml_data.getroot()

        self.store[container] = \
                        Container(container,self,ROOT_CONTAINER_ID, unicode(root.find("./channel/title").text))
        self.store[container].description = unicode(root.find("./channel/description").text)
        self.store[container].cover = root.find("./channel/image/url").text
        self.store[ROOT_CONTAINER_ID].add_child(self.store[container])

        for podcast in root.findall("./channel/item"):
            item = Item(self.store[container], self.get_next_id(), unicode(podcast.find("./title").text), podcast.find("./link").text)
            self.store[container].add_child(item)
            item.description = unicode(podcast.find("./description").text)
            #item.date = datetime(*parsedate_tz(podcast.find("./pubDate").text)[0:6])
            enclosure = podcast.find("./enclosure")
            item.size = int(enclosure.attrib['length'])
            item.mimetype = enclosure.attrib['type']
            #item.date = podcast.find("./pubDate")


        self.update_id += 1
        #if self.server:
        #    self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
        #    value = (ROOT_CONTAINER_ID,self.container.update_id)
        #    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)
