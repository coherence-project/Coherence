# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2010 Frank Scholz <dev@coherence-project.org>

from coherence.upnp.devices.wan_device_client import WANDeviceClient

from coherence import log

import coherence.extern.louie as louie

class InternetGatewayDeviceClient(log.Loggable):
    logCategory = 'igd_client'

    def __init__(self, device):
        self.device = device
        self.device_type = self.device.get_friendly_device_type()
        self.version = int(self.device.get_device_type_version())
        self.icons = device.icons

        self.wan_device = None

        self.detection_completed = False

        louie.connect(self.embedded_device_notified, signal='Coherence.UPnP.EmbeddedDeviceClient.detection_completed', sender=self.device)

        try:
            wan_device = self.device.get_embedded_device_by_type('WANDevice')[0]
            self.wan_device = WANDeviceClient(wan_device)
        except:
            self.warning("Embedded WANDevice device not available, device not implemented properly according to the UPnP specification")
            raise

        self.info("InternetGatewayDevice %s" % (self.device.get_friendly_name()))

    def remove(self):
        self.info("removal of InternetGatewayDeviceClient started")
        if self.wan_device != None:
            self.wan_device.remove()

    def embedded_device_notified(self, device):
        self.info("EmbeddedDevice %r sent notification" % device);
        if self.detection_completed == True:
            return
        self.detection_completed = True
        louie.send('Coherence.UPnP.DeviceClient.detection_completed', None,
                               client=self,udn=self.device.udn)
