# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2014, Hartmut Goebel <h.goebel@goebel-consult.de>

"""
Test cases for L{upnp.core.sspd}
"""

import time

from twisted.trial import unittest
from twisted.internet import protocol
from twisted.test import proto_helpers

from coherence.upnp.core import ssdp

SSDP_PORT = 1900
SSDP_ADDR = '239.255.255.250'

USN_1 = 'uuid:e711a4bf::upnp:rootdevice'
SSDP_NOTIFY_1 = (
    'NOTIFY * HTTP/1.1',
    'Host:239.255.255.250:1900',
    'NT:upnp:rootdevice',
    'NTS:ssdp:alive',
    'Location:http://10.10.222.94:2869/upnp?content=uuid:e711a4bf',
    'USN: ' + USN_1,
    'Cache-Control: max-age=1842',
    'Server:Microsoft-Windows-NT/5.1 UPnP/1.0 UPnP-Device-Host/1.0',
    )


class TestSSDP(unittest.TestCase):

    def setUp(self):
        self.proto = ssdp.SSDPServer(test=True)
        self.tr = proto_helpers.FakeDatagramTransport()
        self.proto.makeConnection(self.tr)

    def test_ssdp_notify(self):
        self.assertEqual(self.proto._known, {})
        data = '\r\n'.join(SSDP_NOTIFY_1) + '\r\n\r\n'
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        self.assertTrue(self.proto.isKnown(USN_1))
        self.assertFalse(self.proto.isKnown(USN_1*2))
        service = self.proto._known[USN_1]
        del service['last-seen']
        self.assertEqual(service, {
            'HOST': '10.20.30.40',
            'ST': 'upnp:rootdevice',
            'LOCATION': 'http://10.10.222.94:2869/upnp?content=uuid:e711a4bf',
            'USN': 'uuid:e711a4bf::upnp:rootdevice',
            'CACHE-CONTROL': 'max-age=1842',
            'SERVER': 'Microsoft-Windows-NT/5.1 UPnP/1.0 UPnP-Device-Host/1.0',
            'MANIFESTATION': 'remote',
            'SILENT': False,
            'EXT': '',
            })

    def test_ssdp_notify_does_not_send_reply(self):
        data = '\r\n'.join(SSDP_NOTIFY_1) + '\r\n\r\n'
        self.proto.datagramReceived(data, ('127.0.0.1', 1234))
        self.assertEqual(self.tr.written, [])

    def test_ssdp_notify_updates_timestamp(self):
        data = '\r\n'.join(SSDP_NOTIFY_1) + '\r\n\r\n'
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        service1 = self.proto._known[USN_1]
        last_seen1 = service1['last-seen']
        time.sleep(0.5)
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        service2 = self.proto._known[USN_1]
        last_seen2 = service1['last-seen']
        self.assertIs(service1, service2)
        self.assertLess(last_seen1, last_seen2+0.5)

    def test_doNotify(self):
        data = '\r\n'.join(SSDP_NOTIFY_1) + '\r\n\r\n'
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        self.assertEqual(self.tr.written, [])
        self.proto.doNotify('uuid:e711a4bf::upnp:rootdevice')
        expected = [(l + '\r\n') for l in [
            'NOTIFY * HTTP/1.1',
            'HOST: 239.255.255.250:1900',
            'NT: upnp:rootdevice',
            'NTS: ssdp:alive',
            'EXT: ',
            'LOCATION: http://10.10.222.94:2869/upnp?content=uuid:e711a4bf',
            'USN: ' + USN_1,
            'CACHE-CONTROL: max-age=1842',
            'SERVER: Microsoft-Windows-NT/5.1 UPnP/1.0 UPnP-Device-Host/1.0',
            ''
            ]]
        # :fixme: What is the reason the notification is send twice?
        self.assertEqual(len(self.tr.written), 2)
        self.assertEqual(self.tr.written[0], self.tr.written[1])
        data, (host, port) = self.tr.written[0]
        self.assertEqual((host, port), (SSDP_ADDR, SSDP_PORT))
        recieved = data.splitlines(True)
        self.assertEqual(sorted(recieved), sorted(expected))

    def test_doByebye(self):
        data = '\r\n'.join(SSDP_NOTIFY_1) + '\r\n\r\n'
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        self.assertEqual(self.tr.written, [])
        self.proto.doByebye('uuid:e711a4bf::upnp:rootdevice')
        expected = [(l + '\r\n') for l in [
            'NOTIFY * HTTP/1.1',
            'HOST: 239.255.255.250:1900',
            'NT: upnp:rootdevice',
            'NTS: ssdp:byebye',
            'EXT: ',
            'LOCATION: http://10.10.222.94:2869/upnp?content=uuid:e711a4bf',
            'USN: ' + USN_1,
            'CACHE-CONTROL: max-age=1842',
            'SERVER: Microsoft-Windows-NT/5.1 UPnP/1.0 UPnP-Device-Host/1.0',
            ''
            ]]
        self.assertEqual(len(self.tr.written), 1)
        data, (host, port) = self.tr.written[0]
        self.assertEqual((host, port), (SSDP_ADDR, SSDP_PORT))
        recieved = data.splitlines(True)
        self.assertEqual(sorted(recieved), sorted(expected))
