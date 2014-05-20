# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>
# Copyright 2014, Hartmut Goebel <h.goebel@crazy-compilers.com>

from .basics import BasicClient
from ..services.clients.connection_manager_client import ConnectionManagerClient
from ..services.clients.rendering_control_client import RenderingControlClient
from ..services.clients.av_transport_client import AVTransportClient

class MediaRendererClient(BasicClient):
    logCategory = 'mr_client'

    _service_definition = (
        ('rendering_control', RenderingControlClient, True,
         ["urn:schemas-upnp-org:service:RenderingControl:1",
          "urn:schemas-upnp-org:service:RenderingControl:2"]),
        ('connection_manager', ConnectionManagerClient, True,
         ["urn:schemas-upnp-org:service:ConnectionManager:1",
          "urn:schemas-upnp-org:service:ConnectionManager:2"]),
        ('av_transport', AVTransportClient, False,
         ["urn:schemas-upnp-org:service:AVTransport:1",
          "urn:schemas-upnp-org:service:AVTransport:2"]),
        )
