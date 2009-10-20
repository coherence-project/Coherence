# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# a backend to expose a YMAJ library via UPnP
# see http://code.google.com/p/moviejukebox/ for more info on YAMJ (Yet Another Movie Jukebox): 

# Copyright 2007, Frank Scholz <coherence@beebits.net>
# Copyright 2009, Jean-Michel Sizun <jm.sizun AT free.fr>
#
# TODO: add comments

import urllib

from coherence.upnp.core import DIDLLite
from coherence.backend import BackendStore,BackendItem
from coherence import log

from coherence.backends.picasa_storage import Container, LazyContainer, AbstractBackendStore

from coherence.upnp.core.utils import getPage
from coherence.extern.et import parse_xml

import mimetypes
mimetypes.init()
mimetypes.add_type('audio/x-m4a', '.m4a')
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/mpegts', '.ts')
mimetypes.add_type('video/divx', '.divx')
mimetypes.add_type('video/divx', '.avi')
mimetypes.add_type('video/x-matroska', '.mkv')


class MovieItem(BackendItem):

    def __init__(self, movie, store):
        self.movie_id = movie.find('./id').text
        self.title = movie.find('./title').text
        self.plot = movie.find('./plot').text
        self.outline = movie.find('./outline').text
        self.posterFilename = movie.find('./posterFile').text
        self.thumbnailFilename = movie.find('./thumbnail').text
        self.movie_url = movie.find('./files/file/fileURL').text
        self.rating = movie.find('./rating').text
        self.director = movie.find('./director').text
        self.genres = movie.findall('./genres/genre')
        self.year = movie.find('year').text 
        self.audioChannels = movie.find('audioChannels').text
        self.resolution = movie.find('resolution').text
        
        self.posterURL = "%s/%s" % (store.jukebox_url, self.posterFilename)
        self.thumbnailURL = "%s/%s" % (store.jukebox_url, self.thumbnailFilename)       
        #print self.movie_id, self.title, self.url, self.posterURL
        self.str_genres = []
        for genre in self.genres:
            self.str_genres.append(genre.text)
        
        url_mimetype,_ = mimetypes.guess_type(self.movie_url,strict=False)
        if url_mimetype == None:
            url_mimetype = "video"
        
        self.name = self.title
        self.duration = None
        self.size = None
        self.mimetype = url_mimetype
        self.item = None

    def get_item(self):
        if self.item == None:
            upnp_id = self.get_id()
            upnp_parent_id = self.parent.get_id()
            self.item = DIDLLite.VideoItem(upnp_id, upnp_parent_id, self.title)
            self.item.album = None
            self.item.albumArtURI = self.posterURL
            self.item.artist = None 
            self.item.creator = self.director
            self.item.date = self.year          
            self.item.description = self.plot
            self.item.director = self.director
            self.item.longDescription = self.outline
            self.item.originalTrackNumber = None
            self.item.restricted = None
            self.item.title = self.title
            self.item.writeStatus = "PROTECTED"
            self.item.icon = self.thumbnailURL
            self.item.genre = None
            self.item.genres = self.str_genres
           
            res = DIDLLite.Resource(self.movie_url, 'http-get:*:%s:*' % self.mimetype)
            res.duration = self.duration
            res.size = self.size
            res.nrAudioChannels = self.audioChannels
            res.resolution = self.resolution
            self.item.res.append(res)
        return self.item

    def get_path(self):
        return self.movie_url

    def get_id(self):
        return self.storage_id


class YamjStore(AbstractBackendStore):

    logCategory = 'yamj_store'

    implements = ['MediaServer']

    description = ('YAMJ', 'exposes the movie/TV series data files and metadata from a given YAMJ (Yet Another Movie Jukebox) library.', None)

    options = [{'option':'name', 'text':'Server Name:', 'type':'string','default':'my media','help': 'the name under this MediaServer shall show up with on other UPnP clients'},
       {'option':'version','text':'UPnP Version:','type':'int','default':2,'enum': (2,1),'help': 'the highest UPnP version this MediaServer shall support','level':'advance'},
       {'option':'uuid','text':'UUID Identifier:','type':'string','help':'the unique (UPnP) identifier for this MediaServer, usually automatically set','level':'advance'},    
       {'option':'refresh','text':'Refresh period','type':'string'},
       {'option':'yamj_url','text':'Library URL:','type':'string', 'help':'URL to the library root directory.'}
    ]

    def __init__(self, server, **kwargs):
        AbstractBackendStore.__init__(self, server, **kwargs)

        self.name = kwargs.get('name','YAMJ')
        self.yamj_url = kwargs.get('yamj_url',"http://localhost/yamj");
        self.jukebox_url = self.yamj_url + "/Jukebox/"
        self.refresh = int(kwargs.get('refresh',60))*60
        
        rootItem = Container(None, self.name)
        self.set_root_item(rootItem)

        d = self.retrieveCategories(rootItem)


    def upnp_init(self):
        self.current_connection_id = None
        if self.server:
            self.server.presentationURL = self.yamj_url
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                        ['internal:%s:video/mp4:*' % self.server.coherence.hostname,
                         'http-get:*:video/mp4:*',
                         'internal:%s:video/x-msvideo:*' % self.server.coherence.hostname,
                         'http-get:*:video/x-msvideo:*',
                         'internal:%s:video/mpeg:*' % self.server.coherence.hostname,
                         'http-get:*:video/mpeg:*',
                         'internal:%s:video/avi:*' % self.server.coherence.hostname,
                         'http-get:*:video/avi:*',
                         'internal:%s:video/divx:*' % self.server.coherence.hostname,
                         'http-get:*:video/divx:*',
                         'internal:%s:video/quicktime:*' % self.server.coherence.hostname,
                         'http-get:*:video/quicktime:*'],
                        default=True)
            self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            #self.server.content_directory_server.set_variable(0, 'SortCapabilities', '*')


    def retrieveCategories (self, parent):
        filepath = self.jukebox_url + "Categories.xml"
        dfr = getPage(filepath)
             
        def read_categories(data, parent_item, jukebox_url):
            nbMoviesPerFile = int(data.find('preferences/mjb.nbThumbnailsPerPage').text)
            self.debug("YMAJ: Nb Movies per file =  %s" % nbMoviesPerFile) 
            for category in data.findall('category'):
                type = category.get('name')
                category_title = type
                if (type != 'Other'):
                    category_title = "By %s" % category_title
                categoryItem = Container(parent_item, category_title)
                parent_item.add_child(categoryItem)
                for index in category.findall('./index'):
                    name = index.get('name')
                    first_filename = index.text
                    root_name = first_filename[:-2]
                    self.debug("adding index %s:%s" % (type,name))
                    indexItem = LazyContainer(categoryItem, name, None, self.refresh, self.retrieveIndexMovies, per_page=nbMoviesPerFile, name=name, root_name=root_name)
                    if (type == 'Other'):
                        parent_item.add_child(indexItem)
                    else:
                        categoryItem.add_child(indexItem)
            self.init_completed()                  

        def fail_categories_read(f):
            self.warning("failure reading yamj categories: %r" % f.getErrorMessage())
            return f

        dfr.addCallback(parse_xml)
        dfr.addErrback(fail_categories_read)
        dfr.addCallback(read_categories, parent_item=parent, jukebox_url=self.jukebox_url)
        dfr.addErrback(fail_categories_read)
        return dfr
      

    def retrieveIndexMovies (self, parent, name, root_name, per_page=10, offset=0):
        #print offset, per_page
        counter = abs(offset / per_page)+1
        fileUrl = "%s/%s_%d.xml" % (self.jukebox_url, urllib.quote(root_name), counter)
        
        def fail_readIndex(f):
            self.warning("failure reading yamj index: %r" % f.getErrorMessage())
            return f

        def readIndex(data):
            for index in data.findall('category/index'):
                current = index.get('current')
                if (current == "true"):
                    currentIndex = index.get('currentIndex')
                    lastIndex = index.get('lastIndex')
                    if (currentIndex != lastIndex):
                        parent.childrenRetrievingNeeded = True
                    self.debug("%s: %s/%s" % (root_name, currentIndex, lastIndex))
                    break
            for movie in data.findall('movies/movie'):
                movie_id = movie.find('./id').text
                url = movie.find('./files/file/fileURL').text
                external_id = "%s/%s" % (movie_id,url)
                item = MovieItem(movie, self)
                parent.add_child(item, external_id)

        self.debug("Reading index file %s" % fileUrl)
        d = getPage(fileUrl)
        d.addCallback(parse_xml)
        d.addErrback(fail_readIndex)
        d.addCallback(readIndex)
        d.addErrback(fail_readIndex)
        return d

    def __repr__(self):
        return self.__class__.__name__        
        



