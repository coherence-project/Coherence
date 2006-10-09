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

global hostname, web_server_port
hostname = None
web_server_port = None

class EventServer(resource.Resource):

    def __init__(self, name, control_point):
        self.coherence = control_point.coherence
        self.control_point = control_point
        self.coherence.add_web_resource('events',
                                        self)
        global hostname, web_server_port
        hostname = self.coherence.hostname
        web_server_port = self.coherence.web_server_port
        
    def render_NOTIFY(self, request):
        print "EventServer received request, code:", request.code
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
                        "HOST: %s:%s" % (host, port),
                        "TIMEOUT: Second-300",
                        ]
        else:
            request = ["UNSUBSCRIBE %s HTTP/1.1" % service.get_event_sub_url(),
                        "HOST: %s:%s" % (host, port),
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
