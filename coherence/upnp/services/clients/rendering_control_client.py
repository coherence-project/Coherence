# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

class RenderingControlClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.subscribe()
        self.service.client = self
        #print "RenderingControlClient __init__", self.url

    #def __del__(self):
    #    #print "RenderingControlClient deleted"
    #    pass

    def remove(self):
        self.service.remove()
        self.service = None
        self.namespace = None
        self.url = None
        del self

    def subscribe_for_variable(self, var_name, callback,signal=False):
        self.service.subscribe_for_variable(var_name, instance=0, callback=callback,signal=signal)

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