# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2014 Hartmut Goebel <h.goebel@goebel-consult.de>

"""
Test cases for L{upnp.backends.fs_storage}
"""

from twisted.trial import unittest
from twisted.python.filepath import FilePath

from coherence.backends import fs_storage

import coherence.log
coherence.log.init()

class TestFSStorageAssumptions(unittest.TestCase):

    def setUp(self):
        self.tmp_content = FilePath(self.mktemp())
        self.tmp_content.makedirs()
        self.storage = fs_storage.FSStore(None, name='my media',
                                          content=self.tmp_content.path,
                                          urlbase='http://fsstore-host/xyz',
                                          enable_inotify=False)

    def tearDown(self):
        self.tmp_content.remove()
        pass

    def test_ContentLen(self):
        self.assertEqual(len(self.storage.content), 1)
        self.assertEqual(len(self.storage.store), 1)
        self.assertEqual(self.storage.len(), 1)

    def test_Root(self):
        root = self.storage.get_by_id('1000')
        self.assertIs(root.parent, None)
        self.assertRaises(AttributeError, getattr, root, 'path')
        # A single path passed, so content is a "directory" named by
        # it's basename
        self.assertEqual(root.mimetype, 'directory')
        self.assertEqual(root.get_name(), 'temp')


class TestFSStorageWithMultiContentAssumptions(unittest.TestCase):

    def setUp(self):
        f = self.tmp_content = FilePath(self.mktemp())
        audio = f.child('audio') ; audio.makedirs()
        video = f.child('video') ; video.makedirs()
        self.storage = fs_storage.FSStore(None, name='my media',
                                          content=[audio.path, video.path],
                                          urlbase='http://fsstore-host/xyz',
                                          enable_inotify=False)

    def tearDown(self):
        self.tmp_content.remove()
        pass

    def test_ContentLen(self):
        self.assertEqual(len(self.storage.content), 2)
        self.assertEqual(len(self.storage.store), 3)
        self.assertEqual(self.storage.len(), 3)

    def test_Root(self):
        root = self.storage.get_by_id('1000')
        self.assertIs(root.parent, None)
        self.assertRaises(AttributeError, getattr, root, 'path')
        # A several paths passed, so content is a "root" named "media"
        self.assertEqual(root.mimetype, 'root')
        self.assertEqual(root.get_name(), 'media')

# todo: test get_xml()
'''
self.storage.get_by_id("1000").get_xml()
<container xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" childCount="2" id="1000" parentID="-1" restricted="0"><dc:title>media</dc:title><upnp:class>object.container</upnp:class><dc:date>2003-07-23T01:18:00+02:00</dc:date></container>
'''

class TestFSStorage(unittest.TestCase):

    def setUp(self):
        self.tmp_content = FilePath(self.mktemp())
        f = self.tmp_content.child('my content')
        audio = f.child('audio') ; audio.makedirs()
        video = f.child('video') ; video.makedirs()
        images = f.child('images') ; images.makedirs()
        album = audio.child('album-1')
        album.makedirs()
        album.child('track-1.mp3').touch()
        album.child('track-2.mp3').touch()
        album = audio.child('album-2')
        album.makedirs()
        album.child('track-1.ogg').touch()
        album.child('track-2.ogg').touch()
        self.storage = fs_storage.FSStore(None, name='my media',
                                          content=self.tmp_content.path,
                                          urlbase='http://fsstore-host/xyz',
                                          enable_inotify=False)

    def tearDown(self):
        self.tmp_content.remove()

    def test_ContentLen(self):
        self.assertEqual(len(self.storage.content), 1)
        # 11 items, since we have "<tempdir>/my content/..."
        self.assertEqual(len(self.storage.store), 11)
        self.assertEqual(self.storage.len(), 11)

    def test_Content(self):
        root = self.storage.get_by_id('1000')
        content = self.storage.get_by_id('1001')
        self.assertEqual(content.mimetype, 'directory')
        self.assertEqual(content.get_name(), 'my content')
        self.assertIs(root.get_children(0, 0)[0], content)
        self.assertEqual(self.storage.get_by_id('1002').get_name(),
                         'audio')
        self.assertEqual(self.storage.get_by_id('1005').get_name(),
                         'album-1')
