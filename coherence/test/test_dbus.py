# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

"""
Test cases for L{dbus_service}
"""

import os

from twisted.trial import unittest
from twisted.internet import reactor
from twisted.internet.defer import Deferred

from coherence import __version__
from coherence.base import Coherence
from coherence.upnp.core import uuid
import coherence.extern.louie as louie

from coherence.test import wrapped

try:
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)
    import dbus.service
except ImportError:
    dbus = None

BUS_NAME = 'org.Coherence'
OBJECT_PATH = '/org/Coherence'


class TestDBUS(unittest.TestCase):

    if not dbus:
        skip = "Python dbus-bindings not available."
    elif reactor.__class__.__name__ != 'Glib2Reactor':
        skip = ("This test needs a Glib2Reactor, please start trial "
                "with the '-r glib2' option.")

    def setUp(self):
        louie.reset()
        self.coherence = Coherence({'unittest': 'yes', 'logmode': 'error', 'use_dbus': 'yes', 'controlpoint': 'yes'})
        self.bus = dbus.SessionBus()
        self.coherence_service = self.bus.get_object(BUS_NAME, OBJECT_PATH)
        self.uuid = str(uuid.UUID())

    def tearDown(self):

        def cleaner(r):
            self.coherence.clear()
            return r

        dl = self.coherence.shutdown()
        dl.addBoth(cleaner)
        return dl

    def test_dbus_version(self):
        """ tests the version number request via dbus
        """

        d = Deferred()

        @wrapped(d)
        def handle_version_reply(version):
            self.assertEqual(version, __version__)
            d.callback(version)

        self.coherence_service.version(dbus_interface=BUS_NAME,
                                       reply_handler=handle_version_reply,
                                       error_handler=d.errback)
        return d

    def test_dbus_plugin_add_and_remove(self):
        """ tests creation and removal of a backend via dbus
        """

        d = Deferred()

        @wrapped(d)
        def add_it(uuid):
            self.coherence_service.add_plugin(
                'SimpleLight', {'name': 'dbus-test-light-%d' % os.getpid(),
                                'uuid': uuid,
                                },
                dbus_interface=BUS_NAME,
                reply_handler=handle_add_plugin_reply,
                error_handler=d.errback)

        @wrapped(d)
        def handle_add_plugin_reply(uuid):
            self.assertEqual(self.uuid, uuid)
            reactor.callLater(2, remove_it, uuid)

        @wrapped(d)
        def remove_it(uuid):
            self.coherence_service.remove_plugin(
                uuid,
                dbus_interface=BUS_NAME,
                reply_handler=handle_remove_plugin_reply,
                error_handler=d.errback)

        @wrapped(d)
        def handle_remove_plugin_reply(uuid):
            self.assertEqual(self.uuid, uuid)
            d.callback(uuid)

        add_it(self.uuid)
        return d
