# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007 - Frank Scholz <coherence@beebits.net>

""" DBUS service class

"""

import time

#import gtk
import dbus

if dbus.__version__ < '0.82.2':
    raise ImportError, 'dbus-python module too old, pls get a newer one from http://dbus.freedesktop.org/releases/dbus-python/'

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import dbus.service
import dbus.gobject_service

#import dbus.glib

DLNA_BUS_NAME = 'org.DLNA'     # bus name for DLNA API

BUS_NAME = 'org.Coherence'     # the one with the dots
OBJECT_PATH = '/org/Coherence'  # the one with the slashes ;-)

from coherence import __version__
from coherence.upnp.core import DIDLLite


import coherence.extern.louie as louie

from coherence import log

class DBusProxy(log.Loggable):
    logCategory = 'dbus'

    def __init__(self, bus):
        self.bus = bus


class DBusService(dbus.service.Object,log.Loggable):
    logCategory = 'dbus'

    def __init__(self, service, dbus_device, bus):
        self.service = service
        self.dbus_device = dbus_device
        self.type = self.service.service_type.split(':')[3] # get the service name
        bus_name = dbus.service.BusName(BUS_NAME+'.service', bus)
        self.path = OBJECT_PATH + '/devices/' + dbus_device.id + '/services/' + self.type
        s = dbus.service.Object.__init__(self, bus_name, self.path)
        self.debug("DBusService %r %r %r", service, self.type, s)
        louie.connect(self.variable_changed, 'Coherence.UPnP.StateVariable.changed', sender=self.service)

        self.subscribe()

        #interfaces = self._dbus_class_table[self.__class__.__module__ + '.' + self.__class__.__name__]
        #for (name, funcs) in interfaces.iteritems():
        #    print name, funcs
        #    if funcs.has_key('destroy_object'):
        #        print """removing 'destroy_object'"""
        #        del funcs['destroy_object']
        #    for func in funcs.values():
        #        if getattr(func, '_dbus_is_method', False):
        #            print self.__class__._reflect_on_method(func)

        #self._get_service_methods()

    def _get_service_methods(self):
        '''Returns a list of method descriptors for this object'''
        methods = []
        for func in dir(self):
            func = getattr(self,func)
            if callable(func) and hasattr(func, '_dbus_is_method'):
                print func, func._dbus_interface, func._dbus_is_method
                if hasattr(func, 'im_func'):
                    print func.im_func

    def variable_changed(self,variable):
        #print self.service, "got signal for change of", variable
        #print variable.name, variable.value
        #print type(variable.name), type(variable.value)
        self.StateVariableChanged(self.dbus_device.device.get_id(),self.type,variable.name, variable.value)

    @dbus.service.signal(BUS_NAME+'.service',
                         signature='sssv')
    def StateVariableChanged(self, udn, service, variable, value):
        self.info("%s service %s signals StateVariable %s changed to %r" % (self.dbus_device.device.get_friendly_name(), self.type, variable, value))

    @dbus.service.method(BUS_NAME+'.service',in_signature='',out_signature='as')
    def get_available_actions(self):
        actions = self.service.get_actions()
        r = []
        for name in actions.keys():
            r.append(name)
        return r

    @dbus.service.method(BUS_NAME+'.service',in_signature='sv',out_signature='v',
                         async_callbacks=('dbus_async_cb', 'dbus_async_err_cb'))
    def action(self,name,arguments,dbus_async_cb,dbus_async_err_cb):

        def reply(data):
            dbus_async_cb(dbus.Dictionary(data,signature='sv',variant_level=4))

        if self.service.client is not None:
            #print "action", name
            func = getattr(self.service.client,name,None)
            #print "action", func
            if callable(func):
                kwargs = {}
                try:
                    for k,v in arguments.items():
                        kwargs[str(k)] = unicode(v)
                except:
                    pass
                d = func(**kwargs)
                d.addCallback(reply)
                d.addErrback(dbus_async_err_cb)
        return ''

    @dbus.service.method(BUS_NAME+'.service',in_signature='v',out_signature='v',
                         async_callbacks=('dbus_async_cb', 'dbus_async_err_cb'))
    def destroy_object(self,arguments,dbus_async_cb,dbus_async_err_cb):

        def reply(data):
            dbus_async_cb(dbus.Dictionary(data,signature='sv',variant_level=4))

        if self.service.client is not None:
            kwargs = {}
            for k,v in arguments.items():
                kwargs[str(k)] = str(v)
            d = self.service.client.destroy_object(**kwargs)
            d.addCallback(reply)
            d.addErrback(dbus_async_err_cb)
        return ''

    @dbus.service.method(BUS_NAME+'.service',in_signature='',out_signature='ssv')
    def subscribe(self):
        notify = [v for v in self.service._variables[0].values() if v.send_events == True]
        if len(notify) == 0:
            return
        data = {}
        for n in notify:
            if n.name == 'LastChange':
                lc = {}
                for instance, vdict in self.service._variables.items():
                    v = {}
                    for variable in vdict.values():
                        if( variable.name != 'LastChange' and
                            variable.name[0:11] != 'A_ARG_TYPE_' and
                            variable.never_evented == False):
                                if hasattr(variable, 'dbus_updated') == False:
                                    variable.dbus_updated = None
                                #if variable.dbus_updated != variable.last_touched:
                                #    v[unicode(variable.name)] = unicode(variable.value)
                                #    variable.dbus_updated = time.time()
                                #    #FIXME: we are missing variable dependencies here
                    if len(v) > 0:
                        lc[str(instance)] = v
                if len(lc) > 0:
                    data[unicode(n.name)] = lc
            else:
                data[unicode(n.name)] = unicode(n.value)
        return self.dbus_device.device.get_id(), self.type, dbus.Dictionary(data,signature='sv',variant_level=3)


class DBusDevice(dbus.service.Object,log.Loggable):
    logCategory = 'dbus'

    def __init__(self,device, bus):
        self.device = device
        self.id = device.get_id()[5:].replace('-','')
        bus_name = dbus.service.BusName(BUS_NAME+'.device', bus)
        d = dbus.service.Object.__init__(self, bus_name, self.path())
        self.debug("DBusDevice %r %r %r", device, self.id, d)
        self.services = []
        for service in device.get_services():
            self.services.append(DBusService(service,self,bus))

    def path(self):
        return OBJECT_PATH + '/devices/' + self.id

    @dbus.service.method(BUS_NAME+'.device',in_signature='',out_signature='v')
    def get_info(self):
        r = {'path':self.path(),
             'device_type':self.device.get_device_type(),
             'friendly_name':self.device.get_friendly_name(),
             'udn':self.device.get_id(),
             'services':[x.path for x in self.services]}
        return dbus.Dictionary(r,signature='sv',variant_level=2)

    @dbus.service.method(BUS_NAME+'.device',in_signature='',out_signature='s')
    def get_friendly_name(self):
        return self.device.get_friendly_name()

    @dbus.service.method(BUS_NAME+'.device',in_signature='',out_signature='s')
    def get_id(self):
        return self.device.get_id()

    @dbus.service.method(BUS_NAME+'.device',in_signature='',out_signature='s')
    def get_device_type(self):
        return self.device.get_device_type()

    @dbus.service.method(BUS_NAME+'.device',in_signature='',out_signature='s')
    def get_usn(self):
        return self.device.get_usn()

    @dbus.service.method(BUS_NAME+'.device',in_signature='',out_signature='av')
    def get_device_icons(self):
        return dbus.Array(self.device.icons,signature='av',variant_level=2)


class DBusPontoon(dbus.service.Object,log.Loggable):
    logCategory = 'dbus'

    def __init__(self,controlpoint):
        self.bus = dbus.SessionBus()
        self.bus_name = dbus.service.BusName(BUS_NAME, self.bus)
        dbus.service.Object.__init__(self, self.bus_name, OBJECT_PATH)

        self.debug("D-Bus pontoon %r %r %r" % (self, self.bus, self.bus_name))

        self.devices = []
        self.controlpoint = controlpoint

        for device in self.controlpoint.get_devices():
            self.devices.append(DBusDevice(device,self.bus_name))

        louie.connect(self.cp_ms_detected, 'Coherence.UPnP.ControlPoint.MediaServer.detected', louie.Any)
        louie.connect(self.cp_ms_removed, 'Coherence.UPnP.ControlPoint.MediaServer.removed', louie.Any)
        louie.connect(self.cp_mr_detected, 'Coherence.UPnP.ControlPoint.MediaRenderer.detected', louie.Any)
        louie.connect(self.cp_mr_removed, 'Coherence.UPnP.ControlPoint.MediaRenderer.removed', louie.Any)
        louie.connect(self.remove_client, 'Coherence.UPnP.Device.remove_client', louie.Any)

        self.debug("D-Bus pontoon started")
        self.pinboard = {}

    @dbus.service.method(BUS_NAME,in_signature='sv',out_signature='')
    def pin(self,key,value):
        self.pinboard[key] = value
        print self.pinboard

    @dbus.service.method(BUS_NAME,in_signature='s',out_signature='v')
    def get_pin(self,key):
        return self.pinboard.get(key,'Coherence::Pin::None')

    @dbus.service.method(BUS_NAME,in_signature='s',out_signature='')
    def unpin(self,key):
        del self.pinboard[key]

    @dbus.service.method(BUS_NAME,in_signature='s',out_signature='s')
    def create_oob(self,file):
        print 'create_oob'
        key = str(time.time())
        self.pinboard[key] = file
        print self.pinboard
        return self.controlpoint.coherence.urlbase + 'oob?key=' + key

    def remove_client(self, usn, client):
        self.info("removed %s %s" % (client.device_type,client.device.get_friendly_name()))
        try:
            getattr(self,str('UPnP_ControlPoint_%s_removed' % client.device_type))(usn)
        except:
            pass

    def remove(self,udn):
        #print "DBusPontoon remove", udn
        for device in self.devices:
            #print "check against", device.device.get_id()
            if udn == device.device.get_id():
                device.device = None
                self.devices.remove(device)
                break

    @dbus.service.method(BUS_NAME,in_signature='',out_signature='s')
    def version(self):
        return __version__

    @dbus.service.method(BUS_NAME,in_signature='',out_signature='s')
    def hostname(self):
        return self.controlpoint.coherence.hostname

    @dbus.service.method(BUS_NAME,in_signature='',out_signature='av')
    def get_devices(self):
        r = []
        for device in self.devices:
            #r.append(device.path())
            r.append(device.get_info())
        return dbus.Array(r,signature='v',variant_level=2)

    @dbus.service.method(BUS_NAME,in_signature='s',out_signature='v')
    def get_device_with_id(self,id):
        r = {}
        device = self.controlpoint.get_device_with_id(id)
        r['id'] = device.get_id()
        r['udn'] = device.udn
        r['name'] = device.get_friendly_name()
        r['type'] = device.get_device_type()
        return r

    @dbus.service.method(BUS_NAME,in_signature='ssoss',out_signature='s')
    def register(self, device_type, name, dbus_object,action_mapping,container_mapping):
        id = "n/a"
        return id

    @dbus.service.method(BUS_NAME,in_signature='sa{ss}',out_signature='s')
    def add_plugin(self,backend,arguments):
        kwargs = {}
        for k,v in arguments.iteritems():
            kwargs[str(k)] = str(v)
        p = self.controlpoint.coherence.add_plugin(backend,**kwargs)
        return str(p.uuid)

    @dbus.service.method(BUS_NAME,in_signature='s',out_signature='s')
    def remove_plugin(self,uuid):
        return self.controlpoint.coherence.remove_plugin(uuid)

    @dbus.service.method(BUS_NAME,in_signature='ssa{ss}',out_signature='s')
    def call_plugin(self,uuid,method,arguments):
        try:
            plugin = self.controlpoint.coherence.active_backends[uuid]
        except KeyError:
            self.warning("no backend with the uuid %r found" % uuid)
            return ""
        function = getattr(plugin.backend, method, None)
        if function == None:
            return ""
        kwargs = {}
        for k,v in arguments.iteritems():
            kwargs[str(k)] = unicode(v)
        function(**kwargs)
        return uuid


    @dbus.service.method(BUS_NAME,in_signature='ssa{ss}',out_signature='v',
                         async_callbacks=('dbus_async_cb', 'dbus_async_err_cb'))
    def create_object(self,device_id,container_id,arguments,dbus_async_cb,dbus_async_err_cb):
        device = self.controlpoint.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            new_arguments = {}
            for k,v in arguments.items():
                new_arguments[str(k)] = unicode(v)

            def reply(data):
                dbus_async_cb(dbus.Dictionary(data,signature='sv',variant_level=4))

            d = client.content_directory.create_object(str(container_id), new_arguments)
            d.addCallback(reply)
            d.addErrback(dbus_async_err_cb)

    @dbus.service.method(BUS_NAME,in_signature='sss',out_signature='v',
                         async_callbacks=('dbus_async_cb', 'dbus_async_err_cb'))
    def import_resource(self,device_id,source_uri, destination_uri,dbus_async_cb,dbus_async_err_cb):
        device = self.controlpoint.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()

            def reply(data):
                dbus_async_cb(dbus.Dictionary(data,signature='sv',variant_level=4))

            d = client.content_directory.import_resource(str(source_uri), str(destination_uri))
            d.addCallback(reply)
            d.addErrback(dbus_async_err_cb)

    @dbus.service.method(BUS_NAME,in_signature='ss',out_signature='v',
                         async_callbacks=('dbus_async_cb', 'dbus_async_err_cb'))
    def put_resource(self,destination_uri,filepath,dbus_async_cb,dbus_async_err_cb):
        def reply(data):
            dbus_async_cb(200)

        d = self.controlpoint.put_resource(str(destination_uri),unicode(filepath))
        d.addCallback(reply)
        d.addErrback(dbus_async_err_cb)

    def cp_ms_detected(self,client,udn=''):
        new_device = DBusDevice(client.device,self.bus)
        self.devices.append(new_device)
        self.UPnP_ControlPoint_MediaServer_detected(new_device.get_info(),udn)

    def cp_mr_detected(self,client,udn=''):
        new_device = DBusDevice(client.device,self.bus)
        self.devices.append(new_device)
        self.UPnP_ControlPoint_MediaRenderer_detected(new_device.get_info(),udn)

    def cp_ms_removed(self,udn):
        #print "cp_ms_removed", udn
        self.UPnP_ControlPoint_MediaServer_removed(udn)
        self.remove(udn)

    def cp_mr_removed(self,udn):
        self.UPnP_ControlPoint_MediaRenderer_removed(udn)
        self.remove(udn)

    @dbus.service.signal(BUS_NAME,
                         signature='vs')
    def UPnP_ControlPoint_MediaServer_detected(self,device,udn):
        self.info("emitting signal UPnP_ControlPoint_MediaServer_detected")

    @dbus.service.signal(BUS_NAME,
                         signature='s')
    def UPnP_ControlPoint_MediaServer_removed(self,udn):
        self.info("emitting signal UPnP_ControlPoint_MediaServer_removed")

    @dbus.service.signal(BUS_NAME,
                         signature='vs')
    def UPnP_ControlPoint_MediaRenderer_detected(self,device,udn):
        self.info("emitting signal UPnP_ControlPoint_MediaRenderer_detected")

    @dbus.service.signal(BUS_NAME,
                         signature='s')
    def UPnP_ControlPoint_MediaRenderer_removed(self,udn):
        self.info("emitting signal UPnP_ControlPoint_MediaRenderer_removed")
