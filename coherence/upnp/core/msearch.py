# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
#
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>
        
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet import task

from coherence.upnp.core import utils

import louie

SSDP_PORT = 1900
SSDP_ADDR = '239.255.255.250'

from coherence.extern.logger import Logger
log = Logger('MSEARCH')

class MSearch(DatagramProtocol):

    def __init__(self, ssdp_server):
        self.ssdp_server = ssdp_server
        port = reactor.listenUDP(0, self)

        l = task.LoopingCall(self.double_discover)
        l.start(120.0)

    def datagramReceived(self, data, (host, port)):
        #make raw data available
        #log.info('UPnT.msearch_datagram_received')
        louie.send('UPnT.msearch_datagram_received', None, data, host, port)

        cmd, headers = utils.parse_http_response(data)
        log.msg('datagramReceived from %s:%d, code %s' % (host, port, cmd[1]))
        if cmd[0] == 'HTTP/1.1' and cmd[1] == '200':
            log.msg('for', headers['usn'])
            if not self.ssdp_server.isKnown(headers['usn']):
                log.msg('register as remote %s, %s, %s' % (headers['usn'], headers['st'], headers['location']))
                self.ssdp_server.register('remote',
                                            headers['usn'], headers['st'],
                                            headers['location'],
                                            headers['server'],
                                            headers['cache-control'])

    def double_discover(self):
        " Because it's worth it (with UDP's reliability) "
        log.msg('send out discovery for ssdp:all')
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
