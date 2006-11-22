# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Connection Manager service

from twisted.python import log
from twisted.web import resource, static, soap
from twisted.internet import defer

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from soap_service import UPnPPublisher

import service

class ConnectionManagerControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class ConnectionManagerServer(service.Server, resource.Resource):

    def __init__(self, version, backend):
        self.backend = backend
        resource.Resource.__init__(self)
        service.Server.__init__(self, 'ConnectionManager', version, backend)

        self.control = ConnectionManagerControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.control))
        self.putChild(self.control_url, self.control)
        
        self.set_variable(0, 'SourceProtocolInfo', 'http-get:*:audio/mpeg:*')
        self.set_variable(0, 'SinkProtocolInfo', '')
        self.set_variable(0, 'CurrentConnectionIDs', '0')
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl
        
    def render(self,request):
        return '<html><p>root of the ConnectionManager</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)

