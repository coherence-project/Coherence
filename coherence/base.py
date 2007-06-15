# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import string
import socket
import os, sys
import traceback

from twisted.python import filepath, util
from twisted.internet import task, address, defer
from twisted.internet import reactor
from twisted.web import resource

import louie

import pkg_resources

from coherence import __version__

from coherence.upnp.core.ssdp import SSDPServer
from coherence.upnp.core.msearch import MSearch
from coherence.upnp.core.device import Device, RootDevice
from coherence.upnp.core.utils import parse_xml, get_ip_address, get_host_address

from coherence.upnp.core.utils import Site

from coherence.upnp.devices.control_point import ControlPoint
from coherence.upnp.devices.media_server import MediaServer
from coherence.upnp.devices.media_renderer import MediaRenderer

from coherence.extern.logger import Logger, LOG_WARNING
log = Logger('Coherence')


class SimpleRoot(resource.Resource):
    addSlash = True

    def __init__(self, coherence):
        resource.Resource.__init__(self)
        self.coherence = coherence

    def getChild(self, name, request):
        log.info('SimpleRoot getChild %s, %s' % (name, request))
        try:
            return self.coherence.children[name]
        except:
            return self

    def listchilds(self, uri):
        log.info('listchilds %s' % uri)
        if uri[-1] != '/':
            uri += '/'
        cl = ''
        for c in self.coherence.children:
            device = self.coherence.get_device_with_id(c)
            if device != None:
                _,_,_,device_type,version = device.get_device_type().split(':')
                cl +=  '<li><a href=%s%s>%s:%s %s</a></li>' % (
                                        uri,c,
                                        device_type.encode('utf-8'), version.encode('utf-8'),
                                        device.get_friendly_name().encode('utf-8'))

        for c in self.children:
                cl += '<li><a href=%s%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return """<html><head><title>Coherence</title></head><body>
<a href="http://coherence.beebits.net">Coherence</a> - a Python UPnP A/V framework for the Digital Living<p>Hosting:<ul>%s</ul></p></body></html>""" % self.listchilds(request.uri)


class WebServer:

    def __init__(self, ui, port, coherence):
        try:
            if ui != 'yes':
                """ use this to jump out here if we do not want
                    the web ui """
                raise ImportError

            from nevow import __version_info__, __version__
            if __version_info__ <(0,9,17):
                log.warning( "Nevow version %s too old, disabling WebUI" % __version__)
                raise ImportError

            from nevow import appserver, inevow
            from coherence.web.ui import Web, IWeb, WebUI
            from twisted.python.components import registerAdapter

            def ResourceFactory( original):
                return WebUI( IWeb, original)

            registerAdapter(ResourceFactory, Web, inevow.IResource)

            self.web_root_resource = Web(coherence)
            self.site = appserver.NevowSite( self.web_root_resource)
        except ImportError:
            self.site = Site(SimpleRoot(coherence))

        port = reactor.listenTCP( port, self.site)
        coherence.web_server_port = port._realPortNumber
        # XXX: is this the right way to do it?
        log.warning( "WebServer on port %d ready" % coherence.web_server_port)


class Coherence(object):
    _instance_ = None  # Singleton

    def __new__(cls, *args, **kwargs):
        obj = getattr(cls, '_instance_', None)
        if obj is not None:
            return obj
        else:
            obj = super(Coherence, cls).__new__(cls, *args, **kwargs)
            cls._instance_ = obj
            obj.setup(*args, **kwargs)
            return obj

    def __init__(self, *args, **kwargs):
        pass

    def setup(self, config={}):

        self.devices = []
        self.children = {}
        self._callbacks = {}

        logmode = config.get('logmode', 'info')
        network_if = config.get('interface')

        self.web_server_port = int(config.get('serverport', 0))
        log.start_logging(config.get('logfile', None))

        log.set_master_level(logmode)

        subsystem_log = config.get('subsystem_log',{})

        for subsystem,level in subsystem_log.items():
            log.warning( "setting log-level for subsystem %s to %s" % (subsystem,level))
            log.set_level(name=subsystem,level=level)

        #log.disable(name='Variable')
        #log.enable(name='Variable')
        #log.set_level(name='Variable')

        plugin = louie.TwistedDispatchPlugin()
        louie.install_plugin(plugin)

        if config.get('logfile', None) is not None:
            print "Coherence UPnP framework version %s starting..." % __version__
            print "directing output to logfile %s" % config.get('logfile')

        log.warning("Coherence UPnP framework version %s starting..." % __version__)
        self.ssdp_server = SSDPServer()
        louie.connect( self.add_device, 'Coherence.UPnP.SSDP.new_device', louie.Any)
        louie.connect( self.remove_device, 'Coherence.UPnP.SSDP.removed_device', louie.Any)
        louie.connect( self.receiver, 'Coherence.UPnP.Device.detection_completed', louie.Any)
        #louie.connect( self.receiver, 'Coherence.UPnP.Service.detection_completed', louie.Any)

        self.ssdp_server.subscribe("new_device", self.add_device)
        self.ssdp_server.subscribe("removed_device", self.remove_device)

        self.msearch = MSearch(self.ssdp_server)

        reactor.addSystemEventTrigger( 'before', 'shutdown', self.shutdown)

        if network_if:
            self.hostname = get_ip_address(network_if)
        else:
            try:
                self.hostname = socket.gethostbyname(socket.gethostname())
            except socket.gaierror:
                log.error("hostname can't be resolved, maybe a system misconfiguration?")
                self.hostname = '127.0.0.1'

            if self.hostname == '127.0.0.1':
                """ use interface detection via routing table as last resort """
                self.hostname = get_host_address()

        log.warning('running on host: %s' % self.hostname)
        if self.hostname == '127.0.0.1':
            log.error('detection of own ip failed, using 127.0.0.1 as own address, functionality will be limited')
        self.web_server = WebServer( config.get('web-ui',None), self.web_server_port, self)

        self.urlbase = 'http://%s:%d/' % (self.hostname, self.web_server_port)

        self.renew_service_subscription_loop = task.LoopingCall(self.check_devices)
        self.renew_service_subscription_loop.start(20.0, now=False)

        self.installed_plugins = {}

        for entrypoint in pkg_resources.iter_entry_points("coherence.plugins.backend.media_server"):
            try:
                self.installed_plugins[entrypoint.name] = entrypoint.load()
            except ImportError:
                log.warning("Can't load plugin %s, maybe missing dependencies..." % entrypoint.name)
        for entrypoint in pkg_resources.iter_entry_points("coherence.plugins.backend.media_renderer"):
            try:
                self.installed_plugins[entrypoint.name] = entrypoint.load()
            except ImportError:
                log.warning("Can't load plugin %s, maybe missing dependencies..." % entrypoint.name)

        plugins = config.get('plugins',None)
        if plugins is None:
            log.warning("No plugin defined!")
        else:
            for plugin,arguments in plugins.items():
                try:
                    if not isinstance(arguments, dict):
                        arguments = {}
                    self.add_plugin(plugin, **arguments)
                except Exception, msg:
                    log.critical("Can't enable plugin, %s: %s!" % (plugin, msg))

        if config.get('controlpoint', 'no') == 'yes':
            self.ctrl = ControlPoint(self)

    def add_plugin(self, plugin, **kwargs):
        log.info("adding plugin", plugin)
        try:
            #plugin_class=globals().get(plugin,None)
            plugin_class = self.installed_plugins.get(plugin,None)
            if plugin_class == None:
                raise KeyError
            for device in plugin_class.implements:
                try:
                    device_class=globals().get(device,None)
                    if device_class == None:
                        raise KeyError
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
        l = []
        for root_device in self.get_devices():
            l.append(root_device.unsubscribe_service_subscriptions())
            for device in root_device.get_devices():
                l.append(device.unsubscribe_service_subscriptions())
        self.ssdp_server.shutdown()
        dl = defer.DeferredList(l)
        log.warning('Coherence UPnP framework shutdown')
        return dl

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

    def get_nonlocal_devices(self):
        return [d for d in self.devices if d.manifestation == 'remote']

    def add_device(self, device_type, infos):
        log.info("adding",infos['ST'],infos['USN'])
        if infos['ST'] == 'upnp:rootdevice':
            log.info("adding upnp:rootdevice",infos['USN'])
            root = RootDevice(infos)
            self.devices.append(root)
        else:
            log.info("adding device/service",infos['USN'])
            root_id = infos['USN'][:-len(infos['ST'])-2]
            root = self.get_device_with_id(root_id)
            device = Device(infos, root)
        # fire this only after the device detection is fully completed
        # and we are on the device level already, so we can work with them instead with the SSDP announce
        #if infos['ST'] == 'upnp:rootdevice':
        #    self.callback("new_device", infos['ST'], infos)


    def remove_device(self, device_type, infos):
        log.info("removed device",infos['ST'],infos['USN'])
        device = self.get_device_with_usn(infos['USN'])
        if device:
            self.devices.remove(device)
            device.remove()
            if infos['ST'] == 'upnp:rootdevice':
                louie.send('Coherence.UPnP.Device.removed', None, usn=infos['USN'])
                self.callback("removed_device", infos['ST'], infos['USN'])


    def add_web_resource(self, name, sub):
        #self.web_server.web_root_resource.putChild(name, sub)
        self.children[name] = sub
        #print self.web_server.web_root_resource.children

    def remove_web_resource(self, name):
        # XXX implement me
        pass
