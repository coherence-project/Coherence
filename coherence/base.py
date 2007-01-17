# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import string
import socket
import os, sys
import traceback

from zope.interface import implements, Interface
from twisted.python import log, filepath, util
from twisted.python.components import registerAdapter
from twisted.internet import task, address
from twisted.internet import reactor
from nevow import athena, inevow, loaders, tags, static
from twisted.web import resource

import louie

from coherence.upnp.core.ssdp import SSDPServer
from coherence.upnp.core.msearch import MSearch
from coherence.upnp.core.device import Device, RootDevice
from coherence.upnp.core.utils import parse_xml, get_ip_address, get_host_address

from coherence.upnp.devices.control_point import ControlPoint
from coherence.upnp.devices.media_server import MediaServer
from coherence.upnp.devices.media_renderer import MediaRenderer

from coherence.backends.fs_storage import FSStore
from coherence.backends.elisa_storage import ElisaMediaStore

from coherence.backends.gstreamer_audio_player import Player

from coherence.extern.logger import Logger, LOG_WARNING
log = Logger('Coherence')

class IWeb(Interface):

    def goingLive(self):
        pass

class Web(object):

    def __init__(self, coherence):
        super(Web, self).__init__()
        self.coherence = coherence

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
<p>
<div nevow:render="listchilds"></div>
</p>
</body>
</html>
""")

    def __init__(self, *a, **kw):
        super(WebUI, self).__init__( *a, **kw)
        self.coherence = self.rootObject.coherence

    def childFactory(self, ctx, name):
        log.info('WebUI childFactory: %s' % name)
        try:
            return self.rootObject.coherence.children[name]
        except:
            ch = super(WebUI, self).childFactory(ctx, name)
            if ch is None:
                p = util.sibpath(__file__, name)
                if os.path.exists(p):
                    ch = static.File(p)
            return ch
        
    def render_listchilds(self, ctx, data):
        cl = []
        log.info('children: %s' % self.coherence.children)
        for c in self.coherence.children:
            device = self.coherence.get_device_with_id(c)
            if device != None:
                _,_,_,device_type,version = device.get_device_type().split(':')
                cl.append( tags.li[tags.a(href='/'+c)[device_type,
                                                      ':',
                                                      version,
                                                      ' ',
                                                      device.get_friendly_name()]])
            else:
                cl.append( tags.li[c])
        return ctx.tag[tags.ul[cl]]
        
class WebServer:

    def __init__(self, port, coherence):
        from nevow import appserver

        def ResourceFactory( original):
            return WebUI( IWeb, original)

        registerAdapter(ResourceFactory, Web, inevow.IResource)

        self.web_root_resource = Web(coherence)
        #self.web_root_resource = inevow.IResource( web)
        #print self.web_root_resource
        self.site = appserver.NevowSite( self.web_root_resource)
        reactor.listenTCP( port, self.site)
        
        log.warning( "WebServer on port %d ready" % port)


class Coherence:

    def __init__(self, config):
        self.devices = []
        
        self.children = {}
        self._callbacks = {}
        
        try:
            logmode = config['logmode']
        except:
            logmode = 'info'

        try:
            network_if = config['interface']
        except:
            network_if = None
        
        log.set_master_level(logmode)
        
        #log.disable(name='Variable')
        #log.enable(name='Variable')
        #log.set_level(name='Variable')

        plugin = louie.TwistedDispatchPlugin()
        louie.install_plugin(plugin)

        log.warning("Coherence UPnP framework starting...")
        self.ssdp_server = SSDPServer()
        louie.connect( self.add_device, 'Coherence.UPnP.SSDP.new_device', louie.Any)
        louie.connect( self.remove_device, 'Coherence.UPnP.SSDP.remove_device', louie.Any)
        louie.connect( self.receiver, 'Coherence.UPnP.Device.detection_completed', louie.Any)
        #louie.connect( self.receiver, 'Coherence.UPnP.Service.detection_completed', louie.Any)

        self.ssdp_server.subscribe("new_device", self.add_device)
        self.ssdp_server.subscribe("removed_device", self.remove_device)

        self.msearch = MSearch(self.ssdp_server)

        reactor.addSystemEventTrigger( 'before', 'shutdown', self.shutdown)

        self.web_server_port = 30020

        if network_if:
            self.hostname = get_ip_address(network_if)
        else:
            self.hostname = socket.gethostbyname(socket.gethostname())
            if self.hostname == '127.0.0.1':
                """ use interface detection via routing table as last resort """
                self.hostname = get_host_address() 

        log.warning('running on host: %s' % self.hostname)
        self.urlbase = 'http://%s:%d/' % (self.hostname, self.web_server_port)

        self.web_server = WebServer( self.web_server_port, self)
                                
        self.renew_service_subscription_loop = task.LoopingCall(self.check_devices)
        self.renew_service_subscription_loop.start(20.0, now=False)
        
        try:
            plugins = config['plugins']
            for p,a in plugins.items():
                plugin = p
                arguments = a
                if not isinstance(arguments, dict):
                    arguments = {}
                self.add_plugin(plugin, **arguments)
        except KeyError:
            log.warning("No plugin defined!")
        except Exception, msg:
            log.critical("Can't enable plugins, %s: %s!" % (plugin, msg))
        
    def add_plugin(self, plugin, **kwargs):
        try:
            plugin_class=globals().get(plugin)
            for device in plugin_class.implements:
                try:
                    device_class=globals().get(device)
                    log.critical("Activating %s plugin as %s..." % (plugin, device))
                    device_class(self, plugin_class, **kwargs)
                except KeyError:
                    log.critical("Can't enable %s plugin, sub-system %s not found!" % (plugin, device))
                except Exception, msg:
                    log.critical(traceback.print_exc())
                    log.critical("Can't enable %s plugin for sub-system %s, %s!" % (plugin, device, msg))
        except KeyError:
            log.critical("Can't enable %s plugin, not found!" % plugin)
        except Exception, msg:
            log.critical(traceback.print_exc())
            log.critical("Can't enable %s plugin, %s!" % (plugin, msg))
            
            
    def receiver( self, signal, *args, **kwargs):
        #print "Coherence receiver called with", signal
        #print kwargs
        pass

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
        self.ssdp_server.shutdown()
        log.warning('Coherence UPnP framework shutdown')
        
    def check_devices(self):
        """ iterate over devices and their embedded ones and renew subscriptions """
        for root_device in self.get_devices():
            root_device.renew_service_subscriptions()
            for device in root_device.get_devices():
                device.renew_service_subscriptions()

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
            id = device.get_id()
            if device_id[:5] != 'uuid:':
                id = id[5:]
            if id == device_id:
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
        # fire this only after the device detection is fully completed
        # and we are on the device level already, so we can work with them instead with the SSDP announce
        #if infos['ST'] == 'upnp:rootdevice':
        #    self.callback("new_device", infos['ST'], infos)


    def remove_device(self, device_type, infos):
        device = self.get_device_with_usn(infos['USN'])
        if device:
            self.devices.remove(device)
            if infos['ST'] == 'upnp:rootdevice':
                self.callback("removed_device", infos['ST'], infos['USN'])

            
    def add_web_resource(self, name, sub):
        #self.web_server.web_root_resource.putChild(name, sub)
        self.children[name] = sub
        #print self.web_server.web_root_resource.children

    def remove_web_resource(self, name):
        # XXX implement me
        pass
