# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Content Directory service

from twisted.python import log
from twisted.web import resource, static, soap

from twisted.python import reflect

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from coherence.upnp.core.soap_service import UPnPPublisher

from coherence.upnp.core import service

class FakeMediaReceiverRegistrarBackend:

    def upnp_IsAuthorized(self, *args, **kwargs):
        r = { 'Result': 1}
        return r

    def upnp_IsValidated(self, *args, **kwargs):
        r = { 'Result': 1}
        return r

class MediaReceiverRegistrarControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()
        

class MediaReceiverRegistrarServer(service.Server, resource.Resource):

    def __init__(self, device, backend=None):
        self.device = device
        if backend == None:
            backend = self.device.backend
        resource.Resource.__init__(self)
        version = 1
        self.namespace = 'microsoft.com'
        service.Server.__init__(self, 'X_MS_MediaReceiverRegistrar', version, backend)
        
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
