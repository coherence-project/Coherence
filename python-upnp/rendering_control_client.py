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

class RenderingControlClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        #self.service.subscribe()
        #print "RenderingControlClient __init__", self.url

    def list_presets(self, instance_id=0):
        action = self.service.get_action('ListPresets')
        return action.call(InstanceID=instance_id)

    def select_presets(self, instance_id=0, preset_name=''):
        action = self.service.get_action('SelectPresets')
        return action.call( InstanceID=instance_id,
                            PresetName=preset_name)

    def get_mute(self, instance_id=0, channel='Master'):
        action = self.service.get_action('GetMute')
        return action.call( InstanceID=instance_id,
                            Channel=channel)

    def set_mute(self, instance_id=0, channel='Master', desired_mute=0):
        action = self.service.get_action('SetMute')
        return action.call( InstanceID=instance_id,
                            Channel=channel,
                            DesiredMute=desired_mute)

    def get_volume(self, instance_id=0, channel='Master'):
        action = self.service.get_action('GetVolume')
        return action.call( InstanceID=instance_id,
                            Channel=channel)

    def set_volume(self, instance_id=0, channel='Master', desired_volume=0):
        action = self.service.get_action('SetVolume')
        return action.call( InstanceID=instance_id,
                            Channel=channel,
                            DesiredVolume=desired_volume)

    def get_volume_db(self, instance_id=0, channel='Master'):
        action = self.service.get_action('GetVolumeDB')
        return action.call( InstanceID=instance_id,
                            Channel=channel)

    def set_volume_db(self, instance_id=0, channel='Master', desired_volume=0):
        action = self.service.get_action('SetVolumeDB')
        return action.call( InstanceID=instance_id,
                            Channel=channel,
                            DesiredVolume=desired_volume)

    def get_volume_db_range(self, instance_id=0, channel='Master'):
        action = self.service.get_action('GetVolumeDBRange')
        return action.call( InstanceID=instance_id,
                            Channel=channel)

    def get_loudness(self, instance_id=0, channel='Master'):
        action = self.service.get_action('GetLoudness')
        return action.call( InstanceID=instance_id,
                            Channel=channel)

    def set_loudness(self, instance_id=0, channel='Master', desired_loudness=0):
        action = self.service.get_action('SetLoudness')
        return action.call( InstanceID=instance_id,
                            Channel=channel,
                            DesiredLoudness=desired_loudness)