# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006,2007 Frank Scholz <coherence@beebits.net>
# Copyright 2014, Hartmut Goebel <h.goebel@crazy-compilers.com>

from coherence.upnp.devices.basics import DeviceHttpRoot, BasicDevice
from coherence.upnp.services.servers.connection_manager_server import ConnectionManagerServer
from coherence.upnp.services.servers.rendering_control_server import RenderingControlServer
from coherence.upnp.services.servers.av_transport_server import AVTransportServer


class HttpRoot(DeviceHttpRoot):
    logCategory = 'mediarenderer'


class MediaRenderer(BasicDevice):
    logCategory = 'mediarenderer'
    device_type = 'MediaRenderer'

    model_description = 'Coherence UPnP A/V  %s' % device_type
    model_name = 'Coherence UPnP A/V %s' % device_type

    _service_definition = (
        ('connection_manager_server', ConnectionManagerServer),
        ('rendering_control_server', RenderingControlServer),
        ('av_transport_server', AVTransportServer),
        )
    _httpRoot = HttpRoot
