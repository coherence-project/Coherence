# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Connection Manager service
import time

from twisted.web import resource
from twisted.python import failure
from twisted.internet import task

from coherence.upnp.core.soap_service import UPnPPublisher
from coherence.upnp.core.soap_service import errorCode

from coherence.upnp.core import service

from coherence.extern.logger import Logger
log = Logger('ConnectionManagerServer')

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
        self.next_avt_id = 1
        self.next_rcs_id = 1
        
        self.connections = {}
        
        self.set_variable(0, 'SourceProtocolInfo', '')
        self.set_variable(0, 'SinkProtocolInfo', '')
        self.set_variable(0, 'CurrentConnectionIDs', '')
        
        self.remove_lingering_connections_loop = task.LoopingCall(self.remove_lingering_connections)
        self.remove_lingering_connections_loop.start(180.0, now=False)

        
    def add_connection(self, RemoteProtocolInfo,
                             Direction,
                             PeerConnectionID,
                             PeerConnectionManager):
                             

        id = self.next_connection_id
        self.next_connection_id += 1
        
        avt_id = 0
        rcs_id = 0
        
        if self.device.device_type == 'MediaRenderer':
            """ this is the place to instantiate AVTransport and RenderingControl
                for this connection
            """
            avt_id = self.next_avt_id
            self.next_avt_id += 1
            self.device.av_transport_server.create_new_instance(avt_id)
            rcs_id = self.next_rcs_id
            self.next_rcs_id += 1
            self.device.rendering_control_server.create_new_instance(rcs_id)
            self.connections[id] = {'ProtocolInfo':RemoteProtocolInfo,
                                    'Direction':Direction,
                                    'PeerConnectionID':PeerConnectionID,
                                    'PeerConnectionManager':PeerConnectionManager,
                                    'AVTransportID':avt_id,
                                    'RcsID':rcs_id,
                                    'Status':'OK'}
            self.backend.current_connection_id = id

        csv_ids = ','.join([str(x) for x in self.connections])
        self.set_variable(0, 'CurrentConnectionIDs', csv_ids)
        return id, avt_id, rcs_id
        
    def remove_connection(self,id):
        try:
            self.device.av_transport_server.remove_instance(self.lookup_avt_id(id))
            self.device.rendering_control_server.remove_instance(self.lookup_rcs_id(id))
            del self.connections[id]
        except:
            pass
        self.backend.current_connection_id = None
        csv_ids = ','.join([str(x) for x in self.connections])
        self.set_variable(0, 'CurrentConnectionIDs', csv_ids)
        
    def remove_lingering_connections(self):
        """ check if we have a connection that hasn't a StateVariable change
            within the last 300 seconds, if so remove it
        """
        if self.device.device_type != 'MediaRenderer':
            return
            
        now = time.time()
            
        for id, connection in self.connections.items():
            avt_id = connection['AVTransportID']
            rcs_id = connection['RcsID']
            avt_active = True
            rcs_active = True
            
            #print "remove_lingering_connections", id, avt_id, rcs_id
            if avt_id > 0:
                avt_variables = self.device.av_transport_server.get_variables().get(avt_id)
                if avt_variables:
                    avt_active = False
                    for variable in avt_variables.values():
                        if variable.last_time_touched+300 >= now:
                            avt_active = True
                            break
            if rcs_id > 0:
                rcs_variables = self.device.rendering_control_server.get_variables().get(rcs_id)
                if rcs_variables:
                    rcs_active = False
                    for variable in rcs_variables.values():
                        if variable.last_time_touched+300 >= now:
                            rcs_active = True
                            break
            if( avt_active == False and rcs_active == False):
                self.remove_connection(id)
        
    def lookup_connection(self,id):
        return self.connections.get(id)
            
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
        log.info('upnp_PrepareForConnection')
        """ check if we really support that mimetype """
        RemoteProtocolInfo = kwargs['RemoteProtocolInfo']
        """ if we are a MR and this in not 'Input'
            then there is something strange going on
        """
        Direction = kwargs['Direction']
        if( self.device.device_type == 'MediaRenderer' and
            Direction == 'Output'):
            return failure.Failure(errorCode(702))
        if( self.device.device_type == 'MediaServer' and
            Direction != 'Input'):
            return failure.Failure(errorCode(702))
        """ the InstanceID of the MS ? """
        PeerConnectionID = kwargs['PeerConnectionID']
        """ ??? """
        PeerConnectionManager = kwargs['PeerConnectionManager']
        protocolinfo = None
        if self.device.device_type == 'MediaRenderer':
            local_protocol_info = self.get_variable('SinkProtocolInfo').value
        if self.device.device_type == 'MediaServer':
            local_protocol_info = self.get_variable('SourceProtocolInfo').value
        log.info(RemoteProtocolInfo, '--', local_protocol_info)
        if RemoteProtocolInfo in local_protocol_info.split(','):
            connection_id, avt_id, rcs_id = \
                self.add_connection(RemoteProtocolInfo,
                                        Direction,
                                        PeerConnectionID,
                                        PeerConnectionManager)
            return {'ConnectionID': connection_id, 'AVTransportID': avt_id, 'RcsID': rcs_id}
        return failure.Failure(errorCode(701))

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
