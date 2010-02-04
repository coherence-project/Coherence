# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006,2007,2008 Frank Scholz <coherence@beebits.net>

import string
import socket
import os, sys
import traceback
import copy

from twisted.python import filepath, util
from twisted.internet.tcp import CannotListenError
from twisted.internet import task, address, defer
from twisted.internet import reactor
from twisted.web import resource,static

import coherence.extern.louie as louie

from coherence import __version__
from coherence import log

from coherence.upnp.core.ssdp import SSDPServer
from coherence.upnp.core.msearch import MSearch
from coherence.upnp.core.device import Device, RootDevice
from coherence.upnp.core.utils import parse_xml, get_ip_address, get_host_address

from coherence.upnp.core.utils import Site

from coherence.upnp.devices.control_point import ControlPoint
from coherence.upnp.devices.media_server import MediaServer
from coherence.upnp.devices.media_renderer import MediaRenderer
from coherence.upnp.devices.binary_light import BinaryLight
from coherence.upnp.devices.dimmable_light import DimmableLight


try:
    import pkg_resources
except ImportError:
    pkg_resources = None


class SimpleRoot(resource.Resource, log.Loggable):
    addSlash = True
    logCategory = 'coherence'

    def __init__(self, coherence):
        resource.Resource.__init__(self)
        self.coherence = coherence
        self.http_hostname = '%s:%d' % (self.coherence.hostname, self.coherence.web_server_port)

    def getChild(self, name, request):
        self.debug('SimpleRoot getChild %s, %s' % (name, request))
        if name == 'oob':
            """ we have an out-of-band request """
            return static.File(self.coherence.dbus.pinboard[request.args['key'][0]])

        if name == '':
            return self

        # at this stage, name should be a device UUID
        try:
            return self.coherence.children[name]
        except:
            self.warning("Cannot find device for requested name:", name)
            request.setResponseCode(404)
            return static.Data('<html><p>No device for requested UUID: %s</p></html>' % name,'text/html')


    def listchilds(self, uri):
        self.info('listchilds %s' % uri)
        if uri[-1] != '/':
            uri += '/'
        cl = []
        for child in self.coherence.children:
            device = self.coherence.get_device_with_id(child)
            if device is not None:
                cl.append('<li><a href=%s%s>%s:%s %s</a></li>' % (
                        uri, child, device.get_friendly_device_type(),
                        device.get_device_type_version(),
                        device.get_friendly_name()))

        for child in self.children:
                cl.append('<li><a href=%s%s>%s</a></li>' % (uri, child, child))
        return "".join(cl)

    def render(self,request):
        result = """<html><head><title>Coherence</title></head><body>
<a href="http://coherence.beebits.net">Coherence</a> - a Python DLNA/UPnP framework for the Digital Living<p>Hosting:<ul>%s</ul></p></body></html>""" % self.listchilds(request.uri)
        return result.encode('utf-8')


class WebServer(log.Loggable):
    logCategory = 'webserver'

    def __init__(self, ui, port, coherence):
        try:
            if ui != 'yes':
                """ use this to jump out here if we do not want
                    the web ui """
                raise ImportError

            self.warning("Web UI not supported atm, will return with version 0.7.0")
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

        self.port = reactor.listenTCP( port, self.site)
        coherence.web_server_port = self.port._realPortNumber
        # XXX: is this the right way to do it?
        self.warning( "WebServer on port %d ready" % coherence.web_server_port)


class Plugins(log.Loggable):
    logCategory = 'plugins'
    _instance_ = None  # Singleton

    _valids = ("coherence.plugins.backend.media_server",
               "coherence.plugins.backend.media_renderer",
               "coherence.plugins.backend.binary_light",
               "coherence.plugins.backend.dimmable_light")

    _plugins = {}

    def __new__(cls, *args, **kwargs):
        obj = getattr(cls, '_instance_', None)
        if obj is not None:
            return obj
        else:
            obj = super(Plugins, cls).__new__(cls, *args, **kwargs)
            cls._instance_ = obj
            obj._collect(*args, **kwargs)
            return obj

    def __repr__(self):
        return str(self._plugins)

    def __init__(self, *args, **kwargs):
        pass

    def __getitem__(self, key):
        plugin = self._plugins.__getitem__(key)
        if pkg_resources and isinstance(plugin, pkg_resources.EntryPoint):
            try:
                plugin = plugin.load(require=False)
            except (ImportError, AttributeError, pkg_resources.ResolutionError), msg:
                self.warning("Can't load plugin %s (%s), maybe missing dependencies..." % (plugin.name,msg))
                self.info(traceback.format_exc())
                del self._plugins[key]
                raise KeyError
            else:
                self._plugins[key] = plugin
        return plugin

    def get(self, key,default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def __setitem__(self, key, value):
        self._plugins.__setitem__(key,value)

    def set(self, key,value):
        return self.__setitem__(key,value)

    def keys(self):
        return self._plugins.keys()

    def _collect(self, ids=_valids):
        if not isinstance(ids, (list,tuple)):
            ids = (ids,)
        if pkg_resources:
            for group in ids:
                for entrypoint in pkg_resources.iter_entry_points(group):
                    # set a placeholder for lazy loading
                    self._plugins[entrypoint.name] = entrypoint
        else:
            self.info("no pkg_resources, fallback to simple plugin handling")

        if len(self._plugins) == 0:
            self._collect_from_module()

    def _collect_from_module(self):
        from coherence.extern.simple_plugin import Reception
        reception = Reception(os.path.join(os.path.dirname(__file__),'backends'), log=self.warning)
        self.info(reception.guestlist())
        for cls in reception.guestlist():
            self._plugins[cls.__name__.split('.')[-1]] = cls


class Coherence(log.Loggable):
    logCategory = 'coherence'
    _instance_ = None  # Singleton

    def __new__(cls, *args, **kwargs):
        obj = getattr(cls, '_instance_', None)
        if obj is not None:
            cls._incarnations_ += 1
            return obj
        else:
            obj = super(Coherence, cls).__new__(cls)
            cls._instance_ = obj
            cls._incarnations_ = 1
            obj.setup(*args, **kwargs)
            obj.cls = cls
            return obj

    def __init__(self, *args, **kwargs):
        pass

    def clear(self):
        """ we do need this to survive multiple calls
            to Coherence during trial tests
        """
        self.cls._instance_ = None

    def setup(self, config={}):
        self.mirabeau = None

        self.devices = []
        self.children = {}
        self._callbacks = {}
        self.active_backends = {}

        self.dbus = None
        self.config = config
        self.ctrl = None

        network_if = config.get('interface')

        self.web_server_port = int(config.get('serverport', 0))

        """ initializes logsystem
            a COHERENCE_DEBUG environment variable overwrites
            all level settings here
        """

        try:
            logmode = config.get('logging').get('level','warning')
        except (KeyError,AttributeError):
            logmode = config.get('logmode', 'warning')
        _debug = []

        try:
            subsystems = config.get('logging')['subsystem']
            if isinstance(subsystems,dict):
                subsystems = [subsystems]
            for subsystem in subsystems:
                try:
                    if subsystem['active'] == 'no':
                        continue
                except (KeyError,TypeError):
                    pass
                self.info( "setting log-level for subsystem %s to %s" % (subsystem['name'],subsystem['level']))
                _debug.append('%s:%d' % (subsystem['name'].lower(), log.human2level(subsystem['level'])))
        except (KeyError,TypeError):
            subsystem_log = config.get('subsystem_log',{})
            for subsystem,level in subsystem_log.items():
                #self.info( "setting log-level for subsystem %s to %s" % (subsystem,level))
                _debug.append('%s:%d' % (subsystem.lower(), log.human2level(level)))
        if len(_debug) > 0:
            _debug = ','.join(_debug)
        else:
            _debug = '*:%d' % log.human2level(logmode)
        try:
            logfile = config.get('logging').get('logfile',None)
            if logfile != None:
                logfile = unicode(logfile)
        except (KeyError,AttributeError,TypeError):
            logfile = config.get('logfile', None)
        log.init(logfile, _debug)

        self.warning("Coherence UPnP framework version %s starting..." % __version__)

        if network_if:
            self.hostname = get_ip_address('%s' % network_if)
        else:
            try:
                self.hostname = socket.gethostbyname(socket.gethostname())
            except socket.gaierror:
                self.warning("hostname can't be resolved, maybe a system misconfiguration?")
                self.hostname = '127.0.0.1'

        if self.hostname.startswith('127.'):
            """ use interface detection via routing table as last resort """
            def catch_result(hostname):
                self.hostname = hostname
                self.setup_part2()
            d = defer.maybeDeferred(get_host_address)
            d.addCallback(catch_result)
        else:
            self.setup_part2()

    def setup_part2(self):

        self.info('running on host: %s' % self.hostname)
        if self.hostname.startswith('127.'):
            self.warning('detection of own ip failed, using %s as own address, functionality will be limited', self.hostname)

        unittest = self.config.get('unittest', 'no')
        if unittest == 'no':
            unittest = False
        else:
            unittest = True

        self.ssdp_server = SSDPServer(test=unittest,interface=self.hostname)
        louie.connect( self.create_device, 'Coherence.UPnP.SSDP.new_device', louie.Any)
        louie.connect( self.remove_device, 'Coherence.UPnP.SSDP.removed_device', louie.Any)
        louie.connect( self.add_device, 'Coherence.UPnP.RootDevice.detection_completed', louie.Any)
        #louie.connect( self.receiver, 'Coherence.UPnP.Service.detection_completed', louie.Any)

        self.ssdp_server.subscribe("new_device", self.add_device)
        self.ssdp_server.subscribe("removed_device", self.remove_device)

        self.msearch = MSearch(self.ssdp_server,test=unittest)

        reactor.addSystemEventTrigger( 'before', 'shutdown', self.shutdown, force=True)

        try:
            self.web_server = WebServer( self.config.get('web-ui',None), self.web_server_port, self)
        except CannotListenError:
            self.warning('port %r already in use, aborting!' % self.web_server_port)
            reactor.stop()
            return

        self.urlbase = 'http://%s:%d/' % (self.hostname, self.web_server_port)

        #self.renew_service_subscription_loop = task.LoopingCall(self.check_devices)
        #self.renew_service_subscription_loop.start(20.0, now=False)

        self.available_plugins = None


        try:
            plugins = self.config['plugin']
            if isinstance(plugins,dict):
                plugins=[plugins]
        except:
            plugins = None
        if plugins is None:
            plugins = self.config.get('plugins',None)

        if plugins is None:
            self.info("No plugin defined!")
        else:
            if isinstance(plugins,dict):
                for plugin,arguments in plugins.items():
                    try:
                        if not isinstance(arguments, dict):
                            arguments = {}
                        self.add_plugin(plugin, **arguments)
                    except Exception, msg:
                        self.warning("Can't enable plugin, %s: %s!" % (plugin, msg))
                        self.info(traceback.format_exc())
            else:
                for plugin in plugins:
                    try:
                        if plugin['active'] == 'no':
                            continue
                    except (KeyError,TypeError):
                        pass
                    try:
                        backend = plugin['backend']
                        arguments = copy.copy(plugin)
                        del arguments['backend']
                        backend = self.add_plugin(backend, **arguments)
                        if self.writeable_config() == True:
                            if 'uuid' not in plugin:
                                plugin['uuid'] = str(backend.uuid)[5:]
                                self.config.save()
                    except Exception, msg:
                        self.warning("Can't enable plugin, %s: %s!" % (plugin, msg))
                        self.info(traceback.format_exc())


        self.external_address = ':'.join((self.hostname,str(self.web_server_port)))


        if(self.config.get('controlpoint', 'no') == 'yes' or
           self.config.get('json','no') == 'yes'):
            self.ctrl = ControlPoint(self)

        if self.config.get('json','no') == 'yes':
            from coherence.json import JsonInterface
            self.json = JsonInterface(self.ctrl)

        if self.config.get('transcoding', 'no') == 'yes':
            from coherence.transcoder import TranscoderManager
            self.transcoder_manager = TranscoderManager(self)


        self.dbus = None
        if self.config.get('use_dbus', 'no') == 'yes':
            try:
                from coherence import dbus_service
                if self.ctrl == None:
                    self.ctrl = ControlPoint(self)
                self.ctrl.auto_client_append('InternetGatewayDevice')
                self.dbus = dbus_service.DBusPontoon(self.ctrl)
            except Exception, msg:
                self.warning("Unable to activate dbus sub-system: %r" % msg)
                self.debug(traceback.format_exc())
            else:
                if self.config.get('enable_mirabeau', 'no') == 'yes':
                    from coherence import mirabeau
                    from coherence.tube_service import MirabeauProxy

                    mirabeau_cfg = self.config.get('mirabeau', {})

                    self.mirabeau = mirabeau.Mirabeau(mirabeau_cfg, self)
                    self.add_web_resource('mirabeau', MirabeauProxy())
                    self.mirabeau.start()

    def add_plugin(self, plugin, **kwargs):
        self.info("adding plugin %r", plugin)

        self.available_plugins = Plugins()

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
                    new_backend = device_class(self, plugin_class, **kwargs)
                    self.active_backends[str(new_backend.uuid)] = new_backend
                    return new_backend
                except KeyError:
                    self.warning("Can't enable %s plugin, sub-system %s not found!" % (plugin, device))
                except Exception, msg:
                    self.warning("Can't enable %s plugin for sub-system %s, %s!" % (plugin, device, msg))
                    self.debug(traceback.format_exc())
        except KeyError, error:
            self.warning("Can't enable %s plugin, not found!" % plugin)
        except Exception, msg:
            self.warning("Can't enable %s plugin, %s!" % (plugin, msg))
            self.debug(traceback.format_exc())

    def remove_plugin(self, plugin):
        """ removes a backend from Coherence          """
        """ plugin is the object return by add_plugin """
        """ or an UUID string                         """

        if isinstance(plugin,basestring):
            try:
                plugin = self.active_backends[plugin]
            except KeyError:
                self.warning("no backend with the uuid %r found" % plugin)
                return ""

        try:
            del self.active_backends[str(plugin.uuid)]
            self.info("removing plugin %r", plugin)
            plugin.unregister()
            return plugin.uuid
        except KeyError:
            self.warning("no backend with the uuid %r found" % plugin.uuid)
            return ""

    def writeable_config(self):
        """ do we have a new-style config file """
        from coherence.extern.simple_config import ConfigItem
        if isinstance(self.config,ConfigItem):
            return True
        return False

    def store_plugin_config(self,uuid,items):
        """ find the backend with uuid
            and store in its the config
            the key and value pair(s)
        """
        plugins = self.config.get('plugin')
        if plugins is None:
            self.warning("storing a plugin config option is only possible with the new config file format")
            return
        if isinstance(plugins,dict):
            plugins = [plugins]
        uuid = str(uuid)
        if uuid.startswith('uuid:'):
            uuid = uuid[5:]
        if isinstance(items,tuple):
            new = {}
            new[items[0]] = items[1]
        for plugin in plugins:
            try:
                if plugin['uuid'] == uuid:
                    for k,v in items.items():
                        plugin[k] = v
                    self.config.save()
            except:
                pass
        else:
            self.info("storing plugin config option for %s failed, plugin not found" % uuid)

    def receiver( self, signal, *args, **kwargs):
        #print "Coherence receiver called with", signal
        #print kwargs
        pass

    def shutdown( self,force=False):
        if force == True:
            self._incarnations_ = 1
        if self._incarnations_ > 1:
            self._incarnations_ -= 1
            return

        def _shutdown():
            self.mirabeau = None
            if self.dbus:
                self.dbus.shutdown()
                self.dbus = None

            for backend in self.active_backends.itervalues():
                backend.unregister()
            self.active_backends = {}
            """ send service unsubscribe messages """
            try:
                if self.web_server.port != None:
                    self.web_server.port.stopListening()
                    self.web_server.port = None
                if hasattr(self.msearch, 'double_discover_loop'):
                    self.msearch.double_discover_loop.stop()
                if hasattr(self.msearch, 'port'):
                    self.msearch.port.stopListening()
                if hasattr(self.ssdp_server, 'resend_notify_loop'):
                    self.ssdp_server.resend_notify_loop.stop()
                if hasattr(self.ssdp_server, 'port'):
                    self.ssdp_server.port.stopListening()
                #self.renew_service_subscription_loop.stop()
            except:
                pass
            l = []
            for root_device in self.get_devices():
                for device in root_device.get_devices():
                    d = device.unsubscribe_service_subscriptions()
                    d.addCallback(device.remove)
                    l.append(d)
                d = root_device.unsubscribe_service_subscriptions()
                d.addCallback(root_device.remove)
                l.append(d)

            def homecleanup(result):
                """anything left over"""
                louie.disconnect( self.create_device, 'Coherence.UPnP.SSDP.new_device', louie.Any)
                louie.disconnect( self.remove_device, 'Coherence.UPnP.SSDP.removed_device', louie.Any)
                louie.disconnect( self.add_device, 'Coherence.UPnP.RootDevice.detection_completed', louie.Any)
                self.ssdp_server.shutdown()
                if self.ctrl:
                    self.ctrl.shutdown()
                self.warning('Coherence UPnP framework shutdown')
                return result

            dl = defer.DeferredList(l)
            dl.addCallback(homecleanup)
            return dl

        if self.mirabeau is not None:
            d = defer.maybeDeferred(self.mirabeau.stop)
            d.addBoth(lambda x: _shutdown())
            return d
        else:
            return _shutdown()

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

    def get_device_by_host(self, host):
        found = []
        for device in self.devices:
            if device.get_host() == host:
                found.append(device)
        return found

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

    def get_local_devices(self):
        return [d for d in self.devices if d.manifestation == 'local']

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
        self.info("adding device",device.get_id(),device.get_usn(),device.friendly_device_type)
        self.devices.append(device)

    def remove_device(self, device_type, infos):
        self.info("removed device",infos['ST'],infos['USN'])
        device = self.get_device_with_usn(infos['USN'])
        if device:
            louie.send('Coherence.UPnP.Device.removed', None, usn=infos['USN'])
            self.devices.remove(device)
            device.remove()
            if infos['ST'] == 'upnp:rootdevice':
                louie.send('Coherence.UPnP.RootDevice.removed', None, usn=infos['USN'])
                self.callback("removed_device", infos['ST'], infos['USN'])


    def add_web_resource(self, name, sub):
        self.children[name] = sub

    def remove_web_resource(self, name):
        try:
            del self.children[name]
        except KeyError:
            """ probably the backend init failed """
            pass

    def connect(self,receiver,signal=louie.signal.All,sender=louie.sender.Any, weak=True):
        """ wrapper method around louie.connect
        """
        louie.connect(receiver,signal=signal,sender=sender,weak=weak)

    def disconnect(self,receiver,signal=louie.signal.All,sender=louie.sender.Any, weak=True):
        """ wrapper method around louie.disconnect
        """
        louie.disconnect(receiver,signal=signal,sender=sender,weak=weak)
