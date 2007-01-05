# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Connection Manager service

from twisted.web import resource, static, soap
from twisted.internet import defer
from twisted.python import failure

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from coherence.upnp.core.soap_service import UPnPPublisher

from coherence.upnp.core import service

class ConnectionManagerControl(service.ServiceControl,UPnPPublisher):

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()


class ConnectionManagerServer(service.ServiceServer, resource.Resource):

    def __init__(self, device, backend=None):
        self.device = device
        if backend == None:
            backend = self.device.backend
        resource.Resource.__init__(self)
        service.ServiceServer.__init__(self, 'ConnectionManager', self.device.version, backend)
        
        self.control = ConnectionManagerControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.control))
        self.putChild(self.control_url, self.control)
        self.next_connection_id = 1
        
        self.connections = {}
        
        self.set_variable(0, 'SourceProtocolInfo', '')
        self.set_variable(0, 'SinkProtocolInfo', '')
        self.set_variable(0, 'CurrentConnectionIDs', '')
        
    def add_connection(self, RemoteProtocolInfo,
                             Direction,
                             PeerConnectionID,
                             PeerConnectionManager):
                             

        id = self.next_connection_id
        self.next_connection_id += 1
        
        """ this is the place to instantiate AVTransport and RenderingControl
            for this connection
        """
        avt_id = 0
        rcs_id = 0
        # FIXME: get other services real ids
        self.connections[id] = {'ProtocolInfo':RemoteProtocolInfo,
                                'Direction':Direction,
                                'PeerConnectionID':PeerConnectionID,
                                'PeerConnectionManager':PeerConnectionManager,
                                'AVTransportID':avt_id,
                                'RcsID':rcs_id,
                                'Status':'OK'}
        print "add_connection", self.connections
        csv_ids = ','.join([str(x) for x in self.connections])
        self.set_variable(0, 'CurrentConnectionIDs', csv_ids)
        return id, avt_id, rcs_id
        
    def remove_connection(self,id):
        try:
            del self.connections[id]
        except:
            pass
        print "remove_connection", self.connections
        csv_ids = ','.join([str(x) for x in self.connections])
        self.set_variable(0, 'CurrentConnectionIDs', csv_ids)
        
    def lookup_connection(self,id):
        try:
            return self.connections[id]
        except:
            return None
            
    def lookup_avt_id(self,id):
        try:
            return self.connections[id]['AVTransportID']
        except:
            return 0
        
    def lookup_rcs_id(self,id):
        try:
            return self.connections[id]['RcsID']
        except:
            return 0
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl
        
    def render(self,request):
        return '<html><p>root of the ConnectionManager</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)
        

    def upnp_PrepareForConnection(self, *args, **kwargs):
        """ check if we really support that mimetype """
        RemoteProtocolInfo = kwargs['RemoteProtocolInfo']
        """ if we are a MR and this in not 'Input'
            then there is something strange going on
        """
        Direction = kwargs['Direction']
        """ the InstanceID of the MS ? """
        PeerConnectionID = kwargs['PeerConnectionID']
        """ ??? """
        PeerConnectionManager = kwargs['PeerConnectionManager']
        connection_id, avt_id, rcs_id = \
            self.add_connection(RemoteProtocolInfo,
                                    Direction,
                                    PeerConnectionID,
                                    PeerConnectionManager)
        return {'ConnectionID': connection_id, 'AVTransportID': avt_id, 'RcsID': rcs_id}

    def upnp_ConnectionComplete(self, *args, **kwargs):
        ConnectionID = int(kwargs['ConnectionID'])
        """ remove this ConnectionID
            and the associated instances @ AVTransportID and RcsID
        """
        self.remove_connection(ConnectionID)
        return {}

    def upnp_GetCurrentConnectionInfo(self, *args, **kwargs):
        ConnectionID = int(kwargs['ConnectionID'])
        """ return for this ConnectionID
            the associated InstanceIDs @ AVTransportID and RcsID
            ProtocolInfo
            PeerConnectionManager
            PeerConnectionID
            Direction
            Status
            
            or send a 706 if there isn't such a ConnectionID
        """
        connection = self.lookup_connection(ConnectionID)
        if connection == None:
            return failure.Failure(errorCode(706))
        else:
            return {'AVTransportID':connection['AVTransportID'],
                    'RcsID':connection['RcsID'],
                    'ProtocolInfo':connection['ProtocolInfo'],
                    'PeerConnectionManager':connection['PeerConnectionManager'],
                    'PeerConnectionID':connection['PeerConnectionID'],
                    'Direction':connection['Direction'],
                    'Status':connection['Status'],
                    }
