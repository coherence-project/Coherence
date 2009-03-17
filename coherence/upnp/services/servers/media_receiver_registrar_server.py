# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Content Directory service

from twisted.web import resource

from coherence.upnp.core.soap_service import UPnPPublisher

from coherence.upnp.core import service

class FakeMediaReceiverRegistrarBackend:

    def upnp_IsAuthorized(self, *args, **kwargs):
        r = { 'Result': 1}
        return r

    def upnp_IsValidated(self, *args, **kwargs):
        r = { 'Result': 1}
        return r

    def upnp_RegisterDevice(self, *args, **kwargs):
        """ in parameter RegistrationReqMsg """
        RegistrationReqMsg = kwargs['RegistrationReqMsg']
        """ FIXME: check with WMC and WMP """
        r = { 'RegistrationRespMsg': 'WTF should be in here?'}
        return r

class MediaReceiverRegistrarControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class MediaReceiverRegistrarServer(service.ServiceServer, resource.Resource):

    implementation = 'optional'

    def __init__(self, device, backend=None):
        self.device = device
        if backend == None:
            backend = self.device.backend
        resource.Resource.__init__(self)
        self.version = 1
        self.namespace = 'microsoft.com'
        self.id_namespace = 'microsoft.com'
        service.ServiceServer.__init__(self, 'X_MS_MediaReceiverRegistrar', self.version, backend)
        self.device_description_tmpl = 'xbox-description-1.xml'

        self.control = MediaReceiverRegistrarControl(self)
        self.putChild('scpd.xml', service.scpdXML(self, self.control))
        self.putChild('control', self.control)


    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the MediaReceiverRegistrar</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)
