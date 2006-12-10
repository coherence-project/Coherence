# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Connection Manager service

from twisted.python import log
from twisted.web import resource, static, soap
from twisted.internet import defer

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from coherence.upnp.core.soap_service import UPnPPublisher

from coherence.upnp.core import service

class ConnectionManagerControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class ConnectionManagerServer(service.Server, resource.Resource):

    def __init__(self, device, backend=None):
        self.device = device
        if backend == None:
            backend = self.device.backend
        resource.Resource.__init__(self)
        service.Server.__init__(self, 'ConnectionManager', self.device.version, backend)

        self.control = ConnectionManagerControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.control))
        self.putChild(self.control_url, self.control)
        self.next_connection_id = 1
        
        self.connections = {}
        
        self.set_variable(0, 'SourceProtocolInfo', '')
        self.set_variable(0, 'SinkProtocolInfo', '')
        self.set_variable(0, 'CurrentConnectionIDs', '')
        
    def add_connection(self):
        id = self.next_connection_id
        self.next_connection_id += 1
        self.connections[id] = {}
        csv_ids = ','.join([str(x) for x in self.connections])
        self.set_variable(0, 'CurrentConnectionIDs', csv_ids)
        return id
        
    def remove_connection(self,id):
        try:
            del self.connections[id]
        except:
            pass
        csv_ids = ','.join([str(x) for x in self.connections])
        self.set_variable(0, 'CurrentConnectionIDs', csv_ids)
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl
        
    def render(self,request):
        return '<html><p>root of the ConnectionManager</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)

