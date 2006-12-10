# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import cElementTree
import urllib2
import time

from coherence.upnp.core.service import Service
from coherence.upnp.core import utils

import louie

class Device:

    def __init__(self, infos, parent=None):
        self.parent = parent
        self.usn = infos['USN']
        self.server = infos['SERVER']
        self.st = infos['ST']
        self.location = infos['LOCATION']
        self.services = []
        #self.uid = self.usn[:-len(self.st)-2]
        self.friendly_name = ""
        self.device_type = ""
        self.detection_completed = False
        self.client = None

        louie.connect( self.receiver, 'Coherence.UPnP.Service.detection_completed', self)

        self.parse_description()

    def receiver( self, signal, *args, **kwargs):
        #print "Device receiver called with", signal
        if self.detection_completed == True:
            return
        for s in self.services:
            if s.detection_completed == False:
                return
        self.detection_completed = True
        louie.send('Coherence.UPnP.Device.detection_completed', None, device=self)

    def get_id(self):
        return self.udn

    def get_usn(self):
        return self.usn

    def get_st(self):
        return self.st

    def get_location(self):
        return self.location

    def get_services(self):
        return self.services

    def add_service(self, service):
        self.services.append(service)

    def remove_service_with_usn(self, service_usn):
        for service in self.services:
            if service.get_usn() == service_usn:
                self.services.remove(service)
                break

    def get_friendly_name(self):
        return self.friendly_name

    def get_device_type(self):
        return self.device_type

    def set_client(self, client):
        self.client = client
        
    def get_client(self):
        return self.client
        
    def renew_service_subscriptions(self):
        """ iterate over device's services and renew subscriptions """
        now = time.time()
        for service in self.get_services():
            if service.get_sid():
                if service.get_timeout() < now:
                    print "wow, we lost an event subscription for %s, " % service.get_id()+ \
                          "maybe we need to rethink the loop time and timeout calculation?"
                if service.get_timeout() < now + 30 :
                    service.renew_subscription()
        
    def unsubscribe_service_subscriptions(self):
        """ iterate over device's services and unsubscribe subscriptions """
        for service in self.get_services():
            if service.get_sid():
                service.unsubscribe()
            
    def parse_description(self):
        from twisted.web.client import getPage
                                     
        def gotPage(x):
            #print "gotPage"
            tree = utils.parse_xml(x, 'utf-8').getroot()
            ns = "urn:schemas-upnp-org:device-1-0"
            
            d = tree.find('.//{%s}device' % ns)
            if d == None:
                return
                
            self.device_type = unicode(d.findtext('.//{%s}deviceType' % ns))
            self.friendly_name = unicode(d.findtext('.//{%s}friendlyName' % ns))
            self.udn = d.findtext('.//{%s}UDN' % ns)

            s = d.find('.//{%s}serviceList' % ns)
            for service in s.findall('.//{%s}service' % ns):
                serviceType = service.findtext('{%s}serviceType' % ns)
                serviceId = service.findtext('{%s}serviceId' % ns)
                controlUrl = service.findtext('{%s}controlURL' % ns) 
                eventSubUrl = service.findtext('{%s}eventSubURL' % ns) 
                presentationUrl = service.findtext('{%s}presentationURL' % ns)
                scpdUrl = service.findtext('{%s}SCPDURL' % ns)
                self.add_service(Service(serviceType, serviceId, self.location,
                                         controlUrl,
                                         eventSubUrl, presentationUrl, scpdUrl, self))
            
        def gotError(failure, url):
            print "error requesting", url
            print failure

        getPage(self.location).addCallbacks(gotPage, gotError, None, None, self.location, None)


class RootDevice(Device):

    def __init__(self, infos):
        Device.__init__(self, infos)
        self.devices = []

    def add_device(self, device):
        #print "RootDevice add_device", device
        self.devices.append(device)

    def get_devices(self):
        #print "RootDevice get_devices:", self.devices
        return self.devices
