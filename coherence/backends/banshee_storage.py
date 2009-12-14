# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009, Philippe Normand <phil@base-art.net>

"""
TODO:

- podcasts

"""

from twisted.internet import reactor, defer, task

from coherence.extern import db_row
from coherence.upnp.core import DIDLLite
from coherence.backend import BackendItem, BackendStore
from coherence.log import Loggable
import coherence.extern.louie as louie

from sqlite3 import dbapi2
# fallback on pysqlite2.dbapi2

import re
import os
import time
from urlparse import urlsplit
import urllib2


import mimetypes
mimetypes.init()
mimetypes.add_type('audio/x-m4a', '.m4a')
mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/mpegts', '.ts')
mimetypes.add_type('video/divx', '.divx')
mimetypes.add_type('video/divx', '.avi')
mimetypes.add_type('video/x-matroska', '.mkv')
mimetypes.add_type('audio/x-musepack', '.mpc')
mimetypes.add_type('audio/x-wavpack', '.flac')
mimetypes.add_type('audio/x-wavpack', '.wv')
mimetypes.add_type('audio/mp4', '.m4a')

ROOT_CONTAINER_ID = 0
AUDIO_CONTAINER = 200
VIDEO_CONTAINER = 300
AUDIO_ALL_CONTAINER_ID = 201
AUDIO_ARTIST_CONTAINER_ID = 202
AUDIO_ALBUM_CONTAINER_ID = 203
AUDIO_PLAYLIST_CONTAINER_ID = 204
VIDEO_ALL_CONTAINER_ID = 301
VIDEO_PLAYLIST_CONTAINER_ID = 302

def get_cover_path(artist_name, album_title):
    def _escape_part(part):
        escaped = ""
        if part:
            if part.find("(") > -1:
                part = part[:part.find("(")]
            escaped = re.sub("[^A-Za-z0-9]*", "", part).lower()
        return escaped

    base_dir = os.path.expanduser("~/.cache/album-art")
    return os.path.join(base_dir, "%s-%s.jpg" % (_escape_part(artist_name),
                                                 _escape_part(album_title)))

class SQLiteDB(Loggable):
    """
    Python DB API 2.0 backend support.
    """
    logCategory = "sqlite"

    def __init__(self, database):
        """ Connect to a db backend hosting the given database.
        """
        Loggable.__init__(self)
        self._params = {'database': database, 'check_same_thread': True}
        self.connect()

    def disconnect(self):
        self._db.close()

    def connect(self):
        """
        Connect to the database, set L{_db} instance variable.
        """
        self._db = dbapi2.connect(**self._params)

    def reconnect(self):
        """
        Disconnect and reconnect to the database.
        """
        self.disconnect()
        self.connect()

    def sql_execute(self, request, *params, **kw):
        """ Execute a SQL query in the db backend
        """
        t0 = time.time()
        debug_msg = request
        if params:
            debug_msg = u"%s params=%r" % (request, params)
        debug_msg = u''.join(debug_msg.splitlines())
        if debug_msg:
            self.debug('QUERY: %s', debug_msg)

        cursor = self._db.cursor()
        result = []
        cursor.execute(request, params)
        if cursor.description:
            all_rows = cursor.fetchall()
            result = db_row.getdict(all_rows, cursor.description)
        cursor.close()
        delta = time.time() - t0
        self.log("SQL request took %s seconds" % delta)
        return result

class Container(BackendItem):

    get_path = None

    def __init__(self, id, parent_id, name, children_callback=None, store=None,
                 play_container=False):
        self.id = id
        self.parent_id = parent_id
        self.name = name
        self.mimetype = 'directory'
        self.store = store
        self.play_container = play_container
        self.update_id = 0
        if children_callback != None:
            self.children = children_callback
        else:
            self.children = []

    def add_child(self, child):
        self.children.append(child)

    def get_children(self,start=0,request_count=0):
        def got_children(children):
            if request_count == 0:
                return children[start:]
            else:
                return children[start:request_count]

        if callable(self.children):
            dfr = defer.maybeDeferred(self.children)
        else:
            dfr = defer.succeed(self.children)
        dfr.addCallback(got_children)
        return dfr

    def get_child_count(self):
        count = 0
        if callable(self.children):
            count = defer.maybeDeferred(self.children)
            count.addCallback(lambda children: len(children))
        else:
            count = len(self.children)
        return count

    def get_item(self):
        item = DIDLLite.Container(self.id, self.parent_id,self.name)

        def got_count(count):
            item.childCount = count
            if self.store and self.play_container == True:
                if item.childCount > 0:
                    dfr = self.get_children(request_count=1)
                    dfr.addCallback(got_child, item)
                    return dfr
            return item

        def got_child(children, item):
            res = DIDLLite.PlayContainerResource(self.store.server.uuid,
                                                 cid=self.get_id(),
                                                 fid=children[0].get_id())
            item.res.append(res)
            return item


        dfr = defer.maybeDeferred(self.get_child_count)
        dfr.addCallback(got_count)
        return dfr

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id

class Artist(BackendItem):

    def __init__(self, *args, **kwargs):
        BackendItem.__init__(self, *args, **kwargs)
        self._row = args[0]
        self._db = args[1]
        self._local_music_library_id = args[2]
        self.musicbrainz_id = self._row.MusicBrainzID
        self.itemID = self._row.ArtistID
        self.name = self._row.Name or ''
        if self.name:
            self.name = self.name.encode("utf-8")

    def get_children(self,start=0, end=0):
        albums = []

        def query_db():
            q = "select * from CoreAlbums where ArtistID=? and AlbumID in "\
                "(select distinct(AlbumID) from CoreTracks where "\
                "PrimarySourceID=?) order by Title"
            rows = self._db.sql_execute(q, self.itemID,
                                        self._local_music_library_id)
            for row in rows:
                album = Album(row, self._db, self)
                albums.append(album)
                yield album

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: albums)
        return dfr

    def get_child_count(self):
        q = "select count(AlbumID) as c from CoreAlbums where ArtistID=? and "\
            "AlbumID in (select distinct(AlbumID) from CoreTracks where "\
            "PrimarySourceID=?) "
        return self._db.sql_execute(q, self.itemID,
                                    self._local_music_library_id)[0].c

    def get_item(self):
        item = DIDLLite.MusicArtist(self.get_id(),
                                    AUDIO_ARTIST_CONTAINER_ID, self.name)
        item.childCount = self.get_child_count()
        return item

    def get_id(self):
        return "artist.%d" % self.itemID

    def __repr__(self):
        return '<Artist %d name="%s" musicbrainz="%s">' % (self.itemID,
                                                           self.name,
                                                           self.musicbrainz_id)

class Album(BackendItem):
    """ definition for an album """
    mimetype = 'directory'
    get_path = None

    def __init__(self, *args, **kwargs):
        BackendItem.__init__(self, *args, **kwargs)
        self._row = args[0]
        self._db = args[1]
        self.artist = args[2]
        self.itemID = self._row.AlbumID
        self.title = self._row.Title
        self.cover = get_cover_path(self.artist.name, self.title)
        if self.title:
            self.title = self.title.encode("utf-8")
        self.musicbrainz_id = self._row.MusicBrainzID
        self.cd_count = 1

    def get_children(self,start=0,request_count=0):
        tracks = []

        def query_db():
            q = "select * from CoreTracks where AlbumID=? order by TrackNumber"
            if request_count:
                q += " limit %d" % request_count
            rows = self._db.sql_execute(q, self.itemID)
            for row in rows:
                track = Track(row, self._db, self)
                tracks.append(track)
                yield track

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: tracks)
        return dfr

    def get_child_count(self):
        q = "select count(TrackID) as c from CoreTracks where AlbumID=?"
        count = self._db.sql_execute(q, self.itemID)[0].c
        return count

    def get_item(self):
        item = DIDLLite.MusicAlbum(self.get_id(), AUDIO_ALBUM_CONTAINER_ID, self.title)
        item.artist = self.artist.name
        item.childCount = self.get_child_count()
        if self.cover:
            _,ext =  os.path.splitext(self.cover)
            item.albumArtURI = ''.join((self._db.urlbase,
                                        self.get_id(), '?cover', ext))

        def got_tracks(tracks):
            res = DIDLLite.PlayContainerResource(self._db.server.uuid,
                                                 cid=self.get_id(),
                                                 fid=tracks[0].get_id())
            item.res.append(res)
            return item

        if item.childCount > 0:
            dfr = self.get_children(request_count=1)
            dfr.addCallback(got_tracks)
        else:
            dfr = defer.succeed(item)
        return dfr

    def get_id(self):
        return "album.%d" % self.itemID

    def get_name(self):
        return self.title

    def get_cover(self):
        return self.cover

    def __repr__(self):
        return '<Album %d title="%s" artist="%s" #cds %d cover="%s" musicbrainz="%s">' \
               % (self.itemID, self.title,
                  self.artist.name,
                  self.cd_count,
                  self.cover,
                  self.musicbrainz_id)


class BasePlaylist(BackendItem):
    """ definition for a playlist """
    mimetype = 'directory'
    get_path = None

    def __init__(self, *args, **kwargs):
        BackendItem.__init__(self, *args, **kwargs)
        self._row = args[0]
        self._store = args[1]
        self._db = self._store.db
        self.title = self._row.Name
        if self.title:
            self.title = self.title.encode("utf-8")

    def get_tracks(self, request_count):
        return []

    def db_to_didl(self, row):
        album = self._store.get_album_with_id(row.AlbumID)
        track = Track(row, self._db, album)
        return track

    def get_id(self):
        return "%s.%d" % (self.id_type, self.db_id)

    def __repr__(self):
        return '<%s %d title="%s">' % (self.__class___.__name__,
                                       self.db_id, self.title)

    def get_children(self, start=0, request_count=0):
        tracks = []

        def query_db():
            rows = self.get_tracks(request_count)
            for row in rows:
                track = self.db_to_didl(row)
                tracks.append(track)
                yield track

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: tracks)
        return dfr

    def get_child_count(self):
        return self._row.CachedCount

    def get_item(self):
        item = DIDLLite.PlaylistContainer(self.get_id(),
                                          AUDIO_PLAYLIST_CONTAINER_ID,
                                          self.title)
        item.childCount = self.get_child_count()

        def got_tracks(tracks):
            res = DIDLLite.PlayContainerResource(self._db.server.uuid,
                                                 cid=self.get_id(),
                                                 fid=tracks[0].get_id())
            item.res.append(res)
            return item

        if item.childCount > 0:
            dfr = self.get_children(request_count=1)
            dfr.addCallback(got_tracks)
        else:
            dfr = defer.succeed(item)
        return dfr

    def get_name(self):
        return self.title

class MusicPlaylist(BasePlaylist):
    id_type = "musicplaylist"

    @property
    def db_id(self):
        return self._row.PlaylistID

    def get_tracks(self, request_count):
        q = "select * from CoreTracks where TrackID in (select TrackID "\
            "from CorePlaylistEntries where PlaylistID=?)"
        if request_count:
            q += " limit %d" % request_count
        return self._db.sql_execute(q, self.db_id)

class MusicSmartPlaylist(BasePlaylist):
    id_type = "musicsmartplaylist"

    @property
    def db_id(self):
        return self._row.SmartPlaylistID

    def get_tracks(self, request_count):
        q = "select * from CoreTracks where TrackID in (select TrackID "\
            "from CoreSmartPlaylistEntries where SmartPlaylistID=?)"
        if request_count:
            q += " limit %d" % request_count
        return self._db.sql_execute(q, self.db_id)

class VideoPlaylist(MusicPlaylist):
    id_type = "videoplaylist"

    def db_to_didl(self, row):
        return Video(row, self._db)

class VideoSmartPlaylist(MusicSmartPlaylist):
    id_type = "videosmartplaylist"

    def db_to_didl(self, row):
        return Video(row, self._db)

class BaseTrack(BackendItem):
    """ definition for a track """

    def __init__(self, *args, **kwargs):
        BackendItem.__init__(self, *args, **kwargs)
        self._row = args[0]
        self._db = args[1]
        self.itemID = self._row.TrackID
        self.title = self._row.Title
        self.track_nr = self._row.TrackNumber
        self.location = self._row.Uri
        self.playlist = kwargs.get("playlist")

    def get_children(self,start=0,request_count=0):
        return []

    def get_child_count(self):
        return 0

    def get_resources(self):
        resources = []
        _,host_port,_,_,_ = urlsplit(self._db.urlbase)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
        else:
            host = host_port

        _,ext =  os.path.splitext(self.location)
        ext = ext.lower()

        # FIXME: drop this hack when we switch to tagbin
        mimetype, dummy = mimetypes.guess_type("dummy%s" % ext)
        if not mimetype:
            mimetype = 'audio/mpeg'
            ext = "mp3"

        statinfo = os.stat(self.get_path())

        res = DIDLLite.Resource(self.location, 'internal:%s:%s:*' % (host,
                                                                     mimetype))
        try:
            res.size = statinfo.st_size
        except:
            res.size = 0

        resources.append(res)

        url = "%s%s%s" % (self._db.urlbase, self.get_id(), ext)

        res = DIDLLite.Resource(url, 'http-get:*:%s:*' % mimetype)
        try:
            res.size = statinfo.st_size
        except:
            res.size = 0
        resources.append(res)
        return statinfo, resources

    def get_path(self):
        return urllib2.unquote(self.location[7:].encode('utf-8'))

    def get_id(self):
        return "track.%d" % self.itemID

    def get_name(self):
        return self.title

    def get_url(self):
        return self._db.urlbase + str(self.itemID).encode('utf-8')

    def get_cover(self):
        return self.album.cover

    def __repr__(self):
        return '<Track %d title="%s" nr="%d" album="%s" artist="%s" path="%s">' \
               % (self.itemID, self.title, self.track_nr, self.album.title,
                  self.album.artist.name, self.location)

class Track(BaseTrack):

    def __init__(self, *args, **kwargs):
        BaseTrack.__init__(self, *args, **kwargs)
        self.album = args[2]

    def get_item(self):
        item = DIDLLite.MusicTrack(self.get_id(), self.album.itemID,self.title)
        item.artist = self.album.artist.name
        item.album = self.album.title
        item.playlist = self.playlist

        if self.album.cover != '':
            _,ext =  os.path.splitext(self.album.cover)
            """ add the cover image extension to help clients not reacting on
                the mimetype """
            item.albumArtURI = ''.join((self._db.urlbase, self.get_id(),
                                        '?cover',ext))
        item.originalTrackNumber = self.track_nr
        item.server_uuid = str(self._db.server.uuid)[5:]

        statinfo, resources = self.get_resources()
        item.res.extend(resources)

        try:
            # FIXME: getmtime is deprecated in Twisted 2.6
            item.date = datetime.fromtimestamp(statinfo.st_mtime)
        except:
            item.date = None

        return item

class Video(BaseTrack):
    def get_item(self):
        item = DIDLLite.VideoItem(self.get_id(), VIDEO_ALL_CONTAINER_ID,
                                  self.title)
        item.server_uuid = str(self._db.server.uuid)[5:]

        statinfo, resources = self.get_resources()
        item.res.extend(resources)

        try:
            # FIXME: getmtime is deprecated in Twisted 2.6
            item.date = datetime.fromtimestamp(statinfo.st_mtime)
        except:
            item.date = None

        return item

class BansheeDB(Loggable):
    logCategory = "banshee_db"

    def __init__(self, path=None):
        Loggable.__init__(self)
        self._local_music_library_id = None
        self._local_video_library_id = None
        default_db_path = os.path.expanduser("~/.config/banshee-1/banshee.db")
        self._db_path = path or default_db_path

    def open_db(self):
        self.db = SQLiteDB(self._db_path)

    def close(self):
        self.db.disconnect()

    def get_local_music_library_id(self):
        if self._local_music_library_id is None:
            q = "select PrimarySourceID from CorePrimarySources where StringID=?"
            row = self.db.sql_execute(q, 'MusicLibrarySource-Library')[0]
            self._local_music_library_id = row.PrimarySourceID
        return self._local_music_library_id

    def get_local_video_library_id(self):
        if self._local_video_library_id is None:
            q = "select PrimarySourceID from CorePrimarySources where StringID=?"
            row = self.db.sql_execute(q, 'VideoLibrarySource-VideoLibrary')[0]
            self._local_video_library_id = row.PrimarySourceID
        return self._local_video_library_id

    def get_artists(self):
        artists = []

        def query_db():
            source_id = self.get_local_music_library_id()
            q = "select * from CoreArtists where ArtistID in "\
                "(select distinct(ArtistID) from CoreTracks where "\
                "PrimarySourceID=?) order by Name"
            for row in self.db.sql_execute(q, source_id):
                artist = Artist(row, self.db, source_id)
                artists.append(artist)
                yield artist

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: artists)
        return dfr

    def get_albums(self):
        albums = []
        artists = {}

        def query_db():
            q = "select * from CoreAlbums where AlbumID in "\
                "(select distinct(AlbumID) from CoreTracks where "\
                "PrimarySourceID=?) order by Title"
            for row in self.db.sql_execute(q, self.get_local_music_library_id()):
                try:
                    artist = artists[row.ArtistID]
                except KeyError:
                    artist = self.get_artist_with_id(row.ArtistID)
                    artists[row.ArtistID] = artist
                album = Album(row, self.db, artist)
                albums.append(album)
                yield album

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: albums)
        return dfr

    def get_music_playlists(self):
        return self.get_playlists(self.get_local_music_library_id(),
                                  MusicPlaylist, MusicSmartPlaylist)

    def get_playlists(self, source_id, PlaylistClass, SmartPlaylistClass):
        playlists = []

        def query_db():
            q = "select * from CorePlaylists where PrimarySourceID=? order by Name"
            for row in self.db.sql_execute(q, source_id):
                playlist = PlaylistClass(row, self)
                playlists.append(playlist)
                yield playlist

            q = "select * from CoreSmartPlaylists where PrimarySourceID=? order by Name"
            for row in self.db.sql_execute(q, source_id):
                playlist = SmartPlaylistClass(row, self)
                playlists.append(playlist)
                yield playlist

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: playlists)
        return dfr

    def get_artist_with_id(self, artist_id):
        q = "select * from CoreArtists where ArtistID=? limit 1"
        row = self.db.sql_execute(q, artist_id)[0]
        return Artist(row, self.db, self.get_local_music_library_id())

    def get_album_with_id(self, album_id):
        q = "select * from CoreAlbums where AlbumID=? limit 1"
        row = self.db.sql_execute(q, album_id)[0]
        artist = self.get_artist_with_id(row.ArtistID)
        return Album(row, self.db, artist)

    def get_playlist_with_id(self, playlist_id, PlaylistClass):
        q = "select * from CorePlaylists where PlaylistID=? limit 1"
        row = self.db.sql_execute(q, playlist_id)[0]
        return PlaylistClass(row, self)

    def get_smart_playlist_with_id(self, playlist_id, PlaylistClass):
        q = "select * from CoreSmartPlaylists where SmartPlaylistID=? limit 1"
        row = self.db.sql_execute(q, playlist_id)[0]
        return PlaylistClass(row, self)

    def get_music_playlist_with_id(self, playlist_id):
        return self.get_playlist_with_id(playlist_id, MusicPlaylist)

    def get_music_smart_playlist_with_id(self, playlist_id):
        return self.get_smart_playlist_with_id(playlist_id, MusicSmartPlaylist)

    def get_video_playlist_with_id(self, playlist_id):
        return self.get_playlist_with_id(playlist_id, VideoPlaylist)

    def get_video_smart_playlist_with_id(self, playlist_id):
        return self.get_smart_playlist_with_id(playlist_id, VideoSmartPlaylist)

    def get_track_with_id(self, track_id):
        q = "select * from CoreTracks where TrackID=? limit 1"
        row = self.db.sql_execute(q, track_id)[0]
        album = self.get_album_with_id(row.AlbumID)
        return Track(row, self.db, album)

    def get_track_for_uri(self, track_uri):
        q = "select * from CoreTracks where Uri=? limit 1"
        try:
            row = self.db.sql_execute(q, track_uri)[0]
        except IndexError:
            # not found
            track = None
        else:
            album = self.get_album_with_id(row.AlbumID)
            track = Track(row, self, album)
        return track

    def get_tracks(self):
        tracks = []
        albums = {}

        def query_db():
            q = "select * from CoreTracks where TrackID in "\
                "(select distinct(TrackID) from CoreTracks where "\
                "PrimarySourceID=?) order by AlbumID,TrackNumber"
            for row in self.db.sql_execute(q, self.get_local_music_library_id()):
                if row.AlbumID not in albums:
                    album = self.get_album_with_id(row.AlbumID)
                    albums[row.AlbumID] = album
                else:
                    album = albums[row.AlbumID]
                track = Track(row, self.db,album)
                tracks.append(track)
                yield track

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: tracks)
        return dfr

    def get_video_with_id(self, video_id):
        q = "select * from CoreTracks where TrackID=? limit 1"
        row = self.db.sql_execute(q, video_id)[0]
        return Video(row, self.db)

    def get_videos(self):
        videos = []

        def query_db():
            source_id = self.get_local_video_library_id()
            q = "select * from CoreTracks where TrackID in "\
                "(select distinct(TrackID) from CoreTracks where "\
                "PrimarySourceID=?)"
            for row in self.db.sql_execute(q, source_id):
                video = Video(row, self.db, source_id)
                videos.append(video)
                yield video

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: videos)
        return dfr

    def get_video_playlists(self):
        return self.get_playlists(self.get_local_video_library_id(),
                                  VideoPlaylist, VideoSmartPlaylist)

class BansheeStore(BackendStore, BansheeDB):
    logCategory = 'banshee_store'
    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)
        BansheeDB.__init__(self, kwargs.get("db_path"))
        self.update_id = 0
        self.name = kwargs.get('name', 'Banshee')

        self.containers = {}
        self.containers[ROOT_CONTAINER_ID] = Container(ROOT_CONTAINER_ID,
                                                       -1, self.name, store=self)
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def upnp_init(self):
        self.open_db()

        music = Container(AUDIO_CONTAINER, ROOT_CONTAINER_ID,
                          'Music', store=self)
        self.containers[ROOT_CONTAINER_ID].add_child(music)
        self.containers[AUDIO_CONTAINER] = music

        artists = Container(AUDIO_ARTIST_CONTAINER_ID, AUDIO_CONTAINER,
                            'Artists', children_callback=self.get_artists,
                            store=self)
        self.containers[AUDIO_ARTIST_CONTAINER_ID] = artists
        self.containers[AUDIO_CONTAINER].add_child(artists)

        albums = Container(AUDIO_ALBUM_CONTAINER_ID, AUDIO_CONTAINER,
                           'Albums', children_callback=self.get_albums,
                           store=self)
        self.containers[AUDIO_ALBUM_CONTAINER_ID] = albums
        self.containers[AUDIO_CONTAINER].add_child(albums)

        tracks = Container(AUDIO_ALL_CONTAINER_ID, AUDIO_CONTAINER,
                           'All tracks', children_callback=self.get_tracks,
                           play_container=True, store=self)
        self.containers[AUDIO_ALL_CONTAINER_ID] = tracks
        self.containers[AUDIO_CONTAINER].add_child(tracks)

        playlists = Container(AUDIO_PLAYLIST_CONTAINER_ID, AUDIO_CONTAINER,
                              'Playlists', store=self,
                              children_callback=self.get_music_playlists)
        self.containers[AUDIO_PLAYLIST_CONTAINER_ID] = playlists
        self.containers[AUDIO_CONTAINER].add_child(playlists)

        videos = Container(VIDEO_CONTAINER, ROOT_CONTAINER_ID,
                          'Videos', store=self)
        self.containers[ROOT_CONTAINER_ID].add_child(videos)
        self.containers[VIDEO_CONTAINER] = videos

        all_videos = Container(VIDEO_ALL_CONTAINER_ID, VIDEO_CONTAINER,
                               'All Videos', children_callback=self.get_videos,
                               store=self)
        self.containers[VIDEO_ALL_CONTAINER_ID] = all_videos
        self.containers[VIDEO_CONTAINER].add_child(all_videos)

        playlists = Container(VIDEO_PLAYLIST_CONTAINER_ID, VIDEO_CONTAINER,
                              'Playlists', store=self,
                              children_callback=self.get_video_playlists)
        self.containers[VIDEO_PLAYLIST_CONTAINER_ID] = playlists
        self.containers[VIDEO_CONTAINER].add_child(playlists)


        self.db.server = self.server
        self.db.urlbase = self.urlbase
        self.db.containers = self.containers

        self.current_connection_id = None
        if self.server:
            hostname = self.server.coherence.hostname
            source_protocol_info = ['internal:%s:audio/mpeg:*' % hostname,
                                    'http-get:*:audio/mpeg:*',
                                    'internal:%s:application/ogg:*' % hostname,
                                    'http-get:*:application/ogg:*']

            self.server.connection_manager_server.set_variable(0,
                                                               'SourceProtocolInfo',
                                                               source_protocol_info,
                                                               default=True)

    def release(self):
        self.db.disconnect()

    def get_by_id(self,item_id):
        self.info("get_by_id %s" % item_id)
        if isinstance(item_id, basestring) and item_id.find('.') > 0:
            item_id = item_id.split('@',1)
            item_type, item_id = item_id[0].split('.')[:2]
            item_id = int(item_id)
            dfr = self._lookup(item_type, item_id)
        else:
            item_id = int(item_id)
            item = self.containers[item_id]
            dfr = defer.succeed(item)
        return dfr

    def _lookup(self, item_type, item_id):
        lookup_mapping = dict(artist=self.get_artist_with_id,
                              album=self.get_album_with_id,
                              musicplaylist=self.get_music_playlist_with_id,
                              musicsmartplaylist=self.get_music_smart_playlist_with_id,
                              videoplaylist=self.get_video_playlist_with_id,
                              videosmartplaylist=self.get_video_smart_playlist_with_id,
                              track=self.get_track_with_id,
                              video=self.get_video_with_id)
        item = None
        func = lookup_mapping.get(item_type)
        if func:
            item = func(item_id)
        return defer.succeed(item)
