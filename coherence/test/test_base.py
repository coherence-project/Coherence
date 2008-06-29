# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

"""
Test cases for the L{Coherence base class}
"""

import time

from twisted.trial import unittest

from twisted.internet import reactor
from twisted.internet.defer import Deferred

from coherence.base import Coherence

import coherence.extern.louie as louie


class TestCoherence(unittest.TestCase):

    def setUp(self):
        louie.reset()
        self.coherence = Coherence({'unittest':'yes','logmode':'error'})

    def tearDown(self):

        def cleaner(r):
            self.coherence.clear()
            return r

        dl = self.coherence.shutdown()
        dl.addBoth(cleaner)
        return dl

    def test_singleton(self):
        d = Deferred()

        c1 = Coherence({'unittest':'no','logmode':'error'})
        c2 = Coherence({'unittest':'no','logmode':'error'})
        c3 = Coherence({'unittest':'no','logmode':'error'})

        def shutdown(r,instance):
            return instance.shutdown()

        d.addCallback(shutdown,c1)
        d.addCallback(shutdown,c2)
        d.addCallback(shutdown,c3)

        reactor.callLater(3, d.callback, None)


        return d
