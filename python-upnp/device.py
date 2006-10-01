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


import cElementTree
import urllib2
from service import Service
import utils

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
        self.device_type = []
        self.parse_description()
        
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

    def set_device_type(self, type, service_type, client):
        t = {}
        t[u'type'] = unicode(type)
        t[u'service_type'] = unicode(type)
        t[u'client'] = client
        self.device_type.append(t)

    def get_device_type(self):
        return self.device_type
        
    def get_service_client(self, device_type):
        #print "get_service_client"
        for type in self.device_type:
            if type['type'] == device_type:
                return type[u'client']
        return None
            
    def parse_description(self):
        handle = utils.url_fetch(self.location)
        if not handle:
            return
        
        tree = cElementTree.ElementTree(file=handle).getroot()

        ns = "urn:schemas-upnp-org:device-1-0"
        
        self.friendly_name = unicode(tree.findtext('.//{%s}friendlyName' % ns))
        self.udn = tree.findtext('.//{%s}UDN' % ns)

        for service in tree.findall('.//{%s}service' % ns):
            serviceType = service.findtext('{%s}serviceType' % ns)
            serviceId = service.findtext('{%s}serviceId' % ns)
            controlUrl = service.findtext('{%s}controlURL' % ns) 
            eventSubUrl = service.findtext('{%s}eventSubURL' % ns) 
            presentationUrl = service.findtext('{%s}presentationURL' % ns)
            scpdUrl = service.findtext('{%s}SCPDURL' % ns)
            self.add_service(Service(serviceType, serviceId, self.location,
                                     controlUrl,
                                     eventSubUrl, presentationUrl, scpdUrl, self))
        

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
