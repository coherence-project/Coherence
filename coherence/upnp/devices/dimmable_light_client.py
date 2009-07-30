# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

from coherence.upnp.services.clients.switch_power_client import SwitchPowerClient
from coherence.upnp.services.clients.dimming_client import DimmingClient

from coherence import log

import coherence.extern.louie as louie

class DimmableLightClient(log.Loggable):
    logCategory = 'dimminglight_client'

    def __init__(self, device):
        self.device = device
        self.device_type = self.device.get_friendly_device_type()
        self.version = int(self.device.get_device_type_version())
        self.icons = device.icons
        self.switch_power = None
        self.dimming = None

        self.detection_completed = False

        louie.connect(self.service_notified, signal='Coherence.UPnP.DeviceClient.Service.notified', sender=self.device)

        for service in self.device.get_services():
            if service.get_type() in ["urn:schemas-upnp-org:service:SwitchPower:1"]:
                self.switch_power = SwitchPowerClient(service)
            if service.get_type() in ["urn:schemas-upnp-org:service:Dimming:1"]:
                self.dimming = DimmingClient(service)

        self.info("DimmingLight %s" % (self.device.get_friendly_name()))
        if self.switch_power:
            self.info("SwitchPower service available")
        else:
            self.warning("SwitchPower service not available, device not implemented properly according to the UPnP specification")
            return
        if self.dimming:
            self.info("Dimming service available")
        else:
            self.warning("Dimming service not available, device not implemented properly according to the UPnP specification")

    def remove(self):
        self.info("removal of DimmingLightClient started")
        if self.dimming != None:
            self.dimming.remove()
        if self.switch_power != None:
            self.switch_power.remove()

    def service_notified(self, service):
        self.info("Service %r sent notification" % service);
        if self.detection_completed == True:
            return
        if self.switch_power != None:
            if not hasattr(self.switch_power.service, 'last_time_updated'):
                return
            if self.switch_power.service.last_time_updated == None:
                return
        if self.dimming != None:
            if not hasattr(self.dimming.service, 'last_time_updated'):
                return
            if self.dimming.service.last_time_updated == None:
                return
        self.detection_completed = True
        louie.send('Coherence.UPnP.DeviceClient.detection_completed', None,
                               client=self,udn=self.device.udn)

    def state_variable_change( self, variable):
        self.info(variable.name, 'changed from', variable.old_value, 'to', variable.value)
