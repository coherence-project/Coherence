# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>


from twisted.internet import reactor
from twisted.web import resource, server
from twisted.internet.protocol import Protocol, ClientCreator

import platform
import time
import utils

from urlparse import urlsplit

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

    def render_NOTIFY(self, request):
        #print "EventServer received request, code:", request.code
        data = request.content.getvalue()
        if request.code != 200:
            print "data:"
            print data
        else:
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
        
    def render_SUBSCRIBE(self, request):
        #print "EventSubscriptionServer %s received request, code: %d" % (self.service.id, request.code)
        data = request.content.getvalue()
        if request.code != 200:
            print "data:"
            print data
        else:
            headers = request.getAllHeaders()
            try:
                s = self.subscribers[headers['sid']]
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
            request.setHeader('SERVER', ','.join([platform.system(),platform.release(),'UPnP/1.0,Coherence UPnP framework,0.1']))
            request.setHeader('CONTENT-LENGTH', 0)
        return ""
        
    def render_UNSUBSCRIBE(self, request):
        #print "EventSubscriptionServer received request, code:", request.code
        data = request.content.getvalue()
        if request.code != 200:
            print "data:"
            print data
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

    def dataReceived(self, data):
        #print "response received from the Service Events HTTP server "
        #print data
        cmd, headers = utils.parse_http_response(data)
        #print cmd, headers
        try:
            self.service.set_sid(headers['sid'])
            timeout = headers['timeout']
            #print headers['sid'], headers['timeout']
            if timeout.startswith('Second-'):
                timeout = int(timeout[len('Second-'):])
                self.service.set_timeout(time.time() + timeout)
        except:
            #print headers
            pass
            
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
    #print "event.subscribe, action:", action 
    service_url = service.get_base_url()
    
    host_port = service_url.split('//')[1]
    host,port = tuple(host_port.split(':'))
    port = int(port)

    def send_request(p, action):
        #print "event.subscribe.send_request, action:", action 
        if action == 'subscribe':
            request = ["SUBSCRIBE %s HTTP/1.1" % service.get_event_sub_url(),
                        "HOST: %s:%d" % (host, port),
                        "TIMEOUT: Second-300",
                        ]
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
        #print "event.subscribe.send_request", request
        return p.transport.write(request)

    def prepare_connection( service, action):
        #print "event.subscribe.prepare_connection action:", action
        c = ClientCreator(reactor, EventProtocol, service=service, action=action)
        d = c.connectTCP(host, port).addCallback(send_request, action=action)
        return d

    if action == 'unsubscribe':
        """ I'm uncertain if this is really the right way to do this,
            but so far it seems to work
        """
        reactor.addSystemEventTrigger( 'before', 'shutdown', prepare_connection, service, action)
    else:
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
    host,port = tuple(host_port.split(':'))
    port = int(port)

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
        #print "event.send_notification.send_request", request
        s['seq'] += 1
        return p.transport.write(request)

    c = ClientCreator(reactor, NotificationProtocol)
    d = c.connectTCP(host, port).addCallback(send_request)


