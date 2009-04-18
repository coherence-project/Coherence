# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

import os.path

from twisted.internet import reactor, defer
from twisted.python import failure, util

from coherence.upnp.core import DIDLLite
from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core import utils

import dbus

import dbus.service

import coherence.extern.louie as louie

from coherence.backend import BackendItem, BackendStore

ROOT_CONTAINER_ID = 0
AUDIO_CONTAINER_ID = 100
AUDIO_ALL_CONTAINER_ID = 101
AUDIO_ARTIST_CONTAINER_ID = 102
AUDIO_ALBUM_CONTAINER_ID = 103
AUDIO_PLAYLIST_CONTAINER_ID = 104
AUDIO_GENRE_CONTAINER_ID = 105

VIDEO_CONTAINER_ID = 200
VIDEO_ALL_CONTAINER_ID = 201

IMAGE_CONTAINER_ID = 300
IMAGE_ALL_CONTAINER_ID = 301

BUS_NAME = 'org.freedesktop.Tracker'
OBJECT_PATH = '/org/freedesktop/tracker'

tracks_query = """
<rdfq:Condition>\
<rdfq:equals>\
<rdfq:Property name="Audio:Title" />\
<rdf:String>*</rdf:String>\
</rdfq:equals>\
</rdfq:Condition>\
"""

video_query = """
<rdfq:Condition>\
<rdfq:equals>\
<rdfq:Property name="File:Name" />\
<rdf:String>*</rdf:String>\
</rdfq:equals>\
</rdfq:Condition>\
"""

image_query = """
<rdfq:Condition>\
<rdfq:equals>\
<rdfq:Property name="File:Name" />\
<rdf:String>*</rdf:String>\
</rdfq:equals>\
</rdfq:Condition>\
"""


class Container(BackendItem):

    logCategory = 'tracker_store'

    def __init__(self, id, parent_id, name, store=None, children_callback=None, container_class=DIDLLite.Container):
        self.id = id
        self.parent_id = parent_id
        self.name = name
        self.mimetype = 'directory'
        self.item = container_class(id, parent_id,self.name)
        self.item.childCount = 0
        self.update_id = 0
        if children_callback != None:
            self.children = children_callback
        else:
            self.children = util.OrderedDict()
        self.item.childCount = None #self.get_child_count()

        if store!=None:
            self.get_url = lambda: store.urlbase + str(self.id)

    def add_child(self, child):
        id = child.id
        if isinstance(child.id, basestring):
            _,id = child.id.split('.')
        self.children[id] = child
        if self.item.childCount != None:
            self.item.childCount += 1

    def get_children(self,start=0,end=0):
        self.info("container.get_children %r %r", start, end)

        if callable(self.children):
            return self.children(start,end-start)
        else:
            children = self.children.values()
        if end == 0:
            return children[start:]
        else:
            return children[start:end]

    def get_child_count(self):
        if self.item.childCount != None:
            return self.item.childCount

        if callable(self.children):
            return len(self.children())
        else:
            return len(self.children)

    def get_item(self):
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id


class Artist(BackendItem):

    logCategory = 'tracker_store'

    def __init__(self, store, id, name):
        self.store = store
        self.id = 'artist.%d' % int(id)
        self.name = name
        self.children = {}
        self.sorted_children = None

    def add_child(self, child):
        _,id = child.id.split('.')
        self.children[id] = child

    def sort_children(self):
        if self.sorted_children == None:
            def childs_sort(x,y):
                r = cmp(self.children[x].name,self.children[y].name)
                return r

            self.sorted_children = self.children.keys()
            self.sorted_children.sort(cmp=childs_sort)
        return self.sorted_children

    def get_artist_all_tracks(self,start=0,request_count=0):
        children = []
        for album in self.sort_children():
            children += album.get_children()
        if request_count == 0:
            return children[start:]
        else:
            return children[start:request_count]

    def get_children(self,start=0,end=0):
        children = []
        for key in self.sort_children():
            children.append(self.children[key])

        if end == 0:
            return children[start:]
        else:
            return children[start:end]

    def get_child_count(self):
        return len(self.children)

    def get_item(self, parent_id = AUDIO_ARTIST_CONTAINER_ID):
        item = DIDLLite.MusicArtist(self.id, parent_id, self.name)
        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name


class Album(BackendItem):

    logCategory = 'tracker_store'

    def __init__(self, store, id, title, artist):
        self.store = store
        self.id = 'album.%d' % int(id)
        self.name = unicode(title)
        self.artist = unicode(artist)
        self.cover = None
        self.children = {}
        self.sorted_children = None

    def add_child(self, child):
        _,id = child.id.split('.')
        self.children[id] = child

    def get_children(self,start=0,end=0):
        children = []
        if self.sorted_children != None:
            for key in self.sorted_children:
                children.append(self.children[key])
        else:
            def childs_sort(x,y):
                r = cmp(self.children[x].track_nr,self.children[y].track_nr)
                return r

            self.sorted_children = self.children.keys()
            self.sorted_children.sort(cmp=childs_sort)
            for key in self.sorted_children:
                children.append(self.children[key])

        if end == 0:
            return children[start:]
        else:
            return children[start:end]

    def get_child_count(self):
        return len(self.children)

    def get_item(self, parent_id = AUDIO_ALBUM_CONTAINER_ID):
        item = DIDLLite.MusicAlbum(self.id, parent_id, self.name)
        item.childCount = self.get_child_count()
        item.artist = self.artist
        item.albumArtURI = self.cover
        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name

    def get_cover(self):
        return self.cover


class Track(BackendItem):

    logCategory = 'tracker_store'

    def __init__(self,store,
                 id,parent_id,
                 file,title,
                 artist,album,genre,\
                 duration,\
                 track_number,\
                 size,mimetype):

        self.store = store
        self.id = 'song.%d' % int(id)
        self.parent_id = parent_id

        self.path = unicode(file)

        duration = str(duration).strip()
        duration = duration.split('.')[0]
        if len(duration) == 0:
            duration = 0
        seconds = int(duration)
        hours = seconds / 3600
        seconds = seconds - hours * 3600
        minutes = seconds / 60
        seconds = seconds - minutes * 60
        self.duration = ("%d:%02d:%02d") % (hours, minutes, seconds)

        self.bitrate = 0

        self.title = unicode(title)
        self.artist = unicode(artist)
        self.album = unicode(album)
        self.genre = unicode(genre)
        track_number = str(track_number).strip()
        if len(track_number) == 0:
            track_number = 1
        self.track_nr = int(track_number)

        self.cover = None
        self.mimetype = str(mimetype)
        self.size = int(size)

        self.url = self.store.urlbase + str(self.id)


    def get_children(self, start=0, end=0):
        return []

    def get_child_count(self):
        return 0

    def get_item(self, parent_id=None):

        self.debug("Track get_item %r @ %r" %(self.id,self.parent_id))

        # create item
        item = DIDLLite.MusicTrack(self.id,self.parent_id)
        item.album = self.album

        item.artist = self.artist
        #item.date =
        item.genre = self.genre
        item.originalTrackNumber = self.track_nr
        item.title = self.title

        item.albumArtURI = self.cover

        # add http resource
        res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
        if self.size > 0:
            res.size = self.size
        if self.duration > 0:
            res.duration = str(self.duration)
        if self.bitrate > 0:
            res.bitrate = str(bitrate)
        item.res.append(res)

        #if self.store.server.coherence.config.get('transcoding', 'no') == 'yes':
        #    if self.mimetype in ('audio/mpeg',
        #                         'application/ogg','audio/ogg',
        #                         'audio/x-m4a',
        #                         'application/x-flac'):
        #        dlna_pn = 'DLNA.ORG_PN=LPCM'
        #        dlna_tags = DIDLLite.simple_dlna_tags[:]
        #        dlna_tags[1] = 'DLNA.ORG_CI=1'
        #        #dlna_tags[2] = 'DLNA.ORG_OP=00'
        #        new_res = DIDLLite.Resource(self.url+'?transcoded=lpcm',
        #            'http-get:*:%s:%s' % ('audio/L16;rate=44100;channels=2', ';'.join([dlna_pn]+dlna_tags)))
        #        new_res.size = None
        #        if self.duration > 0:
        #            new_res.duration = str(self.duration)
        #        item.res.append(new_res)

        #        if self.mimetype != 'audio/mpeg':
        #            new_res = DIDLLite.Resource(self.url+'?transcoded=mp3',
        #                'http-get:*:%s:*' % 'audio/mpeg')
        #            new_res.size = None
        #            if self.duration > 0:
        #                new_res.duration = str(self.duration)
        #            item.res.append(new_res)

        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.title

    def get_url(self):
        return self.url

    def get_path(self):
        return self.path


class Video(BackendItem):

    logCategory = 'tracker_store'

    def __init__(self,store,
                 id,parent_id,
                 file,title,
                 duration,\
                 size,mimetype):

        self.store = store
        self.id = 'video.%d' % int(id)
        self.parent_id = parent_id

        self.path = unicode(file)

        duration = str(duration).strip()
        duration = duration.split('.')[0]
        if len(duration) == 0:
            duration = 0
        seconds = int(duration)
        hours = seconds / 3600
        seconds = seconds - hours * 3600
        minutes = seconds / 60
        seconds = seconds - minutes * 60
        self.duration = ("%d:%02d:%02d") % (hours, minutes, seconds)

        self.title = unicode(title)

        self.cover = None
        self.mimetype = str(mimetype)
        self.size = int(size)

        self.url = self.store.urlbase + str(self.id)


    def get_children(self, start=0, end=0):
        return []

    def get_child_count(self):
        return 0

    def get_item(self, parent_id=None):

        self.debug("Video get_item %r @ %r" %(self.id,self.parent_id))

        # create item
        item = DIDLLite.VideoItem(self.id,self.parent_id)
        #item.date =
        item.title = self.title

        item.albumArtURI = self.cover

        # add http resource
        res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
        if self.size > 0:
            res.size = self.size
        if self.duration > 0:
            res.duration = str(self.duration)
        item.res.append(res)

        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.title

    def get_url(self):
        return self.url

    def get_path(self):
        return self.path


class Image(BackendItem):

    logCategory = 'tracker_store'

    def __init__(self,store,
                 id,parent_id,
                 file,title,album,
                 date,width,height,\
                 size,mimetype):

        self.store = store
        self.id = 'image.%d' % int(id)
        self.parent_id = parent_id

        self.path = unicode(file)

        self.title = unicode(title)

        self.album = unicode(album.strip())
        self.mimetype = str(mimetype)
        self.size = int(size)

        self.url = self.store.urlbase + str(self.id)


    def get_children(self, start=0, end=0):
        return []

    def get_child_count(self):
        return 0

    def get_item(self, parent_id=None):

        self.debug("Image get_item %r @ %r" %(self.id,self.parent_id))

        # create item
        item = DIDLLite.ImageItem(self.id,self.parent_id)
        #item.date =
        item.title = self.title

        # add http resource
        res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
        if self.size > 0:
            res.size = self.size
        item.res.append(res)

        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.title

    def get_url(self):
        return self.url

    def get_path(self):
        return self.path


class TrackerStore(BackendStore):

    """ this is a backend to Meta Tracker
        http://www.gnome.org/projects/tracker/index.html


    """

    implements = ['MediaServer']
    logCategory = 'tracker_store'

    def __init__(self, server, **kwargs):

        if server.coherence.config.get('use_dbus','no') != 'yes':
            raise Exception, 'this backend needs use_dbus enabled in the configuration'
        BackendStore.__init__(self,server,**kwargs)

        self.config = kwargs
        self.name = kwargs.get('name','Tracker')

        self.update_id = 0
        self.token = None

        self.songs = 0
        self.albums = 0
        self.artists = 0
        self.playlists = 0
        self.genres = 0

        self.videos = 0
        self.images = 0

        self.bus = dbus.SessionBus()
        tracker_object = self.bus.get_object(BUS_NAME,OBJECT_PATH)
        self.tracker_interface = dbus.Interface(tracker_object, 'org.freedesktop.Tracker')
        self.search_interface = dbus.Interface(tracker_object, 'org.freedesktop.Tracker.Search')
        self.keywords_interface = dbus.Interface(tracker_object, 'org.freedesktop.Tracker.Keywords')
        self.metadata_interface = dbus.Interface(tracker_object, 'org.freedesktop.Tracker.Metadata')
        self.query_id = -1

        self.containers = {}
        self.tracks = {}
        self.containers[ROOT_CONTAINER_ID] = \
                    Container(ROOT_CONTAINER_ID,-1,self.name,store=self)

        def queries_finished(r):
            louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

        def queries_failed(r):
            error = ''
            louie.send('Coherence.UPnP.Backend.init_failed', None, backend=self, msg=error)

        services = kwargs.get('service','Music,Videos,Images')
        services = map(lambda x: x.strip().lower(),services.split(','))

        l = []
        mapping =  {'music':self.get_tracks,
                    'videos':self.get_videos,
                    'images':self.get_images}
        for service in services:
            try:
                l.append(mapping[service]())
            except KeyError:
                self.warning('Wrong Tracker service definition - %r' % service)
        if len(l)>0:
            dl = defer.DeferredList(l)
            dl.addCallback(queries_finished)
            dl.addErrback(lambda x: louie.send('Coherence.UPnP.Backend.init_failed', None, backend=self, msg='Connection to Tracker service(s) failed!'))
        else:
            louie.send('Coherence.UPnP.Backend.init_failed', None, backend=self, msg='No Tracker service defined!')

    def __repr__(self):
        return "TrackerStore"

    def get_by_id(self,id):
        self.info("looking for id %r", id)
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        if isinstance(id, basestring) and id.startswith('artist_all_tracks_'):
            try:
                return self.containers[id]
            except:
                return None
        item = None
        try:
            id = int(id)
            item = self.containers[id]
        except (ValueError,KeyError):
            try:
                type,id = id.split('.')
                if type == 'song':
                    return self.containers[AUDIO_ALL_CONTAINER_ID].children[id]
                if type == 'album':
                    return self.containers[AUDIO_ALBUM_CONTAINER_ID].children[id]
                if type == 'artist':
                    return self.containers[AUDIO_ARTIST_CONTAINER_ID].children[id]
                if type == 'video':
                    return self.containers[VIDEO_ALL_CONTAINER_ID].children[id]
                if type == 'image':
                    return self.containers[IMAGE_ALL_CONTAINER_ID].children[id]
            except (ValueError,KeyError):
                return None
        return item

    def get_videos(self):

        def handle_error(error):
            print error
            return error

        def parse_videos_query_result(resultlist):
            videos = []
            for video in resultlist:
                file,_,title,\
                duration,\
                size,mimetype = video
                title = title.strip()
                if len(title) == 0:
                    title = os.path.basename(file)
                if mimetype == 'video/x-theora+ogg':
                    mimetype = u'video/ogg'
                video_item = Video(self,
                                   self.videos,VIDEO_ALL_CONTAINER_ID,
                                   file,title,\
                                   duration,\
                                   size,mimetype)
                self.videos += 1
                videos.append(video_item)

            videos.sort(cmp=lambda x,y : cmp(x.get_name().lower(),y.get_name().lower()))
            for video_item in videos:
                self.containers[VIDEO_ALL_CONTAINER_ID].add_child(video_item)

        self.containers[VIDEO_CONTAINER_ID] = \
                    Container(VIDEO_CONTAINER_ID,ROOT_CONTAINER_ID,'Video',store=self)
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[VIDEO_CONTAINER_ID])

        self.containers[VIDEO_ALL_CONTAINER_ID] = \
                Container( VIDEO_ALL_CONTAINER_ID,VIDEO_CONTAINER_ID,'All Videos',
                          store=self,
                          children_callback=None)
        self.containers[VIDEO_CONTAINER_ID].add_child(self.containers[VIDEO_ALL_CONTAINER_ID])

        fields=[u'Video:Title',u'Video:Duration',
                u'File:Size',u'File:Mime']

        d = defer.Deferred()
        d.addCallback(parse_videos_query_result)
        d.addErrback(handle_error)
        self.search_interface.Query(self.query_id,'Videos',fields,'','',video_query,False,0,-1,
                                    reply_handler=lambda x: d.callback(x),error_handler=lambda x: d.errback(x))
        return d

    def get_images(self):

        def handle_error(error):
            return error

        def parse_images_query_result(resultlist):
            print "images", resultlist
            images = []
            for image in resultlist:
                file,_,title,album,\
                date,width, height, \
                size,mimetype = image
                title = title.strip()
                if len(title) == 0:
                    title = os.path.basename(file)
                image_item = Image(self,
                                   self.images,IMAGE_ALL_CONTAINER_ID,
                                   file,title,album,\
                                   date,width,height,\
                                   size,mimetype)
                self.images += 1
                images.append(image_item)

            images.sort(cmp=lambda x,y : cmp(x.get_name().lower(),y.get_name().lower()))
            for image_item in images:
                self.containers[IMAGE_ALL_CONTAINER_ID].add_child(image_item)

        self.containers[IMAGE_CONTAINER_ID] = \
                    Container(IMAGE_CONTAINER_ID,ROOT_CONTAINER_ID,'Images',store=self)
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[IMAGE_CONTAINER_ID])

        self.containers[IMAGE_ALL_CONTAINER_ID] = \
                Container(IMAGE_ALL_CONTAINER_ID,IMAGE_CONTAINER_ID,'All Images',
                          store=self,
                          children_callback=None)
        self.containers[IMAGE_CONTAINER_ID].add_child(self.containers[IMAGE_ALL_CONTAINER_ID])

        fields=[u'Image:Title',u'Image:Album',
                u'Image:Date',u'Image:Width',u'Image:Height',
                u'File:Size',u'File:Mime']

        d = defer.Deferred()
        d.addCallback(parse_images_query_result)
        d.addErrback(handle_error)
        self.search_interface.Query(self.query_id,'Images',fields,'','',image_query,False,0,-1,
                                    reply_handler=lambda x: d.callback(x),error_handler=lambda x: d.errback(x))
        return d


    def get_tracks(self):

        def handle_error(error):
            return error

        def parse_tracks_query_result(resultlist):
            albums = {}
            artists = {}
            tracks = []
            for track in resultlist:
                file,service,title,artist,album,genre,\
                duration,album_track_count,\
                track_number,codec,\
                size,mimetype = track
                if mimetype == 'video/x-vorbis+ogg':
                    mimetype = 'audio/ogg'
                track_item = Track(self,
                                   self.songs,AUDIO_ALL_CONTAINER_ID,
                                   file,title,artist,album,genre,\
                                   duration,\
                                   track_number,\
                                   size,mimetype)
                self.songs += 1
                tracks.append(track_item)

            tracks.sort(cmp=lambda x,y : cmp(x.get_name(),y.get_name()))
            for track_item in tracks:
                self.containers[AUDIO_ALL_CONTAINER_ID].add_child(track_item)

                try:
                    album_item = albums[track_item.album]
                    album_item.add_child(track_item)
                except:
                    album_item = Album(self, self.albums, track_item.album, track_item.artist)
                    albums[unicode(track_item.album)] = album_item
                    self.albums += 1
                    album_item.add_child(track_item)

                    try:
                        artist_item = artists[track_item.artist]
                        artist_item.add_child(album_item)
                    except:
                        artist_item = Artist(self, self.artists, track_item.artist)
                        artists[unicode(track_item.artist)] = artist_item
                        self.artists += 1
                        artist_item.add_child(album_item)

            sorted_keys = albums.keys()
            sorted_keys.sort()
            for key in sorted_keys:
                self.containers[AUDIO_ALBUM_CONTAINER_ID].add_child(albums[key])
            sorted_keys = artists.keys()
            sorted_keys.sort()
            for key in sorted_keys:
                self.containers[AUDIO_ARTIST_CONTAINER_ID].add_child(artists[key])


        self.containers[AUDIO_CONTAINER_ID] = \
                    Container(AUDIO_CONTAINER_ID,ROOT_CONTAINER_ID,'Audio',store=self)
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_CONTAINER_ID])

        self.containers[AUDIO_ALL_CONTAINER_ID] = \
                Container( AUDIO_ALL_CONTAINER_ID,AUDIO_CONTAINER_ID,'All Tracks',
                          store=self,
                          children_callback=None)
        self.containers[AUDIO_CONTAINER_ID].add_child(self.containers[AUDIO_ALL_CONTAINER_ID])

        self.containers[AUDIO_ALBUM_CONTAINER_ID] = \
                Container( AUDIO_ALBUM_CONTAINER_ID,AUDIO_CONTAINER_ID,'Albums',
                          store=self,
                          children_callback=None)
        self.containers[AUDIO_CONTAINER_ID].add_child(self.containers[AUDIO_ALBUM_CONTAINER_ID])

        self.containers[AUDIO_ARTIST_CONTAINER_ID] = \
                Container( AUDIO_ARTIST_CONTAINER_ID,AUDIO_CONTAINER_ID,'Artists',
                          store=self,
                          children_callback=None)
        self.containers[AUDIO_CONTAINER_ID].add_child(self.containers[AUDIO_ARTIST_CONTAINER_ID])

        self.containers[AUDIO_PLAYLIST_CONTAINER_ID] = \
                Container( AUDIO_PLAYLIST_CONTAINER_ID,AUDIO_CONTAINER_ID,'Playlists',
                          store=self,
                          children_callback=None,
                          container_class=DIDLLite.PlaylistContainer)
        self.containers[AUDIO_CONTAINER_ID].add_child(self.containers[AUDIO_PLAYLIST_CONTAINER_ID])

        self.containers[AUDIO_GENRE_CONTAINER_ID] = \
                Container( AUDIO_GENRE_CONTAINER_ID,AUDIO_CONTAINER_ID,'Genres',
                          store=self,
                          children_callback=None)
        self.containers[AUDIO_CONTAINER_ID].add_child(self.containers[AUDIO_GENRE_CONTAINER_ID])


        self.wmc_mapping.update({'4': lambda : self.get_by_id(AUDIO_ALL_CONTAINER_ID),       # all tracks
                                 '5': lambda : self.get_by_id(AUDIO_GENRE_CONTAINER_ID),     # all genres
                                 '6': lambda : self.get_by_id(AUDIO_ARTIST_CONTAINER_ID),    # all artists
                                 '7': lambda : self.get_by_id(AUDIO_ALBUM_CONTAINER_ID),     # all albums
                                 '13': lambda : self.get_by_id(AUDIO_PLAYLIST_CONTAINER_ID), # all playlists
                                })

        fields=[u'Audio:Title',u'Audio:Artist',
                u'Audio:Album',u'Audio:Genre',
                u'Audio:Duration',u'Audio:AlbumTrackCount',
                u'Audio:TrackNo',u'Audio:Codec',
                u'File:Size', u'File:Mime']

        d = defer.Deferred()
        d.addCallback(parse_tracks_query_result)
        d.addErrback(handle_error)
        self.search_interface.Query(self.query_id,'Music',fields,'','',tracks_query,False,0,-1,
                                    reply_handler=lambda x: d.callback(x),error_handler=lambda x: d.errback(x))
        return d



    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                            ['http-get:*:audio/mpeg:*',
                             'internal:%s:audio/mpeg:*' % self.server.coherence.hostname,
                             'http-get:*:application/ogg:*',
                             'internal:%s:application/ogg:*' % self.server.coherence.hostname,
                             'http-get:*:audio/ogg:*',
                             'internal:%s:audio/ogg:*' % self.server.coherence.hostname,
                             'http-get:*:video/ogg:*',
                             'internal:%s:video/ogg:*' % self.server.coherence.hostname,
                             'http-get:*:video/mpeg:*',
                             'internal:%s:video/mpeg:*' % self.server.coherence.hostname,
                             'http-get:*:video/x-msvideo:*',
                             'internal:%s:video/x-msvideo:*' % self.server.coherence.hostname,
                             'http-get:*:video/avi:*',
                             'internal:%s:video/avi:*' % self.server.coherence.hostname,
                             'http-get:*:video/mp4:*',
                             'internal:%s:video/mp4:*' % self.server.coherence.hostname,
                             'http-get:*:video/quicktime:*',
                             'internal:%s:video/quicktime:*' % self.server.coherence.hostname,
                             'http-get:*:image/jpg:*',
                             'internal:%s:image/jpg:*' % self.server.coherence.hostname,
                             'http-get:*:image/png:*',
                             'internal:%s:image/png:*' % self.server.coherence.hostname,
                             'http-get:*:image/gif:*',
                             'internal:%s:image/gif:*' % self.server.coherence.hostname,])
