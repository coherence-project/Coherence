# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

"""
Test cases for L{upnp.services.servers.content_directory_server}
"""

import os

from twisted.trial import unittest
from twisted.internet import reactor
from twisted.internet.defer import Deferred

from twisted.python.filepath import FilePath

from coherence import __version__
from coherence.base import Coherence
from coherence.upnp.core.uuid import UUID
from coherence.upnp.devices.control_point import DeviceQuery
from coherence.upnp.core import DIDLLite

import coherence.extern.louie as louie


class TestContentDirectoryServer(unittest.TestCase):

    def setUp(self):
        self.tmp_content = FilePath('tmp_content_coherence-%d'%os.getpid())
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
        self.coherence = Coherence({'unittest':'yes','logmode':'debug','subsystem_log':{'controlpoint':'error',
                                                                                        'action':'error',
                                                                                        'soap':'error'},'controlpoint':'yes'})
        self.uuid = UUID()
        p = self.coherence.add_plugin('FSStore',
                                      name='MediaServer-%d'%os.getpid(),
                                      content=self.tmp_content.path,
                                      uuid=str(self.uuid))

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

        def the_result(mediaserver):
            try:
                self.assertEqual(str(self.uuid), mediaserver.udn)
            except:
                d.errback()

            def got_second_answer(r,childcount):
                try:
                    self.assertEqual(int(r['TotalMatches']), childcount)
                    d.callback(None)
                except:
                    d.errback()

            def got_first_answer(r):
                try:
                    self.assertEqual(int(r['TotalMatches']), 1)
                except:
                    d.errback()

                didl = DIDLLite.DIDLElement.fromString(r['Result'])
                item = didl.getItems()[0]
                try:
                    self.assertEqual(item.childCount, 3)
                except:
                    d.errback()

                call = mediaserver.client.content_directory.browse(object_id=item.id,
                                                         process_result=False)
                call.addCallback(got_second_answer,item.childCount)
                return call

            call = mediaserver.client.content_directory.browse(process_result=False)
            call.addCallback(got_first_answer)

        self.coherence.ctrl.add_query(DeviceQuery('uuid', str(self.uuid), the_result, timeout=10, oneshot=True))
        return d

    def test_Browse_Metadata(self):
        """ tries to find the activated FSStore backend
            and requests metadata for ObjectID 0.
        """
        d = Deferred()

        def the_result(mediaserver):
            try:
                self.assertEqual(str(self.uuid), mediaserver.udn)
            except:
                d.errback()

            def got_first_answer(r):
                try:
                    self.assertEqual(int(r['TotalMatches']), 1)
                except:
                    d.errback()
                    return
                didl = DIDLLite.DIDLElement.fromString(r['Result'])
                item = didl.getItems()[0]
                try:
                    self.assertEqual(item.title, 'root')
                except:
                    d.errback()
                    return
                d.callback(None)

            call = mediaserver.client.content_directory.browse(object_id='0',browse_flag='BrowseMetadata',process_result=False)
            call.addCallback(got_first_answer)
            call.addErrback(lambda x: d.errback(None))

        self.coherence.ctrl.add_query(DeviceQuery('uuid', str(self.uuid), the_result, timeout=10, oneshot=True))
        return d

    def test_XBOX_Browse(self):
        """ tries to find the activated FSStore backend
            and browses all audio files.
        """
        d = Deferred()

        def the_result(mediaserver):
            try:
                self.assertEqual(str(self.uuid), mediaserver.udn)
            except:
                d.errback()

            def got_first_answer(r):
                """ we expect four audio files here """
                try:
                    self.assertEqual(int(r['TotalMatches']), 4)
                except:
                    d.errback()
                    return
                d.callback(None)

            def my_browse(*args,**kwargs):
                kwargs['ContainerID'] = kwargs['ObjectID']
                del kwargs['ObjectID']
                del kwargs['BrowseFlag']
                kwargs['SearchCriteria'] = ''
                return 'Search',kwargs

            #mediaserver.client.overlay_actions = {'Browse':my_browse}
            mediaserver.client.overlay_headers = {'user-agent':'Xbox/Coherence emulation'}

            call = mediaserver.client.content_directory.browse(object_id='4',process_result=False)
            call.addCallback(got_first_answer)
            call.addErrback(lambda x: d.errback(None))

        self.coherence.ctrl.add_query(DeviceQuery('uuid', str(self.uuid), the_result, timeout=10, oneshot=True))
        return d

    def test_XBOX_Browse_Metadata(self):
        """ tries to find the activated FSStore backend
            and requests metadata for ObjectID 0.
        """
        d = Deferred()

        def the_result(mediaserver):
            try:
                self.assertEqual(str(self.uuid), mediaserver.udn)
            except:
                d.errback()

            def got_first_answer(r):
                """ we expect one item here """
                try:
                    self.assertEqual(int(r['TotalMatches']), 1)
                except:
                    d.errback()
                    return
                didl = DIDLLite.DIDLElement.fromString(r['Result'])
                item = didl.getItems()[0]
                try:
                    self.assertEqual(item.title, 'root')
                except:
                    d.errback()
                    return
                d.callback(None)

            mediaserver.client.overlay_headers = {'user-agent':'Xbox/Coherence emulation'}

            call = mediaserver.client.content_directory.browse(object_id='0',browse_flag='BrowseMetadata',process_result=False)
            call.addCallback(got_first_answer)
            call.addErrback(lambda x: d.errback(None))

        self.coherence.ctrl.add_query(DeviceQuery('uuid', str(self.uuid), the_result, timeout=10, oneshot=True))
        return d

    def test_XBOX_Search(self):
        """ tries to find the activated FSStore backend
            and searches for all its audio files.
        """
        d = Deferred()

        def the_result(mediaserver):
            try:
                self.assertEqual(str(self.uuid), mediaserver.udn)
            except:
                d.errback()

            def got_first_answer(r):
                """ we expect four audio files here """
                try:
                    self.assertEqual(len(r), 4)
                except:
                    d.errback()
                d.callback(None)

            mediaserver.client.overlay_headers = {'user-agent':'Xbox/Coherence emulation'}

            call = mediaserver.client.content_directory.search(container_id='4',
                                                               criteria='')
            call.addCallback(got_first_answer)
            call.addErrback(lambda x: d.errback(None))

        self.coherence.ctrl.add_query(DeviceQuery('uuid', str(self.uuid), the_result, timeout=10, oneshot=True))
        return d
