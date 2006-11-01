# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from connection_manager_client import ConnectionManagerClient
from rendering_control_client import RenderingControlClient
from av_transport_client import AVTransportClient

class MediaRendererClient:

    def __init__(self, device):
        self.device = device
        self.rendering_control = None
        self.connection_manager = None
        self.av_transport = None
        for service in self.device.get_services():
            if service.get_type() == "urn:schemas-upnp-org:service:RenderingControl:1":    
                self.rendering_control = RenderingControlClient( service)
            if service.get_type() == "urn:schemas-upnp-org:service:ConnectionManager:1":
                self.connection_manager = ConnectionManagerClient( service)
            if service.get_type() == "urn:schemas-upnp-org:service:AVTransport:1":
                self.av_transport = AVTransportClient( service)
        print "MediaRenderer %s:" % (self.device.get_friendly_name())
        if self.rendering_control:
            print "RenderingControl available"
            """
            actions =  self.rendering_control.service.get_actions()
            print actions
            for action in actions:
                print "Action:", action
                for arg in actions[action].get_arguments_list():
                    print "       ", arg
            """
        else:
            print "RenderingControl not available, device not implemented properly according to the UPnP specification"
            return
        if self.connection_manager:
            print "ConnectionManager available"
        else:
            print "ConnectionManager not available, device not implemented properly according to the UPnP specification"
            return
        if self.av_transport:
            print "AVTransport (optional) available"
        #self.connection_manager.get_protocol_info()
        #self.rendering_control.list_presets()
        #self.rendering_control.get_mute()
        #self.rendering_control.get_volume()
        #self.rendering_control.set_mute(desired_mute=1)
        self.av_transport.service.subscribe_for_variable('LastChange', 0, self.state_variable_change)
        self.av_transport.service.subscribe_for_variable('TransportState', 0, self.state_variable_change)
        self.av_transport.service.subscribe_for_variable('CurrentTransportActions', 0, self.state_variable_change)
        self.av_transport.get_transport_info()
        self.av_transport.get_current_transport_actions()

    def state_variable_change( self, variable):
        print variable.name, 'changed from', variable.old_value, 'to', variable.value

