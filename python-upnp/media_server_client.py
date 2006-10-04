# Python UPnP Framework
# Copyright (C) 2006 Frank Scholz (dev@netzflocken.de)
# All rights reserved.
# 
# This software is available under three licence agreements.
# 
# There are some parts and extra modules for the Python UPnP Framework licenced
# under the MIT licence.
# 
# The core of the Python UPnP Framework is licenced under GPL version 2.
# See "LICENCE.GPL" in the root of this distribution
# 
# The GPL part is also available under a commerical licencing
# agreement.
# 
# The third licence is the Python UPnP Framework Commercial Licence Agreement.
# See "LICENCE" in the root of this distribution

from connection_manager_client import ConnectionManagerClient
from content_directory_client import ContentDirectoryClient
from av_transport_client import AVTransportClient

class MediaServerClient:

    def __init__(self, device):
        self.device = device
        self.scheduled_recording = None
        self.content_directoy = None
        self.connection_manager = None
        self.av_transport = None
        for service in self.device.get_services():
            if service.get_type() in ["urn:schemas-upnp-org:service:ContentDirectory:1",
                                      "urn:schemas-upnp-org:service:ContentDirectory:2"]:
                self.content_directoy = ContentDirectoryClient( service)
            if service.get_type() in ["urn:schemas-upnp-org:service:ConnectionManager:1",
                                      "urn:schemas-upnp-org:service:ConnectionManager:2"]:
                self.connection_manager = ConnectionManagerClient( service)
            if service.get_type() in ["urn:schemas-upnp-org:service:AVTransport:1",
                                      "urn:schemas-upnp-org:service:AVTransport:2"]:
                self.av_transport = AVTransportClient( service)
            #if service.get_type()  in ["urn:schemas-upnp-org:service:ScheduledRecording:1",
            #                           "urn:schemas-upnp-org:service:ScheduledRecording:2"]:    
            #    self.scheduled_recording = ScheduledRecordingClient( service)
        print "MediaServer %s:" % (self.device.get_friendly_name())
        if self.content_directoy:
            print "ContentDirectory available"
        else:
            print "ContentDirectory not available, device not implemented properly according to the UPnP specification"
            return
        if self.connection_manager:
            print "ConnectionManager available"
        else:
            print "ConnectionManager not available, device not implemented properly according to the UPnP specification"
            return
        if self.av_transport:
            print "AVTransport (optional) available"
        if self.scheduled_recording:
            print "ScheduledRecording (optional) available"

    def state_variable_change( self, variable):
        print variable.name, 'changed from', variable.old_value, 'to', variable.value

