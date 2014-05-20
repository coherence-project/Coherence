# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>
# Copyright 2014, Hartmut Goebel <h.goebel@crazy-compilers.com>

from .basics import BasicClient
from ..services.clients.connection_manager_client import ConnectionManagerClient
from ..services.clients.content_directory_client import ContentDirectoryClient
from ..services.clients.av_transport_client import AVTransportClient


class MediaServerClient(BasicClient):
    logCategory = 'ms_client'

    _service_definition = (
        ('content_directory', ContentDirectoryClient, True,
         ["urn:schemas-upnp-org:service:ContentDirectory:1",
          "urn:schemas-upnp-org:service:ContentDirectory:2"]),
        ('connection_manager', ConnectionManagerClient, True,
          ["urn:schemas-upnp-org:service:ConnectionManager:1",
           "urn:schemas-upnp-org:service:ConnectionManager:2"]),
        ('av_transport', AVTransportClient, False,
         ["urn:schemas-upnp-org:service:AVTransport:1",
          "urn:schemas-upnp-org:service:AVTransport:2"]),
        ## ScheduledRecordingClient is not yet implemented
        ## ('scheduled_recording', ScheduledRecordingClient, False,
        ##  ["urn:schemas-upnp-org:service:ScheduledRecording:1",
        ##   "urn:schemas-upnp-org:service:ScheduledRecording:2"]),
        )

    def print_results(self, results):
        self.info("results= %s", results)

    def process_meta(self, results):
        for k, v in results.iteritems():
            dfr = self.content_directory.browse(k, "BrowseMetadata")
            dfr.addCallback(self.print_results)
