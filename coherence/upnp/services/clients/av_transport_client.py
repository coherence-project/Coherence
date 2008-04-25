# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006-2008, Frank Scholz <coherence@beebits.net>

from coherence import log

class AVTransportClient(log.Loggable):
    logCategory = 'avtransportclient'

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.subscribe()
        self.service.client = self

    #def __del__(self):
    #    #print "AVTransportClient deleted"
    #    pass

    def remove(self):
        self.service.remove()
        self.service = None
        self.namespace = None
        self.url = None
        del self

    def subscribe_for_variable(self, var_name, callback,signal=False):
        self.service.subscribe_for_variable(var_name, instance=0, callback=callback,signal=signal)

    def set_av_transport_uri(self, instance_id=0, current_uri='', current_uri_metadata=''):
        action = self.service.get_action('SetAVTransportURI')
        return action.call( InstanceID=instance_id,
                            CurrentURI=current_uri,
                            CurrentURIMetaData=current_uri_metadata)

    def set_next_av_transport_uri(self, instance_id=0, next_uri='', next_uri_metadata=''):
        action = self.service.get_action('SetNextAVTransportURI')
        if action:  # optional
            return action.call( InstanceID=instance_id,
                            NextURI=next_uri,
                            NextURIMetaData=next_uri_metadata)
        return None

    def get_media_info(self, instance_id=0):
        action = self.service.get_action('GetMediaInfo')
        return action.call( InstanceID=instance_id)

    def get_media_info_ext(self, instance_id=0):
        action = self.service.get_action('GetMediaInfo_Ext')
        return action.call( InstanceID=instance_id)

    def get_transport_info(self, instance_id=0):
        action = self.service.get_action('GetTransportInfo')
        return action.call( InstanceID=instance_id)

    def get_position_info(self, instance_id=0):
        action = self.service.get_action('GetPositionInfo')
        return action.call( InstanceID=instance_id)

    def get_device_capabilities(self, instance_id=0):
        action = self.service.get_action('GetDeviceCapabilities')
        return action.call( InstanceID=instance_id)

    def get_transport_settings(self, instance_id=0):
        action = self.service.get_action('GetTransportSettings')
        return action.call( InstanceID=instance_id)

    def pause(self, instance_id=0):
        action = self.service.get_action('Pause')
        if action:  # optional
            return action.call( InstanceID=instance_id)
        return None

    def play(self, instance_id=0, speed=1):
        action = self.service.get_action('Play')
        return action.call( InstanceID=instance_id,Speed=speed)

    def stop(self, instance_id=0):
        action = self.service.get_action('Stop')
        return action.call( InstanceID=instance_id)

    def record(self, instance_id=0):
        action = self.service.get_action('Record')
        if action:  # optional
            return action.call( InstanceID=instance_id)
        return None

    def seek(self, instance_id=0, unit='', target=0):
        action = self.service.get_action('Seek')
        return action.call( InstanceID=instance_id,
                            Unit=unit,
                            Target=target)

    def next(self, instance_id=0):
        action = self.service.get_action('Next')
        return action.call( InstanceID=instance_id)

    def previous(self, instance_id=0):
        action = self.service.get_action('Previous')
        return action.call( InstanceID=instance_id)

    def get_current_transport_actions(self, instance_id=0):
        action = self.service.get_action('GetCurrentTransportActions')
        return action.call( InstanceID=instance_id)
