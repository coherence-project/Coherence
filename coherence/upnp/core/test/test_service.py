# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2014, Hartmut Goebel <h.goebel@goebel-consult.de>

"""
Test cases for L{upnp.core.service}
"""

import time
try:
    import unittest.mock as mock
except ImportError:
    import mock

from twisted.trial import unittest
from twisted.internet.defer import Deferred

from coherence.upnp.core import service, device


class DummyDevice:
    client = None
    friendly_name = 'Dummy Device'
    def get_location(self): return "DummyDevice's Location"
    def get_urlbase(self): return "DummyDevice's URL base"
    def get_id(self):return "DummyDevice's ID"
    def make_fullyqualified(self, url):
        return "DummyDevice's FQ-URL/" + url

# :todo: put this into a central module
def raiseError(url):
    """
    Used for mocking coherence.upnp.core.utils.getPage, behaves as if
    the file was not read.
    """
    def _raiseError(*args): raise Exception('Meaningless Error')
    d = Deferred()
    d.addCallback(_raiseError)
    return d

# :todo: put this into a central module
def fakeGetPage(content):
    def returnEmptyPage(url):
        """
        Used for mocking coherence.upnp.core.utils.getPage, behaves as if
        the file contains `content`.
        """
        d = Deferred()
        d.callback((content, {}))
        return d
    return returnEmptyPage


class DescriptionNotFound(unittest.TestCase):

    def setUp(self):
        with mock.patch('coherence.upnp.core.utils.getPage', raiseError):
            self.setUp_main()

    def setUp_main(self):
        self.device= DummyDevice()
        self.service = service.Service(
            'my-service-type', 'my-service-id',
            'http://localhost:8080/my-location',
            'http://localhost/my-service/control',
            'http://localhost/my-service/subscribe',
            'http://localhost/my-service/view',
            'http://localhost/my-service/scpd',
            self.device)

    def tearDown(self):
        try:
            self.service.renew_subscription_call.cancel()
        except AttributeError:
            pass

    def test_init(self):
        """ Test initialization of Service() instance """
        svc = self.service
        self.assertEqual(svc.service_type, 'my-service-type')
        self.assertEqual(svc.id, 'my-service-id')
        # parameter location  goes into  url_base
        self.assertEqual(svc.control_url,
                         'http://localhost/my-service/control')
        self.assertEqual(svc.event_sub_url,
                         'http://localhost/my-service/subscribe')
        self.assertEqual(svc.presentation_url,
                         'http://localhost/my-service/view')
        self.assertEqual(svc.scpd_url, 'http://localhost/my-service/scpd')
        self.assertIs(svc.device, self.device)
        # not completed as we have *no* valid description
        self.assertFalse(svc.detection_completed)

        self.assertEqual(svc._actions, {})
        self.assertEqual(svc._variables, {0: {}})
        # :fixme: this attribute is unused, remove it
        self.assertEqual(svc._var_subscribers, {})

        self.assertIs(svc.subscription_id, None)
        self.assertEqual(svc.timeout, 0)
        # :todo: rethink last_time_updated: maybe better to init with 0
        self.assertIs(svc.last_time_updated, None)
        self.assertIs(svc.event_connection, None)
        self.assertIs(svc.client, None)

        self.assertEqual(svc.url_base, 'http://localhost:8080')

    def test_scpdXML(self):
        svc = self.service
        # scpdXML is not set as we have not parsed any description
        self.assertRaises(AttributeError, getattr, svc, 'scpdXML')
        self.assertRaises(AttributeError, svc.get_scpdXML)

    def test_getters(self):
        svc = self.service
        self.assertIs(svc.get_device(), self.device)
        self.assertEqual(svc.get_type(), 'my-service-type')
        self.assertEqual(svc.get_id(), 'my-service-id')
        self.assertEqual(svc.get_timeout(), 0)
        self.assertEqual(svc.get_sid(), None)
        self.assertEqual(svc.get_actions(), {})
        self.assertEqual(svc.get_state_variables(0), {})
        self.assertEqual(
            svc.get_control_url(),
            "DummyDevice's FQ-URL/http://localhost/my-service/control")
        self.assertEqual(
            svc.get_event_sub_url(),
            "DummyDevice's FQ-URL/http://localhost/my-service/subscribe")
        self.assertEqual(
            svc.get_presentation_url(),
            "DummyDevice's FQ-URL/http://localhost/my-service/view")
        self.assertEqual(
            svc.get_scpd_url(),
            "DummyDevice's FQ-URL/http://localhost/my-service/scpd")
        self.assertEqual(svc.get_base_url(), "DummyDevice's FQ-URL/.")

    def test_as_dict(self):
        """ Test Service.as_dict() """
        svc = self.service
        self.assertEqual(svc.as_dict(),
                         {'type': 'my-service-type',
                          'actions': [] })

    def test_as_tuple(self):
        """ Test Service.as_tuples() """
        svc = self.service
        self.assertEqual(svc.as_tuples(), [
            ("Location", ("DummyDevice's Location", "DummyDevice's Location")),
            ("URL base", "DummyDevice's URL base"),
            ("UDN", "DummyDevice's ID"),
            ("Type", 'my-service-type'),
            ("ID", 'my-service-id'),
            ("Service Description URL",
             ('http://localhost/my-service/scpd',
              "DummyDevice's FQ-URL/http://localhost/my-service/scpd")),
            ("Control URL",
             ('http://localhost/my-service/control',
              "DummyDevice's FQ-URL/http://localhost/my-service/control",
              False)),
            ("Event Subscription URL",
             ('http://localhost/my-service/subscribe',
              "DummyDevice's FQ-URL/http://localhost/my-service/subscribe",
              False)),
            ])

    def test_set_timeout(self):
        svc = self.service
        self.assertEqual(svc.get_timeout(), 0)
        svc.set_timeout(654)
        self.assertEqual(svc.get_timeout(), 654)

    def test_set_sid(self):
        svc = self.service
        self.assertEqual(svc.get_sid(), None)
        svc.set_sid('my-subscription-id')
        self.assertEqual(svc.get_sid(), 'my-subscription-id')


class EmptyDescription(DescriptionNotFound):
    """
    Same as DescriptionNotFound, except now we pass an empty
    description XML. Results should be the same, except for scpdXML.
    """

    def setUp(self):
        with mock.patch('coherence.upnp.core.utils.getPage',
                        fakeGetPage('')):
            self.setUp_main()

    def test_scpdXML(self):
        svc = self.service
        # scpdXML is empty as we have not parsed any description
        self.assertEqual(svc.scpdXML, '')
        self.assertEqual(svc.get_scpdXML(), '')


class InvalidDescriptionXML(DescriptionNotFound):
    """
    Same as DescriptionNotFound, except now we pass a
    description which is invalid XML. Results should be the same,
    except for scpdXML.
    """

    def setUp(self):
        with mock.patch('coherence.upnp.core.utils.getPage',
                        fakeGetPage('<x>')):
            self.setUp_main()

    def test_scpdXML(self):
        svc = self.service
        # :fixme: rethink if invalid scpdXML should really be stored
        self.assertEqual(svc.scpdXML, '<x>')
        self.assertEqual(svc.get_scpdXML(), '<x>')


_scpdXMLTemplate = '''\
<?xml version="1.0"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
%s
%s
</scpd>
'''

_scdpActions = '''
<actionList>
  <action>
    <name>GetCurrentConnectionIDs</name>
    <argumentList>
      <argument>
        <name>ConnectionIDs</name>
        <direction>out</direction>
        <relatedStateVariable>CurrentConnectionIDs</relatedStateVariable>
      </argument>
    </argumentList>
  </action>
</actionList>
'''

_scdpServiceStates = '''
<serviceStateTable>
  <stateVariable sendEvents="yes">
    <name>SourceProtocolInfo</name>
    <dataType>string</dataType>
  </stateVariable>
</serviceStateTable>
'''

class CompleteDescription(unittest.TestCase):

    _scpdXML = _scpdXMLTemplate % (_scdpActions, _scdpServiceStates)
    _expected_actions = [
        {'name': 'GetCurrentConnectionIDs',
         'arguments':
             [{'name': 'ConnectionIDs',
               'direction': 'out',
               'related_state_variable': 'CurrentConnectionIDs'
               }]
         }
        ]
    _expected_variables = [
        [('Name', 'SourceProtocolInfo'),
         ('Evented', 'yes'),
         ('Data Type', 'string'),
         ('Default Value', ''),
         ('Current Value', ''),
         ]
        ]

    def setUp(self):
        #from coherence.upnp.core import utils
        #utils.parse_xml(self._scpdXML, 'utf-8')
        #raise NotImplementedError(self._scpdXML)
        info = {
            'USN': "RootDevice's USN",
            'SERVER': "RootDevice's Server",
            'ST': "RootDevice's ST",
            'LOCATION': "http://localhost:8080/my-location",
            'MANIFESTATION': "RootDevice's Manifestation",
            'HOST': "RootDevice's Host",
            }
        # Create an empty RootDevice without services, actions, icons,
        # etc. Do not use DummyDevice here as we want to test URLs,
        # too.
        with mock.patch('coherence.upnp.core.utils.getPage', raiseError):
            self.device = device.RootDevice(info)
        # Since the Device has got no description, wenn need to set
        # urlbase manually. It is required to be set.
        # :fixme: this one is used in make_fullyqualified, rethink
        self.device.urlbase = 'http://localhost:8888'
        # Create the service we want to test, using meaningful values
        with mock.patch('coherence.upnp.core.utils.getPage',
                        fakeGetPage(self._scpdXML)):
            self.service = service.Service(
                'urn:schemas-upnp-org:service:RenderingControl:1',
                'urn:upnp-org:serviceId:RenderingControl',
                self.device.get_location(),
                '/my-service/control',
                '/my-service/subscribe',
                '/my-service/view',
                '/my-service/scpd',
                self.device)

    def tearDown(self):
        try:
            self.service.renew_subscription_call.cancel()
        except AttributeError:
            pass

    def test_init(self):
        """ Test initialization of Service() instance """
        svc = self.service
        self.assertEqual(svc.service_type,
                         'urn:schemas-upnp-org:service:RenderingControl:1')
        self.assertEqual(svc.id, 'urn:upnp-org:serviceId:RenderingControl')
        # parameter location  goes into  url_base
        self.assertEqual(svc.control_url, '/my-service/control')
        self.assertEqual(svc.event_sub_url, '/my-service/subscribe')
        self.assertEqual(svc.presentation_url, '/my-service/view')
        self.assertEqual(svc.scpd_url, '/my-service/scpd')
        self.assertIs(svc.device, self.device)
        # completed as we have a valid description
        self.assertTrue(svc.detection_completed)

        self.assertIs(svc.subscription_id, None)
        self.assertEqual(svc.timeout, 0)
        # :todo: rethink last_time_updated: maybe better to init with 0
        self.assertIs(svc.last_time_updated, None)
        self.assertIs(svc.event_connection, None)
        self.assertIs(svc.client, None)
        # :fixme: this one is *not* used in make_fullyqualified, rethink
        self.assertEqual(svc.url_base, 'http://localhost:8080')

    def test_scpdXML(self):
        svc = self.service
        self.assertEqual(svc.scpdXML, self._scpdXML)
        self.assertEqual(svc.get_scpdXML(), self._scpdXML)

    def test_actions(self):

        def compare_actions(actions_to_test):
            self.assertEqual(len(actions_to_test), len(self._expected_actions))
            for i, name in enumerate(actions_to_test):
                # Note: This implicitly tests Action.as_dict(), too,
                # but saves a lot of code.
                self.assertEqual(actions_to_test[name].as_dict(),
                                self._expected_actions[i])

        svc = self.service
        compare_actions(svc._actions)
        compare_actions(svc.get_actions())

    def test_variables(self):

        def compare_variables(variables_to_test):
            self.assertEqual(len(variables_to_test),
                             len(self._expected_variables))
            for i, name in enumerate(variables_to_test):
                # Note: This implicitly tests Variable.as_tuples(),
                # too, but saves a lot of code.
                self.assertEqual(variables_to_test[name].as_tuples(),
                                 self._expected_variables[i])

        svc = self.service
        # there is one instance
        self.assertEqual(len(svc._variables), 1)
        self.assertEqual(svc._variables.keys(), [0])
        compare_variables(svc._variables[0])
        #compare_variables(svc.get_state_variables(0))

    def test_getters(self):
        svc = self.service
        self.assertIs(svc.get_device(), self.device)
        self.assertEqual(svc.get_type(),
                         'urn:schemas-upnp-org:service:RenderingControl:1')
        self.assertEqual(svc.get_id(),
                         'urn:upnp-org:serviceId:RenderingControl')
        self.assertEqual(svc.get_timeout(), 0)
        self.assertEqual(svc.get_sid(), None)
        self.assertEqual(svc.get_control_url(),
                         'http://localhost:8888/my-service/control')
        self.assertEqual(svc.get_event_sub_url(),
                         'http://localhost:8888/my-service/subscribe')
        self.assertEqual(svc.get_presentation_url(),
                         'http://localhost:8888/my-service/view')
        self.assertEqual(svc.get_scpd_url(),
                         'http://localhost:8888/my-service/scpd')
        self.assertEqual(svc.get_base_url(), "http://localhost:8888/")


class DescriptionWithoutActions(CompleteDescription):

    _scpdXML = _scpdXMLTemplate % ('', _scdpServiceStates)
    _expected_actions = {}


class DescriptionWithoutVariables(CompleteDescription):

    _scpdXML = _scpdXMLTemplate % (_scdpActions, '')
    _expected_variables = []


class DescriptionWithoutNamespaceDeclaration(CompleteDescription):

    _scpdXML = _scpdXMLTemplate.replace(' xmlns=', ' dummy=') \
               % ('', _scdpServiceStates)
    _expected_actions = {}
    _expected_variables = []


class DescriptionWithWrongNamespace(CompleteDescription):

    _scpdXML = _scpdXMLTemplate.replace(' xmlns="urn:', ' xmlns="dummy:') \
               % ('', _scdpServiceStates)
    _expected_actions = {}
    _expected_variables = []


# :todo: test-cases for subscribe/unsubscribe, subscribe_for_variable
# :todo: test-cases for process_event()
# :todo: test-cases for ServiceServer
# :todo: test-cases for scpdXML
# :todo: test-cases for ServiceControl
