# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

"""

MediaStore

*** WORK IN PROGRESS ***

A MediaServer with a database backend,
exposes its content in All, Albums and Artists containers.
Serves cover art with the Album object, and keeps references to
the MusicBrainz DB - http://musicbrainz.org/

Should not scan for files, but gets feeded
with proper tagged ones via some import tool
or/and allow imports via the web-UI.

depends on: Axiom - http://divmod.org/trac/wiki/DivmodAxiom
            Epsilon - http://divmod.org/trac/wiki/DivmodEpsilon
            CoversByAmazon - https://coherence.beebits.net/browser/trunk/coherence/extern/covers_by_amazon.py
            libmtag - http://code.google.com/p/libmtag/
            taglib - http://developer.kde.org/~wheeler/taglib.html

"""

import os
import string
import urllib

from axiom import store, item, attributes
from epsilon.extime import Time

from coherence.extern.covers_by_amazon import CoverGetter

import libmtag

MEDIA_DB = 'media.db'

def sanitize(filename):
    badchars = ''.join(set(string.punctuation) - set('-_+.~'))
    f = unicode(filename.lower())
    f = f.replace(unicode(u'ä'),unicode('ae'))
    f = f.replace(unicode(u'ö'),unicode('oe'))
    f = f.replace(unicode(u'ü'),unicode('ue'))
    f = f.replace(unicode(u'ß'),unicode('ss'))
    f = f.replace(badchars, '_')
    return f

class Artist(item.Item):
    """ definition for an artist """

    schemaVersion = 1
    typeName = 'artist'

    name = attributes.text(allowNone=False, indexed=True)
    musicbrainz_id = attributes.text()

    def __repr__(self):
        return '<Artist name="%s" musicbrainz="%s">' \
               % (self.name.encode('ascii', 'ignore'), self.musicbrainz_id)

class Album(item.Item):
    """ definition for an album """

    schemaVersion = 1
    typeName = 'album'

    title = attributes.text(allowNone=False, indexed=True)
    musicbrainz_id = attributes.text()
    artist = attributes.reference(allowNone=False, indexed=True)
    cd_count = attributes.integer(default=1)
    cover = attributes.text(default=u'') # maybe attributes.path?

    def __repr__(self):
        return '<Album title="%s" artist="%s" #cds %d cover="%s" musicbrainz="%s">' \
               % (self.title.encode('ascii', 'ignore'),
                  self.artist.name.encode('ascii', 'ignore'),
                  self.cd_count,
                  self.cover.encode('ascii', 'ignore'),
                  self.musicbrainz_id)

class Track(item.Item):
    """ definition for a track """

    schemaVersion = 1
    typeName = 'track'

    title = attributes.text(allowNone=False, indexed=True)
    track_nr = attributes.integer(default=1,allowNone=False)
    cd_nr = attributes.integer(default=1,allowNone=False)
    album = attributes.reference(allowNone=False, indexed=True)
    path=attributes.text(allowNone=False) # maybe attributes.path?
    rating=attributes.integer(default=0,allowNone=False)
    last_played=attributes.timestamp()
    added=attributes.timestamp(default=Time(),allowNone=False)

    def __repr__(self):
        return '<Track title="%s" nr="%d" album="%s" artist="%s" path="%s">' \
               % (self.title.encode('ascii', 'ignore'),
                  self.track_nr,
                  self.album.title.encode('ascii', 'ignore'),
                  self.album.artist.name.encode('ascii', 'ignore'),
                  self.path.encode('ascii', 'ignore'))

class Playlist(item.Item):
    """ definition for a playlist """

    schemaVersion = 1
    typeName = ''

    name = attributes.text(allowNone=False, indexed=True)
    # references to tracks

class MediaStore(object):

    def __init__(self, musiclocation, coverlocation):
        print musiclocation, coverlocation
        if coverlocation[-1] != '/':
            coverlocation = coverlocation + '/'
        self.coverlocation = coverlocation

        db_is_new = False
        if os.path.exists(MEDIA_DB) is False:
            db_is_new = True
        self.db = store.Store(MEDIA_DB)

        if db_is_new is True:
            self.get_music_files(musiclocation)
        #self.show_db()
        self.show_artists()
        self.show_albums()
        #self.show_tracks_by_artist(u'Meat Loaf')
        #self.show_tracks_by_artist(u'Beyonce')
        #self.show_tracks_by_title(u'Bad')
        #self.show_tracks_to_filename(u'säen')
        self.get_album_covers()

    def walk(self, path):
        if os.path.exists(path):
            for filename in os.listdir(path):
                if os.path.isdir(os.path.join(path,filename)):
                    self.walk(os.path.join(path,filename))
                else:
                    _,ext =  os.path.splitext(filename)
                    if ext.lower()[1:] in ['mp3','ogg']:
                        self.filelist.append(os.path.join(path,filename))

    def get_music_files(self, musiclocation):
        if not isinstance(musiclocation, list):
            musiclocation = [musiclocation]
        self.filelist = []
        for path in musiclocation:
            self.walk(path)

        for file in self.filelist:
            audio_file = libmtag.File(file)
            album=audio_file.tag().get('album')
            artist=audio_file.tag().get('artist')
            title=audio_file.tag().get('title')
            track=audio_file.tag().get('track')

            if len(artist) == 0:
                continue;
                artist = u'UNKNOWN_ARTIST'
            if len(album) == 0:
                continue;
                album = u'UNKNOWN_ALBUM'
            if len(title) == 0:
                continue;
                title = u'UNKNOWN_TITLE'

            #print "Tags:", album, artist, file

            artist_ds = self.db.findOrCreate(Artist, name=unicode(artist,'utf8'))
            album_ds = self.db.findOrCreate(Album,
                                            title=unicode(album,'utf8'),
                                            artist=artist_ds)
            track_ds = self.db.findOrCreate(Track,
                                            title=unicode(title,'utf8'),
                                            track_nr=int(track),
                                            album=album_ds,
                                            path=unicode(file,'utf8'))

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
        artist = self.db.query(Artist,Artist.name == artist_name)
        artist = list(artist)[0]
        for album in list(self.db.query(Album, Album.artist == artist)):
            for track in list(self.db.query(Track, Track.album == album,sort=Track.title.ascending)):
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

            cover_path = os.path.join(self.coverlocation,filename +'.jpg')
            if os.path.exists(cover_path) is True:
                print "cover found:", cover_path
                album.cover = cover_path
            else:
                def got_it(f,a):
                    print "cover saved:",f, a.title
                    a.cover = f

                CoverGetter(cover_path,
                            callback=(got_it,(album)),
                            artist=album.artist.name,
                            title=album.title)

if __name__ == '__main__':
    from twisted.internet import reactor
    from twisted.internet import task

    reactor.callWhenRunning(MediaStore, '/data/audio/music','data/covers')
    reactor.run()
