# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2010 Frank Scholz <dev@coherence-project.org>

from coherence.upnp.devices.wan_connection_device_client import WANConnectionDeviceClient

from coherence.upnp.services.clients.wan_common_interface_config_client import WANCommonInterfaceConfigClient

from coherence import log

import coherence.extern.louie as louie

class WANDeviceClient(log.Loggable):
    logCategory = 'wan_device_client'

    def __init__(self, device):
        self.device = device
        self.device_type = self.device.get_friendly_device_type()
        self.version = int(self.device.get_device_type_version())
        self.icons = device.icons

        self.wan_connection_device = None
        self.wan_common_interface_connection = None

        self.embedded_device_detection_completed = False
        self.service_detection_completed = False

        louie.connect(self.embedded_device_notified, signal='Coherence.UPnP.EmbeddedDeviceClient.detection_completed', sender=self.device)

        try:
            wan_connection_device = self.device.get_embedded_device_by_type('WANConnectionDevice')[0]
            self.wan_connection_device = WANConnectionDeviceClient(wan_connection_device)
        except:
            self.warning("Embedded WANConnectionDevice device not available, device not implemented properly according to the UPnP specification")
            raise

        louie.connect(self.service_notified, signal='Coherence.UPnP.DeviceClient.Service.notified', sender=self.device)
        for service in self.device.get_services():
            if service.get_type() in ["urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1"]:
                self.wan_common_interface_connection = WANCommonInterfaceConfigClient(service)

        self.info("WANDevice %s" % (self.device.get_friendly_name()))

    def remove(self):
        self.info("removal of WANDeviceClient started")
        if self.wan_common_interface_connection != None:
            self.wan_common_interface_connection.remove()
        if self.wan_connection_device != None:
            self.wan_connection_device.remove()

    def embedded_device_notified(self, device):
        self.info("EmbeddedDevice %r sent notification" % device);
        if self.embedded_device_detection_completed == True:
            return

        self.embedded_device_detection_completed = True
        if self.embedded_device_detection_completed == True and self.service_detection_completed == True:
            louie.send('Coherence.UPnP.EmbeddedDeviceClient.detection_completed', None,
                               self)

    def service_notified(self, service):
        self.info("Service %r sent notification" % service);
        if self.service_detection_completed == True:
            return
        if self.wan_common_interface_connection != None:
            if not hasattr(self.wan_common_interface_connection.service, 'last_time_updated'):
                return
            if self.wan_common_interface_connection.service.last_time_updated == None:
                return
        self.service_detection_completed = True
        if self.embedded_device_detection_completed == True and self.service_detection_completed == True:
            louie.send('Coherence.UPnP.EmbeddedDeviceClient.detection_completed', None,
                               self)
