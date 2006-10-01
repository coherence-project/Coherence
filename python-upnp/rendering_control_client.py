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

class RenderingControlClient( ServiceClient):

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        #self.service.subscribe()
        #print "RenderingControlClient __init__", self.url

    def list_presets(self, instance_id=0):
        client = self._get_client( "ListPresets")
        d = client.callRemote("ListPresets",
                                InstanceID=instance_id)
        def got_results(results):
            print "list presets: %r" % results
        d.addCallback(got_results)
        return d

    def select_presets(self, instance_id=0, preset_name=''):
        client = self._get_client( "SelectPresets")
        d = client.callRemote("SelectPresets",
                                InstanceID=instance_id,
                                PresetName=preset_name)
        def got_results(results):
            print "select presets: %r" % results
        d.addCallback(got_results)
        return d

    def get_mute(self, instance_id=0, channel='Master'):
        client = self._get_client( "GetMute")
        d = client.callRemote("GetMute",
                                InstanceID=instance_id,
                                Channel=channel)
        def got_results(results):
            print "get mute: %r" % results
        d.addCallback(got_results)
        return d

    def set_mute(self, instance_id=0, channel='Master', desired_mute=0):
        client = self._get_client( "SetMute")
        d = client.callRemote("SetMute",
                                InstanceID=instance_id,
                                Channel=channel,
                                DesiredMute=desired_mute)
        def got_results(results):
            print "set mute: %r" % results
        d.addCallback(got_results)
        return d

    def get_volume(self, instance_id=0, channel='Master'):
        client = self._get_client( "GetVolume")
        d = client.callRemote("GetVolume",
                                InstanceID=instance_id,
                                Channel=channel)
        def got_results(results):
            print "get volume: %r" % results
        d.addCallback(got_results)
        return d

    def set_volume(self, instance_id=0, channel='Master', desired_volume=0):
        client = self._get_client( "SetVolume")
        d = client.callRemote("SetVolume",
                                InstanceID=instance_id,
                                Channel=channel,
                                DesiredVolume=desired_volume)
        def got_results(results):
            print "set volume: %r" % results
        d.addCallback(got_results)
        return d

    def get_volume_db(self, instance_id=0, channel='Master'):
        client = self._get_client( "GetVolumeDB")
        d = client.callRemote("GetVolumeDB",
                                InstanceID=instance_id,
                                Channel=channel)
        def got_results(results):
            print "get volumeDB: %r" % results
        d.addCallback(got_results)
        return d

    def set_volume_db(self, instance_id=0, channel='Master', desired_volume=0):
        client = self._get_client( "SetVolumeDB")
        d = client.callRemote("SetVolumeDB",
                                InstanceID=instance_id,
                                Channel=channel,
                                DesiredVolume=desired_volume)
        def got_results(results):
            print "set volumeDB: %r" % results
        d.addCallback(got_results)
        return d

    def get_volume_db_range(self, instance_id=0, channel='Master'):
        client = self._get_client( "GetVolumeDBRange")
        d = client.callRemote("GetVolumeDBRange",
                                InstanceID=instance_id,
                                Channel=channel)
        def got_results(results):
            print "get volumeDB range: %r" % results
        d.addCallback(got_results)
        return d

    def get_loudness(self, instance_id=0, channel='Master'):
        client = self._get_client( "GetLoudness")
        d = client.callRemote("GetLoudness",
                                InstanceID=instance_id,
                                Channel=channel)
        def got_results(results):
            print "get loudness: %r" % results
        d.addCallback(got_results)
        return d

    def set_loudness(self, instance_id=0, channel='Master', desired_loudness=0):
        client = self._get_client( "SetLoudness")
        d = client.callRemote("SetLoudness",
                                InstanceID=instance_id,
                                Channel=channel,
                                DesiredLoudness=desired_loudnesse)
        def got_results(results):
            print "set loudness: %r" % results
        d.addCallback(got_results)
        return d

    def _failure(self, error):
        log.msg(error.getTraceback(), debug=True)
        error.trap(Exception)
