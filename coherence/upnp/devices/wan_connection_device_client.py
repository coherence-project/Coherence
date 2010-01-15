# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2010 Frank Scholz <dev@coherence-project.org>

from coherence.upnp.services.clients.wan_ip_connection_client import WANIPConnectionClient
from coherence.upnp.services.clients.wan_ppp_connection_client import WANPPPConnectionClient


from coherence import log

import coherence.extern.louie as louie

class WANConnectionDeviceClient(log.Loggable):
    logCategory = 'igd_client'

    def __init__(self, device):
        self.device = device
        self.device_type = self.device.get_friendly_device_type()
        self.version = int(self.device.get_device_type_version())
        self.icons = device.icons

        self.wan_ip_connection = None
        self.wan_ppp_connection = None

        self.detection_completed = False

        louie.connect(self.service_notified, signal='Coherence.UPnP.DeviceClient.Service.notified', sender=self.device)

        for service in self.device.get_services():
            if service.get_type() in ["urn:schemas-upnp-org:service:WANIPConnection:1"]:
                self.wan_ip_connection = WANIPConnectionClient(service)
            if service.get_type() in ["urn:schemas-upnp-org:service:WANPPPConnection:1"]:
                self.wan_ppp_connection = WANPPPConnectionClient(service)
        self.info("WANConnectionDevice %s" % (self.device.get_friendly_name()))
        if self.wan_ip_connection:
            self.info("WANIPConnection service available")
        if self.wan_ppp_connection:
            self.info("WANPPPConnection service available")

    def remove(self):
        self.info("removal of WANConnectionDeviceClient started")
        if self.wan_ip_connection != None:
            self.wan_ip_connection.remove()
        if self.wan_ppp_connection != None:
            self.wan_ppp_connection.remove()

    def service_notified(self, service):
        self.info("Service %r sent notification" % service);
        if self.detection_completed == True:
            return
        if self.wan_ip_connection != None:
            if not hasattr(self.wan_ip_connection.service, 'last_time_updated'):
                return
            if self.wan_ip_connection.service.last_time_updated == None:
                return
        if self.wan_ppp_connection != None:
            if not hasattr(self.wan_ppp_connection.service, 'last_time_updated'):
                return
            if self.wan_ppp_connection.service.last_time_updated == None:
                return
        self.detection_completed = True
        louie.send('Coherence.UPnP.EmbeddedDeviceClient.detection_completed', None,
                               self)
