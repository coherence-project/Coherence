# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import urllib2
import time

from twisted.internet import defer

from coherence.upnp.core.service import Service
from coherence.upnp.core import utils
from coherence import log

import coherence.extern.louie as louie

ns = "urn:schemas-upnp-org:device-1-0"


class Device(log.Loggable):
    logCategory = 'device'

    def __init__(self, parent=None):
        log.Loggable.__init__(self)
        self.parent = parent
        self.services = []
        #self.uid = self.usn[:-len(self.st)-2]
        self.friendly_name = ""
        self.device_type = ""
        self.friendly_device_type = "[unknown]"
        self.device_type_version = 0
        self.udn = None
        self.detection_completed = False
        self.client = None
        self.icons = []
        self.devices = []

        self.dlna_device_classes = []
        self.dlna_caps = []

        louie.connect(self.receiver, 'Coherence.UPnP.Service.detection_completed', self)
        louie.connect(self.service_detection_failed, 'Coherence.UPnP.Service.detection_failed', self)

    def __repr__(self):
        return "embedded device %r %r, parent %r" % (self.friendly_name, self.device_type, self.parent)
    #def __del__(self):
    #    #print "Device removal completed"
    #    pass

    def as_dict(self):
        import copy
        d = {'device_type': self.get_device_type(),
             'friendly_name': self.get_friendly_name(),
             'udn': self.get_id(),
             'services': [x.as_dict() for x in self.services]}
        icons = []
        for icon in self.icons:
            icons.append({"mimetype": icon['mimetype'], "url": icon['url'], "height": icon['height'], "width": icon['width'], "depth": icon['depth']})
        d['icons'] = icons
        return d

    def remove(self, *args):
        self.info("removal of  %s %s", self.friendly_name, self.udn)
        while len(self.devices) > 0:
            device = self.devices.pop()
            self.debug("try to remove %r", device)
            device.remove()
        while len(self.services) > 0:
            service = self.services.pop()
            self.debug("try to remove %r", service)
            service.remove()
        if self.client != None:
            louie.send('Coherence.UPnP.Device.remove_client', None, self.udn, self.client)
            self.client = None
        #del self

    def receiver(self, *args, **kwargs):
        if self.detection_completed == True:
            return
        for s in self.services:
            if s.detection_completed == False:
                return
        if self.udn == None:
            return
        self.detection_completed = True
        if self.parent != None:
            self.info("embedded device %r %r initialized, parent %r", self.friendly_name, self.device_type, self.parent)
        louie.send('Coherence.UPnP.Device.detection_completed', None, device=self)
        if self.parent != None:
            louie.send('Coherence.UPnP.Device.detection_completed', self.parent, device=self)
        else:
            louie.send('Coherence.UPnP.Device.detection_completed', self, device=self)

    def service_detection_failed(self, device):
        self.remove()

    def get_id(self):
        return self.udn

    def get_uuid(self):
        return self.udn[5:]

    def get_embedded_devices(self):
        return self.devices

    def get_embedded_device_by_type(self, type):
        r = []
        for device in self.devices:
            if type == device.friendly_device_type:
                r.append(device)
        return r

    def get_services(self):
        return self.services

    def get_service_by_type(self, type):
        if not isinstance(type, (tuple, list)):
            type = [type, ]
        for service in self.services:
            _, _, _, service_class, version = service.service_type.split(':')
            if service_class in type:
                return service

    def add_service(self, service):
        self.debug("add_service %r", service)
        self.services.append(service)

    def remove_service_with_usn(self, service_usn):
        for service in self.services:
            if service.get_usn() == service_usn:
                self.services.remove(service)
                service.remove()
                break

    def add_device(self, device):
        self.debug("Device add_device %r", device)
        self.devices.append(device)

    def get_friendly_name(self):
        return self.friendly_name

    def get_device_type(self):
        return self.device_type

    def get_friendly_device_type(self):
        return self.friendly_device_type

    def get_markup_name(self):
        try:
            return self._markup_name
        except AttributeError:
            self._markup_name = u"%s:%s %s" % (self.friendly_device_type,
                    self.device_type_version, self.friendly_name)
            return self._markup_name

    def get_device_type_version(self):
        return self.device_type_version

    def set_client(self, client):
        self.client = client

    def get_client(self):
        return self.client

    def renew_service_subscriptions(self):
        """ iterate over device's services and renew subscriptions """
        self.info("renew service subscriptions for %s", self.friendly_name)
        now = time.time()
        for service in self.services:
            self.info("check service %r %r %s %s", service.id, service.get_sid(),
                      service.get_timeout(), now)
            if service.get_sid() is not None:
                if service.get_timeout() < now:
                    self.debug("wow, we lost an event subscription for %s %s, "
                               "maybe we need to rethink the loop time and "
                               "timeout calculation?",
                               self.friendly_name, service.get_id())
                if service.get_timeout() < now + 30:
                    service.renew_subscription()

        for device in self.devices:
            device.renew_service_subscriptions()

    def unsubscribe_service_subscriptions(self):
        """ iterate over device's services and unsubscribe subscriptions """
        l = []
        for service in self.get_services():
            if service.get_sid() is not None:
                l.append(service.unsubscribe())
        dl = defer.DeferredList(l)
        return dl

    def parse_device(self, d):
        self.info("parse_device %r", d)
        self.device_type = unicode(d.findtext('./{%s}deviceType' % ns))
        self.friendly_device_type, self.device_type_version = \
                self.device_type.split(':')[-2:]
        self.friendly_name = unicode(d.findtext('./{%s}friendlyName' % ns))
        self.udn = d.findtext('./{%s}UDN' % ns)
        self.info("found udn %r %r", self.udn, self.friendly_name)

        for attrname, tag in (
            ('manufacturer', 'manufacturer'),
            ('manufacturer_url', 'manufacturerURL'),
            ('model_name', 'modelName'),
            ('model_description', 'modelDescription'),
            ('model_number', 'modelNumber'),
            ('model_url', 'modelURL'),
            ('serial_number', 'serialNumber'),
            ('upc', 'UPC'),
            ('presentation_url', 'presentationURL'),
            ):
            try:
                setattr(self, attrname, d.findtext('./{%s}%s' % (ns, tag)))
            except:
                pass

        try:
            for dlna_doc in d.findall('./{%s}X_DLNADOC' % ns):
                self.dlna_device_classes.append(dlna_doc.text)
        except:
            pass
        try:
            for dlna_cap in d.findall('./{%s}X_DLNACAP' % ns):
                for cap in dlna_cap.text.split(','):
                    self.dlna_caps.append(cap)
        except:
            pass

        icon_list = d.find('./{%s}iconList' % ns)
        if icon_list is not None:
            import urllib2
            url_base = "%s://%s" % urllib2.urlparse.urlparse(self.get_location())[:2]
            for icon in icon_list.findall('./{%s}icon' % ns):
                try:
                    i = {}
                    i['mimetype'] = icon.find('./{%s}mimetype' % ns).text
                    i['width'] = icon.find('./{%s}width' % ns).text
                    i['height'] = icon.find('./{%s}height' % ns).text
                    i['depth'] = icon.find('./{%s}depth' % ns).text
                    i['realurl'] = icon.find('./{%s}url' % ns).text
                    i['url'] = self.make_fullyqualified(i['realurl'])
                    self.icons.append(i)
                    self.debug("adding icon %r for %r", i, self.friendly_name)
                except:
                    import traceback
                    self.debug(traceback.format_exc())
                    self.warning("device %r seems to have an invalid icon description, ignoring that icon", self.friendly_name)

        serviceList = d.find('./{%s}serviceList' % ns)
        if serviceList:
            for service in serviceList.findall('./{%s}service' % ns):
                serviceType = service.findtext('{%s}serviceType' % ns)
                serviceId = service.findtext('{%s}serviceId' % ns)
                controlUrl = service.findtext('{%s}controlURL' % ns)
                eventSubUrl = service.findtext('{%s}eventSubURL' % ns)
                presentationUrl = service.findtext('{%s}presentationURL' % ns)
                scpdUrl = service.findtext('{%s}SCPDURL' % ns)
                """ check if values are somehow reasonable
                """
                if len(scpdUrl) == 0:
                    self.warning("service has no uri for its description")
                    continue
                if len(eventSubUrl) == 0:
                    self.warning("service has no uri for eventing")
                    continue
                if len(controlUrl) == 0:
                    self.warning("service has no uri for controling")
                    continue
                self.add_service(Service(serviceType, serviceId, self.get_location(),
                                         controlUrl,
                                         eventSubUrl, presentationUrl, scpdUrl, self))

            # now look for all sub devices
            embedded_devices = d.find('./{%s}deviceList' % ns)
            if embedded_devices:
                for d in embedded_devices.findall('./{%s}device' % ns):
                    embedded_device = Device(self)
                    self.add_device(embedded_device)
                    embedded_device.parse_device(d)

        self.receiver()

    def get_location(self):
        return self.parent.get_location()

    def get_usn(self):
        return self.parent.get_usn()

    def get_upnp_version(self):
        return self.parent.get_upnp_version()

    def get_urlbase(self):
        return self.parent.get_urlbase()

    def get_presentation_url(self):
        try:
            return self.make_fullyqualified(self.presentation_url)
        except:
            return ''

    def get_parent_id(self):
        try:
            return self.parent.get_id()
        except:
            return ''

    def make_fullyqualified(self, url):
        return self.parent.make_fullyqualified(url)

    def as_tuples(self):
        r = []

        def append(name, *attributes):
            value = []
            try:
                for attr in attributes:
                    if callable(attr):
                        res = attr()
                    else:
                        res = getattr(self, attr)
                    if not res:
                        return
                    elif isinstance(res, list):
                        res = ','.join(res)
                    value.append(res)
                if len(value) == 1:
                    value = value[0]
                else:
                    value = tuple(value)
                r.append((name, value))
            except:
                import traceback
                self.error(traceback.format_exc())


        append('Location', self.get_location, self.get_location)
        append('URL base', self.get_urlbase)
        append('UDN', self.get_id)
        append('Type', 'device_type')
        append('UPnP Version', 'upnp_version')
        append('DLNA Device Class', 'dlna_device_classes')
        append('DLNA Device Capability', 'dlna_caps')
        append('Friendly Name', 'friendly_name)')
        append('Manufacturer', 'manufacturer')
        append('Manufacturer URL', 'manufacturer_url', 'manufacturer_url')
        append('Model Description', 'model_description')
        append('Model Name', 'model_name')
        append('Model Number', 'model_number')
        append('Model URL', 'model_url', 'model_url')
        append('Serial Number', 'serial_number')
        append('UPC', 'upc')
        append('Presentation URL',
               ('presentation_url',
                lambda: self.make_fullyqualified(getattr(self, 'presentation_url'))))

        for icon in self.icons:
            r.append(('Icon', (icon['realurl'],
                               self.make_fullyqualified(icon['realurl']),
                               {'Mimetype': icon['mimetype'],
                                'Width': icon['width'],
                                'Height': icon['height'],
                                'Depth': icon['depth']})))

        return r


class RootDevice(Device):

    def __init__(self, infos):
        self.usn = infos['USN']
        self.server = infos['SERVER']
        self.st = infos['ST']
        self.location = infos['LOCATION']
        self.manifestation = infos['MANIFESTATION']
        self.host = infos['HOST']
        self.root_detection_completed = False
        Device.__init__(self, None)
        louie.connect(self.device_detect, 'Coherence.UPnP.Device.detection_completed', self)
        # we need to handle root device completion
        # these events could be ourself or our children.
        self.parse_description()

    def __repr__(self):
        return "rootdevice %r %r %r %r, manifestation %r" % (self.friendly_name, self.udn, self.st, self.host, self.manifestation)

    def remove(self, *args):
        result = Device.remove(self, *args)
        louie.send('Coherence.UPnP.RootDevice.removed', self, usn=self.get_usn())
        return result

    def get_usn(self):
        return self.usn

    def get_st(self):
        return self.st

    def get_location(self):
        return self.location

    def get_upnp_version(self):
        return self.upnp_version

    def get_urlbase(self):
        return self.urlbase

    def get_host(self):
        return self.host

    def is_local(self):
        if self.manifestation == 'local':
            return True
        return False

    def is_remote(self):
        if self.manifestation != 'local':
            return True
        return False

    def device_detect(self, *args, **kwargs):
        self.debug("device_detect %r", kwargs)
        self.debug("root_detection_completed %r", self.root_detection_completed)
        if self.root_detection_completed == True:
            return
        # our self is not complete yet

        self.debug("detection_completed %r", self.detection_completed)
        if self.detection_completed == False:
            return

        # now check child devices.
        self.debug("self.devices %r", self.devices)
        for d in self.devices:
            self.debug("check device %r %r", d.detection_completed, d)
            if d.detection_completed == False:
                return
        # now must be done, so notify root done
        self.root_detection_completed = True
        self.info("rootdevice %r %r %r initialized, manifestation %r", self.friendly_name, self.st, self.host, self.manifestation)
        louie.send('Coherence.UPnP.RootDevice.detection_completed', None, device=self)

    def add_device(self, device):
        self.debug("RootDevice add_device %r", device)
        self.devices.append(device)

    def get_devices(self):
        self.debug("RootDevice get_devices: %s", self.devices)
        return self.devices

    def parse_description(self):

        def gotPage(x):
            self.debug("got device description from %r", self.location)
            data, headers = x
            xml_data = None
            try:
                xml_data = utils.parse_xml(data, 'utf-8')
            except:
                self.warning("Invalid device description received from %r", self.location)
                import traceback
                self.debug(traceback.format_exc())

            if xml_data is not None:
                tree = xml_data.getroot()
                major = tree.findtext('./{%s}specVersion/{%s}major' % (ns, ns))
                minor = tree.findtext('./{%s}specVersion/{%s}minor' % (ns, ns))
                try:
                    self.upnp_version = '.'.join((major, minor))
                except:
                    self.upnp_version = 'n/a'
                try:
                    self.urlbase = tree.findtext('./{%s}URLBase' % ns)
                except:
                    import traceback
                    self.debug(traceback.format_exc())

                d = tree.find('./{%s}device' % ns)
                if d is not None:
                    self.parse_device(d)  # root device

        def gotError(failure, url):
            self.warning("error getting device description from %r", url)
            self.info(failure)

        utils.getPage(self.location).addCallbacks(gotPage, gotError, None, None, [self.location], None)

    def make_fullyqualified(self, url):
        if url.startswith('http://'):
            return url
        import urlparse
        base = self.get_urlbase()
        if base != None:
            if base[-1] != '/':
                base += '/'
            r = urlparse.urljoin(base, url)
        else:
            r = urlparse.urljoin(self.get_location(), url)
        return r
