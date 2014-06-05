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


class TestAction(unittest.TestCase):

    def __build_action_arguments(self):
        args = [
            action.Argument('InstanceID', 'in', 'A_ARG_TYPE_InstanceID'),
            action.Argument('CurrentBrightness', 'out', 'Brightness')
            ]
        return args

    def test_action(self):
        svc = DummyService()
        arguments = self.__build_action_arguments()
        act = action.Action(svc, 'SomeAction', NoImplementation,
                            arguments)
        self.assertEqual(act.get_name(), 'SomeAction')
        self.assertIs(act.get_service(), svc)
        self.assertIs(act.get_implementation(), NoImplementation)
        self.assertEqual(act.get_arguments_list(), arguments)
        self.assertEqual(act.get_in_arguments(), [arguments[0]])
        self.assertEqual(act.get_out_arguments(), [arguments[1]])
        self.assertIs(act.get_in_arguments()[0], arguments[0])
        self.assertIs(act.get_out_arguments()[0], arguments[1])
        self.assertIs(act.get_callback(), None)

    def test_action_set_callback(self):
        def _this_callback(): pass
        act = action.Action(None, 'SomeAction', NoImplementation, [])
        self.assertIs(act.get_callback(), None)
        act.set_callback(_this_callback)
        self.assertIs(act.get_callback(), _this_callback)
