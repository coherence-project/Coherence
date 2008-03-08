# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

import time

try:
    import hashlib
    def md5(s):
        m =hashlib.md5()
        m.update(s)
        return m.hexdigest()
except ImportError:
    import md5 as oldmd5
    def md5(s):
        m=oldmd5.new()
        m.update(s)
        return m.hexdigest()

from twisted.internet import reactor
from twisted.python import failure

from coherence.upnp.core import DIDLLite
from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core import utils

import louie

from coherence.backend import BackendItem, BackendStore


ROOT_CONTAINER_ID = 0
AUDIO_CONTAINER = 100
AUDIO_ALL_CONTAINER_ID = 101
AUDIO_ARTIST_CONTAINER_ID = 102
AUDIO_ALBUM_CONTAINER_ID = 103

CONTAINER_COUNT = 10000

TRACK_COUNT = 1000000

class Container(BackendItem):

    logCategory = 'ampache_store'

    def __init__(self, id, parent_id, name, children_callback=None):
        self.id = id
        self.parent_id = parent_id
        self.name = name
        self.mimetype = 'directory'
        self.item = DIDLLite.Container(id, parent_id,self.name)
        self.update_id = 0
        if children_callback != None:
            self.children = children_callback
        else:
            self.children = []
        self.item.childCount = None #self.get_child_count()

    def add_child(self, child):
        self.children.append(child)
        if self.item.childCount != None:
            self.item.childCount += 1

    def get_children(self,start=0,request_count=0):
        if callable(self.children):
            children = self.children(start,request_count)
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
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id


class Album(BackendItem):

    logCategory = 'ampache_store'

    def __init__(self, element):
        self.id = int(element.get('id'))
        self.title = element.get('name')
        self.artist = element.get('artist')
        self.tracks = int(element.get('tracks'))
        try:
            self.cover = element.find('art').text
        except:
            self.cover = None

    def get_children(self,start=0,request_count=0):
        children = []

        if request_count == 0:
            return children[start:]
        else:
            return children[start:request_count]

    def get_child_count(self):
        return len(self.get_children())

    def get_item(self, parent_id = AUDIO_ALBUM_CONTAINER_ID):
        item = DIDLLite.MusicAlbum(self.id, parent_id, self.title)
        item.artist = self.artist
        item.albumArtURI = self.cover
        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.title

    def get_cover(self):
        return self.cover


class Artist(BackendItem):

    logCategory = 'ampache_store'

    def __init__(self, element):
        self.id = int(element.get('id'))
        self.name = element.get('name')

    def get_children(self,start=0,request_count=0):
        children = []

        if request_count == 0:
            return children[start:]
        else:
            return children[start:request_count]

    def get_child_count(self):
        return len(self.get_children())

    def get_item(self, parent_id = AUDIO_ARTIST_CONTAINER_ID):
        item = DIDLLite.MusicArtist(self.id, parent_id, self.name)
        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name


class Track(BackendItem):

    logCategory = 'ampache_store'

    def __init__(self, element):
        self.id = int(element.get('id'))
        self.parent_id = int(element.find('album').get('id'))

        self.path = element.find('url').text

        seconds = int(element.find('time').text)
        hours = seconds / 3600
        seconds = seconds - hours * 3600
        minutes = seconds / 60
        seconds = seconds - minutes * 60
        self.duration = ("%02d:%02d:%02d") % (hours, minutes, seconds)

        self.title = element.find('title').text
        self.artist = element.find('artist').text
        self.album = element.find('album').text
        self.genre = element.find('genre').text
        self.track_nr = element.find('track').text

        try:
            self.cover = element.find('art').text
        except:
            self.cover = None
        try:
            self.mimetype = element.find('mimetype').text
        except:
            self.mimetype = "audio/mpeg"
        try:
            self.size = int(element.find('size').text)
        except:
            self.size = 0

    def get_children(self, start=0, request_count=0):
        return []

    def get_child_count(self):
        return 0

    def get_item(self, parent_id=None):

        self.info("Track get_item %r @ %r" %(self.id,self.parent_id))

        # create item
        item = DIDLLite.MusicTrack(self.id + TRACK_COUNT,self.parent_id)
        item.album = self.album

        item.artist = self.artist
        #item.date =
        item.genre = self.genre
        item.originalTrackNumber = self.track_nr
        item.title = self.title

        item.albumArtURI = self.cover

        # add http resource
        res = DIDLLite.Resource(self.get_url(), 'http-get:*:%s:*' % self.mimetype)
        if self.size > 0:
            res.size = size
        if self.duration > 0:
            res.duration = str(duration)
        if self.bitrate > 0:
            res.bitrate = str(bitrate)
        item.res.append(res)

        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.title

    def get_url(self):
        return self.url

    def get_path(self):
        return None


class AmpacheStore(BackendStore):

    """ this is a backend to the Ampache Media DB

    """

    implements = ['MediaServer']
    logCategory = 'ampache_store'

    def __init__(self, server, **kwargs):
        self.config = kwargs
        self.name = kwargs.get('name','Ampache')
        self.key = kwargs.get('key','')
        self.user = kwargs.get('user',None)
        self.url = kwargs.get('url','http://localhost/ampache/server/xml.server.php')

        self.server = server
        self.update_id = 0
        self.token = None

        self.get_token()

    def __repr__(self):
        return "Ampache storage"


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
        try:
            id = int(id)
        except ValueError:
            id = 1000
        try:
            item = self.containers[id]
        except:
            try:
                item = None
            except:
                item = None
        return item

    def got_auth_response( self, response):
        response = utils.parse_xml(response, encoding='utf-8')
        try:
            self.warning('error on token request %r', response.find('error').text)
            raise ValueError, response.find('error').text
        except AttributeError:
            try:
                self.token = response.find('auth').text
                self.info('ampache returned auth token %r', self.token)

                self.containers = {}
                self.containers[ROOT_CONTAINER_ID] = \
                            Container( ROOT_CONTAINER_ID,-1, self.name)

                self.wmc_mapping.update({'4': lambda : self.get_by_id(AUDIO_ALL_CONTAINER_ID),    # all tracks
                                         '7': lambda : self.get_by_id(AUDIO_ALBUM_CONTAINER_ID),    # all albums
                                         '6': lambda : self.get_by_id(AUDIO_ARTIST_CONTAINER_ID),    # all artists
                                        })

                louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)
            except AttributeError:
                raise ValueError, 'no authorization token returned'

    def got_auth_error(self, e):
        self.warning('error calling ampache %r', e)
        louie.send('Coherence.UPnP.Backend.init_failed', None, backend=self, msg=e)

    def get_token( self, media_type='audio'):
        """ ask Ampache for the authorization token """
        timestamp = int(time.time())
        passphrase = md5('%d%s' % (timestamp, self.key))
        request = ''.join((self.url, '?action=handshake&auth=%s&timestamp=%d' % (passphrase, timestamp)))
        if self.user != None:
            request = ''.join((request, '&user=%s' % self.user))
        d = utils.getPage(request)
        d.addCallback(self.got_auth_response)
        d.addErrback(self.got_auth_error)

    def got_error(self, e):
        self.warning('error calling ampache %r', e)

    def got_response(self, response, query_item):
        response = utils.parse_xml(response, encoding='utf-8')
        try:
            self.warning('error on token request %r', response.find('error').text)
            raise ValueError, response.find('error').text
        except AttributeError:
            for q in response.findall(query_item):
                if query_item == 'song':
                    print q.find('title').text, q.find('artist').text
                    item = Track(q)
                    items.append(item)
        print "got_response", items
        return items

    def ampache_query(self, item, start=0, request_count=0):
        request = ''.join((self.url, '?action=%ss&auth=%s&offset=%d' % (item,self.token, start)))
        if request_count > 0:
            request = ''.join((request, '&limit=%d' % request_count))
        d = utils.getPage(request)
        d.addCallback(self.got_response, item)
        d.addErrback(self.got_error)
        return d

    def ampache_query_songs(self, start=0, request_count=0):
        return self.ampache_query('song', start, request_count)

    def ampache_query_albums(self, start=0, request_count=0):
        return self.ampache_query('album', start, request_count)

    def ampache_query_artists(self, start=0, request_count=0):
        return self.ampache_query('artist', start, request_count)

    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                            ['http-get:*:audio/mpeg:*',
                             'http-get:*:application/ogg:*',])
        self.containers[AUDIO_ALL_CONTAINER_ID] = \
                Container( AUDIO_ALL_CONTAINER_ID,ROOT_CONTAINER_ID, 'All tracks',
                          children_callback=self.ampache_query_songs)
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ALL_CONTAINER_ID])
        self.containers[AUDIO_ALBUM_CONTAINER_ID] = \
                Container( AUDIO_ALBUM_CONTAINER_ID,ROOT_CONTAINER_ID, 'Albums',
                          children_callback=self.ampache_query_albums)
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ALBUM_CONTAINER_ID])
        self.containers[AUDIO_ARTIST_CONTAINER_ID] = \
                Container( AUDIO_ARTIST_CONTAINER_ID,ROOT_CONTAINER_ID, 'Artists',
                          children_callback=self.ampache_query_artists)
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ARTIST_CONTAINER_ID])


if __name__ == '__main__':

    from coherence.base import Coherence

    def main():
        def got_result(result):
            print result

        def call_browse(ObjectID=0,StartingIndex=0,RequestedCount=0):
            r = f.content_directory_server.Browse(BrowseFlag='BrowseDirectChildren',
                            RequestedCount=RequestedCount,
                            StartingIndex=StartingIndex,
                            ObjectID=ObjectID,
                            SortCriteria='*',
                            Filter='')
            print "call_browse", r
            r.addCallback(got_result)
            r.addErrback(got_result)

        #f = AmpacheStore(None,
        #                      url='http://localhost/ampache/server/xml.server.php',
        #                      key='testkey',
        #                      user=None)
        #reactor.callLater(3, f.ampache_query_songs, 65, 1)

        config = {}
        config['logmode'] = 'warning'
        c = Coherence(config)
        f = c.add_plugin('AmpacheStore',
                        url='http://localhost/ampache/server/xml.server.php',
                        key='testkey',
                        user=None)
        reactor.callLater(3, call_browse, AUDIO_ALL_CONTAINER_ID, 0, 10)

    reactor.callWhenRunning(main)
    reactor.run()
