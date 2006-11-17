# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

# RenderingControl service

from twisted.python import log
from twisted.web import resource, static, soap
from twisted.internet import defer

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from soap_service import UPnPPublisher

import service

class RenderingControlControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class RenderingControlServer(service.Server, resource.Resource):

    def __init__(self,backend):
        self.backend = backend
        resource.Resource.__init__(self)
        service.Server.__init__(self, 'RenderingControl',backend)

        self.rendering_control_control = RenderingControlControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.rendering_control_control))
        self.putChild(self.control_url, self.rendering_control_control)
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl
        
    def render(self,request):
        return '<html><p>root of the RenderingControl</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)

