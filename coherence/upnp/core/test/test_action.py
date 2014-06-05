# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2014, Hartmut Goebel <h.goebel@goebel-consult.de>

"""
Test cases for L{upnp.core.action}
"""

import time

from twisted.trial import unittest
from twisted.internet import protocol
from twisted.test import proto_helpers

from coherence.upnp.core import action

class NoImplementation: pass
NoImplementation = NoImplementation()

class DummyService:
    pass

class TestArguments(unittest.TestCase):

    def test_argument(self):
        arg = action.Argument('SomeArgument', 'in-and-out', 'Brightness')
        self.assertEqual(arg.get_name(), 'SomeArgument')
        self.assertEqual(arg.get_direction(), 'in-and-out')
        self.assertEqual(arg.get_state_variable(), 'Brightness')

    def test_argument_as_dict(self):
        arg = action.Argument('SomeArgument', 'in-and-out', 'Brightness')
        self.assertEqual(arg.as_dict(),
                         {'name': 'SomeArgument',
                          'direction': 'in-and-out',
                          'related_state_variable': 'Brightness',
                          })

    def test_argument_as_tuple(self):
        arg = action.Argument('SomeArgument', 'in-and-out', 'Brightness')
        self.assertEqual(arg.as_tuples(),
                         [('Name', 'SomeArgument'),
                          ('Direction', 'in-and-out'),
                          ('Related State Variable', 'Brightness'),
                          ])
