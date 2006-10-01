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


from twisted.internet import reactor
from twisted.web import resource, server
from twisted.internet.protocol import Protocol, ClientCreator
import time
import utils
import socket

"""
TODO:

- unsubscribe()
- renewsubscribe()

"""

EVENT_SERVER_PORT = 10001


class EventProtocol(Protocol):

    def __init__(self, service):
        self.service = service

    def dataReceived(self, data):
        print " response received from the Service Events HTTP server "
        cmd, headers = utils.parse_http_response(data)
        print cmd, headers
        try:
            self.service.set_sid(headers['sid'])
            timeout = headers['timeout']
            print headers['sid'], headers['timeout']
            if timeout.startswith('Second-'):
                timeout = int(timeout[len('Second-'):])
                self.service.set_timeout(time.time() + timeout)
        except:
            #print headers
            pass
            
    def connectionLost( self, reason):
        print " connection closed from the Service Events HTTP server"
        
class EventServer(resource.Resource):

    def __init__(self, control_point):
        resource.Resource.__init__(self)
        self.putChild('', self)
        self.control_point = control_point
        reactor.listenTCP(EVENT_SERVER_PORT, server.Site(self))
        
    def render_NOTIFY(self, request):
        print "EventServer received request, code:", request.code
        headers = request.getAllHeaders()
        sid = headers['sid']
        data = request.content.getvalue()
        print "data:"
        print data
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
    
class Event(dict):
    def __init__(self, sid):
        dict.__init__(self)
        self._sid = sid

    def get_sid(self):
        return self._sid

def subscribe(service):
    """
    send a subscribe request to a service
    return the device response
    """

    service_url = service.get_base_url()
    
    host_port = service_url.split('//')[1]
    host,port = tuple(host_port.split(':'))
    port = int(port)

    print "host:", host, "port:", port
    def send_request(p):

        request = ["SUBSCRIBE %s HTTP/1.1" % service.get_event_sub_url(),
                   "TIMEOUT: Second-300",
                   "HOST: %s:%s" % (host, port),
                   ]

        if service.get_sid():
            request.append("SID: %s" % service.get_sid())
        else:
            ip_address = p.transport.getHost().host
            url = 'http://%s:10001/' % ip_address
            request.append("CALLBACK: <%s>" % url)
            request.append("NT: upnp:event")

        request.append( "Content-Length: 0")
        request.append( "")
        request.append( "")
        request = '\r\n'.join(request)
        print "event.subscribe.send_request", request
        return p.transport.write(request)

    c = ClientCreator(reactor, EventProtocol, service=service)
    c.connectTCP(host, port).addCallback(send_request)
