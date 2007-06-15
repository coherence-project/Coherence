# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import time
from urlparse import urlsplit

from twisted.internet import reactor
from twisted.web import resource, server
from twisted.internet.protocol import Protocol, ClientCreator
from twisted.python import failure

from coherence import SERVER_ID
from coherence.upnp.core import utils

from coherence.extern.logger import Logger
log = Logger('Event')


global hostname, web_server_port
hostname = None
web_server_port = None

class EventServer(resource.Resource):

    def __init__(self, control_point):
        self.coherence = control_point.coherence
        self.control_point = control_point
        self.coherence.add_web_resource('events',
                                        self)
        global hostname, web_server_port
        hostname = self.coherence.hostname
        web_server_port = self.coherence.web_server_port
        log.warning("EventServer ready...")

    def render_NOTIFY(self, request):
        log.info("EventServer received notify from %s, code: %d" % (request.client, request.code))
        data = request.content.getvalue()
        if request.code != 200:
            log.info("data:", data)
        else:
            log.debug("data:", data)
            headers = request.getAllHeaders()
            sid = headers['sid']
            tree = utils.parse_xml(data).getroot()
            ns = "urn:schemas-upnp-org:event-1-0"
            event = Event(sid)
            for prop in tree.findall('{%s}property' % ns):
                for var in prop.getchildren():
                    tag = var.tag
                    idx = tag.find('}') + 1
                    event.update({tag[idx:]: var.text})
            self.control_point.propagate(event)
        return ""


class EventSubscriptionServer(resource.Resource):
    """
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
    def __init__(self, service):
        self.service = service
        self.subscribers = service.get_subscribers()
        try:
            self.backend_name = self.service.backend.name
        except AttributeError:
            self.backend_name = self.service.backend

    def render_SUBSCRIBE(self, request):
        log.info( "EventSubscriptionServer %s (%s) received subscribe request from %s, code: %d" % (
                            self.service.id,
                            self.backend_name,
                            request.client, request.code))
        data = request.content.getvalue()
        if request.code != 200:
            log.debug("data:", data)
        else:
            headers = request.getAllHeaders()
            try:
                #print self.subscribers
                #print headers['sid']
                if self.subscribers.has_key(headers['sid']):
                    s = self.subscribers[headers['sid']]
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
                reactor.callLater(0.8, self.service.new_subscriber, s)

            s['timeout'] = headers['timeout']
            s['created'] = time.time()

            request.setHeader('SID', s['sid'])
            #request.setHeader('Subscription-ID', sid)  wrong example in the UPnP UUID spec?
            request.setHeader('TIMEOUT', s['timeout'])
            request.setHeader('SERVER', SERVER_ID)
            request.setHeader('CONTENT-LENGTH', 0)
        return ""

    def render_UNSUBSCRIBE(self, request):
        log.info( "EventSubscriptionServer %s (%s) received unsubscribe request from %s, code: %d" % (
                            self.service.id,
                            self.backend_name,
                            request.client, request.code))
        data = request.content.getvalue()
        if request.code != 200:
            log.debug("data:", data)
        else:
            headers = request.getAllHeaders()
            try:
                del self.subscribers[headers['sid']]
            except:
                """ XXX if not found set right error code """
                pass
            #print self.subscribers
        return ""

class Event(dict):
    def __init__(self, sid):
        dict.__init__(self)
        self._sid = sid

    def get_sid(self):
        return self._sid

class EventProtocol(Protocol):

    def __init__(self, service, action):
        self.service = service
        self.action = action

    def __del__(self):
        pass
        #print "EventProtocol deleted"

    def dataReceived(self, data):
        log.info("response received from the Service Events HTTP server ")
        #log.debug(data)
        cmd, headers = utils.parse_http_response(data)
        log.debug(cmd, headers)
        try:
            self.service.set_sid(headers['sid'])
            timeout = headers['timeout']
            log.debug(headers['sid'], headers['timeout'])
            if timeout.startswith('Second-'):
                timeout = int(timeout[len('Second-'):])
                self.service.set_timeout(time.time() + timeout)
        except:
            #print headers
            pass

        #del self.service
        #del self

    def connectionLost( self, reason):
        #print "connection closed from the Service Events HTTP server"
        pass

def unsubscribe(service, action='unsubscribe'):
    subscribe(service, action)

def subscribe(service, action='subscribe'):
    """
    send a subscribe/renewal/unsubscribe request to a service
    return the device response
    """
    log.info("event.subscribe, action:", action)

    _,host_port,path,_,_ = urlsplit(service.get_base_url())
    if host_port.find(':') != -1:
        host,port = tuple(host_port.split(':'))
        port = int(port)
    else:
        host = host_port
        port = 80

    def send_request(p, action):
        log.info("event.subscribe.send_request, action:", action, service.get_event_sub_url())
        if action == 'subscribe':
            request = ["SUBSCRIBE %s HTTP/1.1" % service.get_event_sub_url(),
                        "HOST: %s:%d" % (host, port),
                        "TIMEOUT: Second-300",
                        ]
            service.event_connection = p
        else:
            request = ["UNSUBSCRIBE %s HTTP/1.1" % service.get_event_sub_url(),
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

        request.append( "Content-Length: 0")
        request.append( "")
        request.append( "")
        request = '\r\n'.join(request)
        log.debug("event.subscribe.send_request", request)
        return p.transport.write(request)

    def got_error(failure, action):
        log.info("error on %s request with %s" % (action,service.get_base_url()))
        log.debug(failure)

    def teardown_connection(c, d):
        log.info("event.subscribe.teardown_connection")
        del d
        del c

    def prepare_connection( service, action):
        log.info("event.subscribe.prepare_connection action:", action, service.event_connection)
        if service.event_connection == None:
            c = ClientCreator(reactor, EventProtocol, service=service, action=action)
            log.info("event.subscribe.prepare_connection:", host, port)
            d = c.connectTCP(host, port)
            d.addCallback(send_request, action=action)
            d.addErrback(got_error, action)
            #reactor.callLater(3, teardown_connection, c, d)
        else:
            send_request(service.event_connection, action)

    """ FIXME:
        we need to find a way to be sure that our unsubscribe calls get through
        on shutdown
        reactor.addSystemEventTrigger( 'before', 'shutdown', prepare_connection, service, action)
    """

    prepare_connection(service, action)

    #print "event.subscribe finished"

class NotificationProtocol(Protocol):

    def __init__(self):
        pass

    def dataReceived(self, data):
        #print "Notificationresponse received"
        #cmd, headers = utils.parse_http_response(data)
        #print cmd, headers
        pass

    def connectionLost( self, reason):
        #print "connection closed from the Service Events HTTP server"
        pass


def send_notification(s, xml):
    """
    send a notification a subscriber
    return its response
    """

    _,host_port,path,_,_ = urlsplit(s['callback'])
    if host_port.find(':') != -1:
        host,port = tuple(host_port.split(':'))
        port = int(port)
    else:
        host = host_port
        port = 80

    def send_request(p):
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
        log.info("send_notification.send_request to", s['sid'], s['callback'])
        log.debug("request:", request)
        s['seq'] += 1
        return p.transport.write(request)

    def got_error(failure):
        log.info("error sending notification to", s['sid'], s['callback'])
        log.debug(failure)

    c = ClientCreator(reactor, NotificationProtocol)
    d = c.connectTCP(host, port)
    d.addCallback(send_request)
    d.addErrback(got_error)
