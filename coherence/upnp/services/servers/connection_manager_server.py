# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Connection Manager service

from twisted.python import log
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
        self.connections[id] = {'ProtocolInfo':RemoteProtocolInfo,
                                'Direction':Direction,
                                'PeerConnectionID':PeerConnectionID,
                                'PeerConnectionManager':PeerConnectionManager,
                                'AVTransportID':0,
                                'RcsID':0,
                                'Status':'OK'} #FIXME: get other services real ids
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
        

    def upnp_XPrepareForConnection(self, *args, **kwargs):
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
        if self.server:
            self.connection_id = \
                    self.server.connection_manager_server.add_connection(RemoteProtocolInfo,
                                                                            Direction,
                                                                            PeerConnectionID,
                                                                            PeerConnectionManager)

        return {'ConnectionID': self.connection_id, 'AVTransportID': 0, 'RcsID': 0}

    def upnp_XConnectionComplete(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        """ remove this InstanceID
            and the associated InstanceIDs @ AVTransportID and RcsID
        """
        if self.server:
            self.server.connection_manager_server.remove_connection(self.connection_id)
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
