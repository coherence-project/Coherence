# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uroegon.edu>

#
# Implementation of SSDP server under Twisted Python.
#

import random
import string
import sys
import time

from twisted.python import log
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, error


SSDP_PORT = 1900
SSDP_ADDR = '239.255.255.250'

class SSDPServer(DatagramProtocol):
    """A class implementing a SSDP server.  The notifyReceived and
    searchReceived methods are called when the appropriate type of
    datagram is received by the server."""

    # not used yet
    stdheaders = [ ('Server', 'Twisted, UPnP/1.0, python-upnp'), ]
    elements = {}
    known = {}

    _callbacks = {}

    def __init__(self, enable_log):
        
        # Create SSDP server
        try:
            port = reactor.listenMulticast(SSDP_PORT, self, listenMultiple=True)
        except error.CannotListenError, err:
            self._failure("There seems to be already a SSDP server running on this host, no need starting a second one.")
        else:
            if enable_log:
                log.startLogging(sys.stdout)
            
            # don't get our own sends
            port.setLoopbackMode(0)

            port.joinGroup(SSDP_ADDR)
        
    def _failure(self, error):
        print error
    
    def datagramReceived(self, data, (host, port)):
        """Handle a received multicast datagram."""
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

        if cmd[0] == 'M-SEARCH' and cmd[1] == '*':
            # SSDP discovery
            #self.discoveryRequest(headers, (host, port))
            pass
        elif cmd[0] == 'NOTIFY' and cmd[1] == '*':
            # SSDP presence
            self.notifyReceived(headers, (host, port))
        else:
            log.msg('Unknown SSDP command %s %s' % cmd)

    def register(self, usn, st, location, server, cache_control):
        """Register a service or device that this SSDP server will
        respond to."""
        
        #log.msg('Registering %s (%s)' % (st, location))

        self.known[usn] = {}
        self.known[usn]['USN'] = usn
        self.known[usn]['LOCATION'] = location
        self.known[usn]['ST'] = st
        self.known[usn]['EXT'] = ''
        self.known[usn]['SERVER'] = server
        self.known[usn]['CACHE-CONTROL'] = cache_control
        
        if st == 'upnp:rootdevice':
            self.callback("new_device", st, self.known[usn])

    def unRegister(self, usn):
        #log.msg("Un-registering %s" % usn)

        st = self.known[usn]['ST']
        if st == 'upnp:rootdevice':
            self.callback("removed_device", st, self.known[usn])
            
        del self.known[usn]

    def isKnown(self, usn):
        return self.known.has_key(usn)

    def notifyReceived(self, headers, (host, port)):
        """Process a presence announcement.  We just remember the
        details of the SSDP service announced."""

        if headers['nts'] == 'ssdp:alive':
            if not self.isKnown(headers['usn']):
                self.register(headers['usn'], headers['nt'], headers['location'],
                              headers['server'], headers['cache-control'])
        elif headers['nts'] == 'ssdp:byebye':
            if self.isKnown(headers['usn']):
                self.unRegister(headers['usn'])
        else:
            log.msg('Unknown subtype %s for notification type %s' %
                    (headers['nts'], headers['nt']))

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
