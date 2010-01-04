# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Coherence backend presenting the content of the MIRO Guide catalog for on-line videos
#
# The APi is described on page:
# https://develop.participatoryculture.org/trac/democracy/wiki/MiroGuideApi

# Copyright 2009, Jean-Michel Sizun
# Copyright 2009 Frank Scholz <coherence@beebits.net>

import urllib

from coherence.upnp.core import utils
from coherence.upnp.core import DIDLLite
from coherence.backend import BackendStore, BackendItem, Container, LazyContainer, \
     AbstractBackendStore

from coherence.backends.youtube_storage import TestVideoProxy

class VideoItem(BackendItem):

    def __init__(self, name, description, url, thumbnail_url, store):
        self.name = name
        self.duration = None
        self.size = None
        self.mimetype = "video"
        self.url = None
        self.video_url = url
        self.thumbnail_url = thumbnail_url
        self.description = description
        self.date = None
        self.item = None

        self.location = TestVideoProxy(self.video_url, hash(self.video_url),
                                   store.proxy_mode,
                                   store.cache_directory, store.cache_maxsize,store.buffer_size
                                   )

    def get_item(self):
        if self.item == None:
            upnp_id = self.get_id()
            upnp_parent_id = self.parent.get_id()
            self.item = DIDLLite.VideoItem(upnp_id, upnp_parent_id, self.name)
            self.item.description = self.description
            self.item.date = self.date
            if self.thumbnail_url is not None:
                self.item.icon = self.thumbnail_url
                self.item.albumArtURI = self.thumbnail_url
            res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            res.duration = self.duration
            res.size = self.size
            self.item.res.append(res)
        return self.item

    def get_path(self):
        return self.url

    def get_id(self):
        return self.storage_id


class MiroGuideStore(AbstractBackendStore):

    logCategory = 'miroguide_store'

    implements = ['MediaServer']

    description = ('Miro Guide', 'connects to the MIRO Guide service and exposes the podcasts catalogued by the service. ', None)

    options = [{'option':'name', 'text':'Server Name:', 'type':'string','default':'my media','help': 'the name under this MediaServer shall show up with on other UPnP clients'},
       {'option':'version','text':'UPnP Version:','type':'int','default':2,'enum': (2,1),'help': 'the highest UPnP version this MediaServer shall support','level':'advance'},
       {'option':'uuid','text':'UUID Identifier:','type':'string','help':'the unique (UPnP) identifier for this MediaServer, usually automatically set','level':'advance'},    
       {'option':'language','text':'Language:','type':'string', 'default':'English'},
       {'option':'refresh','text':'Refresh period','type':'string'},
       {'option':'proxy_mode','text':'Proxy mode:','type':'string', 'enum': ('redirect','proxy','cache','buffered')},
       {'option':'buffer_size','text':'Buffering size:','type':'int'},
       {'option':'cache_directory','text':'Cache directory:','type':'dir', 'group':'Cache'},
       {'option':'cache_maxsize','text':'Cache max size:','type':'int', 'group':'Cache'},
    ]

    def __init__(self, server, **kwargs):
        AbstractBackendStore.__init__(self, server, **kwargs)

        self.name = kwargs.get('name','MiroGuide')

        self.language = kwargs.get('language','English')

        self.refresh = int(kwargs.get('refresh',60))*60

        self.proxy_mode = kwargs.get('proxy_mode', 'redirect')
        self.cache_directory = kwargs.get('cache_directory', '/tmp/coherence-cache')
        try:
            if self.proxy_mode != 'redirect':
                os.mkdir(self.cache_directory)
        except:
            pass
        self.cache_maxsize = kwargs.get('cache_maxsize', 100000000)
        self.buffer_size = kwargs.get('buffer_size', 750000)

        rootItem = Container(None, self.name)
        self.set_root_item(rootItem)

        categoriesItem = Container(rootItem, "All by Categories")
        rootItem.add_child(categoriesItem)
        languagesItem = Container(rootItem, "All by Languages")
        rootItem.add_child(languagesItem)

        self.appendLanguage("Recent Videos", self.language, rootItem, sort='-age', count=15)
        self.appendLanguage("Top Rated", self.language, rootItem, sort='rating', count=15)
        self.appendLanguage("Most Popular", self.language, rootItem, sort='-popular', count=15)


        def gotError(error):
            print "ERROR: %s" % error

        def gotCategories(result):
            if result is None:
                print "Unable to retrieve list of categories"
                return
            data,header = result
            categories = eval(data) # FIXME add some checks to avoid code injection
            for category in categories:
                name = category['name'].encode('ascii', 'strict')
                category_url = category['url'].encode('ascii', 'strict')
                self.appendCategory(name, name, categoriesItem)

        categories_url = "https://www.miroguide.com/api/list_categories"
        d1 = utils.getPage(categories_url)
        d1.addCallbacks(gotCategories, gotError)

        def gotLanguages(result):
            if result is None:
                print "Unable to retrieve list of languages"
                return
            data,header = result
            languages = eval(data) # FIXME add some checks to avoid code injection
            for language in languages:
                name = language['name'].encode('ascii', 'strict')
                language_url = language['url'].encode('ascii', 'strict')
                self.appendLanguage(name, name, languagesItem)

        languages_url = "https://www.miroguide.com/api/list_languages"
        d2 = utils.getPage(languages_url)
        d2.addCallbacks(gotLanguages, gotError)

        self.init_completed()


    def __repr__(self):
        return self.__class__.__name__

    def appendCategory( self, name, category_id, parent):
        item = LazyContainer(parent, name, category_id, self.refresh, self.retrieveChannels, filter="category", filter_value=category_id, per_page=100)
        parent.add_child(item, external_id=category_id)

    def appendLanguage( self, name, language_id, parent, sort='name', count=0):
        item = LazyContainer(parent, name, language_id, self.refresh, self.retrieveChannels, filter="language", filter_value=language_id, per_page=100, sort=sort, count=count)
        parent.add_child(item, external_id=language_id)

    def appendChannel(self, name, channel_id, parent):
        item = LazyContainer(parent, name, channel_id, self.refresh, self.retrieveChannelItems, channel_id=channel_id)
        parent.add_child(item, external_id=channel_id)


    def upnp_init(self):
        self.current_connection_id = None

        if self.server:
            self.server.connection_manager_server.set_variable(
               0, 'SourceProtocolInfo',
               ['http-get:*:%s:*' % 'video/'], #FIXME put list of all possible video mimetypes
               default=True)

        self.wmc_mapping = {'15': self.get_root_id()}


    def retrieveChannels (self, parent, filter, filter_value, per_page=100, page=0, offset=0, count=0, sort='name'):
        filter_value = urllib.quote(filter_value.encode("utf-8"))

        limit = count
        if (count == 0):
            limit = per_page
        uri = "https://www.miroguide.com/api/get_channels?limit=%d&offset=%d&filter=%s&filter_value=%s&sort=%s" % (limit, offset, filter, filter_value, sort)
        #print uri
        d = utils.getPage(uri)

        def gotChannels(result):
           if result is None:
               print "Unable to retrieve channel for category %s" % category_id
               return
           data,header = result
           channels = eval(data)
           for channel in channels:
               publisher = channel['publisher']
               description = channel['description']
               url = channel['url']
               hi_def = channel['hi_def']
               thumbnail_url = channel['thumbnail_url']
               postal_code = channel['postal_code']
               id = channel['id']
               website_url = channel['website_url']
               name = channel['name']
               self.appendChannel(name, id, parent)
           if ((count == 0) and (len(channels) >= per_page)):
               #print "reached page limit (%d)" % len(channels)
               parent.childrenRetrievingNeeded = True

        def gotError(error):
            print "ERROR: %s" % error

        d.addCallbacks(gotChannels, gotError)
        return d


    def retrieveChannelItems (self, parent, channel_id):
        uri = "https://www.miroguide.com/api/get_channel?id=%s" % channel_id
        d = utils.getPage(uri)

        def gotItems(result):
           if result is None:
               print "Unable to retrieve items for channel %s" % channel_id
               return
           data,header = result
           channel = eval(data)
           items = []
           if (channel.has_key('item')):
               items = channel['item']
           for item in items:
               #print "item:",item
               url = item['url']
               description = item['description']
               #print "description:", description              
               name = item['name']
               thumbnail_url = None
               if (channel.has_key('thumbnail_url')):
                   #print "Thumbnail:", channel['thumbnail_url']
                   thumbnail_url = channel['thumbnail_url']
               #size = size['size']
               item = VideoItem(name, description, url, thumbnail_url, self)
               item.parent = parent
               parent.add_child(item, external_id=url)

        def gotError(error):
            print "ERROR: %s" % error

        d.addCallbacks(gotItems, gotError)
        return d
