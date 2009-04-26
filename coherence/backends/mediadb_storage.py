# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007,2008, Frank Scholz <coherence@beebits.net>

"""

MediaStore

A MediaServer with a database backend,
exposes its content in All, Albums and Artists containers.
Serves cover art with the Album object, and keeps references to
the MusicBrainz DB - http://musicbrainz.org/

Should not scan for files, but gets feeded
with proper tagged ones via some import tool
or/and allow imports via the web-UI.

depends on:
            for the sqlite db handling:

                Axiom - http://divmod.org/trac/wiki/DivmodAxiom
                Epsilon - http://divmod.org/trac/wiki/DivmodEpsilon

            for id3 tag extraction:

                libmtag - http://code.google.com/p/libmtag/
                taglib - http://developer.kde.org/~wheeler/taglib.html

                or

                pyid3lib - http://pyid3lib.sourceforge.net/doc.html

                or

                tagpy - http://news.tiker.net/software/tagpy
                taglib - http://developer.kde.org/~wheeler/taglib.html

            CoversByAmazon - https://coherence.beebits.net/browser/trunk/coherence/extern/covers_by_amazon.py
"""

import os, shutil
import string
import urllib

from urlparse import urlsplit

from axiom import store, item, attributes
from epsilon.extime import Time

import coherence.extern.louie as louie

from twisted.internet import reactor, defer

from twisted.python.filepath import FilePath
from coherence.upnp.core import DIDLLite

from coherence.extern.covers_by_amazon import CoverGetter

from coherence.backend import BackendItem, BackendStore

KNOWN_AUDIO_TYPES = {'.mp3':'audio/mpeg',
                     '.ogg':'application/ogg',
                     '.mpc':'audio/x-musepack',
                     '.flac':'audio/x-wavpack',
                     '.wv':'audio/x-wavpack',
                     '.m4a':'audio/mp4',}


def _dict_from_tags(tag):
    tags = {}
    tags['artist'] = tag.artist.strip()
    tags['album'] = tag.album.strip()
    tags['title'] = tag.title.strip()
    if type(tag.track) == int:
        tags['track'] = tag.track
    elif type(tag.track) in (str, unicode):
        tags['track'] = int(tag.track.strip())
    else:
        tags['track'] = tag.track[0]

    for key in ('artist', 'album', 'title'):
        value = tags.get(key, u'')
        if isinstance(value, unicode):
            tags[key] = value.encode('utf-8')

    return tags

try:
    import libmtag

    def get_tags(filename):
        audio_file = libmtag.File(filename)
        tags = {}
        tags['artist'] = audio_file.tag().get('artist').strip()
        tags['album'] = audio_file.tag().get('album').strip()
        tags['title'] = audio_file.tag().get('title').strip()
        tags['track'] = audio_file.tag().get('track').strip()
        return tags

except ImportError:
    try:
        import pyid3lib

        def get_tags(filename):
            audio_file = pyid3lib.tag(filename)
            return _dict_from_tags(audio_file)

    except ImportError:
        try:
            import tagpy

            def get_tags(filename):
                audio_file = tagpy.FileRef(filename)
                return _dict_from_tags(audio_file.tag())
        except ImportError:
            get_tags = None

if not get_tags:
    raise ImportError, "we need some installed id3 tag library for this backend: python-tagpy, pyid3lib or libmtag"



MEDIA_DB = 'tests/media.db'

ROOT_CONTAINER_ID = 0
AUDIO_CONTAINER = 100
AUDIO_ALL_CONTAINER_ID = 101
AUDIO_ARTIST_CONTAINER_ID = 102
AUDIO_ALBUM_CONTAINER_ID = 103

def sanitize(filename):
    badchars = ''.join(set(string.punctuation) - set('-_+.~'))
    f = unicode(filename.lower())
    for old, new in ((u'ä','ae'),(u'ö','oe'),(u'ü','ue'),(u'ß','ss')):
        f = f.replace(unicode(old),unicode(new))
    f = f.replace(badchars, '_')
    return f


class Container(BackendItem):

    get_path = None

    def __init__(self, id, parent_id, name, children_callback=None,store=None,play_container=False):
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
        if callable(self.children):
            children = self.children()
        else:
            children = self.children
        if request_count == 0:
            return children[start:]
        else:
            return children[start:request_count]

    def get_child_count(self):
        if callable(self.children):
            return len(self.children())
        else:
            return len(self.children)

    def get_item(self):
        item = DIDLLite.Container(self.id, self.parent_id,self.name)
        item.childCount = self.get_child_count()
        if self.store and self.play_container == True:
            if item.childCount > 0:
                res = DIDLLite.PlayContainerResource(self.store.server.uuid,cid=self.get_id(),fid=self.get_children()[0].get_id())
                item.res.append(res)
        return item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id


class Artist(item.Item,BackendItem):
    """ definition for an artist """

    schemaVersion = 1
    typeName = 'artist'
    mimetype = 'directory'

    name = attributes.text(allowNone=False, indexed=True)
    musicbrainz_id = attributes.text()

    get_path = None

    def get_artist_all_tracks(self,start=0,request_count=0):
        children = [x[1] for x in list(self.store.query((Album,Track),
                            attributes.AND(Album.artist == self,
                                           Track.album == Album.storeID),
                            sort=(Album.title.ascending,Track.track_nr.ascending)
                            ))]
        if request_count == 0:
            return children[start:]
        else:
            return children[start:request_count]

    def get_children(self,start=0,request_count=0):
        all_id = 'artist_all_tracks_%d' % (self.storeID+1000)
        self.store.containers[all_id] = \
                Container( all_id, self.storeID+1000, 'All tracks of %s' % self.name,
                          children_callback=self.get_artist_all_tracks,
                          store=self.store,play_container=True)

        children = [self.store.containers[all_id]] + list(self.store.query(Album, Album.artist == self,sort=Album.title.ascending))
        if request_count == 0:
            return children[start:]
        else:
            return children[start:request_count]

    def get_child_count(self):
        return len(list(self.store.query(Album, Album.artist == self))) + 1

    def get_item(self):
        item = DIDLLite.MusicArtist(self.storeID+1000, AUDIO_ARTIST_CONTAINER_ID, self.name)
        item.childCount = self.get_child_count()
        return item

    def get_id(self):
        return self.storeID + 1000

    def get_name(self):
        return self.name

    def __repr__(self):
        return '<Artist %d name="%s" musicbrainz="%s">' \
               % (self.storeID, self.name.encode('ascii', 'ignore'), self.musicbrainz_id)


class Album(item.Item,BackendItem):
    """ definition for an album """

    schemaVersion = 1
    typeName = 'album'
    mimetype = 'directory'

    title = attributes.text(allowNone=False, indexed=True)
    musicbrainz_id = attributes.text()
    artist = attributes.reference(allowNone=False, indexed=True)
    cd_count = attributes.integer(default=1)
    cover = attributes.text(default=u'')

    get_path = None

    def get_children(self,start=0,request_count=0):
        children = list(self.store.query(Track, Track.album == self,sort=Track.track_nr.ascending))
        if request_count == 0:
            return children[start:]
        else:
            return children[start:request_count]

    def get_child_count(self):
        return len(list(self.store.query(Track, Track.album == self)))

    def get_item(self):
        item = DIDLLite.MusicAlbum(self.storeID+1000, AUDIO_ALBUM_CONTAINER_ID, self.title)
        item.artist = self.artist.name
        item.childCount = self.get_child_count()
        if len(self.cover)>0:
            _,ext =  os.path.splitext(self.cover)
            item.albumArtURI = ''.join((self.store.urlbase,str(self.get_id()),'?cover',ext))

        if self.get_child_count() > 0:
            res = DIDLLite.PlayContainerResource(self.store.server.uuid,cid=self.get_id(),fid=self.get_children()[0].get_id())
            item.res.append(res)
        return item

    def get_id(self):
        return self.storeID + 1000

    def get_name(self):
        return self.title

    def get_cover(self):
        return self.cover

    def __repr__(self):
        return '<Album %d title="%s" artist="%s" #cds %d cover="%s" musicbrainz="%s">' \
               % (self.storeID, self.title.encode('ascii', 'ignore'),
                  self.artist.name.encode('ascii', 'ignore'),
                  self.cd_count,
                  self.cover.encode('ascii', 'ignore'),
                  self.musicbrainz_id)


class Track(item.Item,BackendItem):
    """ definition for a track """

    schemaVersion = 1
    typeName = 'track'

    title = attributes.text(allowNone=False, indexed=True)
    track_nr = attributes.integer(default=1,allowNone=False)
    cd_nr = attributes.integer(default=1,allowNone=False)
    album = attributes.reference(allowNone=False, indexed=True)
    location = attributes.text(allowNone=False)
    rating=attributes.integer(default=0,allowNone=False)
    last_played=attributes.timestamp()
    added=attributes.timestamp(default=Time(),allowNone=False)

    def get_children(self,start=0,request_count=0):
        return []

    def get_child_count(self):
        return 0

    def get_item(self):
        item = DIDLLite.MusicTrack(self.storeID+1000, self.album.storeID+1000,self.title)
        item.artist = self.album.artist.name
        item.album = self.album.title
        if self.album.cover != '':
            _,ext =  os.path.splitext(self.album.cover)
            """ add the cover image extension to help clients not reacting on
                the mimetype """
            item.albumArtURI = ''.join((self.store.urlbase,str(self.storeID+1000),'?cover',ext))
        item.originalTrackNumber = self.track_nr
        item.server_uuid = str(self.store.server.uuid)[5:]

        _,host_port,_,_,_ = urlsplit(self.store.urlbase)
        if host_port.find(':') != -1:
            host,port = tuple(host_port.split(':'))
        else:
            host = host_port

        _,ext =  os.path.splitext(self.location)
        ext = ext.lower()

        try:
            mimetype = KNOWN_AUDIO_TYPES[ext]
        except KeyError:
            mimetype = 'audio/mpeg'

        statinfo = os.stat(self.location)

        res = DIDLLite.Resource('file://'+self.location, 'internal:%s:%s:*' % (host,mimetype))
        try:
            res.size = statinfo.st_size
        except:
            res.size = 0
        item.res.append(res)

        url = self.store.urlbase + str(self.storeID+1000) + ext

        res = DIDLLite.Resource(url, 'http-get:*:%s:*' % mimetype)
        try:
            res.size = statinfo.st_size
        except:
            res.size = 0
        item.res.append(res)

        #if self.store.server.coherence.config.get('transcoding', 'no') == 'yes':
        #    if mimetype in ('audio/mpeg',
        #                    'application/ogg','audio/ogg',
        #                    'audio/x-m4a',
        #                    'application/x-flac'):
        #        dlna_pn = 'DLNA.ORG_PN=LPCM'
        #        dlna_tags = DIDLLite.simple_dlna_tags[:]
        #        dlna_tags[1] = 'DLNA.ORG_CI=1'
        #        #dlna_tags[2] = 'DLNA.ORG_OP=00'
        #        new_res = DIDLLite.Resource(url+'?transcoded=lpcm',
        #            'http-get:*:%s:%s' % ('audio/L16;rate=44100;channels=2', ';'.join([dlna_pn]+dlna_tags)))
        #        new_res.size = None
        #        item.res.append(new_res)
        #
        #        if mimetype != 'audio/mpeg':
        #            new_res = DIDLLite.Resource(url+'?transcoded=mp3',
        #                'http-get:*:%s:*' % 'audio/mpeg')
        #            new_res.size = None
        #            item.res.append(new_res)

        try:
            # FIXME: getmtime is deprecated in Twisted 2.6
            item.date = datetime.fromtimestamp(statinfo.st_mtime)
        except:
            item.date = None


        return item

    def get_path(self):
        return self.location.encode('utf-8')

    def get_id(self):
        return self.storeID + 1000

    def get_name(self):
        return self.title

    def get_url(self):
        return self.store.urlbase + str(self.storeID+1000).encode('utf-8')

    def get_cover(self):
        return self.album.cover

    def __repr__(self):
        return '<Track %d title="%s" nr="%d" album="%s" artist="%s" path="%s">' \
               % (self.storeID, self.title.encode('ascii', 'ignore'),
                  self.track_nr,
                  self.album.title.encode('ascii', 'ignore'),
                  self.album.artist.name.encode('ascii', 'ignore'),
                  self.location.encode('ascii', 'ignore'))


class Playlist(item.Item,BackendItem):
    """ definition for a playlist

        - has a name
        - and references to tracks
        - that reference list must keep its ordering
           and items can be inserted at any place,
           moved up or down or deleted
    """

    schemaVersion = 1
    typeName = ''

    name = attributes.text(allowNone=False, indexed=True)
    # references to tracks

    get_path = None


class MediaStore(BackendStore):
    logCategory = 'media_store'
    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)
        self.info("MediaStore __init__")
        self.update_id = 0

        self.medialocation = kwargs.get('medialocation','tests/content/audio')
        self.coverlocation = kwargs.get('coverlocation',None)
        if self.coverlocation is not None and self.coverlocation[-1] != '/':
            self.coverlocation = self.coverlocation + '/'
        self.mediadb = kwargs.get('mediadb',MEDIA_DB)

        self.name = kwargs.get('name','MediaStore')

        self.containers = {}
        self.containers[ROOT_CONTAINER_ID] = \
                Container( ROOT_CONTAINER_ID,-1, self.name)

        self.wmc_mapping.update({'4': lambda : self.get_by_id(AUDIO_ALL_CONTAINER_ID),    # all tracks
                                 '7': lambda : self.get_by_id(AUDIO_ALBUM_CONTAINER_ID),    # all albums
                                 '6': lambda : self.get_by_id(AUDIO_ARTIST_CONTAINER_ID),    # all artists
                                })


        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def walk(self, path):
        #print "walk", path
        if os.path.exists(path):
            for filename in os.listdir(path):
                if os.path.isdir(os.path.join(path,filename)):
                    self.walk(os.path.join(path,filename))
                else:
                    _,ext =  os.path.splitext(filename)
                    if ext.lower() in KNOWN_AUDIO_TYPES:
                        self.filelist.append(os.path.join(path,filename))

    def get_music_files(self, musiclocation):
        if not isinstance(musiclocation, list):
            musiclocation = [musiclocation]
        self.filelist = []
        for path in musiclocation:
            self.walk(path)

        def check_for_cover_art(path):
            #print "check_for_cover_art", path
            """ let's try to find in the current directory some jpg file,
                or png if the jpg search fails, and take the first one
                that comes around
            """
            jpgs = [i for i in os.listdir(path) if os.path.splitext(i)[1] in ('.jpg', '.JPG')]
            try:
                return unicode(jpgs[0])
            except IndexError:
                pngs = [i for i in os.listdir(path) if os.path.splitext(i)[1] in ('.png', '.PNG')]
                try:
                    return unicode(pngs[0])
                except IndexError:
                    return u''

        def got_tags(tags, file):
            #print "got_tags", tags

            album=tags.get('album', '')
            artist=tags.get('artist', '')
            title=tags.get('title', '')
            track=tags.get('track', 0)

            if len(artist) == 0:
                return;
                artist = u'UNKNOWN_ARTIST'
            if len(album) == 0:
                return;
                album = u'UNKNOWN_ALBUM'
            if len(title) == 0:
                return;
                title = u'UNKNOWN_TITLE'

            #print "Tags:", file, album, artist, title, track

            artist_ds = self.db.findOrCreate(Artist, name=unicode(artist,'utf8'))
            album_ds = self.db.findOrCreate(Album,
                                            title=unicode(album,'utf8'),
                                            artist=artist_ds)
            if len(album_ds.cover) == 0:
                dirname = unicode(os.path.dirname(file),'utf-8')
                album_ds.cover = check_for_cover_art(dirname)
                if len(album_ds.cover) > 0:
                    filename = u"%s - %s" % ( album_ds.artist.name, album_ds.title)
                    filename = sanitize(filename + os.path.splitext(album_ds.cover)[1])
                    filename = os.path.join(dirname,filename)
                    shutil.move(os.path.join(dirname,album_ds.cover),filename)
                    album_ds.cover = filename
            #print album_ds.cover
            track_ds = self.db.findOrCreate(Track,
                                            title=unicode(title,'utf8'),
                                            track_nr=int(track),
                                            album=album_ds,
                                            location=unicode(file,'utf8'))

        for file in self.filelist:
            d = defer.maybeDeferred(get_tags,file)
            d.addBoth(got_tags, file)


    def show_db(self):
        for album in list(self.db.query(Album,sort=Album.title.ascending)):
            print album
            for track in list(self.db.query(Track, Track.album == album,sort=Track.track_nr.ascending)):
                print track

    def show_albums(self):
        for album in list(self.db.query(Album,sort=Album.title.ascending)):
            print album

    def show_artists(self):
        for artist in list(self.db.query(Artist,sort=Artist.name.ascending)):
            print artist

    def show_tracks_by_artist(self, artist_name):
        """
        artist = self.db.query(Artist,Artist.name == artist_name)
        artist = list(artist)[0]
        for album in list(self.db.query(Album, Album.artist == artist)):
            for track in list(self.db.query(Track, Track.album == album,sort=Track.title.ascending)):
                print track
        """
        for track in [x[2] for x in list(self.db.query((Artist,Album,Track),
                            attributes.AND(Artist.name == artist_name,
                                           Album.artist == Artist.storeID,
                                           Track.album == Album.storeID),
                            sort=(Track.title.ascending)
                            ))]:
            print track

    def show_tracks_by_title(self, title_or_part):
            for track in list(self.db.query(Track, Track.title.like(u'%',title_or_part,u'%'),sort=Track.title.ascending)):
                print track

    def show_tracks_to_filename(self, title_or_part):
        for track in list(self.db.query(Track, Track.title.like(u'%',title_or_part,u'%'),sort=Track.title.ascending)):
            print track.title, track.album.artist.name, track.track_nr
            _,ext = os.path.splitext(track.path)
            f = "%02d - %s - %s%s" % ( track.track_nr, track.album.artist.name,
                                       track.title, ext)
            f = sanitize(f)
            print f

    def get_album_covers(self):
        for album in list(self.db.query(Album, Album.cover == u'')):
            print "missing cover for:", album.artist.name, album.title
            filename = "%s - %s" % ( album.artist.name, album.title)
            filename = sanitize(filename)

            if self.coverlocation is not None:
                cover_path = os.path.join(self.coverlocation,filename +'.jpg')
                if os.path.exists(cover_path) is True:
                    print "cover found:", cover_path
                    album.cover = cover_path
                else:
                    def got_it(f,a):
                        print "cover saved:",f, a.title
                        a.cover = f

                    aws_key = '1XHSE4FQJ0RK0X3S9WR2'
                    CoverGetter(cover_path,aws_key,
                                callback=(got_it,(album)),
                                artist=album.artist.name,
                                title=album.title)

    def get_by_id(self,id):
        self.info("get_by_id %s" % id)
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0].split('.')[0]
        if isinstance(id, basestring) and id.startswith('artist_all_tracks_'):
            try:
                return self.containers[id]
            except:
                return None
        try:
            id = int(id)
        except ValueError:
            id = 1000
        try:
            item = self.containers[id]
        except:
            try:
                item = self.db.getItemByID(id-1000)
            except:
                item = None
        self.info("get_by_id found", item)
        return item

    def upnp_init(self):
        #print "MediaStore upnp_init"
        db_is_new = False
        if os.path.exists(self.mediadb) is False:
            db_is_new = True
        self.db = store.Store(self.mediadb)

        self.containers[AUDIO_ALL_CONTAINER_ID] = \
                Container( AUDIO_ALL_CONTAINER_ID,ROOT_CONTAINER_ID, 'All tracks',
                          children_callback=lambda :list(self.db.query(Track,sort=Track.title.ascending)),
                          store=self,play_container=True)
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ALL_CONTAINER_ID])
        self.containers[AUDIO_ALBUM_CONTAINER_ID] = \
                Container( AUDIO_ALBUM_CONTAINER_ID,ROOT_CONTAINER_ID, 'Albums',
                          children_callback=lambda :list(self.db.query(Album,sort=Album.title.ascending)))
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ALBUM_CONTAINER_ID])
        self.containers[AUDIO_ARTIST_CONTAINER_ID] = \
                Container( AUDIO_ARTIST_CONTAINER_ID,ROOT_CONTAINER_ID, 'Artists',
                          children_callback=lambda :list(self.db.query(Artist,sort=Artist.name.ascending)))
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ARTIST_CONTAINER_ID])

        self.db.server = self.server
        self.db.urlbase = self.urlbase
        self.db.containers = self.containers



        if db_is_new is True:
            self.get_music_files(self.medialocation)
            self.get_album_covers()

        #self.show_db()
        #self.show_artists()
        #self.show_albums()
        #self.show_tracks_by_artist(u'Meat Loaf')
        #self.show_tracks_by_artist(u'Beyonce')
        #self.show_tracks_by_title(u'Bad')
        #self.show_tracks_to_filename(u'säen')


        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                        ['internal:%s:audio/mpeg:*' % self.server.coherence.hostname,
                         'http-get:*:audio/mpeg:*',
                         'internal:%s:application/ogg:*' % self.server.coherence.hostname,
                         'http-get:*:application/ogg:*'],
                        default=True)


if __name__ == '__main__':
    from twisted.internet import reactor
    from twisted.internet import task

    def run():
        m = MediaStore(None, medialocation='/data/audio/music',
                             coverlocation='/data/audio/covers',
                             mediadb='/tmp/media.db')
        m.upnp_init()

    reactor.callWhenRunning(run)
    reactor.run()
