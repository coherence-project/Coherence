# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>
# Copyright 2014, Hartmut Goebel <h.goebel@crazy-compilers.com>

from coherence.upnp.devices.basics import DeviceHttpRoot, BasicDevice
from coherence.upnp.services.servers.switch_power_server import SwitchPowerServer

class HttpRoot(DeviceHttpRoot):
    logCategory = 'binarylight'


class BinaryLight(BasicDevice):
    logCategory = 'binarylight'
    device_type = 'BinaryLight'
    version = 1

    model_description = 'Coherence UPnP %s' % device_type
    model_name = 'Coherence UPnP %s' % device_type

    _service_definition = (
        ('switch_power_server', SwitchPowerServer),
        )
    _httpRoot = HttpRoot
