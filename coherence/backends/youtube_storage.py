# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009, Jean-Michel Sizun
# Copyright 2009 Frank Scholz <coherence@beebits.net>

import os.path

from twisted.internet import reactor, threads

from twisted.web import server, static
from twisted.web.error import PageRedirect

from coherence.upnp.core import utils
from coherence.upnp.core.utils import ReverseProxyUriResource, ReverseProxyResource
from coherence.upnp.core import DIDLLite
from coherence.backend import BackendStore,BackendItem

from coherence import log

from gdata.youtube.service import YouTubeService
from coherence.extern.youtubedl import FileDownloader,YoutubeIE,MetacafeIE,YoutubePlaylistIE
from coherence.backends.picasa_storage import Container, LazyContainer, AbstractBackendStore

MPEG4_MIMETYPE = 'video/mp4'
MPEG4_EXTENSION = 'mp4'

class TestVideoProxy(ReverseProxyUriResource, log.Loggable):

    logCategory = 'internetVideoProxy'

    def __init__(self, uri, id,
                 proxy_mode,
                 cache_directory,
                 cache_maxsize=100000000,
                 buffer_size=2000000,
                 fct=None, **kwargs):

        ReverseProxyUriResource.__init__(self, uri)

        self.id = id
        if isinstance(self.id,int):
            self.id = '%d' % self.id
        self.proxy_mode = proxy_mode

        self.cache_directory = cache_directory
        self.cache_maxsize = int(cache_maxsize)
        self.buffer_size = int(buffer_size)
        self.downloader = None

        self.video_url = None # the url we get from the youtube page
        self.stream_url = None # the real video stream, cached somewhere
        self.mimetype = None

        self.filesize = 0
        self.file_in_cache = False

        self.url_extractor_fct = fct
        self.url_extractor_params = kwargs



    def requestFinished(self, result):
        """ self.connection is set in utils.ReverseProxyResource.render """
        self.info("ProxyStream requestFinished:",result)
        if hasattr(self,'connection'):
            self.connection.transport.loseConnection()


    def render(self, request):

        self.info("VideoProxy render", request, self.stream_url, self.video_url)
        self.info("VideoProxy headers:", request.getAllHeaders())
        self.info("VideoProxy id:", self.id)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished)

        if self.stream_url is None:

            web_url = "http://%s%s" % (self.host,self.path)
            self.info("Web_url: %s" % web_url)

            def got_real_urls(real_urls):
                if len(real_urls) == 0:
                    self.warning('Unable to retrieve any URL for video stream')
                    return self.requestFinished(None)
                else:
                    got_real_url(real_urls[0])

            def got_real_url(real_url):
                self.info("Real URL is %s" % real_url)
                self.stream_url = real_url
                if self.stream_url is None:
                    self.warning('Unable to retrieve URL - inconsistent web page')
                    return self.requestFinished(None) #FIXME
                self.stream_url = self.stream_url.encode('ascii', 'strict')
                self.resetUri(self.stream_url)
                self.info("Video URL: %s" % self.stream_url)
                self.video_url = self.stream_url[:]
                d = self.followRedirects(request)
                d.addCallback(self.proxyURL)
                d.addErrback(self.requestFinished)

            if self.url_extractor_fct is not None:
                d = self.url_extractor_fct(web_url, **self.url_extractor_params)
                d.addCallback(got_real_urls)
            else:
                got_real_url(web_url)
            return server.NOT_DONE_YET

        reactor.callLater(0.05,self.proxyURL,request)
        return server.NOT_DONE_YET

    def followRedirects(self, request):
        self.info("HTTP redirect ", request, self.stream_url)
        d = utils.getPage(self.stream_url, method="HEAD", followRedirect=0)

        def gotHeader(result,request):
            data,header = result
            self.info("finally got something %r", header)
            #FIXME what do we do here if the headers aren't there?
            self.filesize = int(header['content-length'][0])
            self.mimetype = header['content-type'][0]
            return request

        def gotError(error,request):
            # error should be a "Failure" instance at this point
            self.info("gotError" % error)

            error_value = error.value
            if (isinstance(error_value,PageRedirect)):
                self.info("got PageRedirect %r" % error_value.location)
                self.stream_url = error_value.location
                self.resetUri(self.stream_url)
                return self.followRedirects(request)
            else:
                self.warning("Error while retrieving page header for URI ", self.stream_url)
                self.requestFinished(None)
                return error

        d.addCallback(gotHeader, request)
        d.addErrback(gotError,request)
        return d

    def proxyURL(self, request):
        self.info("proxy_mode: %s, request %s" % (self.proxy_mode,request.method))

        if self.proxy_mode == 'redirect':
            # send stream url to client for redirection
            request.redirect(self.stream_url)
            request.finish()
        elif self.proxy_mode in ('proxy',):
            res = ReverseProxyResource.render(self,request)
            if isinstance(res,int):
                return res
            request.write(res)
            return
        elif self.proxy_mode in ('buffer','buffered'):
            # download stream to cache,
            # and send it to the client in // after X bytes
            filepath = os.path.join(self.cache_directory, self.id)

            file_is_already_available = False
            if (os.path.exists(filepath)
                and os.path.getsize(filepath) == self.filesize):
                res = self.renderFile(request, filepath)
                if isinstance(res,int):
                    return res
                request.write(res)
                request.finish()
            else:
                if request.method != 'HEAD':
                    self.downloadFile(request, filepath, None)
                    range = request.getHeader('range')
                    if range is not None:
                        bytesrange = range.split('=')
                        assert bytesrange[0] == 'bytes',\
                               "Syntactically invalid http range header!"
                        start, end = bytesrange[1].split('-', 1)
                        #print "%r %r" %(start,end)
                        if start:
                            start = int(start)
                            if end:
                                end = int(end)
                            else:
                                end = self.filesize -1
                            # Are we requesting something beyond the current size of the file?
                            try:
                                size = os.path.getsize(filepath)
                            except OSError:
                                size = 0
                            if (start >= size and
                                end+10 > self.filesize and
                                end-start < 200000):
                                #print "let's hand that through, it is probably a mp4 index request"
                                res = ReverseProxyResource.render(self,request)
                                if isinstance(res,int):
                                    return res
                                request.write(res)
                                return

                res = self.renderBufferFile (request, filepath, self.buffer_size)
                if res == '' and request.method != 'HEAD':
                    return server.NOT_DONE_YET
                if not isinstance(res,int):
                    request.write(res)
                if request.method == 'HEAD':
                    request.finish()

        else:
            self.warning("Unsupported Proxy Mode: %s" % self.proxy_mode)
            return self.requestFinished(None)

    def getMimetype(self):
        type = MPEG4_MIMETYPE
        if self.mimetype is not None:
            type = self.mimetype
        return type
            

    def renderFile(self,request,filepath):
        self.info('Cache file available %r %r ' %(request, filepath))
        downloadedFile = utils.StaticFile(filepath, self.mimetype)
        downloadedFile.type = self.getMimetype()
        downloadedFile.encoding = None
        return downloadedFile.render(request)


    def renderBufferFile (self, request, filepath, buffer_size):
        # Try to render file(if we have enough data)
        self.info("renderBufferFile %s" % filepath)
        rendering = False
        if os.path.exists(filepath) is True:
            filesize = os.path.getsize(filepath)
            if ((filesize >= buffer_size) or (filesize == self.filesize)):
                rendering = True
                self.info("Render file", filepath, self.filesize, filesize, buffer_size)
                bufferFile = utils.BufferFile(filepath, self.filesize, MPEG4_MIMETYPE)
                bufferFile.type = self.getMimetype()
                bufferFile.encoding = None
                try:
                    return bufferFile.render(request)
                except Exception,error:
                    self.info(error)

        if request.method != 'HEAD':
            self.info('Will retry later to render buffer file')
            reactor.callLater(0.5, self.renderBufferFile, request,filepath,buffer_size)
        return ''

    def downloadFinished(self, result):
        self.info('Download finished!')
        self.downloader = None

    def gotDownloadError(self, error, request):
        self.info("Unable to download stream to file: %s" % self.stream_url)
        self.info(request)
        self.info(error)

    def downloadFile(self, request, filepath, callback, *args):
        if (self.downloader is None):
            self.info("Proxy: download data to cache file %s" % filepath)
            self.checkCacheSize()
            self.downloader = utils.downloadPage(self.stream_url, filepath, supportPartial=1)
            self.downloader.addCallback(self.downloadFinished)
            self.downloader.addErrback(self.gotDownloadError, request)
        if(callback is not None):
            self.downloader.addCallback(callback, request, filepath, *args)
        return self.downloader


    def checkCacheSize(self):
        cache_listdir = os.listdir(self.cache_directory)

        cache_size = 0
        for filename in cache_listdir:
            path = "%s%s%s" % (self.cache_directory, os.sep, filename)
            statinfo = os.stat(path)
            cache_size += statinfo.st_size
        self.info("Cache size: %d (max is %s)" % (cache_size, self.cache_maxsize))

        if (cache_size > self.cache_maxsize):
            cache_targetsize = self.cache_maxsize * 2/3
            self.info("Cache above max size: Reducing to %d" % cache_targetsize)

            def compare_atime(filename1, filename2):
                path1 = "%s%s%s" % (self.cache_directory, os.sep, filename1)
                path2 = "%s%s%s" % (self.cache_directory, os.sep, filename2)
                cmp = int(os.stat(path1).st_atime - os.stat(path2).st_atime)
                return cmp
            cache_listdir = sorted(cache_listdir,compare_atime)

            while (cache_size > cache_targetsize):
                filename = cache_listdir.pop(0)
                path = "%s%s%s" % (self.cache_directory, os.sep, filename)
                cache_size -= os.stat(path).st_size
                os.remove(path)
                self.info("removed %s" % filename)

            self.info("new cache size is %d" % cache_size)


class YoutubeVideoItem(BackendItem):

    def __init__(self, external_id, title, url, mimetype, entry, store):
        self.external_id = external_id
        self.name = title
        self.duration = None
        self.size = None
        self.mimetype = mimetype
        self.description = None
        self.date = None
        self.item = None
        self.youtube_entry = entry
        self.store = store

        def extractDataURL(url, quality):
            if (quality == 'hd'):
                format = '22'
            else:
                format = '18'

            kwargs = {
                'usenetrc': False,
                'quiet': True,
                'forceurl': True,
                'forcetitle': False,
                'simulate': True,
                'format': format,
                'outtmpl': u'%(id)s.%(ext)s',
                'ignoreerrors': True,
                'ratelimit': None,
                }
            if len(self.store.login) > 0:
                kwargs['username'] = self.store.login
                kwargs['password'] = self.store.password
            fd = FileDownloader(kwargs)

            youtube_ie = YoutubeIE()
            fd.add_info_extractor(YoutubePlaylistIE(youtube_ie))
            fd.add_info_extractor(MetacafeIE(youtube_ie))
            fd.add_info_extractor(youtube_ie)

            deferred = fd.get_real_urls([url])
            return deferred

        #self.location = VideoProxy(url, self.external_id,
        #                           store.proxy_mode,
        #                           store.cache_directory, store.cache_maxsize, store.buffer_size,
        #                           extractDataURL, quality=self.store.quality)

        self.location = TestVideoProxy(url, self.external_id,
                                   store.proxy_mode,
                                   store.cache_directory, store.cache_maxsize,store.buffer_size,
                                   extractDataURL, quality=self.store.quality)


    def get_item(self):
        if self.item == None:
            upnp_id = self.get_id()
            upnp_parent_id = self.parent.get_id()
            self.item = DIDLLite.VideoItem(upnp_id, upnp_parent_id, self.name)
            self.item.description = self.description
            self.item.date = self.date

            # extract thumbnail from youtube entry
            # we take the last one, hoping this is the bigger one
            thumbnail_url = None
            for image in self.youtube_entry.media.thumbnail:
                thumbnail_url = image.url
            if thumbnail_url is not None:
                self.item.albumArtURI = thumbnail_url

            res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            res.duration = self.duration
            res.size = self.size
            self.item.res.append(res)
        return self.item

    def get_path(self):
        self.url = self.store.urlbase + str(self.storage_id) + "." + MPEG4_EXTENSION
        return self.url

    def get_id(self):
        return self.storage_id


class YouTubeStore(AbstractBackendStore):

    logCategory = 'youtube_store'

    implements = ['MediaServer']

    description = ('Youtube', 'connects to the YouTube service and exposes the standard feeds (public) and the uploads/favorites/playlists/subscriptions of a given user.', None)

    options = [{'option':'name', 'text':'Server Name:', 'type':'string','default':'my media','help': 'the name under this MediaServer shall show up with on other UPnP clients'},
       {'option':'version','text':'UPnP Version:','type':'int','default':2,'enum': (2,1),'help': 'the highest UPnP version this MediaServer shall support','level':'advance'},
       {'option':'uuid','text':'UUID Identifier:','type':'string','help':'the unique (UPnP) identifier for this MediaServer, usually automatically set','level':'advance'},    
       {'option':'refresh','text':'Refresh period','type':'string'},
       {'option':'login','text':'User ID:','type':'string','group':'User Account'},
       {'option':'password','text':'Password:','type':'string','group':'User Account'},
       {'option':'location','text':'Locale:','type':'string'},
       {'option':'quality','text':'Video quality:','type':'string', 'default':'sd','enum': ('sd','hd')},
       {'option':'standard_feeds','text':'Include standard feeds:','type':'bool', 'default': True},
       {'option':'proxy_mode','text':'Proxy mode:','type':'string', 'enum': ('redirect','proxy','cache','buffered')},
       {'option':'buffer_size','text':'Buffering size:','type':'int'},
       {'option':'cache_directory','text':'Cache directory:','type':'dir', 'group':'Cache'},
       {'option':'cache_maxsize','text':'Cache max size:','type':'int', 'group':'Cache'},
    ]

    def __init__(self, server, **kwargs):
        AbstractBackendStore.__init__(self, server, **kwargs)

        self.name = kwargs.get('name','YouTube')

        self.login = kwargs.get('userid',kwargs.get('login',''))
        self.password = kwargs.get('password','')
        self.locale = kwargs.get('location',None)
        self.quality = kwargs.get('quality','sd')
        self.showStandardFeeds = (kwargs.get('standard_feeds','True') in ['Yes','yes','true','True','1'])
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

        if (self.showStandardFeeds):
            standardfeeds_uri = 'http://gdata.youtube.com/feeds/api/standardfeeds'
            if self.locale is not None:
                standardfeeds_uri += "/%s" % self.locale
            standardfeeds_uri += "/%s"
            self.appendFeed('Most Viewed', standardfeeds_uri % 'most_viewed', rootItem)
            self.appendFeed('Top Rated', standardfeeds_uri % 'top_rated', rootItem)
            self.appendFeed('Recently Featured', standardfeeds_uri % 'recently_featured', rootItem)
            self.appendFeed('Watch On Mobile', standardfeeds_uri % 'watch_on_mobile', rootItem)
            self.appendFeed('Most Discussed', standardfeeds_uri % 'most_discussed', rootItem)
            self.appendFeed('Top Favorites', standardfeeds_uri % 'top_favorites', rootItem)
            self.appendFeed('Most Linked', standardfeeds_uri % 'most_linked', rootItem)
            self.appendFeed('Most Responded', standardfeeds_uri % 'most_responded', rootItem)
            self.appendFeed('Most Recent', standardfeeds_uri % 'most_recent', rootItem)

        if len(self.login) > 0:
            userfeeds_uri = 'http://gdata.youtube.com/feeds/api/users/%s/%s'
            self.appendFeed('My Uploads', userfeeds_uri % (self.login,'uploads'), rootItem)
            self.appendFeed('My Favorites', userfeeds_uri % (self.login,'favorites'), rootItem)
            playlistsItem = LazyContainer(rootItem, 'My Playlists', None, self.refresh, self.retrievePlaylistFeeds)
            rootItem.add_child(playlistsItem)
            subscriptionsItem = LazyContainer(rootItem, 'My Subscriptions', None, self.refresh, self.retrieveSubscriptionFeeds)
            rootItem.add_child(subscriptionsItem)

        self.init_completed()

    def __repr__(self):
        return self.__class__.__name__        
        
    def appendFeed( self, name, feed_uri, parent):
        item = LazyContainer(parent, name, None, self.refresh, self.retrieveFeedItems, feed_uri=feed_uri)
        parent.add_child(item, external_id=feed_uri)


    def appendVideoEntry(self, entry, parent):
        external_id = entry.id.text.split('/')[-1]
        title = entry.media.title.text
        url = entry.media.player.url
        mimetype = MPEG4_MIMETYPE
        
        #mimetype = 'video/mpeg'
        item = YoutubeVideoItem (external_id, title, url, mimetype, entry, self)
        item.parent = parent
        parent.add_child(item, external_id=external_id)


    def upnp_init(self):
        self.current_connection_id = None

        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    ['http-get:*:%s:*' % MPEG4_MIMETYPE],
                                                                    default=True)


        self.wmc_mapping = {'15': self.get_root_id()}

        self.yt_service = YouTubeService()
        self.yt_service.client_id = 'ytapi-JeanMichelSizun-youtubebackendpl-ruabstu7-0'
        self.yt_service.developer_key = 'AI39si7dv2WWffH-s3pfvmw8fTND-cPWeqF1DOcZ8rwTgTPi4fheX7jjQXpn7SG61Ido0Zm_9gYR52TcGog9Pt3iG9Sa88-1yg'
        self.yt_service.email = self.login
        self.yt_service.password = self.password
        self.yt_service.source = 'Coherence UPnP backend'
        if len(self.login) > 0:
            d = threads.deferToThread(self.yt_service.ProgrammaticLogin)


    def retrieveFeedItems (self, parent=None, feed_uri=''):
        feed = threads.deferToThread(self.yt_service.GetYouTubeVideoFeed, feed_uri)

        def gotFeed(feed):
           if feed is None:
               self.warning("Unable to retrieve feed %s" % feed_uri)
               return
           for entry in feed.entry:
               self.appendVideoEntry(entry, parent)

        def gotError(error):
            self.warning("ERROR: %s" % error)

        feed.addCallbacks(gotFeed, gotError)
        return feed

    def retrievePlaylistFeedItems (self, parent, playlist_id):

        feed = threads.deferToThread(self.yt_service.GetYouTubePlaylistVideoFeed,playlist_id=playlist_id)
        def gotFeed(feed):
           if feed is None:
               self.warning("Unable to retrieve playlist items %s" % feed_uri)
               return
           for entry in feed.entry:
               self.appendVideoEntry(entry, parent)

        def gotError(error):
            self.warning("ERROR: %s" % error)

        feed.addCallbacks(gotFeed, gotError)
        return feed

    def retrieveSubscriptionFeedItems (self, parent, uri):
        entry = threads.deferToThread(self.yt_service.GetYouTubeSubscriptionEntry,uri)

        def gotEntry(entry):
           if entry is None:
               self.warning("Unable to retrieve subscription items %s" % uri)
               return
           feed_uri = entry.feed_link[0].href
           return self.retrieveFeedItems(parent, feed_uri)

        def gotError(error):
            self.warning("ERROR: %s" % error)
        entry.addCallbacks(gotEntry, gotError)
        return entry

    def retrievePlaylistFeeds(self, parent):
        playlists_feed = threads.deferToThread(self.yt_service.GetYouTubePlaylistFeed, username=self.login)

        def gotPlaylists(playlist_video_feed):
           if playlist_video_feed is None:
               self.warning("Unable to retrieve playlists feed")
               return
           for playlist_video_entry in playlist_video_feed.entry:
               title = playlist_video_entry.title.text
               playlist_id = playlist_video_entry.id.text.split("/")[-1] # FIXME find better way to retrieve the playlist ID

               item = LazyContainer(parent, title, playlist_id, self.refresh, self.retrievePlaylistFeedItems, playlist_id=playlist_id)
               parent.add_child(item, external_id=playlist_id)

        def gotError(error):
            self.warning("ERROR: %s" % error)

        playlists_feed.addCallbacks(gotPlaylists, gotError)
        return playlists_feed


    def retrieveSubscriptionFeeds(self, parent):
        playlists_feed = threads.deferToThread(self.yt_service.GetYouTubeSubscriptionFeed, username=self.login)

        def gotPlaylists(playlist_video_feed):
           if playlist_video_feed is None:
               self.warning("Unable to retrieve subscriptions feed")
               return
           for entry in playlist_video_feed.entry:
               type = entry.GetSubscriptionType()
               title = entry.title.text
               uri = entry.id.text
               name = "[%s] %s" % (type,title)

               item = LazyContainer(parent, name, uri, self.refresh, self.retrieveSubscriptionFeedItems, uri=uri)
               item.parent = parent
               parent.add_child(item, external_id=uri)

        def gotError(error):
            self.warning("ERROR: %s" % error)

        playlists_feed.addCallbacks(gotPlaylists, gotError)
        return playlists_feed