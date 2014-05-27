# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>
# Copyright 2014 Hartmut Goebel <h.goebel@crazy-compilers.com>

"""
Test cases for L{upnp.services.servers.content_directory_server}
"""

import os

from twisted.trial import unittest
from twisted.internet.defer import Deferred

from twisted.python.filepath import FilePath

from coherence import __version__
from coherence.base import Coherence
from coherence.upnp.core.uuid import UUID
from coherence.upnp.devices.control_point import DeviceQuery
from coherence.upnp.core import DIDLLite
import coherence.extern.louie as louie

from coherence.test import wrapped

class TestContentDirectoryServer(unittest.TestCase):

    def setUp(self):
        self.tmp_content = FilePath(self.mktemp())
        f = self.tmp_content.child('content')
        audio = f.child('audio')
        f.child('images').makedirs()
        f.child('video').makedirs()
        album = audio.child('album-1')
        album.makedirs()
        album.child('track-1.mp3').touch()
        album.child('track-2.mp3').touch()
        album = audio.child('album-2')
        album.makedirs()
        album.child('track-1.ogg').touch()
        album.child('track-2.ogg').touch()
        louie.reset()
        self.coherence = Coherence(
            {'unittest': 'yes',
             'logmode': 'critical',
             'no-subsystem_log': {'controlpoint': 'error',
                               'action': 'info',
                               'soap': 'error'},
             'controlpoint': 'yes'})
        self.uuid = str(UUID())
        p = self.coherence.add_plugin('FSStore',
                                      name='MediaServer-%d' % os.getpid(),
                                      content=self.tmp_content.path,
                                      uuid=self.uuid,
                                      enable_inotify=False)

    def tearDown(self):
        self.tmp_content.remove()

        def cleaner(r):
            self.coherence.clear()
            return r

        dl = self.coherence.shutdown()
        dl.addBoth(cleaner)
        return dl


    def test_Browse(self):
        """ tries to find the activated FSStore backend
            and browses its root.
        """
        d = Deferred()

        @wrapped(d)
        def the_result(mediaserver):
            cdc = mediaserver.client.content_directory
            self.assertEqual(self.uuid, mediaserver.udn)
            call = cdc.browse(process_result=False)
            call.addCallback(got_first_answer, cdc)

        @wrapped(d)
        def got_first_answer(r, cdc):
            self.assertEqual(int(r['TotalMatches']), 1)
            didl = DIDLLite.DIDLElement.fromString(r['Result'])
            item = didl.getItems()[0]
            self.assertEqual(item.childCount, 3)
            call = cdc.browse(object_id=item.id, process_result=False)
            call.addCallback(got_second_answer, item.childCount)

        @wrapped(d)
        def got_second_answer(r, childcount):
            self.assertEqual(int(r['TotalMatches']), childcount)
            d.callback(None)

        self.coherence.ctrl.add_query(
            DeviceQuery('uuid', self.uuid,
                        the_result, timeout=10, oneshot=True))
        return d


    def test_Browse_Non_Existing_Object(self):

        d = Deferred()

        @wrapped(d)
        def the_result(mediaserver):
            cdc = mediaserver.client.content_directory
            self.assertEqual(self.uuid, mediaserver.udn)
            call = cdc.browse(object_id='9999.nothing', process_result=False)
            call.addCallback(got_first_answer)

        @wrapped(d)
        def got_first_answer(r):
            self.assertIs(r, None)
            d.callback(None)

        self.coherence.ctrl.add_query(
            DeviceQuery('uuid', self.uuid, the_result,
                        timeout=10, oneshot=True))
        return d


    def test_Browse_Metadata(self):
        """ tries to find the activated FSStore backend
            and requests metadata for ObjectID 0.
        """
        d = Deferred()

        @wrapped(d)
        def the_result(mediaserver):
            self.assertEqual(self.uuid, mediaserver.udn)
            cdc = mediaserver.client.content_directory
            call = cdc.browse(object_id='0', browse_flag='BrowseMetadata',
                              process_result=False)
            call.addCallback(got_first_answer)

        @wrapped(d)
        def got_first_answer(r):
            self.assertEqual(int(r['TotalMatches']), 1)
            didl = DIDLLite.DIDLElement.fromString(r['Result'])
            item = didl.getItems()[0]
            self.assertEqual(item.title, 'root')
            d.callback(None)

        self.coherence.ctrl.add_query(
            DeviceQuery('uuid', self.uuid,
                        the_result, timeout=10, oneshot=True))
        return d


    def test_XBOX_Browse(self):
        """ tries to find the activated FSStore backend
            and browses all audio files.
        """
        d = Deferred()

        @wrapped(d)
        def the_result(mediaserver):

            def my_browse(*args, **kwargs):
                kwargs['ContainerID'] = kwargs['ObjectID']
                del kwargs['ObjectID']
                del kwargs['BrowseFlag']
                kwargs['SearchCriteria'] = ''
                return 'Search', kwargs

            #mediaserver.client.overlay_actions = {'Browse': my_browse}
            mediaserver.client.overlay_headers = {
                'user-agent': 'Xbox/Coherence emulation'}
            cdc = mediaserver.client.content_directory
            self.assertEqual(self.uuid, mediaserver.udn)
            call = cdc.browse(object_id='4', process_result=False)
            call.addCallback(got_first_answer)

        @wrapped(d)
        def got_first_answer(r):
            """ we expect four audio files here """
            self.assertEqual(int(r['TotalMatches']), 4)
            d.callback(None)

        d = Deferred()
        self.coherence.ctrl.add_query(
            DeviceQuery('uuid', self.uuid, the_result,
                        timeout=10, oneshot=True))
        return d


    def test_XBOX_Browse_Metadata(self):
        """ tries to find the activated FSStore backend
            and requests metadata for ObjectID 0.
        """
        d = Deferred()

        @wrapped(d)
        def the_result(mediaserver):
            mediaserver.client.overlay_headers = {
                'user-agent': 'Xbox/Coherence emulation'}
            cdc = mediaserver.client.content_directory
            self.assertEqual(self.uuid, mediaserver.udn)
            call = cdc.browse(object_id='0', browse_flag='BrowseMetadata',
                              process_result=False)
            call.addCallback(got_first_answer)

        @wrapped(d)
        def got_first_answer(r):
            """ we expect one item here """
            self.assertEqual(int(r['TotalMatches']), 1)
            didl = DIDLLite.DIDLElement.fromString(r['Result'])
            item = didl.getItems()[0]
            self.assertEqual(item.title, 'root')
            d.callback(None)

        self.coherence.ctrl.add_query(
            DeviceQuery('uuid', self.uuid, the_result,
                        timeout=10, oneshot=True))
        return d


    def test_XBOX_Search(self):
        """ tries to find the activated FSStore backend
            and searches for all its audio files.
        """

        d = Deferred()

        @wrapped(d)
        def the_result(mediaserver):
            mediaserver.client.overlay_headers = {
                'user-agent': 'Xbox/Coherence emulation'}
            cdc = mediaserver.client.content_directory
            self.assertEqual(self.uuid, mediaserver.udn)
            call = cdc.search(container_id='4', criteria='')
            call.addCallback(got_first_answer)

        @wrapped(d)
        def got_first_answer(r):
            """ we expect four audio files here """
            self.assertEqual(len(r), 4)
            d.callback(None)

        self.coherence.ctrl.add_query(
            DeviceQuery('uuid', self.uuid, the_result,
                        timeout=10, oneshot=True))
        return d
