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

        
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet import task

import utils

SSDP_PORT = 1900
SSDP_ADDR = '239.255.255.250'

class MSearch(DatagramProtocol):

    def __init__(self, ssdp_server):
        self.ssdp_server = ssdp_server
        port = reactor.listenUDP(5654, self)

        l = task.LoopingCall(self.double_discover)
        l.start(50.0)

    def datagramReceived(self, data, (host, port)):
        cmd, headers = utils.parse_http_response(data)

        if cmd[0] == 'HTTP/1.1' and cmd[1] == '200':
            if not self.ssdp_server.isKnown(headers['usn']):
                self.ssdp_server.register(headers['usn'], headers['st'],
                                          headers['location'],
                                          headers['server'],
                                          headers['cache-control'])

    def double_discover(self):
        " Because it's worth it (with UDP's reliability) "
        self.discover()
        self.discover()
        
    def discover(self):
        req = [ 'M-SEARCH * HTTP/1.1',
                'HOST: %s:%d' % (SSDP_ADDR, SSDP_PORT),
                'MAN: "ssdp:discover"',
                'MX: 5',
                'ST: ssdp:all',
                '','']
        req = '\r\n'.join(req)
        
        self.transport.write(req, (SSDP_ADDR, SSDP_PORT))
