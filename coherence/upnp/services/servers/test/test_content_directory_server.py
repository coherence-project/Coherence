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

import louie


class TestContentDirectoryServer(unittest.TestCase):

    def setUp(self):
        self.tmp_content = FilePath('tmp_content_coherence-%d'%os.getpid())
        f = self.tmp_content.child('content')
        f.child('audio').makedirs()
        f.child('images').makedirs()
        f.child('video').makedirs()
        louie.reset()
        self.coherence = Coherence({'logmode':'error','subsystem_log':{'controlpoint':'error'},'controlpoint':'yes'})
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
            self.assertEqual(str(self.uuid), mediaserver.udn)

            def got_second_answer(r,childcount):
                self.assertEqual(len(r), childcount)
                d.callback(None)

            def got_first_answer(r):
                self.assertEqual(len(r), 1)
                item = r[0]
                self.assertEqual(item.childCount, 3)
                call = mediaserver.client.content_directory.browse(object_id=item.id,
                                                         process_result=False)
                call.addCallback(got_second_answer,item.childCount)
                return call

            call = mediaserver.client.content_directory.browse(process_result=False)
            call.addCallback(got_first_answer)

        self.coherence.ctrl.add_query(DeviceQuery('uuid', str(self.uuid), the_result, timeout=10, oneshot=True))
        return d