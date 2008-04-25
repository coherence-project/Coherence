# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006-2008, Frank Scholz <coherence@beebits.net>

class ConnectionManagerClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.client = self
        self.service.subscribe()

    #def __del__(self):
    #    #print "ConnectionManagerClient deleted"
    #    pass

    def connection_manager_id(self):
        return "%s/%s" % (self.service.device.get_id(), self.service.get_id())

    def remove(self):
        self.service.remove()
        self.service = None
        self.namespace = None
        self.url = None
        del self

    def subscribe_for_variable(self, var_name, callback,signal=False):
        self.service.subscribe_for_variable(var_name, instance=0, callback=callback,signal=signal)

    def get_protocol_info(self):
        action = self.service.get_action('GetProtocolInfo')
        return action.call()

    def prepare_for_connection(self, remote_protocol_info, peer_connection_manager, peer_connection_id, direction):
        action = self.service.get_action('PrepareForConnection')
        if action:  # optional
            return action.call( RemoteProtocolInfo=remote_protocol_info,
                            PeerConnectionManager=peer_connection_manager,
                            PeerConnectionID=peer_connection_id,
                            Direction=direction)
        return None

    def connection_complete(self, connection_id):
        action = self.service.get_action('ConnectionComplete')
        if action:  # optional
            return action.call(ConnectionID=connection_id)
        return None


    def get_current_connection_ids(self):
        action = self.service.get_action('GetCurrentConnectionIDs')
        return action.call()

    def get_current_connection_info(self, connection_id):
        action = self.service.get_action('GetCurrentConnectionInfo')
        return action.call(ConnectionID=connection_id)