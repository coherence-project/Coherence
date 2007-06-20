# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from coherence.upnp.services.clients.connection_manager_client import ConnectionManagerClient
from coherence.upnp.services.clients.content_directory_client import ContentDirectoryClient
from coherence.upnp.services.clients.av_transport_client import AVTransportClient

from coherence import log

class MediaServerClient(log.Loggable):
    logCategory = 'ms_client'
    
    def __init__(self, device):
        self.device = device
        self.device_type,self.version = device.get_device_type().split(':')[3:5]
        self.scheduled_recording = None
        self.content_directory = None
        self.connection_manager = None
        self.av_transport = None
        for service in self.device.get_services():
            if service.get_type() in ["urn:schemas-upnp-org:service:ContentDirectory:1",
                                      "urn:schemas-upnp-org:service:ContentDirectory:2"]:
                self.content_directory = ContentDirectoryClient( service)
            if service.get_type() in ["urn:schemas-upnp-org:service:ConnectionManager:1",
                                      "urn:schemas-upnp-org:service:ConnectionManager:2"]:
                self.connection_manager = ConnectionManagerClient( service)
            if service.get_type() in ["urn:schemas-upnp-org:service:AVTransport:1",
                                      "urn:schemas-upnp-org:service:AVTransport:2"]:
                self.av_transport = AVTransportClient( service)
            #if service.get_type()  in ["urn:schemas-upnp-org:service:ScheduledRecording:1",
            #                           "urn:schemas-upnp-org:service:ScheduledRecording:2"]:    
            #    self.scheduled_recording = ScheduledRecordingClient( service)
        self.info("MediaServer %s" % (self.device.get_friendly_name()))
        if self.content_directory:
            self.info("ContentDirectory available")
        else:
            self.warning("ContentDirectory not available, device not implemented properly according to the UPnP specification")
            return
        if self.connection_manager:
            self.info("ConnectionManager available")
        else:
            self.warning("ConnectionManager not available, device not implemented properly according to the UPnP specification")
            return
        if self.av_transport:
            self.info("AVTransport (optional) available")
        if self.scheduled_recording:
            self.info("ScheduledRecording (optional) available")
            
        #d = self.content_directory.browse(0, recursive=False) # browse top level
        #d.addCallback( self.process_meta)
        
    def __del__(self):
        #print "MediaServerClient deleted"
        pass
        
    def remove(self):
        self.info("removal of MediaServerClient started")
        if self.content_directory != None:
            del self.content_directory
        if self.connection_manager != None:
            del self.connection_manager
        if self.av_transport != None:
            del self.av_transport
        if self.scheduled_recording != None:
            del self.scheduled_recording
        del self
        
    def state_variable_change( self, variable):
        self.info(variable.name, 'changed from', variable.old_value, 'to', variable.value)

    def print_results(self, results):
        self.info("results=", results)

    def process_meta( self, results):
        for k,v in results.iteritems():
            dfr = self.content_directory.browse(k, "BrowseMetadata")
            dfr.addCallback( self.print_results)

