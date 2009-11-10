# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006,2007,2008,2009 Frank Scholz <coherence@beebits.net>

import time
from urlparse import urlsplit

from twisted.internet import reactor, defer
from twisted.web import resource, server
from twisted.web.http import datetimeToString
from twisted.internet.protocol import Protocol, ClientCreator, _InstanceFactory
from twisted.python import failure

from coherence import log, SERVER_ID
from coherence.upnp.core import utils

import coherence.extern.louie as louie

global hostname, web_server_port
hostname = None
web_server_port = None


class EventServer(resource.Resource, log.Loggable):
    logCategory = 'event_server'

    def __init__(self, control_point):
        self.coherence = control_point.coherence
        self.control_point = control_point
        self.coherence.add_web_resource('events',
                                        self)
        global hostname, web_server_port
        hostname = self.coherence.hostname
        web_server_port = self.coherence.web_server_port
        self.info("EventServer ready...")

    def render_NOTIFY(self, request):
        self.info("EventServer received notify from %s, code: %d" % (request.client, request.code))
        data = request.content.getvalue()
        request.setResponseCode(200)

        command = {'method': request.method, 'path': request.path}
        headers = request.received_headers
        louie.send('UPnP.Event.Server.message_received', None, command, headers, data)

        if request.code != 200:
            self.info("data:", data)
        else:
            self.debug("data:", data)
            headers = request.getAllHeaders()
            sid = headers['sid']
            try:
                tree = utils.parse_xml(data).getroot()
            except (SyntaxError,AttributeError):
                self.warning("malformed event notification from %r", request.client)
                self.debug("data: %r", data)
                request.setResponseCode(400)
                return ""

            event = Event(sid,tree,raw=data)
            if len(event) != 0:
                self.control_point.propagate(event)
        return ""


class EventSubscriptionServer(resource.Resource, log.Loggable):
    """
    This class ist the server part on the device side. It listens to subscribe
    requests and registers the subscriber to send event messages to this device.
    If an unsubscribe request is received, the subscription is cancelled and no
    more event messages will be sent.

    we receive a subscription request
    {'callback': '<http://192.168.213.130:9083/BYvZMzfTSQkjHwzOThaP/ConnectionManager>',
     'host': '192.168.213.107:30020',
     'nt': 'upnp:event',
     'content-length': '0',
     'timeout': 'Second-300'}

    modify the callback value
    callback = callback[1:len(callback)-1]
    and pack it into a subscriber dict

    {'uuid:oAQbxiNlyYojCAdznJnC':
        {'callback': '<http://192.168.213.130:9083/BYvZMzfTSQkjHwzOThaP/ConnectionManager>',
         'created': 1162374189.257338,
         'timeout': 'Second-300',
         'sid': 'uuid:oAQbxiNlyYojCAdznJnC'}}
    """
    logCategory = 'event_subscription_server'

    def __init__(self, service):
        resource.Resource.__init__(self)
        log.Loggable.__init__(self)
        self.service = service
        self.subscribers = service.get_subscribers()
        try:
            self.backend_name = self.service.backend.name
        except AttributeError:
            self.backend_name = self.service.backend

    def render_SUBSCRIBE(self, request):
        self.info( "EventSubscriptionServer %s (%s) received subscribe request from %s, code: %d" % (
                            self.service.id,
                            self.backend_name,
                            request.client, request.code))
        data = request.content.getvalue()
        request.setResponseCode(200)

        command = {'method': request.method, 'path': request.path}
        headers = request.received_headers
        louie.send('UPnP.Event.Client.message_received', None, command, headers, data)

        if request.code != 200:
            self.debug("data:", data)
        else:
            headers = request.getAllHeaders()
            try:
                #print self.subscribers
                #print headers['sid']
                if self.subscribers.has_key(headers['sid']):
                    s = self.subscribers[headers['sid']]
                    s['timeout'] = headers['timeout']
                    s['created'] = time.time()
                elif not headers.has_key('callback'):
                    request.setResponseCode(404)
                    request.setHeader('SERVER', SERVER_ID)
                    request.setHeader('CONTENT-LENGTH', 0)
                    return ""
            except:
                from uuid import UUID
                sid = UUID()
                s = { 'sid' : str(sid),
                      'callback' : headers['callback'][1:len(headers['callback'])-1],
                      'seq' : 0}
                s['timeout'] = headers['timeout']
                s['created'] = time.time()
                self.service.new_subscriber(s)

            request.setHeader('SID', s['sid'])
            #request.setHeader('Subscription-ID', sid)  wrong example in the UPnP UUID spec?
            request.setHeader('TIMEOUT', s['timeout'])
            request.setHeader('SERVER', SERVER_ID)
            request.setHeader('CONTENT-LENGTH', 0)
        return ""

    def render_UNSUBSCRIBE(self, request):
        self.info( "EventSubscriptionServer %s (%s) received unsubscribe request from %s, code: %d" % (
                            self.service.id,
                            self.backend_name,
                            request.client, request.code))
        data = request.content.getvalue()
        request.setResponseCode(200)

        command = {'method': request.method, 'path': request.path}
        headers = request.received_headers
        louie.send('UPnP.Event.Client.message_received', None, command, headers, data)

        if request.code != 200:
            self.debug("data:", data)
        else:
            headers = request.getAllHeaders()
            try:
                del self.subscribers[headers['sid']]
            except:
                """ XXX if not found set right error code """
                pass
            #print self.subscribers
        return ""


class Event(dict, log.Loggable):
    logCategory = 'event'
    ns = "urn:schemas-upnp-org:event-1-0"

    def __init__(self, sid,elements=None,raw=None):
        dict.__init__(self)
        self._sid = sid
        self.raw = raw
        if elements != None:
            self.from_elements(elements)

    def get_sid(self):
        return self._sid

    def from_elements(self,elements):
        for prop in elements.findall('{%s}property' % self.ns):
            self._update_event(prop)
        if len(self) == 0:
            self.warning("event notification without property elements")
            self.debug("data: %r", self.raw)
            for prop in elements.findall('property'):
                self._update_event(prop)

    def _update_event(self,prop):
        for var in prop.getchildren():
            tag = var.tag
            idx = tag.find('}') + 1
            value = var.text
            if value == None:
                value = ''
            self.update({tag[idx:]: value})



class EventProtocol(Protocol, log.Loggable):

    logCategory = 'event_protocol'

    def __init__(self, service, action):
        self.service = service
        self.action = action

    def teardown(self):
        self.transport.loseConnection()
        self.service.event_connection = None

    def connectionMade(self):
        self.timeout_checker = reactor.callLater(30, self.teardown)

    def dataReceived(self, data):
        try:
            self.timeout_checker.cancel()
        except:
            pass
        self.info("response received from the Service Events HTTP server ")
        #self.debug(data)
        cmd, headers = utils.parse_http_response(data)
        self.debug("%r %r", cmd, headers)
        if int(cmd[1]) != 200:
            self.warning("response with error code %r received upon our %r request", cmd[1], self.action)
            # XXX get around devices that return an error on our event subscribe request
            self.service.process_event({})
        else:
            try:
                self.service.set_sid(headers['sid'])
                timeout = headers['timeout']
                self.debug("%r %r", headers['sid'], headers['timeout'])
                if timeout == 'infinite':
                    self.service.set_timeout(time.time() + 4294967296) # FIXME: that's lame
                elif timeout.startswith('Second-'):
                    timeout = int(timeout[len('Second-'):])
                    self.service.set_timeout(timeout)
            except:
                #print headers
                pass
        self.teardown()

    def connectionLost( self, reason):
        try:
            self.timeout_checker.cancel()
        except:
            pass
        self.debug( "connection closed %r from the Service Events HTTP server", reason)


def unsubscribe(service, action='unsubscribe'):
    return subscribe(service, action)

def subscribe(service, action='subscribe'):
    """
    send a subscribe/renewal/unsubscribe request to a service
    return the device response
    """
    log_category = "event_protocol"
    log.info(log_category, "event.subscribe, action: %r", action)

    _,host_port,path,_,_ = urlsplit(service.get_base_url())
    if host_port.find(':') != -1:
        host,port = tuple(host_port.split(':'))
        port = int(port)
    else:
        host = host_port
        port = 80

    def send_request(p, action):
        log.info(log_category, "event.subscribe.send_request %r, action: %r %r",
                 p, action, service.get_event_sub_url())
        _,_,event_path,_,_ = urlsplit(service.get_event_sub_url())
        if action == 'subscribe':
            timeout = service.timeout
            if timeout == 0:
                timeout = 1800
            request = ["SUBSCRIBE %s HTTP/1.1" % event_path,
                        "HOST: %s:%d" % (host, port),
                        "TIMEOUT: Second-%d" % timeout,
                        ]
            service.event_connection = p
        else:
            request = ["UNSUBSCRIBE %s HTTP/1.1" % event_path,
                        "HOST: %s:%d" % (host, port),
                        ]

        if service.get_sid():
            request.append("SID: %s" % service.get_sid())
        else:
            # XXX use address and port set in the coherence instance
            #ip_address = p.transport.getHost().host
            global hostname, web_server_port
            #print hostname, web_server_port
            url = 'http://%s:%d/events' % (hostname, web_server_port)
            request.append("CALLBACK: <%s>" % url)
            request.append("NT: upnp:event")

        request.append('Date: %s' % datetimeToString())
        request.append( "Content-Length: 0")
        request.append( "")
        request.append( "")
        request = '\r\n'.join(request)
        log.debug(log_category, "event.subscribe.send_request %r %r", request, p)
        try:
            p.transport.writeSomeData(request)
        except AttributeError:
            log.info(log_category, "transport for event %r already gone", action)
       # print "event.subscribe.send_request", d
        #return d

    def got_error(failure, action):
        log.info(log_category, "error on %s request with %s" % (action,service.get_base_url()))
        log.debug(log_category, failure)

    def teardown_connection(c, d):
        log.info(log_category, "event.subscribe.teardown_connection")
        del d
        del c

    def prepare_connection( service, action):
        log.info(log_category, "event.subscribe.prepare_connection action: %r %r",
                 action, service.event_connection)
        if service.event_connection == None:
            c = ClientCreator(reactor, EventProtocol, service=service, action=action)
            log.info(log_category, "event.subscribe.prepare_connection: %r %r",
                     host, port)
            d = c.connectTCP(host, port)
            d.addCallback(send_request, action=action)
            d.addErrback(got_error, action)
            #reactor.callLater(3, teardown_connection, c, d)
        else:
            d = defer.Deferred()
            d.addCallback(send_request, action=action)
            d.callback(service.event_connection)
            #send_request(service.event_connection, action)
        return d

    """ FIXME:
        we need to find a way to be sure that our unsubscribe calls get through
        on shutdown
        reactor.addSystemEventTrigger( 'before', 'shutdown', prepare_connection, service, action)
    """

    return prepare_connection(service, action)
    #print "event.subscribe finished"


class NotificationProtocol(Protocol, log.Loggable):

    logCategory = "notification_protocol"

    def connectionMade(self):
        self.timeout_checker = reactor.callLater(30, lambda : self.transport.loseConnection())

    def dataReceived(self, data):
        try:
            self.timeout_checker.cancel()
        except:
            pass
        cmd, headers = utils.parse_http_response(data)
        self.debug( "notification response received %r %r", cmd, headers)
        try:
            if int(cmd[1]) != 200:
                self.warning("response with error code %r received upon our notification", cmd[1])
        except:
            self.debug("response without error code received upon our notification")
        self.transport.loseConnection()

    def connectionLost( self, reason):
        try:
            self.timeout_checker.cancel()
        except:
            pass
        self.debug("connection closed %r", reason)


def send_notification(s, xml):
    """
    send a notification a subscriber
    return its response
    """
    log_category = "notification_protocol"

    _,host_port,path,_,_ = urlsplit(s['callback'])
    if path == '':
        path = '/'
    if host_port.find(':') != -1:
        host,port = tuple(host_port.split(':'))
        port = int(port)
    else:
        host = host_port
        port = 80

    def send_request(p,port_item):
        request = ['NOTIFY %s HTTP/1.1' % path,
                    'HOST:  %s:%d' % (host, port),
                    'SEQ:  %d' % s['seq'],
                    'CONTENT-TYPE:  text/xml;charset="utf-8"',
                    'SID:  %s' % s['sid'],
                    'NTS:  upnp:propchange',
                    'NT:  upnp:event',
                    'Content-Length: %d' % len(xml),
                    '',
                    xml]

        request = '\r\n'.join(request)
        log.info(log_category, "send_notification.send_request to %r %r",
                 s['sid'], s['callback'])
        log.debug(log_category, "request: %r", request)
        s['seq'] += 1
        if s['seq'] > 0xffffffff:
            s['seq'] = 1
        p.transport.write(request)
        port_item.disconnect()
        #return p.transport.write(request)

    def got_error(failure,port_item):
        port_item.disconnect()
        log.info(log_category, "error sending notification to %r %r",
                 s['sid'], s['callback'])
        log.debug(log_category, failure)

    #c = ClientCreator(reactor, NotificationProtocol)
    #d = c.connectTCP(host, port)

    d = defer.Deferred()
    f = _InstanceFactory(reactor, NotificationProtocol(), d)
    port_item = reactor.connectTCP(host, port, f, timeout=30, bindAddress=None)

    d.addCallback(send_request, port_item)
    d.addErrback(got_error, port_item)

    return d,port_item
