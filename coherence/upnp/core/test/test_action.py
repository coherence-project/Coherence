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
from twisted.internet.defer import Deferred, DeferredList
from twisted.test import proto_helpers

from coherence.upnp.core import action

from coherence.test import wrapped

class NoImplementation: pass
NoImplementation = NoImplementation()

class DummyClient:
    def __init__(self, result):
        self.__result = result

    def callRemote(self, action_name, arguments):
        self._called_action_name = action_name
        self._passed_arguments = arguments
        d = Deferred()
        d.callback(self.__result)
        return d


class DummyStateVariable:
    def __init__(self, name):
        self.name = name
        self.value = NoImplementation

    def update(self, value):
        self.value = value


class DummyDevice:
    client = None


class DummyService:
    def __init__(self):
        self.device = DummyDevice()

    def _set_client(self, client):
        self.__client = client

    def _get_client(self, name):
        return self.__client

class DummyServiceWithStateVariables(DummyService):
    def __init__(self, *argnames):
        DummyService.__init__(self)
        self.service_type = 'urn:some:service'
        self.control_url = 'http://localhost/control'
        self.__variables = {}
        for name in argnames:
            self.__variables[name] = DummyStateVariable(name)

    def get_state_variable(self, name, instance=0):
        return self.__variables.get(name)


class TestArguments(unittest.TestCase):

    def test_argument(self):
        """ Test initialization of Argument() instance """
        arg = action.Argument('SomeArgument', 'in-and-out', 'Brightness')
        self.assertEqual(arg.get_name(), 'SomeArgument')
        self.assertEqual(arg.get_direction(), 'in-and-out')
        self.assertEqual(arg.get_state_variable(), 'Brightness')

    def test_argument_as_dict(self):
        """ Test Argument.as_dict() """
        arg = action.Argument('SomeArgument', 'in-and-out', 'Brightness')
        self.assertEqual(arg.as_dict(),
                         {'name': 'SomeArgument',
                          'direction': 'in-and-out',
                          'related_state_variable': 'Brightness',
                          })

    def test_argument_as_tuple(self):
        """ Test Argument.as_tuples() """
        arg = action.Argument('SomeArgument', 'in-and-out', 'Brightness')
        self.assertEqual(arg.as_tuples(),
                         [('Name', 'SomeArgument'),
                          ('Direction', 'in-and-out'),
                          ('Related State Variable', 'Brightness'),
                          ])


def _build_action_arguments():
    args = [
        action.Argument('InstanceID', 'in', 'A_ARG_TYPE_InstanceID'),
        action.Argument('CurrentBrightness', 'out', 'Brightness'),
        action.Argument('Color', 'in', 'Color'),
        ]
    return args


class TestAction(unittest.TestCase):

    def setUp(self):
        self.service = DummyService()
        self.arguments = _build_action_arguments()
        self.action= action.Action(self.service, 'SomeTestAction',
                                   NoImplementation, self.arguments)

    def test_action(self):
        """ Test initialization of Action() instance """
        act = self.action
        arguments = self.arguments
        self.assertEqual(act.get_name(), 'SomeTestAction')
        self.assertIs(act.get_service(), self.service)
        self.assertIs(act.get_implementation(), NoImplementation)
        self.assertEqual(act.get_arguments_list(), arguments)
        self.assertEqual(act.get_in_arguments(), [arguments[0], arguments[2]])
        self.assertEqual(act.get_out_arguments(), [arguments[1]])
        self.assertIs(act.get_in_arguments()[0], arguments[0])
        self.assertIs(act.get_in_arguments()[1], arguments[2])
        self.assertIs(act.get_out_arguments()[0], arguments[1])
        self.assertIs(act.get_callback(), None)

    def test_action_as_dict(self):
        """ Test Action.as_dict() """
        self.assertEqual(self.action.as_dict(),
                         {'name': 'SomeTestAction',
                          'arguments': [
            {'name': 'InstanceID',
             'direction': 'in',
             'related_state_variable': 'A_ARG_TYPE_InstanceID',
             },
            {'name': 'CurrentBrightness',
             'direction': 'out',
             'related_state_variable': 'Brightness',
             },
            {'name': 'Color',
             'direction': 'in',
             'related_state_variable': 'Color',
             },
            ]})

    def test_action_as_tuple(self):
        """ Test Action.as_tuples() """
        self.assertEqual(self.action.as_tuples(),
                         [("Name", 'SomeTestAction'),
                          ("Number of 'in' arguments", 2),
                          ("Number of 'out' arguments", 1),
                          ])

    def test_action_set_callback(self):
        """ Test Action.set_callback() """
        def _this_callback(): pass
        act = self.action
        self.assertIs(act.get_callback(), None)
        act.set_callback(_this_callback)
        self.assertIs(act.get_callback(), _this_callback)

    def test_call_action_without_arguments(self):
        # :fixme: Action.call() does not raise an error if no
        # `in_argument` is passed. IMHO this should be treated as an
        # programming error and should be fixed.
        #self.assertRaises(..., act.call)
        self.assertIs(self.action.call(), None)

    def test_call_action_with_missing_arguments(self):
        # :fixme: Action.call() does not raise an error if an
        # `in_argument` is not passed. IMHO this should be treated as
        # an programming error and should be fixed.
        #self.assertRaises(..., act.call, InstanceID=22)
        self.assertIs(self.action.call(InstanceID=22), None)

    def test_call_action_with_wrong_argument(self):
        # :fixme: Action.call() does not raise an error if a invalid
        # `in_argument` is passed. IMHO this should be treated as an
        # programming error and should be fixed.
        #self.assertRaises(..., act.call, ThisIsNoValidArgName=123)
        self.assertIs(self.action.call(ThisIsNoValidArgName=123), None)


class TestAction2(unittest.TestCase):

    def setUp(self):
        self.arguments = _build_action_arguments()
        self.service = DummyServiceWithStateVariables('Brightness')
        self.action= action.Action(self.service, 'SomeTestAction',
                                   NoImplementation, self.arguments)

    def test_setup(self):
        """ Test is setup of this test-case works as expected. """
        self.assertIsInstance(self.service, DummyServiceWithStateVariables)
        for name in ('Brightness', ):
            var = self.service.get_state_variable(name)
            self.assertIsInstance(var, DummyStateVariable)
            self.assertIs(var.value, NoImplementation)

    def test_call_action(self):

        def check_result(*args, **kw):
            self.assertEqual(
                self.service.get_state_variable('Brightness').value,
                12)
            self.assertEqual(client._called_action_name, 'SomeTestAction')
            self.assertEqual(client._passed_arguments,
                             {'InstanceID': 23, 'Color': 'red'})

        self.assertIs(self.service.get_state_variable('Brightness').value,
                      NoImplementation)
        client = DummyClient({'CurrentBrightness': 12} )
        self.service._set_client(client)
        result = self.action.call(InstanceID=23, Color='red')
        result.addCallback(check_result)
        return result

    def test_call_action_extraneous_result_values(self):
        """
        Check if extraneous result values are silently ignored.
        """
        # NB: This behaviour is new in coherence 0.7. Former versions
        # would raise an IndexError.

        def check_result(*args, **kw):
            self.assertEqual(
                self.service.get_state_variable('Brightness').value,
                12)

        client = DummyClient({'CurrentBrightness': 12, 'XtraValue': 456})
        self.service._set_client(client)
        result = self.action.call(InstanceID=23, Color='red')
        result.addCallback(check_result)
        return result

    def test_call_action_too_less_result_values(self):
        """
        Check if missing result values are silently ignored.
        """
        def check_result(*args, **kw):
            self.assertEqual(
                self.service.get_state_variable('Brightness').value,
                NoImplementation)

        self.assertIs(self.service.get_state_variable('Brightness').value,
                      NoImplementation)
        client = DummyClient({})
        self.service._set_client(client)
        result = self.action.call(InstanceID=23, Color='red')
        result.addCallback(check_result)
        return result
