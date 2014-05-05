# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2013, Hartmut Goebel <h.goebel@crazy-compilers.com>

"""
Test cases for upnp.core.uuid
"""

from twisted.trial import unittest

from coherence.upnp.core import uuid


class TestUUID(unittest.TestCase):

    def setUp(self):
        self.uuid = uuid.UUID()

    def test_UUID_str(self):
        self.assertEqual(str(self.uuid)[:5], 'uuid:')

    def test_UUID_repr(self):
        self.assertEqual(repr(self.uuid)[:5], 'uuid:')
