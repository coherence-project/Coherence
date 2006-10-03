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

import service
from ssdp import SSDPServer
from event import EventServer
from msearch import MSearch
from device import Device, RootDevice
from utils import parse_xml

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import xmlrpc

import string

class ControlPoint:

    def __init__(self, enable_log=False):
        self.devices = []
        self.ssdp_server = SSDPServer(enable_log)
        self.ssdp_server.subscribe("new_device", self.add_device)
        self.ssdp_server.subscribe("removed_device", self.remove_device)
        self.events_server = EventServer(self)
        self.msearch = MSearch(self.ssdp_server)

        reactor.addSystemEventTrigger( 'before', 'shutdown', self.shutdown)

        self.renew_service_subscription_loop = task.LoopingCall(self.check_devices)
        self.renew_service_subscription_loop.start(20.0)

    def shutdown( self):
        """ send control point unsubscribe messages """
        try:
            self.renew_service_subscription_loop.stop()
        except:
            pass
        for root_device in self.get_devices():
            root_device.unsubscribe_service_subscriptions()
            for device in root_device.get_devices():
                device.unsubscribe_service_subscriptions()
        print 'ControlPoint shutdown'

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

    def propagate(self, event):
        #print 'propagate:', event
        if event.get_sid() in service.subscribers.keys():
            target_service = service.subscribers[event.get_sid()]
            for var_name, var_value  in event.items():
                if var_name == 'LastChange':
                    """ we have an AVTransport or RenderingControl event """
                    target_service.get_state_variable(var_name, 0).update(var_value)
                    tree = parse_xml(var_value).getroot()
                    namespace_uri, tag = string.split(tree.tag[1:], "}", 1)
                    for instance in tree.findall('{%s}InstanceID' % namespace_uri):
                        instance_id = instance.attrib['val']
                        for var in instance.getchildren():
                            namespace_uri, tag = string.split(var.tag[1:], "}", 1)
                            target_service.get_state_variable(tag, instance_id).update(var.attrib['val'])
                else:    
                    target_service.get_state_variable(var_name, 0).update(var_value)


class XMLRPC( xmlrpc.XMLRPC):

    def __init__(self, control_point):
        self.control_point = control_point
        self.allowNone = True

    def xmlrpc_list_devices(self):
        print "list_devices"
        r = []
        for device in self.control_point.get_devices():
            #print device.get_friendly_name(), device.get_service_type(), device.get_location(), device.get_id()
            d = {}
            d[u'friendly_name']=device.get_friendly_name()
            device_type = []
            for t in device.get_device_type():
                device_type.append(t[u'type'])
            d[u'device_type']=device_type
            d[u'location']=unicode(device.get_location())
            d[u'id']=unicode(device.get_id())
            r.append(d)
        return r

    def xmlrpc_mute_device(self, device_id):
        print "mute"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.rendering_control.set_mute(desired_mute=1)
                return "Ok"
        return "Error"

    def xmlrpc_unmute_device(self, device_id):
        print "unmute", device_id
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.rendering_control.set_mute(desired_mute=0)
                return "Ok"
        return "Error"

    def xmlrpc_set_volume(self, device_id, volume):
        print "set volume"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.rendering_control.set_volume(desired_volume=volume)
                return "Ok"
        return "Error"

    def xmlrpc_play(self, device_id):
        print "play"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.av_transport.play()
                return "Ok"
        return "Error"
        
    def xmlrpc_pause(self, device_id):
        print "pause"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.av_transport.pause()
                return "Ok"
        return "Error"

    def xmlrpc_stop(self, device_id):
        print "stop"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.av_transport.stop()
                return "Ok"
        return "Error"
        
    def xmlrpc_next(self, device_id):
        print "next"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.av_transport.next()
                return "Ok"
        return "Error"
        
    def xmlrpc_previous(self, device_id):
        print "previous"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.av_transport.previous()
                return "Ok"
        return "Error"
        
    def xmlrpc_set_av_transport_uri(self, device_id, uri):
        print "set_av_transport_uri"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_service_client( 'MediaRenderer')
            if client != None:
                client.av_transport.set_av_transport_uri(current_uri=uri)
                return "Ok"
        return "Error"

    def xmlrpc_ping(self):
        print "ping"
        return "Ok"

        
def startXMLRPC( control_point, port):
    from twisted.web import server
    r = XMLRPC( control_point)
    print "XMLRPC-API on port %d ready" % port
    reactor.listenTCP(port, server.Site(r))            

                    
if __name__ == '__main__':
    from content_directory_client import ContentDirectoryClient
    from connection_manager_client import ConnectionManagerClient
    from media_renderer_client import MediaRendererClient

    ctrl = ControlPoint()

    def print_results(results):
        print "results="
        print results

    def process_meta(results, client):
        for k,v in results.iteritems():
            dfr = client.browse(k, "BrowseMetadata")
            dfr.addCallback(print_results)

    def browse(st, infos):
        device = ctrl.get_device_with_usn(infos['USN'])
        if not device:
            return

        print 'Browsing services on device %s (%s)' % (device.get_friendly_name(),
                                                       device.get_location())
        for service in device.get_services():
            #print "service: %s" % (service.get_type())
            """
            cmgr = "urn:schemas-upnp-org:service:ConnectionManager:1"
            if service.get_type() == cmgr:
                print "found Connection Manager on", device.get_friendly_name()
                control_url = service.get_control_url()
                client = ConnectionManagerClient(control_url)
                dfr = client.get_protocol_info()
            """

            if service.get_type() in ["urn:schemas-upnp-org:service:ContentDirectory:1",
                                      "urn:schemas-upnp-org:service:ContentDirectory:2"]:    
                print "found MediaServer", device.get_friendly_name()
                client = None
                device.set_device_type('MediaServer', service.get_type(), client)
            """
                #service.subscribe()
                #
                client = MediaServerClient(device)
                client.get_system_update_id()
                #
                #dfr = client.get_search_capabilities()
                #dfr2 = client.get_sort_capabilities()
                #dfr3 = client.browse(0)
                #dfr3.addCallback(process_meta, client)
                #dfr4 = client.search("0",'upnp:class = "object.item.audioItem"',
                #                     requested_count=1)
                #dfr4.addCallback(print_results)
            """

            if service.get_type() in ["urn:schemas-upnp-org:service:RenderingControl:1",
                                      "urn:schemas-upnp-org:service:RenderingControl:2"]:    
                print "found MediaRenderer", device.get_friendly_name()
                client = MediaRendererClient(device)
                device.set_device_type('MediaRenderer', service.get_type(), client)
                
                
    ctrl.subscribe("new_device", browse)
    reactor.callWhenRunning( startXMLRPC, ctrl, 31020)

    reactor.run()
