# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from coherence.upnp.services.clients.connection_manager_client import ConnectionManagerClient
from coherence.upnp.services.clients.rendering_control_client import RenderingControlClient
from coherence.upnp.services.clients.av_transport_client import AVTransportClient

from coherence import log

import coherence.extern.louie as louie

class MediaRendererClient(log.Loggable):
    logCategory = 'mr_client'

    def __init__(self, device):
        self.device = device
        self.device_type = self.device.get_friendly_device_type()
        self.version = int(self.device.get_device_type_version())
        self.icons = device.icons
        self.rendering_control = None
        self.connection_manager = None
        self.av_transport = None

        self.detection_completed = False

        louie.connect(self.service_notified, signal='Coherence.UPnP.DeviceClient.Service.notified', sender=self.device)

        for service in self.device.get_services():
            if service.get_type() in ["urn:schemas-upnp-org:service:RenderingControl:1",
                                      "urn:schemas-upnp-org:service:RenderingControl:2"]:
                self.rendering_control = RenderingControlClient( service)
            if service.get_type() in ["urn:schemas-upnp-org:service:ConnectionManager:1",
                                      "urn:schemas-upnp-org:service:ConnectionManager:2"]:
                self.connection_manager = ConnectionManagerClient( service)
            if service.get_type() in ["urn:schemas-upnp-org:service:AVTransport:1",
                                      "urn:schemas-upnp-org:service:AVTransport:2"]:
                self.av_transport = AVTransportClient( service)
        self.info("MediaRenderer %s" % (self.device.get_friendly_name()))
        if self.rendering_control:
            self.info("RenderingControl available")
            """
            actions =  self.rendering_control.service.get_actions()
            print actions
            for action in actions:
                print "Action:", action
                for arg in actions[action].get_arguments_list():
                    print "       ", arg
            """
            #self.rendering_control.list_presets()
            #self.rendering_control.get_mute()
            #self.rendering_control.get_volume()
            #self.rendering_control.set_mute(desired_mute=1)
        else:
            self.warning("RenderingControl not available, device not implemented properly according to the UPnP specification")
            return
        if self.connection_manager:
            self.info("ConnectionManager available")
            #self.connection_manager.get_protocol_info()
        else:
            self.warning("ConnectionManager not available, device not implemented properly according to the UPnP specification")
            return
        if self.av_transport:
            self.info("AVTransport (optional) available")
            #self.av_transport.service.subscribe_for_variable('LastChange', 0, self.state_variable_change)
            #self.av_transport.service.subscribe_for_variable('TransportState', 0, self.state_variable_change)
            #self.av_transport.service.subscribe_for_variable('CurrentTransportActions', 0, self.state_variable_change)
            #self.av_transport.get_transport_info()
            #self.av_transport.get_current_transport_actions()

    #def __del__(self):
    #    #print "MediaRendererClient deleted"
    #    pass

    def remove(self):
        self.info("removal of MediaRendererClient started")
        if self.rendering_control != None:
            self.rendering_control.remove()
        if self.connection_manager != None:
            self.connection_manager.remove()
        if self.av_transport != None:
            self.av_transport.remove()
        #del self

    def service_notified(self, service):
        self.info("Service %r sent notification" % service);
        if self.detection_completed == True:
            return
        if self.rendering_control != None:
            if not hasattr(self.rendering_control.service, 'last_time_updated'):
                return
            if self.rendering_control.service.last_time_updated == None:
                return
        if self.connection_manager != None:
            if not hasattr(self.connection_manager.service, 'last_time_updated'):
                return
            if self.connection_manager.service.last_time_updated == None:
                return
        if self.av_transport != None:
            if not hasattr(self.av_transport.service, 'last_time_updated'):
                return
            if self.av_transport.service.last_time_updated == None:
                return
        self.detection_completed = True
        louie.send('Coherence.UPnP.DeviceClient.detection_completed', None,
                               client=self,udn=self.device.udn)

    def state_variable_change( self, variable):
        self.info(variable.name, 'changed from', variable.old_value, 'to', variable.value)
