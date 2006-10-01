# Elisa - Home multimedia server
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# All rights reserved.
# 
# This software is available under three license agreements.
# 
# There are various plugins and extra modules for Elisa licensed
# under the MIT license. For instance our upnp module uses this license.
# 
# The core of Elisa is licensed under GPL version 2.
# See "LICENSE.GPL" in the root of this distribution including a special 
# exception to use Elisa with Fluendo's plugins.
# 
# The GPL part is also available under a commerical licensing
# agreement.
# 
# The second license is the Elisa Commercial License Agreement.
# This license agreement is available to licensees holding valid
# Elisa Commercial Agreement licenses.
# See "LICENSE.Elisa" in the root of this distribution.

from twisted.internet import reactor, defer
from twisted.python import log
import sys, threading
import DIDLLite, utils

from service import ServiceClient

class AVTransportClient( ServiceClient):

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.subscribe()
        print "AVTransportClient __init__", self.url

    def set_av_transport_uri(self, instance_id=0, current_uri='', current_uri_metadata='<dc:title>Test</dc:title>'):
        client = self._get_client("SetAVTransportURI")
        d = client.callRemote("SetAVTransportURI",
                                    InstanceID=instance_id,
                                    CurrentURI=current_uri,
                                    CurrentURIMetaData=current_uri_metadata)
        def got_results(results):
            print "set_av_transport_uri: %r" % results
        d.addCallback(got_results)
        return d

    def set_next_av_transport_uri(self, instance_id=0, next_uri='', next_uri_metadata=''):
        client = self._get_client("SetAVTransportURI")
        d = client.callRemote("SetAVTransportURI",
                                    InstanceID=instance_id,
                                    NextURI=next_uri,
                                    NextURIMetaData=next_uri_metadata)
        def got_results(results):
            print "set_next_av_transport_uri: %r" % results
        d.addCallback(got_results)
        return d

    def get_media_info(self, instance_id=0):
        client = self._get_client("GetMediaInfo")
        d = client.callRemote("GetMediaInfo",
                                InstanceID=instance_id)
        def got_results(results):
            print "get_media_info: %r" % results
        d.addCallback(got_results)
        return d
        
    def get_media_info_ext(self, instance_id=0):
        client = self._get_client("GetMediaInfo_Ext")
        d = client.callRemote("GetMediaInfo_Ext",
                                InstanceID=instance_id)
        def got_results(results):
            print "get_media_info: %r" % results
        d.addCallback(got_results)
        return d

    def get_transport_info(self, instance_id=0):
        client = self._get_client("GetTransportInfo")
        d = client.callRemote("GetTransportInfo",
                                InstanceID=instance_id)
        def got_results(results):
            print "get_transport_info: %r" % results
        d.addCallback(got_results)
        return d
        
    def get_position_info(self, instance_id=0):
        client = self._get_client("GetPositionInfo")
        d = client.callRemote("GetPositionInfo",
                                InstanceID=instance_id)
        def got_results(results):
            print "get_position_info: %r" % results
        d.addCallback(got_results)
        return d
        
    def get_device_capabilities(self, instance_id=0):
        client = self._get_client("GetDeviceCapabilities")
        d = client.callRemote("GetDeviceCapabilities",
                                InstanceID=instance_id)
        def got_results(results):
            print "get_device_capabilities: %r" % results
        d.addCallback(got_results)
        return d

    def get_transport_settings(self, instance_id=0):
        client = self._get_client("GetTransportSettings")
        d = client.callRemote("GetTransportSettings",
                                InstanceID=instance_id)
        def got_results(results):
            print "get_transport_settings: %r" % results
        d.addCallback(got_results)
        return d

    def pause(self, instance_id=0):
        client = self._get_client("Pause")
        d = client.callRemote("Pause",
                                InstanceID=instance_id)
        def got_results(results):
            print "pause: %r" % results
        d.addCallback(got_results)
        return d

    def play(self, instance_id=0):
        client = self._get_client("Play")
        d = client.callRemote("Play",
                                InstanceID=instance_id)
        def got_results(results):
            print "play: %r" % results
        d.addCallback(got_results)
        return d

    def stop(self, instance_id=0):
        client = self._get_client("Stop")
        d = client.callRemote("Stop",
                                InstanceID=instance_id)
        def got_results(results):
            print "stop: %r" % results
        d.addCallback(got_results)
        return d

    def record(self, instance_id=0):
        client = self._get_client("Record")
        d = client.callRemote("Record",
                                InstanceID=instance_id)
        def got_results(results):
            print "record: %r" % results
        d.addCallback(got_results)
        return d

    def seek(self, instance_id=0, unit='', target=0):
        client = self._get_client("Seek")
        d = client.callRemote("Seek",
                                    InstanceID=instance_id,
                                    Unit=unit,
                                    Target=target)
        def got_results(results):
            print "seek: %r" % results
        d.addCallback(got_results)
        return d
        
    def next(self, instance_id=0):
        print "next"
        client = self._get_client("Next")
        d = client.callRemote("Next",
                                InstanceID=instance_id)
        def got_results(results):
            print "next: %r" % results
        d.addCallback(got_results)
        return d
        
    def previous(self, instance_id=0):
        print "previous"
        client = self._get_client("Previous")
        d = client.callRemote("Previous",
                                InstanceID=instance_id)
        def got_results(results):
            print "previous: %r" % results
        d.addCallback(got_results)
        return d

