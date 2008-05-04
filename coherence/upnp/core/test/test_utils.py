# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

"""
Test cases for L{upnp.core.utils}
"""

from twisted.trial import unittest

from coherence.upnp.core.utils import *

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
        newData = de_chunk_payload(testData)
        # see whether we can parse the result
        self.assertEqual(newData, '\r\n'.join( testChunkedDataResult))


# $Id:$
