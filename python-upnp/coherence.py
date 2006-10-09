#! /usr/bin/env python
#
# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
 	
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import task, address
from twisted.internet import reactor

import os
from zope.interface import implements, Interface
from twisted.python import log, filepath, util
from twisted.python.components import registerAdapter
from nevow import athena, inevow, loaders, tags, static
from twisted.web import resource


import service

from ssdp import SSDPServer
from msearch import MSearch
from device import Device, RootDevice
from utils import parse_xml

import string
import socket

class RootDeviceXML(static.Data):
	def __init__(self, hostname, uuid, urlbase):
		r = {
			'hostname': hostname,
			'uuid': uuid,
			'urlbase': urlbase,
		}
		d = file('root-device.xml').read() % r
		static.Data.__init__(self, d, 'text/xml')


class WebUI(athena.LivePage):
    """
    """

    addSlash = True
    docFactory = loaders.xmlstr("""\
<html xmlns:nevow="http://nevow.com/ns/nevow/0.1">
<head>
<nevow:invisible nevow:render="liveglue" />
<link rel="stylesheet" type="text/css" href="main.css" />
</head>
<body>
Coherence - a Python UPnP A/V framework
</body>
</html>
""")

    def __init__(self, coherence, *a, **kw):
        super(WebUI, self).__init__( *a, **kw)
        self.coherence = coherence

    def childFactory(self, ctx, name):
        ch = super(WebUI, self).childFactory(ctx, name)
        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = static.File(p)
        return ch
        
class WebServer:

    def __init__(self, port, coherence):
        from nevow import appserver
        
        self.web_root_resource = WebUI(coherence)
        self.site = appserver.NevowSite( self.web_root_resource)
        reactor.listenTCP( port, self.site)
        
        print "WebServer on port %d ready" % port


class Coherence:

    def __init__(self):
        print "Coherence UPnP framework starting..."
        self.enable_log = False
        self.devices = []
        
        self.ssdp_server = SSDPServer(self.enable_log)
        self.ssdp_server.subscribe("new_device", self.add_device)
        self.ssdp_server.subscribe("removed_device", self.remove_device)

        self.msearch = MSearch(self.ssdp_server)

        reactor.addSystemEventTrigger( 'before', 'shutdown', self.shutdown)

        self.web_server_port = 30020
        self.hostname = socket.gethostbyname(socket.gethostname())
        print 'running on host:', self.hostname
        self.urlbase = 'http://%s:%d/' % (self.hostname, self.web_server_port)

        self.web_server = WebServer( self.web_server_port, self)
        self.add_web_resource('root-device.xml',
                                RootDeviceXML( self.hostname,
                                'test',
                                self.urlbase))
                                
        self.renew_service_subscription_loop = task.LoopingCall(self.check_devices)
        self.renew_service_subscription_loop.start(20.0)


    
        # are we supposed to start a ControlPoint?
        try:
            from control_point import ControlPoint
            ControlPoint( self)
        except ImportError:
            print "Can't enable ControlPoint functions, sub-system not available."

        
        # are we supposed to start a MediaServer?
        try:
            from media_server import MediaServer
            MediaServer( self)
        except ImportError:
            print "Can't enable MediaServer functions, sub-system not available."
        
        # are we supposed to start a MediaRenderer?
        try:
            from media_renderer import MediaRenderer
            MediaRenderer( self)
        except ImportError:
            print "Can't enable MediaRenderer functions, sub-system not available."
        

    def shutdown( self):
        """ send service unsubscribe messages """
        try:
            self.renew_service_subscription_loop.stop()
        except:
            pass
        for root_device in self.get_devices():
            root_device.unsubscribe_service_subscriptions()
            for device in root_device.get_devices():
                device.unsubscribe_service_subscriptions()
        print 'Coherence UPnP framework shutdown'
        
    def check_devices(self):
        """ iterate over devices and their embedded ones and renew subscriptions """
        for root_device in self.get_devices():
            root_device.renew_service_subscriptions()
            for device in root_device.get_devices():
                device.renew_service_subscriptions()

    def subscribe(self, name, callback):
        self.ssdp_server.subscribe(name, callback)

    def unsubscribe(self, name, callback):
        self.ssdp_server.unsubscribe(name, callback)

    def get_device_with_usn(self, usn):
        found = None
        for device in self.devices:
            if device.get_usn() == usn:
                found = device
                break
        return found

    def get_device_with_id(self, device_id):
        found = None
        for device in self.devices:
            if device.get_id() == device_id:
                found = device
                break
        return found

    def get_devices(self):
        return self.devices

    def add_device(self, device_type, infos):
        if infos['ST'] == 'upnp:rootdevice':
            root = RootDevice(infos)
            self.devices.append(root)
        else:
            root_id = infos['USN'][:-len(infos['ST'])-2]
            root = self.get_device_with_id(root_id)
            device = Device(infos, root)

    def remove_device(self, device_type, infos):
        device = self.get_device_with_usn(infos['USN'])
        if device:
            self.devices.remove(device)
            
    def add_web_resource(self, name, sub):
        self.web_server.web_root_resource.putChild(name, sub)

    def remove_web_resource(self, name):
        # XXX implement me
        pass
        
def main():

    # get settings or options
    Coherence()
    reactor.run()
    
if __name__ == '__main__':
    main()
