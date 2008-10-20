# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

"""
Test cases for L{upnp.core.DIDLLite}
"""

from copy import copy

from twisted.trial import unittest

from coherence.upnp.core import DIDLLite

didl_fragment = """
<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"
           xmlns:dc="http://purl.org/dc/elements/1.1/"
           xmlns:dlna="urn:schemas-dlna-org:metadata-1-0"
           xmlns:pv="http://www.pv.com/pvns/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
    <container childCount="23" id="1161" parentID="103" restricted="0">
        <dc:title>12</dc:title>
        <upnp:class>object.container.album.musicAlbum</upnp:class>
        <dc:date>1997-02-28T17:20:00+01:00</dc:date>
        <upnp:albumArtURI dlna:profileID="JPEG_TN" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0">http://192.168.1.1:30020/776dec17-1ce1-4c87-841e-cac61a14a2e0/1161?cover.jpg</upnp:albumArtURI>
        <upnp:artist>Herby Sängermeister</upnp:artist>
    </container>
</DIDL-Lite>"""

test_didl_fragment = """
<DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/"
           xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"
           xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite">
    <item id="" restricted="0">
        <dc:title>New Track</dc:title>
        <upnp:class>object.item.audioItem.musicTrack</upnp:class>
        <res protocolInfo="*:*:audio:*">
        </res>
    </item>
</DIDL-Lite>"""

class TestDIDLLite(unittest.TestCase):

    def test_DIDLElement_class_detect(self):
        """ tests class creation from an XML DIDLLite fragment,
            expects a MusicAlbum container in return
        """
        didl_element = DIDLLite.DIDLElement.fromString(didl_fragment)
        items = didl_element.getItems()
        self.assertEqual(len(items),1)
        self.assertTrue(isinstance(items[0],DIDLLite.MusicAlbum))

    def test_DIDLElement_class_2_detect(self):
        """ tests class creation from an XML DIDLLite fragment,
            expects a MusicTrack item in return
        """
        didl_element = DIDLLite.DIDLElement.fromString(test_didl_fragment)
        items = didl_element.getItems()
        self.assertEqual(len(items),1)
        self.assertTrue(isinstance(items[0],DIDLLite.MusicTrack))

    def test_DIDLElement_class_fallback_1(self):
        """ tests class fallback creation from an XML DIDLLite fragment with
            an unknown UPnP class identifier,
            expects an Album container in return
        """
        wrong_didl_fragment = copy(didl_fragment)
        wrong_didl_fragment = wrong_didl_fragment.replace('object.container.album.musicAlbum', 'object.container.album.videoAlbum')
        didl_element = DIDLLite.DIDLElement.fromString(wrong_didl_fragment)
        items = didl_element.getItems()
        self.assertEqual(len(items),1)
        self.assertTrue(isinstance(items[0],DIDLLite.Album))

    def test_DIDLElement_class_fallback_2(self):
        """ tests class fallback creation from an XML DIDLLite fragment with
            an unknown UPnP class identifier,
            expects an Exception.AttributeError
        """
        wrong_didl_fragment = copy(didl_fragment)
        wrong_didl_fragment = wrong_didl_fragment.replace('object.container.album.musicAlbum', 'object.wrongcontainer.wrongalbum.videoAlbum')
        e = None
        try:
            didl_element = DIDLLite.DIDLElement.fromString(wrong_didl_fragment)
        except AttributeError:
            return
        self.assert_(False,"DIDLElement didn't return None from a totally wrong UPnP class identifier")
