# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

"""
Test cases for L{upnp.core.utils}
"""

import os
from twisted.trial import unittest
from twisted.python.filepath import FilePath
from twisted.internet import reactor
from twisted.web import static, server
from twisted.protocols import policies

from coherence.upnp.core import utils

# This data is joined using CRLF pairs.
testChunkedData = ['200',
'<?xml version="1.0" ?> ',
'<root xmlns="urn:schemas-upnp-org:device-1-0">',
'	<specVersion>',
'		<major>1</major> ',
'		<minor>0</minor> ',
'	</specVersion>',
'	<device>',
'		<deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType> ',
'		<friendlyName>DMA201</friendlyName> ',
'		<manufacturer>   </manufacturer> ',
'		<manufacturerURL>   </manufacturerURL> ',
'		<modelDescription>DMA201</modelDescription> ',
'		<modelName>DMA</modelName> ',
'		<modelNumber>201</modelNumber> ',
'		<modelURL>   </modelURL> ',
'		<serialNumber>0',
'200',
'00000000001</serialNumber> ',
'		<UDN>uuid:BE1C49F2-572D-3617-8F4C-BB1DEC3954FD</UDN> ',
'		<UPC /> ',
'		<serviceList>',
'			<service>',
'				<serviceType>urn:schemas-upnp-org:service:ConnectionManager:1</serviceType>',
'				<serviceId>urn:upnp-org:serviceId:ConnectionManager</serviceId>',
'				<controlURL>http://10.63.1.113:4444/CMSControl</controlURL>',
'				<eventSubURL>http://10.63.1.113:4445/CMSEvent</eventSubURL>',
'				<SCPDURL>/upnpdev.cgi?file=/ConnectionManager.xml</SCPDURL>',
'			</service>',
'			<service>',
'				<serv',
'223',
'iceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>',
'				<serviceId>urn:upnp-org:serviceId:AVTransport</serviceId>',
'				<controlURL>http://10.63.1.113:4444/AVTControl</controlURL>',
'				<eventSubURL>http://10.63.1.113:4445/AVTEvent</eventSubURL>',
'				<SCPDURL>/upnpdev.cgi?file=/AVTransport.xml</SCPDURL>',
'			</service>',
'			<service>',
'				<serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType>',
'				<serviceId>urn:upnp-org:serviceId:RenderingControl</serviceId>',
'				<controlURL>http://10.63.1.113:4444/RCSControl</',
'c4',
'controlURL>',
'				<eventSubURL>http://10.63.1.113:4445/RCSEvent</eventSubURL>',
'				<SCPDURL>/upnpdev.cgi?file=/RenderingControl.xml</SCPDURL>',
'			</service>',
'		</serviceList>',
'	</device>',
'</root>'
'',
'0',
'']

testChunkedDataResult = ['<?xml version="1.0" ?> ',
'<root xmlns="urn:schemas-upnp-org:device-1-0">',
'	<specVersion>',
'		<major>1</major> ',
'		<minor>0</minor> ',
'	</specVersion>',
'	<device>',
'		<deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType> ',
'		<friendlyName>DMA201</friendlyName> ',
'		<manufacturer>   </manufacturer> ',
'		<manufacturerURL>   </manufacturerURL> ',
'		<modelDescription>DMA201</modelDescription> ',
'		<modelName>DMA</modelName> ',
'		<modelNumber>201</modelNumber> ',
'		<modelURL>   </modelURL> ',
'		<serialNumber>000000000001</serialNumber> ',
'		<UDN>uuid:BE1C49F2-572D-3617-8F4C-BB1DEC3954FD</UDN> ',
'		<UPC /> ',
'		<serviceList>',
'			<service>',
'				<serviceType>urn:schemas-upnp-org:service:ConnectionManager:1</serviceType>',
'				<serviceId>urn:upnp-org:serviceId:ConnectionManager</serviceId>',
'				<controlURL>http://10.63.1.113:4444/CMSControl</controlURL>',
'				<eventSubURL>http://10.63.1.113:4445/CMSEvent</eventSubURL>',
'				<SCPDURL>/upnpdev.cgi?file=/ConnectionManager.xml</SCPDURL>',
'			</service>',
'			<service>',
'				<serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>',
'				<serviceId>urn:upnp-org:serviceId:AVTransport</serviceId>',
'				<controlURL>http://10.63.1.113:4444/AVTControl</controlURL>',
'				<eventSubURL>http://10.63.1.113:4445/AVTEvent</eventSubURL>',
'				<SCPDURL>/upnpdev.cgi?file=/AVTransport.xml</SCPDURL>',
'			</service>',
'			<service>',
'				<serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType>',
'				<serviceId>urn:upnp-org:serviceId:RenderingControl</serviceId>',
'				<controlURL>http://10.63.1.113:4444/RCSControl</controlURL>',
'				<eventSubURL>http://10.63.1.113:4445/RCSEvent</eventSubURL>',
'				<SCPDURL>/upnpdev.cgi?file=/RenderingControl.xml</SCPDURL>',
'			</service>',
'		</serviceList>',
'	</device>',
'</root>',
''
]

class TestUpnpUtils(unittest.TestCase):

    def test_chunked_data(self):
        """ tests proper reassembling of a chunked http-response
            based on a test and data provided by Lawrence
        """
        testData = '\r\n'.join(testChunkedData)
        newData = utils.de_chunk_payload(testData)
        # see whether we can parse the result
        self.assertEqual(newData, '\r\n'.join( testChunkedDataResult))


class TestClient(unittest.TestCase):

    def _listen(self, site):
        return reactor.listenTCP(0, site, interface="127.0.0.1")

    def setUp(self):
        name = self.mktemp()
        os.mkdir(name)
        FilePath(name).child("file").setContent("0123456789")
        r = static.File(name)
        self.site = server.Site(r, timeout=None)
        self.wrapper = policies.WrappingFactory(self.site)
        self.port = self._listen(self.wrapper)
        self.portno = self.port.getHost().port

    def tearDown(self):
        return self.port.stopListening()

    def getURL(self, path):
        return "http://127.0.0.1:%d/%s" % (self.portno, path)

    def assertResponse(self, original, content, headers):
        self.assertIsInstance(original, tuple)
        self.assertEqual(original[0], content)
        originalHeaders = original[1]
        for header in headers:
            self.assertIn(header, originalHeaders)
            self.assertEqual(originalHeaders[header], headers[header])

    def test_getPage(self):
        content = '0123456789'
        headers = {'accept-ranges': ['bytes'],
                   'content-length': ['10'],
                   'content-type': ['text/html']}
        d = utils.getPage(self.getURL("file"))
        d.addCallback(self.assertResponse, content, headers)
        return d



# $Id:$
