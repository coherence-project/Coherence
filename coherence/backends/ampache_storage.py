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

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement
from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core import utils

import louie

from coherence.backend import BackendItem, BackendStore


ROOT_CONTAINER_ID = 0
AUDIO_CONTAINER = 100
AUDIO_ALL_CONTAINER_ID = 101
AUDIO_ARTIST_CONTAINER_ID = 102
AUDIO_ALBUM_CONTAINER_ID = 103


class Container(BackendItem):

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
        self.item.childCount = self.get_child_count()

    def add_child(self, child):
        self.children.append(child)
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
        try:
            return self.store[int(id)]
        except:
            return None

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

    def get_token( self, media_type='audio'):
        """ ask Ampache for the authorization token """
        timestamp = int(time.time())
        passphrase = md5('%d%s' % (timestamp, self.key))
        request = ''.join((self.url, '?action=handshake&auth=%s&timestamp=%d' % (passphrase, timestamp)))
        if self.user != None:
            request = ''.join((request, '&user=%s' % self.user))
        d = utils.getPage(request)
        d.addCallback(self.got_auth_response)
        d.addErrback(self.got_error)

    def got_error(self, e):
        self.warning('error calling ampache %r', e)
        louie.send('Coherence.UPnP.Backend.init_failed', None, backend=self, msg=e)

    def got_response(self, response):
        print response

    def ampache_query_songs(self, start=0, request_count=0):
        request = ''.join((self.url, '?action=songs&auth=%s&offset=%d' % (self.token, start)))
        if request_count > 0:
            request = ''.join((request, '&limit=%d' % request_count))
        d = utils.getPage(request)
        d.addCallback(self.got_response)
        d.addErrback(self.got_error)


    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                            ['http-get:*:audio/mpeg:*'])
        self.containers[AUDIO_ALL_CONTAINER_ID] = \
                Container( AUDIO_ALL_CONTAINER_ID,ROOT_CONTAINER_ID, 'All tracks',
                          children_callback=lambda :self.ampache_query_songs())
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ALL_CONTAINER_ID])
        self.containers[AUDIO_ALBUM_CONTAINER_ID] = \
                Container( AUDIO_ALBUM_CONTAINER_ID,ROOT_CONTAINER_ID, 'Albums',
                          children_callback=lambda :self.ampache_query(Album,sort=Album.title.ascending))
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ALBUM_CONTAINER_ID])
        self.containers[AUDIO_ARTIST_CONTAINER_ID] = \
                Container( AUDIO_ARTIST_CONTAINER_ID,ROOT_CONTAINER_ID, 'Artists',
                          children_callback=lambda :self.ampache_query(Artist,sort=Artist.name.ascending))
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[AUDIO_ARTIST_CONTAINER_ID])



if __name__ == '__main__':

    def main():
        def got_result(result):
            print result

        f = AmpacheStore(None,
                              url='http://localhost/ampache/server/xml.server.php',
                              key='testkey',
                              user=None)
        reactor.callLater(3,f.ampache_query_songs, 0, 100)

    from coherence import log
    log.init(None, '*:5')

    reactor.callWhenRunning(main)
    reactor.run()
