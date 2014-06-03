# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2014, Hartmut Goebel <h.goebel@goebel-consult.de>

"""
Test cases for L{upnp.core.msearch}
"""

import time

from twisted.trial import unittest
from twisted.internet import protocol
from twisted.test import proto_helpers

from coherence.upnp.core import msearch, ssdp

SSDP_PORT = 1900
SSDP_ADDR = '239.255.255.250'

USN_1 = 'uuid:DDF542FB::urn:service:X_MS_MediaReceiverRegistrar:1'
MSEARCH_RESPONSE_1 = (
    'HTTP/1.1 200 OK',
    'Cache-Control: max-age=1802',
    'Date: Mon, 02 Jun 2014 18:04:59 GMT',
    'Ext: ',
    'Location: http://192.168.1.4:9000/plugins/UPnP/MediaServer.xml',
    'Server: Linux/armv5-linux UPnP/1.0 DLNADOC/1.50 MediaServer/7.3/735',
    'ST: urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1',
    'USN: ' + USN_1,
    )


class TestMSearch(unittest.TestCase):

    def setUp(self):
        self.tr = proto_helpers.FakeDatagramTransport()
        self.ssdp_server = ssdp.SSDPServer(test=True)
        self.ssdp_server.makeConnection(self.tr)
        self.proto = msearch.MSearch(self.ssdp_server, test=True)
        self.proto.makeConnection(self.tr)

    def test_msearch_request(self):
        self.assertEqual(self.ssdp_server._known, {})
        data = '\r\n'.join(MSEARCH_RESPONSE_1) + '\r\n\r\n'
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        self.assertTrue(self.ssdp_server.isKnown(USN_1))
        self.assertFalse(self.ssdp_server.isKnown(USN_1*2))
        service = self.ssdp_server._known[USN_1]
        del service['last-seen']
        self.assertEqual(service, {
            'HOST': '10.20.30.40',
            'ST': 'urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1',
            'LOCATION': 'http://192.168.1.4:9000/plugins/UPnP/MediaServer.xml',
            'USN': USN_1,
            'CACHE-CONTROL': 'max-age=1802',
            'SERVER': 'Linux/armv5-linux UPnP/1.0 DLNADOC/1.50 MediaServer/7.3/735',
            'MANIFESTATION': 'remote',
            'SILENT': False,
            'EXT': '',
            })

    def test_msearch_request_does_not_send_reply(self):
        data = '\r\n'.join(MSEARCH_RESPONSE_1) + '\r\n\r\n'
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        self.assertEqual(self.tr.written, [])

    def test_msearch_request_updates_timestamp(self):
        data = '\r\n'.join(MSEARCH_RESPONSE_1) + '\r\n\r\n'
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        service1 = self.ssdp_server._known[USN_1]
        last_seen1 = service1['last-seen']
        time.sleep(0.5)
        self.proto.datagramReceived(data, ('10.20.30.40', 1234))
        service2 = self.ssdp_server._known[USN_1]
        last_seen2 = service1['last-seen']
        self.assertIs(service1, service2)
        self.assertLess(last_seen1, last_seen2+0.5)

    def test_discover(self):
        self.assertEqual(self.tr.written, [])
        self.proto.discover()
        expected = [(l + '\r\n') for l in [
            'M-SEARCH * HTTP/1.1',
            'HOST: 239.255.255.250:1900',
            'MAN: "ssdp:discover"',
            'MX: 5',
            'ST: ssdp:all',
            ''
            ]]
        # :fixme: What is the reason the notification is send twice?
        self.assertEqual(len(self.tr.written), 1)
        data, (host, port) = self.tr.written[0]
        self.assertEqual((host, port), (SSDP_ADDR, SSDP_PORT))
        recieved = data.splitlines(True)
        self.assertEqual(sorted(recieved), sorted(expected))
