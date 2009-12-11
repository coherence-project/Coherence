# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009, Jean-Michel Sizun
# Copyright 2009 Frank Scholz <coherence@beebits.net>

import os.path
import time

from twisted.internet import threads

from twisted.web import server, static
from twisted.web.error import PageRedirect
from coherence.upnp.core.utils import ReverseProxyUriResource
from twisted.internet import task
from coherence.upnp.core import utils
from coherence.upnp.core import DIDLLite
from coherence.backend import BackendStore, BackendItem, Container, LazyContainer, \
     AbstractBackendStore
from coherence import log

from urlparse import urlsplit

import gdata.photos.service
import gdata.media
import gdata.geo




class PicasaProxy(ReverseProxyUriResource):

    def __init__(self, uri):
        ReverseProxyUriResource.__init__(self, uri)

    def render(self, request):
        if request.received_headers.has_key('referer'):
            del request.received_headers['referer']
        return ReverseProxyUriResource.render(self, request)

class PicasaPhotoItem(BackendItem):
    def __init__(self, photo):
        #print photo
        self.photo = photo

        self.name = photo.summary.text
        if self.name is None:
            self.name = photo.title.text
            
        self.duration = None
        self.size = None
        self.mimetype = photo.content.type
        self.description = photo.summary.text
        self.date = None
        self.item = None

        self.photo_url = photo.content.src
        self.thumbnail_url = photo.media.thumbnail[0].url

        self.url = None

        self.location = PicasaProxy(self.photo_url)

    def replace_by(self, item):
        #print photo
        self.photo = item.photo
        self.name = photo.summary.text
        if self.name is None:
            self.name = photo.title.text
        self.mimetype = self.photo.content.type
        self.description = self.photo.summary.text
        self.photo_url = self.photo.content.src
        self.thumbnail_url = self.photo.media.thumbnail[0].url
        self.location = PicasaProxy(self.photo_url)
        return True


    def get_item(self):
        if self.item == None:
            upnp_id = self.get_id()
            upnp_parent_id = self.parent.get_id()
            self.item = DIDLLite.Photo(upnp_id,upnp_parent_id,self.name)
            res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            self.item.res.append(res)
        self.item.childCount = 0
        return self.item

    def get_path(self):
        return self.url

    def get_id(self):
        return self.storage_id


class PicasaStore(AbstractBackendStore):

    logCategory = 'picasa_store'

    implements = ['MediaServer']

    description = ('Picasa Web Albums', 'connects to the Picasa Web Albums service and exposes the featured photos and albums for a given user.', None)

    options = [{'option':'name', 'text':'Server Name:', 'type':'string','default':'my media','help': 'the name under this MediaServer shall show up with on other UPnP clients'},
       {'option':'version','text':'UPnP Version:','type':'int','default':2,'enum': (2,1),'help': 'the highest UPnP version this MediaServer shall support','level':'advance'},
       {'option':'uuid','text':'UUID Identifier:','type':'string','help':'the unique (UPnP) identifier for this MediaServer, usually automatically set','level':'advance'},    
       {'option':'refresh','text':'Refresh period','type':'string'},
       {'option':'login','text':'User ID:','type':'string','group':'User Account'},
       {'option':'password','text':'Password:','type':'string','group':'User Account'},
    ]


    def __init__(self, server, **kwargs):
        AbstractBackendStore.__init__(self, server, **kwargs)

        self.name = kwargs.get('name','Picasa Web Albums')

        self.refresh = int(kwargs.get('refresh',60))*60

        self.login = kwargs.get('userid',kwargs.get('login',''))
        self.password = kwargs.get('password','')

        rootContainer = Container(None, self.name)
        self.set_root_item(rootContainer)

        self.AlbumsContainer = LazyContainer(rootContainer, 'My Albums', None, self.refresh, self.retrieveAlbums)
        rootContainer.add_child(self.AlbumsContainer)

        self.FeaturedContainer = LazyContainer(rootContainer, 'Featured photos', None, self.refresh, self.retrieveFeaturedPhotos)
        rootContainer.add_child(self.FeaturedContainer)

        self.init_completed()


    def __repr__(self):
        return self.__class__.__name__


    def upnp_init(self):
        self.current_connection_id = None

        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                  'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_TN;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000,'
                                                                  'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_SM;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000,'
                                                                  'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_MED;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000,'
                                                                  'http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=00f00000000000000000000000000000,'
                                                                  'http-get:*:image/jpeg:*,'
                                                                  'http-get:*:image/gif:*,'
                                                                  'http-get:*:image/png:*',
                                                                default=True)

        self.wmc_mapping = {'16': self.get_root_id()}

        self.gd_client = gdata.photos.service.PhotosService()
        self.gd_client.email = self.login
        self.gd_client.password = self.password
        self.gd_client.source = 'Coherence UPnP backend'
        if len(self.login) > 0:
            d = threads.deferToThread(self.gd_client.ProgrammaticLogin)


    def retrieveAlbums(self, parent=None):
        albums = threads.deferToThread(self.gd_client.GetUserFeed)

        def gotAlbums(albums):
           if albums is None:
               print "Unable to retrieve albums"
               return
           for album in albums.entry:
               title = album.title.text
               album_id = album.gphoto_id.text
               item = LazyContainer(parent, title, album_id, self.refresh, self.retrieveAlbumPhotos, album_id=album_id)
               parent.add_child(item, external_id=album_id)

        def gotError(error):
            print "ERROR: %s" % error

        albums.addCallbacks(gotAlbums, gotError)
        return albums

    def retrieveFeedPhotos (self, parent=None, feed_uri=''):
        #print feed_uri
        photos = threads.deferToThread(self.gd_client.GetFeed, feed_uri)

        def gotPhotos(photos):
           if photos is None:
               print "Unable to retrieve photos for feed %s" % feed_uri
               return
           for photo in photos.entry:
               photo_id = photo.gphoto_id.text
               item = PicasaPhotoItem(photo)
               item.parent = parent
               parent.add_child(item, external_id=photo_id)

        def gotError(error):
            print "ERROR: %s" % error

        photos.addCallbacks(gotPhotos, gotError)
        return photos

    def retrieveAlbumPhotos (self, parent=None, album_id=''):
        album_feed_uri = '/data/feed/api/user/%s/albumid/%s?kind=photo' % (self.login, album_id)
        return self.retrieveFeedPhotos(parent, album_feed_uri)

    def retrieveFeaturedPhotos (self, parent=None):
        feed_uri = 'http://picasaweb.google.com/data/feed/api/featured'
        return self.retrieveFeedPhotos(parent, feed_uri)
