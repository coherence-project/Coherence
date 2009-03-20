# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009, Frank Scholz <coherence@beebits.net>

# ScheduledRecording service

from twisted.web import resource

from coherence.upnp.core.soap_service import UPnPPublisher

from coherence.upnp.core import service

class ScheduledRecordingControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class ScheduledRecordingServer(service.ServiceServer, resource.Resource):

    implementation = 'optional'

    def __init__(self, device, backend=None):
        self.device = device
        if backend == None:
            backend = self.device.backend
        resource.Resource.__init__(self)
        self.version = 1
        service.ServiceServer.__init__(self, 'ScheduledRecording', self.version, backend)

        self.control = ScheduledRecordingControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.control))
        self.putChild(self.control_url, self.control)

    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the ScheduledRecording</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)
