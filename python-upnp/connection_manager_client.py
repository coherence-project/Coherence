# Elisa - Home multimedia server
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# All rights reserved.
# 
# This software is available under three license agreements.
# 
# There are various plugins and extra modules for Elisa licensed
# under the MIT license. For instance our upnp module uses this license.
# 
# The core of Elisa is licensed under GPL version 2.
# See "LICENSE.GPL" in the root of this distribution including a special 
# exception to use Elisa with Fluendo's plugins.
# 
# The GPL part is also available under a commerical licensing
# agreement.
# 
# The second license is the Elisa Commercial License Agreement.
# This license agreement is available to licensees holding valid
# Elisa Commercial Agreement licenses.
# See "LICENSE.Elisa" in the root of this distribution.

from twisted.internet import reactor, defer
from twisted.python import log
import sys, threading
import DIDLLite, utils

class ConnectionManagerClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        #self.service.subscribe()
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