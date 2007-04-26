# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uroegon.edu>
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>
#
# Implementation of a SSDP server under Twisted Python.
#

import random
import string
import sys
import time
import platform

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, error
from twisted.internet import task

import louie

SSDP_PORT = 1900
SSDP_ADDR = '239.255.255.250'

from coherence.extern.logger import Logger
log = Logger('SSDP')

class SSDPServer(DatagramProtocol):
    """A class implementing a SSDP server.  The notifyReceived and
    searchReceived methods are called when the appropriate type of
    datagram is received by the server."""

    # not used yet
    stdheaders = [ ('Server', 'Twisted, UPnP/1.0, python-upnp'), ]
    elements = {}
    known = {}

    _callbacks = {}

    def __init__(self):
        
        # Create SSDP server
        try:
            port = reactor.listenMulticast(SSDP_PORT, self, listenMultiple=True)
            # don't get our own sends
            port.setLoopbackMode(0)

            port.joinGroup(SSDP_ADDR)

            l = task.LoopingCall(self.resendNotify)
            l.start(777.0, now=False)
            
        except error.CannotListenError, err:
            log.msg("There seems to be already a SSDP server running on this host, no need starting a second one.")

    def shutdown(self):
        '''Make sure we send out the byebye notifications.'''
        for st in self.known:
            if self.known[st]['MANIFESTATION'] == 'local':
                self.doByebye(st)

    def datagramReceived(self, data, (host, port)):
        """Handle a received multicast datagram."""
        #make raw data available
        louie.send('UPnT.ssdp_datagram_received', None, data, host, port)

        try:
            header, payload = data.split('\r\n\r\n')
        except ValueError, err:
            print err
            print 'Arggg,', data
            import pdb; pdb.set_trace()
                                         
        lines = header.split('\r\n')
        cmd = string.split(lines[0], ' ')
        lines = map(lambda x: x.replace(': ', ':', 1), lines[1:])
        lines = filter(lambda x: len(x) > 0, lines)

        headers = [string.split(x, ':', 1) for x in lines]
        headers = dict(map(lambda x: (x[0].lower(), x[1]), headers))

        log.msg('SSDP command %s %s - from %s:%d' % (cmd[0], cmd[1], host, port))
        if cmd[0] == 'M-SEARCH' and cmd[1] == '*':
            # SSDP discovery
            self.discoveryRequest(headers, (host, port))
        elif cmd[0] == 'NOTIFY' and cmd[1] == '*':
            # SSDP presence
            self.notifyReceived(headers, (host, port))
        else:
            log.msg('Unknown SSDP command %s %s' % (cmd[0], cmd[1]))

    def register(self, manifestation, usn, st, location,
                        server='UPnP/1.0,Coherence UPnP framework,0.1',
                        cache_control='max-age=1800'):
        """Register a service or device that this SSDP server will
        respond to."""
        
        log.msg('Registering %s (%s)' % (st, location))

        self.known[usn] = {}
        self.known[usn]['USN'] = usn
        self.known[usn]['LOCATION'] = location
        self.known[usn]['ST'] = st
        self.known[usn]['EXT'] = ''
        if manifestation == 'local':
            self.known[usn]['SERVER'] = ','.join([platform.system(),platform.release(),server])
            self.known[usn]['CACHE-CONTROL'] = cache_control
        else:
            self.known[usn]['SERVER'] = server
            self.known[usn]['CACHE-CONTROL'] = cache_control
            
        self.known[usn]['MANIFESTATION'] = manifestation
        
        log.msg(self.known[usn])
        
        if manifestation == 'local':
            self.doNotify(usn)

        if st == 'upnp:rootdevice':
            louie.send('Coherence.UPnP.SSDP.new_device', None, device_type=st, infos=self.known[usn])
            #self.callback("new_device", st, self.known[usn])

    def unRegister(self, usn):
        log.msg("Un-registering %s" % usn)

        st = self.known[usn]['ST']
        if st == 'upnp:rootdevice':
            louie.send('Coherence.UPnP.SSDP.removed_device', None, device_type=st, infos=self.known[usn])
            #self.callback("removed_device", st, self.known[usn])
            
        del self.known[usn]

    def isKnown(self, usn):
        return self.known.has_key(usn)

    def notifyReceived(self, headers, (host, port)):
        """Process a presence announcement.  We just remember the
        details of the SSDP service announced."""

        log.msg('Notification from (%s,%d) for %s' % (host, port, headers['nt']))
        log.msg('Notification headers:', headers)

        if headers['nts'] == 'ssdp:alive':
            if not self.isKnown(headers['usn']):
                self.register('remote', headers['usn'], headers['nt'], headers['location'],
                              headers['server'], headers['cache-control'])
        elif headers['nts'] == 'ssdp:byebye':
            if self.isKnown(headers['usn']):
                self.unRegister(headers['usn'])
        else:
            log.msg('Unknown subtype %s for notification type %s' %
                    (headers['nts'], headers['nt']))

    def discoveryRequest(self, headers, (host, port)):
        """Process a discovery request.  The response must be sent to
        the address specified by (host, port)."""

        log.msg('Discovery request from (%s,%d) for %s' % (host, port, headers['st']))
        log.msg('Discovery request for %s' % headers['st'])

        # Do we know about this service?
        for i in self.known.values():
            if i['MANIFESTATION'] == 'remote':
                continue
            if( i['ST'] == headers['st'] or
                headers['st'] == 'ssdp:all'):
                response = []
                response.append('HTTP/1.1 200 OK')

                for k, v in i.items():
                    if k == 'USN':
                        usn = v
                    if k != 'MANIFESTATION':
                        response.append('%s: %s' % (k, v))

                response.extend(('', ''))
                delay = random.randint(0, int(headers['mx']))
                log.msg('send Discovery response with delay %d for %s' % (delay, usn))
                reactor.callLater(delay, self.transport.write,
                                '\r\n'.join(response), (host, port))

    def doNotify(self, usn):
        """Do notification"""

        log.msg('Sending alive notification for %s' % usn)

        resp = [ 'NOTIFY * HTTP/1.1',
            'HOST: %s:%d' % (SSDP_ADDR, SSDP_PORT),
            'NTS: ssdp:alive',
            ]
        stcpy = dict(self.known[usn].iteritems())
        stcpy['NT'] = stcpy['ST']
        del stcpy['ST']
        del stcpy['MANIFESTATION']
        resp.extend(map(lambda x: ': '.join(x), stcpy.iteritems()))
        resp.extend(('', ''))
        log.msg('doNotify content', resp)
        self.transport.write('\r\n'.join(resp), (SSDP_ADDR, SSDP_PORT))
        self.transport.write('\r\n'.join(resp), (SSDP_ADDR, SSDP_PORT))

    def doByebye(self, st):
        """Do byebye"""

        log.msg('Sending byebye notification for %s' % st)

        resp = [ 'NOTIFY * HTTP/1.1',
                'HOST: %s:%d' % (SSDP_ADDR, SSDP_PORT),
                'NTS: ssdp:byebye',
                ]
        stcpy = dict(self.known[st].iteritems())
        stcpy['NT'] = stcpy['ST']
        del stcpy['ST']
        del stcpy['MANIFESTATION']
        resp.extend(map(lambda x: ': '.join(x), stcpy.iteritems()))
        resp.extend(('', ''))
        self.transport.write('\r\n'.join(resp), (SSDP_ADDR, SSDP_PORT))
        
    def resendNotify( self):
        for usn in self.known:
            if self.known[usn]['MANIFESTATION'] == 'local':
                self.doNotify(usn)

    def subscribe(self, name, callback):
        self._callbacks.setdefault(name,[]).append(callback)

    def unsubscribe(self, name, callback):
        callbacks = self._callbacks.get(name,[])
        if callback in callbacks:
            callbacks.remove(callback)
        self._callbacks[name] = callbacks

    def callback(self, name, *args):
        for callback in self._callbacks.get(name,[]):
            callback(*args)
