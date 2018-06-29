# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2014, Hartmut Goebel <h.goebel@goebel-consult.de>

"""
Test cases for L{upnp.core.service.ServiceServer}
"""

import time
try:
    import unittest.mock as mock
except ImportError:
    import mock

from twisted.trial import unittest
from twisted.internet.defer import Deferred
from twisted.internet import task

from coherence.upnp.core import service, device
from coherence.extern.et import ET


# :todo: put this into a central module
def fakeXMLparse(content):
    et_parse = ET.parse
    def parse(filename):
        """
        Used for mocking coherence.upnp.core.utils.getPage, behaves as if
        the file contains `content`.
        """
        return ET.fromstring(content)
    return parse


class ServiceServer4Test(service.ServiceServer):
    # All sub-classes of ServiceServer are inheriting
    # twisted.web.resource.Resource, too. The later contributes
    # 'putChild()' which is used in service.ServiceServer.__init__()
    # even if ServiceServer itself does not inherit Resource.
    # :fixme: ServiceServer should inherit twisted.web.resource.Resource.
    # As long as it does not, we need this class :-(
    from twisted.web import resource
    putChild = mock.create_autospec(resource.Resource.putChild)


class DescriptionNotFound(unittest.TestCase):

    def test_init(self):
        # The service "UnknownService1" is, well, unknown and it's
        # description XML for can not be found. As ServiceServer is
        # used for services Coherence is implementing, the XML file
        # ought to exist.
        self.assertRaises(IOError,
                          service.ServiceServer, 'UnknownService', 1, None)


class EmptyDescription(unittest.TestCase):

    def test_init(self):
        # In this case, the description XML is empty. As ServiceServer
        # is used for services Coherence is implementing, the XML file
        # ought to be valid.
        with mock.patch(ET.__name__ + '.parse', fakeXMLparse('')):
            self.assertRaises(ET.ParseError,
                              service.ServiceServer, 'UnknownService', 1, None)


class InvalidDescriptionXML(unittest.TestCase):

    def test_init(self):
        # In thie case, the description XML is empty. As ServiceServer
        # is used for services Coherence is implementing, the XML file
        # ought to be valid.
        with mock.patch(ET.__name__ + '.parse', fakeXMLparse('<x>')):
            self.assertRaises(ET.ParseError,
                              service.ServiceServer, 'UnknownService', 1, None)



class ValidButEmptyDescriptionXML(unittest.TestCase):

    def setUp(self):
        with mock.patch(ET.__name__ + '.parse', fakeXMLparse('<x></x>')):
            self.setUp_main()

    def setUp_main(self):
        # :todo: use service.ServiceServer, see comment at
        # ServiceServer4Test
        self.service_server = ServiceServer4Test(
            'UnknownService', version=1, backend=None)

    def tearDown(self):
        try:
            self.service_server.check_subscribers_loop.stop()
        except AttributeError:
            pass
        try:
            self.service_server.service_service.check_moderated_loop.stop()
        except AttributeError:
            pass

    def test_init(self):
        """ Test initialization of ServiceServer() instance """
        srv = self.service_server
        self.assertEqual(srv.id, 'UnknownService')
        self.assertEqual(srv.version, 1)
        self.assertEqual(srv.backend, None)
        self.assertEqual(srv.namespace, 'schemas-upnp-org')
        self.assertEqual(srv.id_namespace, 'upnp-org')
        self.assertEqual(srv.service_type,
                         'urn:schemas-upnp-org:service:UnknownService:1')
        self.assertEqual(srv.scpd_url, 'scpd.xml')
        self.assertEqual(srv.control_url, 'control')
        self.assertEqual(srv.subscription_url, 'subscribe')
        self.assertEqual(srv.event_metadata, '')

        self.assertEqual(srv._actions, {})
        self.assertEqual(srv._variables, {0: {}})
        self.assertEqual(srv._subscribers, {})
        self.assertEqual(srv._pending_notifications, {})

        # :fixme: rethink last_change: maybe better to init with 0
        self.assertIs(srv.last_change, None)

        # :todo: implement a test for
        # self.putChild(self.subscription_url, EventSubscriptionServer(self))

        self.assertIsInstance(srv.check_subscribers_loop,task.LoopingCall)
        self.assertIs(srv.check_moderated_loop, None)

    def test_getters(self):
        srv = self.service_server

        self.assertEqual(srv.get_actions(), {})
        self.assertEqual(srv.get_variables(), {0: {}})
        self.assertEqual(srv.get_subscribers(), {})

        self.assertEqual(srv.get_id(), 'UnknownService')
        self.assertEqual(srv.get_type(),
                         'urn:schemas-upnp-org:service:UnknownService:1')

    def test_build_single_notification(self):
        srv = self.service_server
        # note: parameter `instance` is ignored.:fixme: remove it?
        self.assertEqual(
            # :rethink: make classmethod
            srv.build_single_notification(0, 'DummyVariable', 987),
            # :todo: this tested result heavily depends on how ElementTree
            # handles the namespace.
            ('<ns0:propertyset xmlns:ns0="urn:schemas-upnp-org:event-1-0">'
             '<ns0:property><DummyVariable>987</DummyVariable></ns0:property>'
             '</ns0:propertyset>'))
        self.assertRaisesRegexp(TypeError, '^cannot serialize',
                                srv.build_single_notification, 0, 321, 987)

    def test_build_last_change_event(self):
        srv = self.service_server
        # this returns None if no variables are found (and we have no
        # variables defined in this test-case)
        self.assertIs(srv.build_last_change_event(), None)
        self.assertIs(srv.build_last_change_event(1), None)
        self.assertIs(srv.build_last_change_event(force=False), None)
        self.assertIs(srv.build_last_change_event(1, force=False), None)

    def test_propagate_notification(self):
        srv = self.service_server
        # This returns None if no variables are found or no
        # subscribers and notifiers are registered. In this test-case
        # we have none of those.
        self.assertIs(srv.propagate_notification([]), None)


class ExpectedDefinitionsMixin(object):

    def test_actions(self):

        def compare_actions(actions_to_test):
            self.assertEqual(len(actions_to_test), len(self._expected_actions))
            for i, action in enumerate(self._expected_actions):
                # Note: This implicitly tests Action.as_dict(), too,
                # but saves a lot of code.
                name = action['name']
                self.assertIn(name, actions_to_test)
                self.assertEqual(actions_to_test[action['name']].as_dict(),
                                 action)

        srv = self.service_server
        compare_actions(srv._actions)
        compare_actions(srv.get_actions())

    def test_variables(self):

        def compare_variables(variables_to_test):
            self.assertEqual(len(variables_to_test),
                             len(self._expected_variables))
            for i, variable in enumerate(self._expected_variables):
                # Note: This implicitly tests Variable.as_tuples(),
                # too, but saves a lot of code.
                name = variable[0][1]
                self.assertIn(name, variables_to_test)
                self.assertEqual(variables_to_test[name].as_tuples(),
                                 variable)

        srv = self.service_server
        # there is one instance
        self.assertEqual(len(srv._variables), 1)
        self.assertEqual(srv._variables.keys(), [0])
        compare_variables(srv._variables[0])


class ValidDescriptionXML_SwitchPower(unittest.TestCase,
                                      ExpectedDefinitionsMixin):
    """
    Test ServerService using real 'SwitchPower1.xml', which is a
    simple one.
    """

    _expected_actions = [
        {'name': 'SetTarget',
         'arguments':
             [{'name': 'NewTargetValue',
               'direction': 'in',
               'related_state_variable': 'Target'
               }]
         },
        {'name': 'GetTarget',
         'arguments':
             [{'name': 'RetTargetValue',
               'direction': 'out',
               'related_state_variable': 'Target'
               }]
         },
        {'name': 'GetStatus',
         'arguments':
             [{'name': 'ResultStatus',
               'direction': 'out',
               'related_state_variable': 'Status'
               }]
         },
        ]

    _expected_variables = [
        [('Name', 'Target'),
         ('Evented', 'no'),
         ('Data Type', 'boolean'),
         ('Default Value', '0'),
         ('Current Value', '0'),
         ],
        [('Name', 'Status'),
         ('Evented', 'yes'),
         ('Data Type', 'boolean'),
         ('Default Value', '0'),
         ('Current Value', '0'),
         ],
        ]

    def setUp(self):
        self.setUp_main()

    def setUp_main(self):
        # :todo: use service.ServiceServer, see comment at
        # ServiceServer4Test
        self.service_server = ServiceServer4Test(
            'SwitchPower', version=1, backend=None)

    def tearDown(self):
        try:
            self.service_server.check_subscribers_loop.stop()
        except AttributeError:
            pass
        try:
            self.service_server.service_service.check_moderated_loop.stop()
        except AttributeError:
            pass

    def test_init(self):
        """ Test initialization of ServiceServer() instance """
        srv = self.service_server
        self.assertEqual(srv.id, 'SwitchPower')
        self.assertEqual(srv.version, 1)
        self.assertEqual(srv.backend, None)
        self.assertEqual(srv.namespace, 'schemas-upnp-org')
        self.assertEqual(srv.id_namespace, 'upnp-org')
        self.assertEqual(srv.service_type,
                         'urn:schemas-upnp-org:service:SwitchPower:1')
        self.assertEqual(srv.scpd_url, 'scpd.xml')
        self.assertEqual(srv.control_url, 'control')
        self.assertEqual(srv.subscription_url, 'subscribe')
        self.assertEqual(srv.event_metadata, '')

        # actions ans variables are tested below
        self.assertEqual(srv._subscribers, {})
        self.assertEqual(srv._pending_notifications, {})

        # :fixme: rethink last_change: maybe better to init with 0
        self.assertIs(srv.last_change, None)

        # :todo: implement a test for
        # self.putChild(self.subscription_url, EventSubscriptionServer(self))

        self.assertIsInstance(srv.check_subscribers_loop,task.LoopingCall)
        self.assertIs(srv.check_moderated_loop, None)

    def test_getters(self):
        srv = self.service_server

        self.assertEqual(srv.get_subscribers(), {})

        self.assertEqual(srv.get_id(), 'SwitchPower')
        self.assertEqual(srv.get_type(),
                         'urn:schemas-upnp-org:service:SwitchPower:1')

    def test_build_last_change_event(self):
        srv = self.service_server
        # this returns None if no variables are found
        self.assertIs(srv.build_last_change_event(), None)
        self.assertIs(srv.build_last_change_event(1), None)
        self.assertIs(srv.build_last_change_event(force=False), None)
        self.assertIs(srv.build_last_change_event(1, force=False), None)

    def test_build_last_change_event(self):
        srv = self.service_server
        # This returns None if no variables are found or no
        # subscribers and notifiers are registered. In this test-cse
        # we have non of those.
        self.assertIs(srv.propagate_notification([]), None)


# :todo: test get_action(name)
# :todo: test rm_notification
# :todo: testsubscribtions
# create_new_instance, remove_instance, set_variable, get_variable
# propagate_notification, check_subscribers, check_moderated_variables
# is_variable_moderated
# simulate_notification
# get_scpdXML
# register_vendor_variable, register_vendor_action
# init_var_and_actions


