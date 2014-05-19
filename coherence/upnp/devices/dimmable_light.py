# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>
# Copyright 2014, Hartmut Goebel <h.goebel@crazy-compilers.com>

from coherence.upnp.devices.basics import DeviceHttpRoot, BasicDevice
from coherence.upnp.services.servers.switch_power_server import SwitchPowerServer
from coherence.upnp.services.servers.dimming_server import DimmingServer


class HttpRoot(DeviceHttpRoot):
    logCategory = 'dimmablelight'


class DimmableLight(BasicDevice):
    logCategory = 'dimmablelight'
    device_type = 'DimmableLight'
    version = 1

    model_description = 'Coherence UPnP %s' % device_type
    model_name = 'Coherence UPnP %s' % device_type

    _service_definition = (
        ('switch_power_server', SwitchPowerServer),
        ('dimming_server', DimmingServer),
        )
    _httpRoot = HttpRoot
