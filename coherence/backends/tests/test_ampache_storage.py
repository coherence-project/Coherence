# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2014, Hartmut Goebel <h.goebel@goebel-consult.de>

"""
Test cases for L{backends.ampache_storage}
"""

from twisted.trial import unittest

from coherence.extern import et
from coherence.backends import ampache_storage

SONG = '''
<!-- taken from https://github.com/ampache/ampache/wiki/XML-API
but the original was not valid XML, so we can not trust it
-->
<root>
  <song id="3180">
    <title>Hells Bells</title>
    <artist id="129348">AC/DC</artist>
    <album id="2910">Back in Black</album>
    <tag id="2481" count="3">Rock &amp; Roll</tag>
    <tag id="2482" count="1">Rock</tag>
    <tag id="2483" count="1">Roll</tag>
    <track>4</track>
    <time>234</time>
    <url>http://localhost/play/index.php?oid=123908...</url>
    <size>654321</size>
    <art>http://localhost/image.php?id=129348</art>
    <preciserating>3</preciserating>
    <rating>2.9</rating>
  </song>
</root>
'''

SONG_370 = '''
<!-- real-world example from Ampache 3.7.0 -->
<root>
<song id="3440">
  <title><![CDATA[Achilles Last Stand]]></title>
  <artist id="141"><![CDATA[Led Zeppelin]]></artist>
  <album id="359"><![CDATA[Presence]]></album>
  <tag id="" count="0"><![CDATA[]]></tag>
  <filename><![CDATA[/mnt/Musique/Led Zeppelin/Presence/01 - Achilles Last Stand.mp3]]></filename>
  <track>1</track>
  <time>625</time>
  <year>1976</year>
  <bitrate>248916</bitrate>
  <mode>vbr</mode>
  <mime>audio/mpeg</mime>
  <url><![CDATA[http://songserver/ampache/play/index.php?ssid=1e11a4&type=song&oid=3440&uid=4&name=Led%20Zeppelin%20-%20Achilles%20Last%20Stand.mp3]]></url>
  <size>19485595</size>
  <mbid></mbid>
  <album_mbid></album_mbid>
  <artist_mbid></artist_mbid>
  <art><![CDATA[http://songserver/ampache/image.php?id=359&object_type=album&auth=1e11a40&name=art.]]></art>
  <preciserating>0</preciserating>
  <rating>0</rating>
  <averagerating></averagerating>
</song>
</root>
'''

class DummyStore:
    proxy = False


class TestAmpache(unittest.TestCase):

    def setUp(self):
        pass

    def test_song(self):
        """Test songs with XML from Ampache 3.7.0"""
        doc = et.parse_xml(SONG)
        song = doc.find('song')
        store = DummyStore()
        track = ampache_storage.Track(store, song)
        self.assertEqual(track.get_id(), 'song.3180')
        self.assertEqual(track.parent_id, 'album.2910')
        self.assertEqual(track.duration, '0:03:54')
        self.assertEqual(track.get_url(),
                         'http://localhost/play/index.php?oid=123908...')
        self.assertEqual(track.get_name(), 'Hells Bells')
        self.assertEqual(track.title, 'Hells Bells')
        self.assertEqual(track.artist, 'AC/DC')
        self.assertEqual(track.album, 'Back in Black')
        self.assertEqual(track.genre, None)
        self.assertEqual(track.track_nr, '4')
        self.assertEqual(track.cover, 'http://localhost/image.php?id=129348')
        self.assertEqual(track.mimetype, 'audio/mpeg') # guessed
        self.assertEqual(track.size, 654321)
        self.assertIs(track.get_path(), None)
        self.assertEqual(track.get_children(), [])
        self.assertEqual(track.get_child_count(), 0)

    def test_song_370(self):
        """Test songs with XML from Ampache 3.7.0"""
        doc = et.parse_xml(SONG_370)
        song = doc.find('song')
        store = DummyStore()
        track = ampache_storage.Track(store, song)
        self.assertEqual(track.get_id(), 'song.3440')
        self.assertEqual(track.parent_id, 'album.359')
        self.assertEqual(track.duration, '0:10:25')
        self.assertEqual(track.get_url(),
                         'http://songserver/ampache/play/index.php?ssid=1e11a4&type=song&oid=3440&uid=4&name=Led%20Zeppelin%20-%20Achilles%20Last%20Stand.mp3')
        self.assertEqual(track.get_name(), 'Achilles Last Stand')
        self.assertEqual(track.title, 'Achilles Last Stand')
        self.assertEqual(track.artist, 'Led Zeppelin')
        self.assertEqual(track.album, 'Presence')
        self.assertEqual(track.genre, None)
        self.assertEqual(track.track_nr, '1')
        self.assertEqual(track.cover, 'http://songserver/ampache/image.php?id=359&object_type=album&auth=1e11a40&name=art.')
        self.assertEqual(track.mimetype, 'audio/mpeg')
        self.assertEqual(track.size, 19485595)
        self.assertIs(track.get_path(), None)
        self.assertEqual(track.get_children(), [])
        self.assertEqual(track.get_child_count(), 0)
