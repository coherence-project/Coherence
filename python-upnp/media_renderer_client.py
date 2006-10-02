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
from soap_proxy import SOAPProxy

from connection_manager_client import ConnectionManagerClient
from rendering_control_client import RenderingControlClient
from av_transport_client import AVTransportClient


global work, pending
work = []
pending = {}


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

    def state_variable_change( self, variable):
        print variable.name, 'changed from', variable.old_value, 'to', variable.value

