# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

class ConnectionManagerClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.subscribe()
        #print "ConnectionManagerClient __init__", self.url

    def get_protocol_info(self):
        action = self.service.get_action('GetProtocolInfo')
        return action.call()

    def prepare_for_connection(self, remote_protocol_info, peer_connection_manager, peer_connection_id, direction):
        action = self.service.get_action('PrepareForConnection')
        return action.call( RemoteProtocolInfo=remote_protocol_info,
                            PeerConnectionManager=peer_connection_manager,
                            PeerConnectionID=peer_connection_id,
                            Direction=direction)

    def connection_complete(self, connection_id):
        action = self.service.get_action('ConnectionComplete')
        return action.call(ConnectionID=connection_id)

    def get_current_connection_ids(self):
        action = self.service.get_action('GetCurrentConnectionIDs')
        return action.call()

    def get_current_connection_info(self, connection_id):
        action = self.service.get_action('GetCurrentConnectionInfo')
        return action.call(ConnectionID=connection_id)