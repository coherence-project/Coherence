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
        
    def soap_PrepareForConnection(self, *args, **kwargs):
        """Optional: this action is used to allow the device to prepare itself to connect
           to the network for the purposes of sending or receiving media content."""
        
        print 'PrepareForConnection()', kwargs
        return { 'PrepareForConnectionResponse': { 'ConnectionID': 0,
                                                    'AVTransportID': 0,
                                                    'RcsID': 0}}

    def soap_ConnectionComplete(self, *args, **kwargs):
        """Optional: this action removes the connection referenced by argument
           ConnectionID by modifying state variable CurrentConnectionIDs, and
           (if necessary) performs any protocol-specific cleanup actions such
           as releasing network resources."""
        
        print 'ConnectionComplete()', kwargs
        return { 'ConnectionCompleteResponse': {}}

    def soap_GetCurrentConnectionIDs(self, *args, **kwargs):
        """Required: this action returns a Comma-Separated Value list of ConnectionIDs
           of currently ongoing Connections. A ConnectionID can be used to manually
           terminate a Connection via action ConnectionComplete(), or to retrieve
           additional information about the ongoing Connection via action
           GetCurrentConnectionInfo(). If a device does not implement PrepareForConnection(),
           this action MUST return the single value '0'."""
        
        print 'GetCurrentConnectionIDs()', kwargs
        r = { 'GetCurrentConnectionIDsResponse': { 'ConnectionIDs': self.variables[0]['CurrentConnectionIDs'].value }}
        print r
        return r

    def soap_GetCurrentConnectionInfo(self, *args, **kwargs):
        """Required: this action returns associated information of the connection
           referred to by the ConnectionID input argument. The AVTransportID argument
           MAY be the reserved value -1 and the PeerConnectionManager argument MAY
           be the empty string in cases where the connection has been setup completely
           out of band, not involving a PrepareForConnection() action."""
        
        print 'GetCurrentConnectionInfo()', kwargs
        return { 'GetCurrentConnectionInfoResponse': { 'RcsID': -1,
                                                       'AVTransportID': -1,
                                                       'ProtocolInfo': '',
                                                       'PeerConnectionManager': '',
                                                       'PeerConnectionID': -1,
                                                       'Direction': 'Output',
                                                       'Status': 'OK',
                                                       }}

        
class ConnectionManagerServer(service.Server, resource.Resource):

    def __init__(self, backend):
        self.backend = backend
        resource.Resource.__init__(self)
        service.Server.__init__(self, 'ConnectionManager', backend)

        self.connection_manager_control = ConnectionManagerControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.connection_manager_control))
        self.putChild(self.control_url, self.connection_manager_control)
        
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

