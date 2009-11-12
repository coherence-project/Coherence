# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009, Philippe Normand <phil@base-art.net>

"""
TODO:

- playlists
- videos
- podcasts

"""

from twisted.internet import reactor, defer, task

from coherence.extern import db_row
from coherence.upnp.core import DIDLLite
from coherence.backend import BackendItem, BackendStore
from coherence.log import Loggable

from sqlite3 import dbapi2
# fallback on pysqlite2.dbapi2

import re
import os
import time
from urlparse import urlsplit
import urllib2

ROOT_CONTAINER_ID = 0
AUDIO_CONTAINER = 200
AUDIO_ALL_CONTAINER_ID = 201
AUDIO_ARTIST_CONTAINER_ID = 202
AUDIO_ALBUM_CONTAINER_ID = 203

KNOWN_AUDIO_TYPES = {'.mp3':'audio/mpeg',
                     '.ogg':'application/ogg',
                     '.mpc':'audio/x-musepack',
                     '.flac':'audio/x-wavpack',
                     '.wv':'audio/x-wavpack',
                     '.m4a':'audio/mp4',}

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
        self.storeID = self._row.ArtistID
        self.name = self._row.Name or ''
        if self.name:
            self.name = self.name.encode("utf-8")

    def get_children(self,start=0, end=0):
        albums = []

        def query_db():
            q = "select * from CoreAlbums where ArtistID=? and AlbumID in "\
                "(select distinct(AlbumID) from CoreTracks where "\
                "PrimarySourceID=?) order by Title"
            rows = self._db.sql_execute(q, self.storeID,
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
        return self._db.sql_execute(q, self.storeID,
                                    self._local_music_library_id)[0].c

    def get_item(self):
        item = DIDLLite.MusicArtist(self.get_id(),
                                    AUDIO_ARTIST_CONTAINER_ID, self.name)
        item.childCount = self.get_child_count()
        return item

    def get_id(self):
        return "artist.%d" % self.storeID

    def __repr__(self):
        return '<Artist %d name="%s" musicbrainz="%s">' % (self.storeID,
                                                           self.name,
                                                           self.musicbrainz_id)

class Album(BackendItem):
    """ definition for an album """
    typeName = 'album'
    mimetype = 'directory'
    get_path = None

    def __init__(self, *args, **kwargs):
        BackendItem.__init__(self, *args, **kwargs)
        self._row = args[0]
        self._db = args[1]
        self.artist = args[2]
        self.storeID = self._row.AlbumID
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
            rows = self._db.sql_execute(q, self.storeID)
            for row in rows:
                track = Track(row, self._db, self)
                tracks.append(track)
                yield track

        dfr = task.coiterate(query_db())
        dfr.addCallback(lambda gen: tracks)
        return dfr

    def get_child_count(self):
        q = "select count(TrackID) as c from CoreTracks where AlbumID=?"
        count = self._db.sql_execute(q, self.storeID)[0].c
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

        if self.get_child_count() > 0:
            dfr = self.get_children(request_count=1)
            dfr.addCallback(got_tracks)
        else:
            dfr = defer.succeed(item)
        return dfr

    def get_id(self):
        return "album.%d" % self.storeID

    def get_name(self):
        return self.title

    def get_cover(self):
        return self.cover

    def __repr__(self):
        return '<Album %d title="%s" artist="%s" #cds %d cover="%s" musicbrainz="%s">' \
               % (self.storeID, self.title,
                  self.artist.name,
                  self.cd_count,
                  self.cover,
                  self.musicbrainz_id)

class Track(BackendItem):
    """ definition for a track """

    def __init__(self, *args, **kwargs):
        BackendItem.__init__(self, *args, **kwargs)
        self._row = args[0]
        self._db = args[1]
        self.album = args[2]
        self.storeID = self._row.TrackID
        self.title = self._row.Title
        self.track_nr = self._row.TrackNumber
        self.location = self._row.Uri

    def get_children(self,start=0,request_count=0):
        return []

    def get_child_count(self):
        return 0

    def get_item(self):
        item = DIDLLite.MusicTrack(self.get_id(), self.album.storeID,self.title)
        item.artist = self.album.artist.name
        item.album = self.album.title
        if self.album.cover != '':
            _,ext =  os.path.splitext(self.album.cover)
            """ add the cover image extension to help clients not reacting on
                the mimetype """
            item.albumArtURI = ''.join((self._db.urlbase, self.get_id(),
                                        '?cover',ext))
        item.originalTrackNumber = self.track_nr
        item.server_uuid = str(self._db.server.uuid)[5:]

        _,host_port,_,_,_ = urlsplit(self._db.urlbase)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
        else:
            host = host_port

        _,ext =  os.path.splitext(self.location)
        ext = ext.lower()

        # FIXME: drop this hack when we switch to tagbin
        try:
            mimetype = KNOWN_AUDIO_TYPES[ext]
        except KeyError:
            mimetype = 'audio/mpeg'
            ext = "mp3"

        statinfo = os.stat(self.get_path())

        res = DIDLLite.Resource(self.location, 'internal:%s:%s:*' % (host,
                                                                     mimetype))
        try:
            res.size = statinfo.st_size
        except:
            res.size = 0
        item.res.append(res)

        url = "%strack.%d%s" % (self._db.urlbase, self.storeID, ext)

        res = DIDLLite.Resource(url, 'http-get:*:%s:*' % mimetype)
        try:
            res.size = statinfo.st_size
        except:
            res.size = 0
        item.res.append(res)

        try:
            # FIXME: getmtime is deprecated in Twisted 2.6
            item.date = datetime.fromtimestamp(statinfo.st_mtime)
        except:
            item.date = None

        return item

    def get_path(self):
        return urllib2.unquote(self.location[7:].encode('utf-8'))

    def get_id(self):
        return "track.%d" % self.storeID

    def get_name(self):
        return self.title

    def get_url(self):
        return self._db.urlbase + str(self.storeID).encode('utf-8')

    def get_cover(self):
        return self.album.cover

    def __repr__(self):
        return '<Track %d title="%s" nr="%d" album="%s" artist="%s" path="%s">' \
               % (self.storeID, self.title, self.track_nr, self.album.title,
                  self.album.artist.name, self.location)


class BansheeStore(BackendStore):
    logCategory = 'banshee_store'
    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)
        self.update_id = 0
        self._local_music_library_id = None
        default_db_path = os.path.expanduser("~/.config/banshee-1/banshee.db")
        self._db_path = kwargs.get("db_path", default_db_path)
        self.name = kwargs.get('name', 'Banshee')

        self.containers = {}
        self.containers[ROOT_CONTAINER_ID] = Container(ROOT_CONTAINER_ID,
                                                       -1, self.name, store=self)

    def upnp_init(self):
        self.db = SQLiteDB(self._db_path)
        artists = Container(AUDIO_ARTIST_CONTAINER_ID, ROOT_CONTAINER_ID,
                            'Artists', children_callback=self.get_artists,
                            store=self)
        self.containers[AUDIO_ARTIST_CONTAINER_ID] = artists
        self.containers[ROOT_CONTAINER_ID].add_child(artists)

        albums = Container(AUDIO_ALBUM_CONTAINER_ID, ROOT_CONTAINER_ID,
                           'Albums', children_callback=self.get_albums,
                           store=self)
        self.containers[AUDIO_ALBUM_CONTAINER_ID] = albums
        self.containers[ROOT_CONTAINER_ID].add_child(albums)

        tracks = Container(AUDIO_ALL_CONTAINER_ID, ROOT_CONTAINER_ID,
                           'All tracks', children_callback=self.get_tracks,
                           play_container=True, store=self)
        self.containers[AUDIO_ALL_CONTAINER_ID] = tracks
        self.containers[ROOT_CONTAINER_ID].add_child(tracks)

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

    def get_local_music_library_id(self):
        if self._local_music_library_id is None:
            q = "select PrimarySourceID from CorePrimarySources where StringID=?"
            row = self.db.sql_execute(q, 'MusicLibrarySource-Library')[0]
            self._local_music_library_id = row.PrimarySourceID
        return self._local_music_library_id

    def get_artists(self):
        artists = []

        def query_db():
            q = "select * from CoreArtists where ArtistID in "\
                "(select distinct(ArtistID) from CoreTracks where "\
                "PrimarySourceID=?) order by Name"
            for row in self.db.sql_execute(q, self.get_local_music_library_id()):
                artist = Artist(row, self.db, self.get_local_music_library_id())
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

    def get_artist_with_id(self, artist_id):
        q = "select * from CoreArtists where ArtistID=? limit 1"
        row = self.db.sql_execute(q, artist_id)[0]
        return Artist(row, self.db, self.get_local_music_library_id())

    def get_album_with_id(self, album_id):
        q = "select * from CoreAlbums where AlbumID=? limit 1"
        row = self.db.sql_execute(q, album_id)[0]
        artist = self.get_artist_with_id(row.ArtistID)
        return Album(row, self.db, artist)

    def get_track_with_id(self, track_id):
        q = "select * from CoreTracks where TrackID=? limit 1"
        row = self.db.sql_execute(q, track_id)[0]
        album = self.get_album_with_id(row.AlbumID)
        return Track(row, self.db, album)

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

    def _lookup(self, item_type, item_id):
        item = None
        if item_type == "artist":
            item = self.get_artist_with_id(item_id)
        elif item_type == "album":
            item = self.get_album_with_id(item_id)
        elif item_type == "track":
            item = self.get_track_with_id(item_id)
        return defer.succeed(item)
