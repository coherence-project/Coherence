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

from coherence import __version__

from coherence.upnp.core.ssdp import SSDPServer
from coherence.upnp.core.msearch import MSearch
from coherence.upnp.core.device import Device, RootDevice
from coherence.upnp.core.utils import parse_xml, get_ip_address, get_host_address

from coherence.upnp.core.utils import Site

from coherence.upnp.devices.control_point import ControlPoint
from coherence.upnp.devices.media_server import MediaServer
from coherence.upnp.devices.media_renderer import MediaRenderer

from coherence import log

class SimpleRoot(resource.Resource, log.Loggable):
    addSlash = True
    logCategory = 'coherence'

    def __init__(self, coherence):
        resource.Resource.__init__(self)
        self.coherence = coherence

    def getChild(self, name, request):
        self.info('SimpleRoot getChild %s, %s' % (name, request))
        try:
            return self.coherence.children[name]
        except:
            return self

    def listchilds(self, uri):
        self.info('listchilds %s' % uri)
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


class WebServer(log.Loggable):
    logCategory = 'webserver'

    def __init__(self, ui, port, coherence):
        try:
            if ui != 'yes':
                """ use this to jump out here if we do not want
                    the web ui """
                raise ImportError

            from nevow import __version_info__, __version__
            if __version_info__ <(0,9,17):
                self.warning( "Nevow version %s too old, disabling WebUI" % __version__)
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
        self.info( "WebServer on port %d ready" % coherence.web_server_port)


class Coherence(log.Loggable):
    logCategory = 'coherence'
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

        self.dbus = None
        self.config = config

        network_if = config.get('interface')

        self.web_server_port = int(config.get('serverport', 0))

        """ initializes logsystem
            a COHERENCE_DEBUG environment variable overwrites
            all level settings here
        """
        subsystem_log = config.get('subsystem_log',{})
        logmode = config.get('logmode', 'warning')
        _debug = []
        for subsystem,level in subsystem_log.items():
            #self.info( "setting log-level for subsystem %s to %s" % (subsystem,level))
            _debug.append('%s:%d' % (subsystem.lower(), log.human2level(level)))
        if len(_debug) > 0:
            _debug = ','.join(_debug)
        else:
            _debug = '*:%d' % log.human2level(logmode)
        log.init(config.get('logfile', None),_debug)

        plugin = louie.TwistedDispatchPlugin()
        louie.install_plugin(plugin)

        self.warning("Coherence UPnP framework version %s starting..." % __version__)

        if config.get('use_dbus', 'no') == 'yes':
            try:
                from coherence import dbus_service
                self.dbus = dbus_service.DBusPontoon(self)
            except Exception, msg:
                self.warning("Unable to activate dbus sub-system: %r" % msg)
                self.debug(traceback.format_exc())

        self.ssdp_server = SSDPServer()
        louie.connect( self.create_device, 'Coherence.UPnP.SSDP.new_device', louie.Any)
        louie.connect( self.remove_device, 'Coherence.UPnP.SSDP.removed_device', louie.Any)
        louie.connect( self.add_device, 'Coherence.UPnP.Device.detection_completed', louie.Any)
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
                self.error("hostname can't be resolved, maybe a system misconfiguration?")
                self.hostname = '127.0.0.1'

        if self.hostname == '127.0.0.1':
            """ use interface detection via routing table as last resort """
            self.hostname = get_host_address()

        self.info('running on host: %s' % self.hostname)
        if self.hostname == '127.0.0.1':
            self.warning('detection of own ip failed, using 127.0.0.1 as own address, functionality will be limited')
        self.web_server = WebServer( config.get('web-ui',None), self.web_server_port, self)

        self.urlbase = 'http://%s:%d/' % (self.hostname, self.web_server_port)

        self.renew_service_subscription_loop = task.LoopingCall(self.check_devices)
        self.renew_service_subscription_loop.start(20.0, now=False)

        self.available_plugins = None

        plugins = config.get('plugins',None)
        if plugins is None:
            self.warning("No plugin defined!")
        else:
            for plugin,arguments in plugins.items():
                try:
                    if not isinstance(arguments, dict):
                        arguments = {}
                    self.add_plugin(plugin, **arguments)
                except Exception, msg:
                    self.warning("Can't enable plugin, %s: %s!" % (plugin, msg))
                    self.info(traceback.format_exc())

        if config.get('controlpoint', 'no') == 'yes':
            self.ctrl = ControlPoint(self)

    def add_plugin(self, plugin, **kwargs):
        self.info("adding plugin", plugin)

        def get_available_plugins(ids):
            if self.available_plugins is None:
                self.available_plugins = {}
                if not isinstance(ids, (list,tuple)):
                    ids = (ids)
                try:
                    import pkg_resources
                    for id in ids:
                        for entrypoint in pkg_resources.iter_entry_points(id):
                            try:
                                self.available_plugins[entrypoint.name] = entrypoint.load()
                            except ImportError, msg:
                                self.warning("Can't load plugin %s (%s), maybe missing dependencies..." % (entrypoint.name,msg))
                                self.info(traceback.format_exc())
                except ImportError:
                    """ no pkg_resources/setuptools installed """
                    self.info("plugin reception activated, no pkg_resources")
                    from coherence.extern.simple_plugin import Reception
                    reception = Reception(os.path.join(os.path.dirname(__file__),'backends'), log=self.warning)
                    for cls in reception.guestlist():
                        self.available_plugins[cls.__name__.split('.')[-1]] = cls


        get_available_plugins(("coherence.plugins.backend.media_server",
                               "coherence.plugins.backend.media_renderer"))
        try:
            plugin_class = self.available_plugins.get(plugin,None)
            if plugin_class == None:
                raise KeyError
            for device in plugin_class.implements:
                try:
                    device_class=globals().get(device,None)
                    if device_class == None:
                        raise KeyError
                    self.info("Activating %s plugin as %s..." % (plugin, device))
                    return device_class(self, plugin_class, **kwargs)
                except KeyError:
                    self.warning("Can't enable %s plugin, sub-system %s not found!" % (plugin, device))
                except Exception, msg:
                    self.warning("Can't enable %s plugin for sub-system %s, %s!" % (plugin, device, msg))
                    self.debug(traceback.format_exc())
        except KeyError:
            self.warning("Can't enable %s plugin, not found!" % plugin)
        except Exception, msg:
            self.warning("Can't enable %s plugin, %s!" % (plugin, msg))
            self.debug(traceback.format_exc())


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
            for device in root_device.get_devices():
                d = device.unsubscribe_service_subscriptions()
                l.append(d)
                d.addCallback(device.remove)
            d = root_device.unsubscribe_service_subscriptions()
            l.append(d)
            d.addCallback(root_device.remove)

        self.ssdp_server.shutdown()
        dl = defer.DeferredList(l)
        self.warning('Coherence UPnP framework shutdown')
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

    def create_device(self, device_type, infos):
        self.info("creating ", infos['ST'],infos['USN'])
        if infos['ST'] == 'upnp:rootdevice':
            self.info("creating upnp:rootdevice ", infos['USN'])
            root = RootDevice(infos)
        else:
            self.info("creating device/service ",infos['USN'])
            root_id = infos['USN'][:-len(infos['ST'])-2]
            root = self.get_device_with_id(root_id)
            device = Device(infos, root)
        # fire this only after the device detection is fully completed
        # and we are on the device level already, so we can work with them instead with the SSDP announce
        #if infos['ST'] == 'upnp:rootdevice':
        #    self.callback("new_device", infos['ST'], infos)

    def add_device(self, device):
        self.info("adding device",device.get_usn())
        self.devices.append(device)

    def remove_device(self, device_type, infos):
        self.info("removed device",infos['ST'],infos['USN'])
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
