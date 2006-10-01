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

from service import ServiceClient

class ConnectionManagerClient( ServiceClient):

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        #self.service.subscribe()
        #print "ConnectionManagerClient __init__", self.url

    def get_protocol_info(self):
        client = self._get_client("GetProtocolInfo")
        d = client.callRemote("GetProtocolInfo")
        def got_results(results):
            print "protocol info: %r" % results
        d.addCallback(got_results)
        return d

    def prepare_for_connection(self, remote_protocol_info, peer_connection_manager, peer_connection_id, direction):
        client = self._get_client("PrepareForConnection")
        d = client.callRemote("PrepareForConnection",
                                    RemoteProtocolInfo=remote_protocol_info,
                                    PeerConnectionManager=peer_connection_manager,
                                    PeerConnectionID=peer_connection_id,
                                    Direction=direction)
        def got_results(results):
            print "prepare for connection: %r" % results
        d.addCallback(got_results)
        return d

    def connection_complete(self, connection_id):
        client = self._get_client("ConnectionComplete")
        d = client.callRemote("ConnectionComplete",
                                    ConnectionID=connection_id)
        def got_results(results):
            print "connection complete: %r" % results
        d.addCallback(got_results)
        return d

    def get_current_connection_ids(self):
        client = self._get_client("GetCurrentConnectionIDs")
        d = client.callRemote("GetCurrentConnectionIDs")
        def got_results(results):
            print "current connection ids: %r" % results
        d.addCallback(got_results)
        return d

    def get_current_connection_info(self, connection_id):
        client = self._get_client("GetCurrentConnectionInfo")
        d = client.callRemote("GetCurrentConnectionInfo",
                                    ConnectionID=connection_id)
        def got_results(results):
            print "current connection info: %r" % results
        d.addCallback(got_results)
        return d

    def _failure(self, error):
        log.msg(error.getTraceback(), debug=True)
        error.trap(Exception)
