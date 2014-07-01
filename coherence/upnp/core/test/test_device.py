# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2014, Hartmut Goebel <h.goebel@crazy-compilers.com>

"""
Test cases for L{upnp.core.device}
"""
# :todo: test-cases with incomplete descriptions
# :todo: test-cases with invalid description XML
# :todo: test-cases with description XML without namespace declaration
# :todo: test-cases with embedded devices

import os
import urlparse
import posixpath
try:
    import unittest.mock as mock
except ImportError:
    import mock

from twisted.trial import unittest
from twisted.internet.defer import Deferred
from twisted.python.filepath import FilePath

from coherence.upnp.core import device

FILE_BASE = os.path.dirname(__file__)

class _DummyParentDevice:
    def get_location(self): return "DummyParentDevice's Location"
    def get_usn(self): return "DummyParentDevice's USN"
    def get_urlbase(self): return "DummyParentDevice's URL base"
    def get_upnp_version(self): return "DummyParentDevice's UPNP version"

class _DummyParentDevice2(_DummyParentDevice):
    def get_id(self): return "DummyParentDevice2's ID"
    def make_fullyqualified(self, url): return "DummyParentDevice2's FQ-URL"


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

# :todo: put something like this this into a central module
def fakeGetPageURL(url):
    """
    Used for mocking coherence.upnp.core.utils.getPage. Returns the
    content of the file with the name taken from the final component
    of a url-path.

    Example:
      http://1.2.3.4/a/b/c/some.xml -> <module-dir>/some.xml
    """
    path = urlparse.urlparse(url).path
    path = posixpath.normpath(path)
    words = path.split('/')
    words = filter(None, words)[-1:]
    file = FilePath(os.path.join(FILE_BASE, *words))
    d = Deferred()
    d.callback((file.open().read(), {}))
    return d


class DeviceWithoutDescription(unittest.TestCase):

    def test_init(self):
        """ Test initialization of Device() instance """
        parent = _DummyParentDevice()
        dev = device.Device(parent)
        self.assertEqual(dev.parent, parent)
        self.assertEqual(dev.services, [])
        self.assertEqual(dev.friendly_name, '')
        self.assertEqual(dev.device_type, '')
        self.assertEqual(dev.friendly_device_type, '[unknown]')
        self.assertEqual(dev.device_type_version, 0)
        self.assertEqual(dev.udn, None)
        self.assertFalse(dev.detection_completed)
        self.assertEqual(dev.client, None)
        self.assertEqual(dev.icons, [])
        self.assertEqual(dev.devices, [])

        self.assertEqual(dev.get_id(), None)
        self.assertRaises(TypeError, dev.get_uuid)
        self.assertEqual(dev.get_embedded_devices(), [])
        self.assertEqual(dev.get_services(), [])
        self.assertEqual(dev.get_friendly_name(), '')
        self.assertEqual(dev.get_device_type(), '')
        self.assertEqual(dev.get_friendly_device_type(), '[unknown]')
        self.assertEqual(dev.get_markup_name(), '[unknown]:0 ')
        self.assertEqual(dev.get_device_type_version(), 0)
        self.assertEqual(dev.get_client(), None)
        self.assertEqual(dev.get_location(), "DummyParentDevice's Location")
        self.assertEqual(dev.get_usn(), "DummyParentDevice's USN")
        self.assertEqual(dev.get_upnp_version(),
                         "DummyParentDevice's UPNP version")
        self.assertEqual(dev.get_urlbase(), "DummyParentDevice's URL base")
        self.assertEqual(dev.get_presentation_url(), '')

    def test_as_dict(self):
        """ Test Device.as_dict() """
        parent = _DummyParentDevice()
        dev = device.Device(parent)
        self.assertEqual(dev.as_dict(),
                         {'device_type': '',
                          'friendly_name': '',
                          'udn': None,
                          'services': [],
                          'icons': [],
                          })

    def test_as_tuple(self):
        """ Test Device.as_tuples() """
        parent = _DummyParentDevice()
        dev = device.Device(parent)
        # Most of the values in the tuple are not set if the
        # description has not yet been parsed.
        self.assertEqual(dev.as_tuples(),
                         [('Location',
                           ("DummyParentDevice's Location",
                            "DummyParentDevice's Location")),
                          ('URL base', "DummyParentDevice's URL base"),
                          ('UDN', None),
                          ('Type', ''),
                          ('Friendly Name', ''),
                          ])

    def test_get_parent_id(self):
        parent = None
        dev = device.Device(parent)
        # :fixme: rethink this behavior, shouldn't this raise an error?
        self.assertEqual(dev.get_parent_id(), "")

        parent = _DummyParentDevice()
        dev = device.Device(parent)
        # :fixme: rethink this behavior, shouldn't this raise an error?
        self.assertEqual(dev.get_parent_id(), "")

        parent = _DummyParentDevice2()
        dev = device.Device(parent)
        self.assertEqual(dev.get_parent_id(), "DummyParentDevice2's ID")

    def test_make_fullyqualified(self):
        parent = None
        dev = device.Device(parent)
        self.assertRaises(AttributeError, dev.make_fullyqualified, '')
        self.assertRaises(AttributeError,
                          dev.make_fullyqualified, 'some-file.xml')

        parent = _DummyParentDevice2()
        dev = device.Device(parent)
        self.assertEqual(dev.make_fullyqualified(''),
                         "DummyParentDevice2's FQ-URL")
        self.assertEqual(dev.make_fullyqualified('some-file.xml'),
                         "DummyParentDevice2's FQ-URL")


    def test_get_markup_name(self):
        dev = device.Device(None)
        self.assertEqual(dev.get_markup_name(), '[unknown]:0 ')


class RootDeviceDescriptionNotFound(unittest.TestCase):

    def setUp(self):
        with mock.patch('coherence.upnp.core.utils.getPage', raiseError):
            self.setUp_main()

    def setUp_main(self):
        info = {
            'USN': "RootDevice's USN",
            'SERVER': "RootDevice's Server",
            'ST': "RootDevice's ST",
            'LOCATION': "RootDevice's Location",
            'MANIFESTATION': "RootDevice's Manifestation",
            'HOST': "RootDevice's Host",
            }
        self.rootdevice = device.RootDevice(info)

    def test_init(self):
        """ Test initialization of RootDevice() instance """
        dev = self.rootdevice
        self.assertEqual(dev.usn, "RootDevice's USN")
        self.assertEqual(dev.server, "RootDevice's Server")
        self.assertEqual(dev.st, "RootDevice's ST")
        self.assertEqual(dev.location, "RootDevice's Location")
        self.assertEqual(dev.manifestation, "RootDevice's Manifestation")
        self.assertEqual(dev.host, "RootDevice's Host")
        # root detection is not completed as there has been no description
        self.assertFalse(dev.root_detection_completed)

        # remaining tests are inherited from device
        # :todo: rethink this: are these meaningful for RootDevices at all?
        self.assertEqual(dev.parent, None)
        self.assertEqual(dev.services, [])
        self.assertEqual(dev.friendly_name, '')
        self.assertEqual(dev.device_type, '')
        self.assertEqual(dev.friendly_device_type, '[unknown]')
        self.assertEqual(dev.device_type_version, 0)
        self.assertEqual(dev.udn, None)
        self.assertEqual(dev.client, None)
        self.assertEqual(dev.icons, [])
        self.assertEqual(dev.devices, [])

    def test_getters(self):
        dev = self.rootdevice
        self.assertEqual(dev.get_usn(), "RootDevice's USN")
        self.assertEqual(dev.get_st(), "RootDevice's ST")
        self.assertEqual(dev.get_location(), "RootDevice's Location")
        # :fixme: should behave like a normal Device (or normal Device
        # should raise, too)
        self.assertRaises(AttributeError, dev.get_upnp_version)
        # :fixme: should behave like a normal Device (or normal Device
        # should raise, too)
        self.assertRaises(AttributeError, dev.get_urlbase)
        self.assertEqual(dev.get_host(), "RootDevice's Host")

        # :todo: implement test-case for a local service
        self.assertTrue(dev.is_remote())
        self.assertFalse(dev.is_local())

        self.assertEqual(dev.get_id(), None)
        self.assertRaises(TypeError, dev.get_uuid)
        self.assertEqual(dev.get_embedded_devices(), [])
        self.assertEqual(dev.get_friendly_name(), '')
        self.assertEqual(dev.get_device_type(), '')
        self.assertEqual(dev.get_friendly_device_type(), '[unknown]')
        self.assertEqual(dev.get_markup_name(), '[unknown]:0 ')
        self.assertEqual(dev.get_device_type_version(), 0)
        self.assertEqual(dev.get_client(), None)
        self.assertEqual(dev.get_presentation_url(), '')

        # services are tested more in detail below
        self.assertEqual(len(dev.get_services()), 0)

    def test_as_dict(self):
        """ Test RootDevice.as_dict() """
        dev = self.rootdevice
        self.assertEqual(dev.as_dict(),
                         {'device_type': '',
                          'friendly_name': '',
                          'udn': None,
                          'services': [],
                          'icons': [],
                          })

    def test_as_tuple(self):
        """ Test RootDevice.as_tuples() """
        dev = self.rootdevice
        # Most of the values in the tupel are not set if the
        # description has not yet been parsed.
        self.assertEqual(dev.as_tuples(),
                         [('Location',
                           ("RootDevice's Location",
                            "RootDevice's Location")),
                          # :fixme: should behave like a normal
                          # Device, see test_rootdevice_init  above
                          #('URL base', "RootDevice's URL base"),
                          ('UDN', None),
                          ('Type', ''),
                          ('Friendly Name', ''),
                          ])

    def test_get_parent_id(self):
        dev = self.rootdevice
        # :fixme: rethink this behavior, shouldn't this raise an error?
        self.assertEqual(dev.get_parent_id(), "")

    def _test_make_fullyqualified(self):
        dev = self.rootdevice
        # :fixme: rethink this behavior, shouldn't this raise an error?
        self.assertEqual(dev.make_fullyqualified(), "")

    def test_get_markup_name(self):
        dev = self.rootdevice
        self.assertEqual(dev.get_markup_name(), '[unknown]:0 ')


class RootDeviceEmptyDescription(RootDeviceDescriptionNotFound):
    """
    Same as RootDeviceDescriptionNotFound, except now we pass an empty
    description XML. Results should be the same.
    """

    def setUp(self):
        with mock.patch('coherence.upnp.core.utils.getPage',
                        fakeGetPage('')):
            self.setUp_main()


class RootDeviceInvalidDescriptionXML(RootDeviceDescriptionNotFound):
    """
    Same as RootDeviceDescriptionNotFound, except now we pass a
    description which is invalid XML. Results should be the same.
    """

    def setUp(self):
        with mock.patch('coherence.upnp.core.utils.getPage',
                        fakeGetPage('<x>')):
            self.setUp_main()


class RootDeviceWithDescription(unittest.TestCase):
    """
    Test setting up a RootDevice from a XML-description.

    This also queries for XML-descriptions of the service the device
    is offering. The descriptions are read from the file-system, just
    beside this module. Only the the final component of a url-path is
    used as filename (see fakeGetPageURL).
    """

    def __getURL(self, path):
        return "http://127.0.0.1/%s" % path

    def setUp(self):
        self._location_url = self.__getURL('device-description-1.xml')
        info = {
            'ST': 'upnp:rootdevice',
            'USN': 'uuid:12345678-ABCE-klmn-RSTU-987654321098::upnp:rootdevice',
            'MANIFESTATION': 'remote',
            'HOST': '192.168.123.123',
            'SERVER': ('Linux/armv5tel-linux UPnP/1.0 DLNADOC/1.50 '
                       'SqueezeboxMediaServer/7.3.1/12345'),
            'LOCATION': self._location_url,
            }
        with mock.patch('coherence.upnp.core.utils.getPage', fakeGetPageURL):
            self.rootdevice = device.RootDevice(info)

    def test_init(self):
        """ Test initialization of RootDevice() instance """
        dev = self.rootdevice
        self.assertEqual(dev.usn,
                         ('uuid:12345678-ABCE-klmn-RSTU-987654321098::'
                          'upnp:rootdevice'))
        self.assertEqual(dev.server,
                         ('Linux/armv5tel-linux UPnP/1.0 DLNADOC/1.50 '
                          'SqueezeboxMediaServer/7.3.1/12345'))
        self.assertEqual(dev.st, 'upnp:rootdevice')
        self.assertEqual(dev.location, self._location_url)
        self.assertEqual(dev.manifestation, 'remote')
        self.assertEqual(dev.host, '192.168.123.123')
        # root detection is completed as there was a description
        self.assertTrue(dev.detection_completed)

        self.assertEqual(dev.parent, None)
        # services are tested more in detail below
        self.assertEqual(len(dev.services), 3)
        self.assertEqual(dev.friendly_name, 'This is my Squeeze Box')
        self.assertEqual(dev.device_type,
                         'urn:schemas-upnp-org:device:MediaRenderer:1')
        self.assertEqual(dev.friendly_device_type, 'MediaRenderer')
        self.assertEqual(dev.device_type_version, '1')
        self.assertEqual(dev.udn, 'uuid:12345678-ABCE-KLMN-rstu-987654321098')
        self.assertEqual(dev.client, None)
        # icons are tested more in detail below
        self.assertEqual(len(dev.icons), 4)
        # devices are not set up by this test
        self.assertEqual(dev.devices, [])

    def test_getters(self):
        dev = self.rootdevice
        self.assertEqual(dev.get_usn(),
                         ('uuid:12345678-ABCE-klmn-RSTU-987654321098::'
                          'upnp:rootdevice'))
        self.assertEqual(dev.get_st(), 'upnp:rootdevice')
        self.assertEqual(dev.get_location(), self._location_url)
        self.assertEqual(dev.get_upnp_version(), '1.0')
        # device-description-1.xml does not contain a URL base
        self.assertEqual(dev.get_urlbase(), None)
        self.assertEqual(dev.get_host(), '192.168.123.123')

        # :todo: implement test-case for a local service
        self.assertTrue(dev.is_remote())
        self.assertFalse(dev.is_local())

        self.assertEqual(dev.get_id(),
                         'uuid:12345678-ABCE-KLMN-rstu-987654321098')
        self.assertEqual(dev.get_uuid(), '12345678-ABCE-KLMN-rstu-987654321098')
        # devices are not set up by this test
        self.assertEqual(dev.get_embedded_devices(), [])
        self.assertEqual(dev.get_friendly_name(), 'This is my Squeeze Box')
        self.assertEqual(dev.get_device_type(),
                         'urn:schemas-upnp-org:device:MediaRenderer:1')
        self.assertEqual(dev.get_friendly_device_type(), 'MediaRenderer')
        self.assertEqual(dev.get_markup_name(),
                         'MediaRenderer:1 This is my Squeeze Box')
        self.assertEqual(dev.get_device_type_version(), '1')
        self.assertEqual(dev.get_client(), None)
        self.assertEqual(dev.get_presentation_url(),
                         'http://192.168.123.123:9000')

        # services are tested more in detail below
        self.assertEqual(len(dev.get_services()), 3)

    def test_as_dict(self):
        """ Test RootDevice.as_dict() """
        dev = self.rootdevice
        as_dict = dev.as_dict()

        # test the icons
        self.assertEqual(len(as_dict['icons']), 4)
        self.assertEqual(as_dict['icons'][0], {
            'mimetype': 'image/png',
            'url': self.__getURL('html/images/Players/baby_120x120.png'),
            'width': '120',
            'height': '120',
            'depth': '24'
            })
        self.assertEqual(as_dict['icons'][1], {
            'mimetype': 'image/png',
            'url': self.__getURL('html/images/Players/baby_48x48.png'),
            'width': '48',
            'height': '48',
            'depth': '24'
            })
        self.assertEqual(as_dict['icons'][2], {
            'mimetype': 'image/jpeg',
            'url': self.__getURL('html/images/Players/baby_120x120.jpg'),
            'width': '120',
            'height': '120',
            'depth': '24'
            })
        self.assertEqual(as_dict['icons'][3], {
            'mimetype': 'image/jpeg',
            'url': self.__getURL('html/images/Players/baby_48x48.jpg'),
            'width': '48',
            'height': '48',
            'depth': '24'
            })
        del as_dict['icons']

        # test the services
        # actions are tested in test_service, skip here.
        self.assertEqual(len(as_dict['services']), 3)
        del as_dict['services'][0]['actions']
        self.assertEqual(as_dict['services'][0], {
            #'actions': [],
            'type': 'urn:schemas-upnp-org:service:RenderingControl:1'})
        del as_dict['services'][1]['actions']
        self.assertEqual(as_dict['services'][1], {
            #'actions': [],
            'type': 'urn:schemas-upnp-org:service:ConnectionManager:1'})
        del as_dict['services'][2]['actions']
        self.assertEqual(as_dict['services'][2], {
            #'actions': [],
            'type': 'urn:schemas-upnp-org:service:AVTransport:1'})
        del as_dict['services']

        # test the remaining data
        self.assertEqual(as_dict, {
            'device_type':
            'urn:schemas-upnp-org:device:MediaRenderer:1',
            'friendly_name': 'This is my Squeeze Box',
            'udn': 'uuid:12345678-ABCE-KLMN-rstu-987654321098',
            })

    def test_as_tuple(self):
        """ Test RootDevice.as_tuples() """
        dev = self.rootdevice
        as_tuples = dev.as_tuples()
        icons = [e for e in as_tuples if e[0] == 'Icon']
        as_tuples = [e for e in as_tuples if e[0] != 'Icon']

        self.assertEqual(as_tuples, [
            ('Location', (self._location_url, self._location_url)),
            # device-description-1.xml does not contain a URL base
            #('URL base', self.__getURL('')),
            ('UDN', 'uuid:12345678-ABCE-KLMN-rstu-987654321098'),
            ('Type', 'urn:schemas-upnp-org:device:MediaRenderer:1'),
            ('UPnP Version', '1.0'),
            ('DLNA Device Class', 'DMR-1.50'),
            ('Friendly Name', 'This is my Squeeze Box'),
            ('Manufacturer', 'Slim Devices'),
            ('Manufacturer URL',
             ('http://www.mysqueezebox.com', 'http://www.mysqueezebox.com')),
            ('Model Description',
             'Squeezebox Server UPnP/DLNA Plugin'),
            ('Model Name', 'Squeezebox Radio'),
            ('Model Number', '1'),
            ('Model URL',
             ('http://wiki.slimdevices.com/Squeezebox_Radio',
              'http://wiki.slimdevices.com/Squeezebox_Radio')),
            ('Serial Number', '00:04:20:12:34:56'),
            # device-description-1.xml does not contain a UPC
            ('Presentation URL',
             ('http://192.168.123.123:9000', 'http://192.168.123.123:9000')),
            ])

        self.assertEqual(len(icons), 4)
        self.assertEqual(icons[0],
            ('Icon',
             ('/html/images/Players/baby_120x120.png',
              self.__getURL('html/images/Players/baby_120x120.png'),
              {'Width': '120', 'Height': '120', 'Depth': '24',
               'Mimetype': 'image/png'})))
        self.assertEqual(icons[1],
            ('Icon',
             ('/html/images/Players/baby_48x48.png',
              self.__getURL('html/images/Players/baby_48x48.png'),
              {'Width': '48', 'Height': '48', 'Depth': '24',
               'Mimetype': 'image/png'})))
        self.assertEqual(icons[2],
            ('Icon',
             ('/html/images/Players/baby_120x120.jpg',
              self.__getURL('html/images/Players/baby_120x120.jpg'),
              {'Width': '120', 'Height': '120', 'Depth': '24',
               'Mimetype': 'image/jpeg'})))
        self.assertEqual(icons[3],
            ('Icon',
             ('/html/images/Players/baby_48x48.jpg',
              self.__getURL('html/images/Players/baby_48x48.jpg'),
              {'Width': '48', 'Height': '48', 'Depth': '24',
               'Mimetype': 'image/jpeg'})))

    def test_icons(self):
        dev = self.rootdevice
        self.assertEqual(len(dev.icons), 4)
        # :todo: get_icons()
        self.assertEqual(dev.icons[0], {
            'mimetype': 'image/png',
            'realurl': '/html/images/Players/baby_120x120.png',
            'url': self.__getURL('html/images/Players/baby_120x120.png'),
            'width': '120',
            'height': '120',
            'depth': '24'
            })
        self.assertEqual(dev.icons[1], {
            'mimetype': 'image/png',
            'realurl': '/html/images/Players/baby_48x48.png',
            'url': self.__getURL('html/images/Players/baby_48x48.png'),
            'width': '48',
            'height': '48',
            'depth': '24'
            })
        self.assertEqual(dev.icons[2], {
            'mimetype': 'image/jpeg',
            'realurl': '/html/images/Players/baby_120x120.jpg',
            'url': self.__getURL('html/images/Players/baby_120x120.jpg'),
            'width': '120',
            'height': '120',
            'depth': '24'
            })
        self.assertEqual(dev.icons[3], {
            'mimetype': 'image/jpeg',
            'realurl': '/html/images/Players/baby_48x48.jpg',
            'url': self.__getURL('html/images/Players/baby_48x48.jpg'),
            'width': '48',
            'height': '48',
            'depth': '24'
            })

    def test_services(self):

        def test_service(service, type):
            self.assertEqual(service.get_type(),
                             'urn:schemas-upnp-org:service:%s:1' % type)
            self.assertEqual(service.get_id(),
                             'urn:upnp-org:serviceId:%s' % type)
            self.assertEqual(service.get_control_url(),
                             'http://127.0.0.1/plugins/UPnP/'
                             'MediaRenderer/%s/control'  % type +
                             '?player=00%3A04%3A20%3A12%3A34%3A56')
            self.assertEqual(service.get_event_sub_url(),
                             'http://192.168.123.123:40872/plugins/UPnP/'
                             'MediaRenderer/%s/eventsub' % type +
                             '?player=00%3A04%3A20%3A12%3A34%3A56')
            # :fixme: this crashes as this test-case does not have a
            # presentation_url. Need to fix Service.get_presentation_url()
            #self.assertEqual(service.get_presentation_url(), '')
            self.assertEqual(service.get_scpd_url(),
                             'http://127.0.0.1'
                             '/plugins/UPnP/MediaRenderer/%s-1.xml' % type)
            self.assertIs(service.device, dev)

        dev = self.rootdevice

        self.assertEqual(len(dev.services), 3)
        test_service(dev.services[0], 'RenderingControl')
        test_service(dev.services[1], 'ConnectionManager')
        test_service(dev.services[2], 'AVTransport')

        got_services = dev.get_services()
        self.assertEqual(len(got_services), 3)
        test_service(got_services[0], 'RenderingControl')
        test_service(got_services[1], 'ConnectionManager')
        test_service(got_services[2], 'AVTransport')

    def test_get_service_by_type(self):
        dev = self.rootdevice
        self.assertIs(dev.get_service_by_type('RenderingControl'),
                      dev.services[0])
        self.assertIs(dev.get_service_by_type('ConnectionManager'),
                      dev.services[1])
        self.assertIs(dev.get_service_by_type('AVTransport'),
                      dev.services[2])

    # :fixme: This fails as Service.get_usn() is not implemented.
    # Rethink if remove_service_with_usn is needed at all and if
    # Service.get_usn should be implemented.
    ## def test_remove_service_with_usn(self):
    ##     dev = self.rootdevice
    ##     dev.remove_service_with_usn(
    ##         'uuid:12345678-ABCE-KLMN-rstu-987654321098'
    ##         '::urn:schemas-upnp-org:service:ConnectionManager:1')
    ##     self.assertEqual(len(dev.services), 2)
    ##     self.assertEqual(dev.services[0].get_type(),
    ##                      'urn:schemas-upnp-org:service:RenderingControl:1')
    ##     self.assertEqual(dev.services[1].get_type(),
    ##                      'urn:schemas-upnp-org:service:AVTransport:1')

    def test_get_parent_id(self):
        dev = self.rootdevice
        # :fixme: rethink this behavior, shouldn't this raise an error?
        self.assertEqual(dev.get_parent_id(), "")

    def test_make_fullyqualified(self):
        # :todo: Find out what is the intented semantic for
        # make_fullyqualified and implement proper test-cases.
        dev = self.rootdevice
        self.assertEqual(dev.make_fullyqualified(''),
                         self.__getURL('device-description-1.xml'))
        self.assertEqual(dev.make_fullyqualified('test-test.html'),
                         self.__getURL('test-test.html'))

    def test_get_markup_name(self):
        dev = self.rootdevice
        self.assertEqual(dev.get_markup_name(),
                         'MediaRenderer:1 This is my Squeeze Box')

# :todo: test-cases for service-subscription
# :todo: test-cases with incomplete device description
# :todo: test-cases with missing service description-XML
# :todo: test-cases embedded devices (see UPnT/xmlfiles/device/WANDevice1.xml)
