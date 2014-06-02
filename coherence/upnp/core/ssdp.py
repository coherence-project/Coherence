# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006 John-Mark Gurney <gurney_j@resnet.uroegon.edu>
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006,2007,2008,2009 Frank Scholz <coherence@beebits.net>
# Copyright 2014 Hartmut Goebel <h.goebel@crazy-compilers.com>
#
# Implementation of a SSDP server under Twisted Python.
#

import random
import string
import sys
import time
import socket

from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, error
from twisted.internet import task
from twisted.web.http import datetimeToString

from coherence import log, SERVER_ID
from coherence.upnp.core import utils
import coherence.extern.louie as louie

SSDP_PORT = 1900
SSDP_ADDR = '239.255.255.250'


class SSDPServer(DatagramProtocol, log.Loggable):
    """A class implementing a SSDP server.  The notifyReceived and
    searchReceived methods are called when the appropriate type of
    datagram is received by the server."""
    logCategory = 'ssdp'

    def __init__(self, test=False, interface=''):
        # Create SSDP server
        log.Loggable.__init__(self)
        self._known = {}
        self._callbacks = {}
        self.__test = test
        self.active_calls = []
        self._resend_notify_loop = None
        self._expire_loop = None
        self._port = None
        if not self.__test:
            try:
                self._port = reactor.listenMulticast(SSDP_PORT, self,
                                                    listenMultiple=True)
                #self.port.setLoopbackMode(1)
                self._port.joinGroup(SSDP_ADDR, interface=interface)
            except error.CannotListenError, err:
                self.error("There seems to already be a SSDP server "
                           "running on this host, no need starting a "
                           "second one.")

            self._resend_notify_loop = task.LoopingCall(self._resendNotify)
            # notify every 777 seconds (~ 13 Minutes)
            self._resend_notify_loop.start(777.0, now=False)

            self._expire_loop = task.LoopingCall(self._expire)
            # expire every 333 seconds (~ 5.5 Minutes)
            self._expire_loop.start(333.0, now=False)

    def stopNotifying(self):
        if self._resend_notify_loop and self._resend_notify_loop.running:
            self._resend_notify_loop.stop()
        if self._port:
            self._port.stopListening()

    def shutdown(self):
        for call in reactor.getDelayedCalls():
            if call.func == self.__send__discovery_request:
                call.cancel()
        if not self.__test:
            self.stopNotifying()
            if self._expire_loop.running:
                self._expire_loop.stop()
            # Make sure we send out the byebye notifications.
            for st in self._known:
                if self._known[st]['MANIFESTATION'] == 'local':
                    self.doByebye(st)

    def datagramReceived(self, data, (host, port)):
        """Handle a received multicast datagram."""
        cmd, headers, content = utils.parse_http_response(data)
        cmd = cmd[:2] # we are interested in only the first two elements
        del content # we do not need the content
        self.info('SSDP command %s %s - from %s:%d', cmd[0], cmd[1], host, port)
        self.debug('with headers: %s', headers)
        if cmd == ['M-SEARCH', '*']:
            # SSDP discovery
            self._discoveryRequest(headers, (host, port))
        elif cmd == ['NOTIFY', '*']:
            # SSDP presence
            self._notifyReceived(headers, (host, port))
        else:
            self.warning('Unknown SSDP command %s %s', *cmd)

        # make raw data available
        # send out the signal after we had a chance to register the device
        louie.send('UPnP.SSDP.datagram_received', None, data, host, port)

    def register(self, manifestation, usn, st, location,
                        server=SERVER_ID,
                        cache_control='max-age=1800',
                        silent=False,
                        host=None):
        """Register a service or device that this SSDP server will
        respond to."""

        self.info('Registering %s (%s)', st, location)

        self._known[usn] = {
            'USN': usn, # Unique Service Name
            'LOCATION': location,
            'ST': st, # Service Type
            'EXT': '',
            'SERVER': server,
            'CACHE-CONTROL': cache_control,
            'MANIFESTATION': manifestation,
            'SILENT': silent,
            'HOST': host,
            'last-seen': time.time(),
            }
        self.debug('%r', self._known[usn])

        if manifestation == 'local':
            self.doNotify(usn)

        if st == 'upnp:rootdevice':
            louie.send('Coherence.UPnP.SSDP.new_device', None,
                       device_type=st, infos=self._known[usn])
            #self.callback("new_device", st, self._known[usn])

    def unRegister(self, usn):
        if not self._isKnown(usn):
            return
        self.info("Un-registering %s", usn)
        st = self._known[usn]['ST']
        if st == 'upnp:rootdevice':
            louie.send('Coherence.UPnP.SSDP.removed_device', None,
                       device_type=st, infos=self._known[usn])
            #self.callback("removed_device", st, self._known[usn])
        del self._known[usn]

    def isKnown(self, usn):
        return self._known.has_key(usn)

    def _notifyReceived(self, headers, (host, port)):
        """Process a presence announcement.  We just remember the
        details of the SSDP service announced."""

        self.info('Notification from (%s,%d) for %s', host, port, headers['nt'])
        self.debug('Notification headers: %s', headers)

        if headers['nts'] == 'ssdp:alive':
            try:
                self._known[headers['usn']]['last-seen'] = time.time()
            except KeyError:
                self.register('remote', headers['usn'], headers['nt'],
                              headers['location'], headers['server'],
                              headers['cache-control'], host=host)
            else:
                self.debug('updating last-seen for %r', headers['usn'])
        elif headers['nts'] == 'ssdp:byebye':
            self.unRegister(headers['usn'])
        else:
            self.warning('Unknown subtype %s for notification type %s',
                         headers['nts'], headers['nt'])
        louie.send('Coherence.UPnP.Log', None, 'SSDP', host,
                   'Notify %s for %s' % (headers['nts'], headers['usn']))

    def __send__discovery_request(self, response, destination, delay, usn):
        self.info('send discovery response delayed by %ds for %s to %r',
                  delay, usn, destination)
        try:
            self.transport.write(response, destination)
        except (AttributeError, socket.error), msg:
            self.info("failure sending out byebye notification: %r", msg)

    def _discoveryRequest(self, headers, (host, port)):
        """Process a discovery request.  The response must be sent to
        the address specified by (host, port)."""

        self.info('Discovery request from (%s,%d) for %s',
                  host, port, headers['st'])
        louie.send('Coherence.UPnP.Log', None, 'SSDP', host,
                   'M-Search for %s' % headers['st'])
        # Do we know about this service?
        for known in self._known.values():
            if known['MANIFESTATION'] == 'remote':
                continue
            elif known['SILENT'] and headers['st'] == 'ssdp:all':
                continue
            elif (headers['st'] == known['ST'] or
                  headers['st'] == 'ssdp:all'):
                response = []
                response.append('HTTP/1.1 200 OK')
                for k, v in known.iteritems():
                    if k not in ('MANIFESTATION', 'SILENT', 'HOST'):
                        response.append('%s: %s' % (k, v))
                response.append('DATE: %s' % datetimeToString())
                response.extend(('', ''))
                response = '\r\n'.join(response)

                delay = random.randint(0, int(headers['mx']))
                reactor.callLater(delay, self.__send__discovery_request,
                                  response, (host, port), delay, known['USN'])

    def __build_response(self, cmd, usn):
        resp = ['NOTIFY * HTTP/1.1',
            'HOST: %s:%d' % (SSDP_ADDR, SSDP_PORT),
            'NTS: %s' % cmd,
            ]
        stcpy = self._known[usn].copy()
        stcpy['NT'] = stcpy['ST']
        for k in ('ST', 'MANIFESTATION', 'SILENT', 'HOST', 'last-seen'):
            try:
                # :fixme: this keys should always exist as we build the entry
                del stcpy[k]
            except:
                pass
        resp.extend(': '.join(x) for x in stcpy.iteritems())
        resp.extend(('', ''))
        return '\r\n'.join(resp)

    def doNotify(self, usn):
        """Do notification"""
        if self._known[usn]['SILENT']:
            return
        self.info('Sending alive notification for %s', usn)
        resp = self.__build_response('ssdp:alive', usn)
        self.debug('doNotify content %s', resp)
        try:
            # :fixme: why is this sent twice?
            self.transport.write(resp, (SSDP_ADDR, SSDP_PORT))
            self.transport.write(resp, (SSDP_ADDR, SSDP_PORT))
        except (AttributeError, socket.error), msg:
            self.info("failure sending out alive notification: %r", msg)

    def doByebye(self, usn):
        """Do byebye"""
        # :todo: unite with doNotify(). Why are there differences at all?
        self.info('Sending byebye notification for %s', usn)
        resp = self.__build_response('ssdp:byebye', usn)
        self.debug('doByebye content %s', resp)
        if self.transport:
            try:
                self.transport.write(resp, (SSDP_ADDR, SSDP_PORT))
            except (AttributeError, socket.error), msg:
                self.info("failure sending out byebye notification: %r",
                          msg)

    def _resendNotify(self):
        for usn, entry in self._known.iteritems():
            if entry['MANIFESTATION'] == 'local':
                self.doNotify(usn)

    def _expire(self):
        """ check if the discovered devices are still ok, or
            if we haven't received a new discovery response
        """
        self.debug("Checking devices/services are still valid")
        removable = []
        for usn, entry in self._known.iteritems():
            if entry['MANIFESTATION'] == 'local':
                continue
            expiry = int(entry['CACHE-CONTROL'].split('=')[1])
            now = time.time()
            last_seen = entry['last-seen']
            self.debug("Checking if %r is still valid - "
                       "last seen %d (+%d), now %d",
                       entry['USN'], last_seen, expiry, now)
            if last_seen + expiry + 30 < now:
                self.debug("Expiring: %r", entry)
                if entry['ST'] == 'upnp:rootdevice':
                    louie.send('Coherence.UPnP.SSDP.removed_device', None,
                               device_type=entry['ST'], infos=entry)
                removable.append(usn)
        for usn in removable:
            del self._known[usn]

    def subscribe(self, name, callback):
        self._callbacks.setdefault(name, []).append(callback)

    def unsubscribe(self, name, callback):
        callbacks = self._callbacks.get(name, [])
        if callback in callbacks:
            callbacks.remove(callback)
        self._callbacks[name] = callbacks

    def callback(self, name, *args):
        for callback in self._callbacks.get(name, []):
            callback(*args)
