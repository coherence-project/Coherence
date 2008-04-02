# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

# Switch Power service

from twisted.web import resource
from twisted.python import failure
from twisted.internet import task

from coherence.upnp.core.soap_service import UPnPPublisher
from coherence.upnp.core.soap_service import errorCode

from coherence.upnp.core import service
from coherence import log


class SwitchPowerControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class SwitchPowerServer(service.ServiceServer, resource.Resource,
                              log.Loggable):
    logCategory = 'switch_power_server'

    def __init__(self, device, backend=None):
        self.device = device
        if backend == None:
            backend = self.device.backend
        resource.Resource.__init__(self)
        service.ServiceServer.__init__(self, 'SwitchPower', self.device.version, backend)

        self.control = SwitchPowerControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.control))
        self.putChild(self.control_url, self.control)