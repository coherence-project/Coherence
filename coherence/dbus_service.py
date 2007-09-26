# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007 - Frank Scholz <coherence@beebits.net>

""" DBUS service class

"""

#import gtk
import dbus

if dbus.__version__ < '0.82.2':
    raise ImportError, 'dbus-python module too old, pls get a newer one from http://dbus.freedesktop.org/releases/dbus-python/'

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import dbus.service
#import dbus.glib


BUS_NAME = 'org.Coherence'     # the one with the dots
OBJECT_PATH = '/org/Coherence'  # the one with the slashes ;-)

from coherence import __version__

import louie

from coherence import log

class DBusService(dbus.service.Object,log.Loggable):
    logCategory = 'dbus'

    def __init__(self, service, dbus_device, bus):
        self.service = service
        self.dbus_device = dbus_device
        self.type = self.service.service_type.split(':')[3] # get the service name
        bus_name = dbus.service.BusName(BUS_NAME+'.service', bus)
        dbus.service.Object.__init__(self, bus_name, OBJECT_PATH + '/devices/' + dbus_device.id + '/services/' + self.type)

    @dbus.service.signal(BUS_NAME+'.service',
                         signature='ss')
    def StateVariableChanged(self, variable, value):
        self.info("%s service %s signals StateVariable %s changed" % (self.dbus_device.device.get_friendly_name(), self.type, variable))

    @dbus.service.method(BUS_NAME+'.service',in_signature='v',out_signature='v',
                         async_callbacks=('dbus_async_cb', 'dbus_async_err_cb'))
    def browse(self,arguments,dbus_async_cb,dbus_async_err_cb):

        def reply(data):
            dbus_async_cb(dbus.Dictionary(data,signature='sv',variant_level=4))

        if self.service.client is not None:
            kwargs = {}
            for k,v in arguments.items():
                kwargs[str(k)] = str(v)
            d = self.service.client.browse(**kwargs)
            d.addCallback(reply)
            d.addErrback(dbus_async_err_cb)
        return ''

class DBusDevice(dbus.service.Object,log.Loggable):
    logCategory = 'dbus'

    def __init__(self,device, bus):
        self.device = device
        self.id = device.get_id()[5:].replace('-','')
        bus_name = dbus.service.BusName(BUS_NAME+'.device', bus)
        dbus.service.Object.__init__(self, bus_name, OBJECT_PATH + '/devices/' + self.id)
        self.services = []
        for service in device.get_services():
            self.services.append(DBusService(service,self,bus))

    @dbus.service.method(BUS_NAME+'.device',in_signature='',out_signature='v')
    def get_info(self):
        r = [self.device.get_device_type(),
                self.device.get_friendly_name(),
                self.device.get_usn(),
                self.services]
        return dbus.Array(r,signature='v',variant_level=2)

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

class DBusPontoon(dbus.service.Object,log.Loggable):
    logCategory = 'dbus'

    def __init__(self,controlpoint):
        self.controlpoint = controlpoint
        self.bus = dbus.SessionBus()
        self.bus_name = dbus.service.BusName(BUS_NAME, self.bus)
        dbus.service.Object.__init__(self, self.bus_name, OBJECT_PATH)

        #print "pontoon", self, self.bus, self.bus_name

        self.devices = []

        for device in self.controlpoint.get_devices():
            self.devices.append(DBusDevice(device,self.bus_name))

        louie.connect(self.cp_ms_detected, 'Coherence.UPnP.ControlPoint.MediaServer.detected', louie.Any)
        louie.connect(self.UPnP_ControlPoint_MediaServer_removed, 'Coherence.UPnP.ControlPoint.MediaServer.removed', louie.Any)
        louie.connect(self.cp_mr_detected, 'Coherence.UPnP.ControlPoint.MediaRenderer.detected', louie.Any)
        louie.connect(self.UPnP_ControlPoint_MediaRenderer_removed, 'Coherence.UPnP.ControlPoint.MediaRenderer.removed', louie.Any)
        louie.connect(self.remove_client, 'Coherence.UPnP.Device.remove_client', louie.Any)

    def remove_client(self, usn, client):
        self.info("removed %s %s" % (client.device_type,client.device.get_friendly_name()))
        try:
            getattr(self,str('UPnP_ControlPoint_%s_removed' % client.device_type))(usn)
        except:
            pass

    @dbus.service.method(BUS_NAME,in_signature='',out_signature='s')
    def version(self):
        return __version__

    @dbus.service.method(BUS_NAME,in_signature='',out_signature='ao')
    def get_devices(self):
        r = []
        for device in self.devices:
            r.append(device)
        return r

    @dbus.service.method(BUS_NAME,in_signature='',out_signature='v')
    def get_devices_old(self):
        r = []
        for device in self.controlpoint.get_devices():
            r.append(device.get_id())
        return r

    @dbus.service.method(BUS_NAME,in_signature='s',out_signature='v')
    def get_device_with_id(self,id):
        r = {}
        device = self.controlpoint.get_device_with_id(id)
        r['id'] = device.get_id()
        r['usn'] = device.usn
        r['name'] = device.get_friendly_name()
        r['type'] = device.get_device_type()
        return r

    @dbus.service.method(BUS_NAME,in_signature='sv',out_signature='v',
                         async_callbacks=('dbus_async_cb', 'dbus_async_err_cb'))
    def mediaserver_cds_browse(self,device_id,arguments,dbus_async_cb,dbus_async_err_cb):

        def reply(data):
            dbus_async_cb(dbus.Dictionary(data,signature='sv',variant_level=4))

        device = self.controlpoint.get_device_with_id(device_id)
        if device is not None:
            client = device.get_client()
            kwargs = {}
            for k,v in arguments.items():
                kwargs[str(k)] = str(v)
            d = client.content_directory.browse(**kwargs)
            d.addCallback(reply)
            d.addErrback(dbus_async_err_cb)
        return ''

    def cp_ms_detected(self,client,usn):
        self.devices.append(DBusDevice(client.device,self.bus))
        self.UPnP_ControlPoint_MediaServer_detected(usn)

    def cp_mr_detected(self,client,usn):
        self.devices.append(DBusDevice(client.device,self.bus))
        self.UPnP_ControlPoint_MediaRenderer_detected(usn),

    @dbus.service.signal(BUS_NAME,
                         signature='s')
    def UPnP_ControlPoint_MediaServer_detected(self,usn):
        self.info("emitting signal UPnP_ControlPoint_MediaServer_detected")

    @dbus.service.signal(BUS_NAME,
                         signature='s')
    def UPnP_ControlPoint_MediaServer_removed(self,usn):
        self.info("emitting signal UPnP_ControlPoint_MediaServer_removed")

    @dbus.service.signal(BUS_NAME,
                         signature='s')
    def UPnP_ControlPoint_MediaRenderer_detected(self,usn):
        self.info("emitting signal UPnP_ControlPoint_MediaRenderer_detected")

    @dbus.service.signal(BUS_NAME,
                         signature='s')
    def UPnP_ControlPoint_MediaRenderer_removed(self,usn):
        self.info("emitting signal UPnP_ControlPoint_MediaRenderer_removed")
