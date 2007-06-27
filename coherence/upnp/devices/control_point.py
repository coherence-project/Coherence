# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import string

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import xmlrpc, client

from coherence.upnp.core import service
from coherence.upnp.core.event import EventServer

from coherence.upnp.devices.media_server_client import MediaServerClient
from coherence.upnp.devices.media_renderer_client import MediaRendererClient

from coherence.upnp.core.utils import parse_xml

import louie

from coherence import log

class ControlPoint(log.Loggable):
    logCategory = 'control_point'
    
    def __init__(self, coherence):
        self.coherence = coherence
        
        self.info("Coherence UPnP ControlPoint starting...")
        self.event_server = EventServer(self)
        
        self.coherence.add_web_resource('RPC2',
                                        XMLRPC(self))

        for device in self.coherence.get_nonlocal_devices():
            self.check_device( device)
            
        louie.connect(self.check_device, 'Coherence.UPnP.Device.detection_completed', louie.Any)
        louie.connect(self.remove_client, 'Coherence.UPnP.Device.remove_client', louie.Any)

    def browse( self, device):
        device = self.coherence.get_device_with_usn(infos['USN'])
        if not device:
            return
        self.check_device( device)
        
    def get_devices(self):
        return self.coherence.get_nonlocal_devices()
        
    def get_device_with_id(self, id):
        return self.coherence.get_device_with_id(id)

    def check_device( self, device):
        if device.is_remote():
            self.info("found device %s of type %s" %(device.get_friendly_name(),
                                                    device.get_device_type()))
            if device.get_device_type() in [ "urn:schemas-upnp-org:device:MediaServer:1",
                                      "urn:schemas-upnp-org:device:MediaServer:2"]:
                self.info("identified MediaServer", device.get_friendly_name())
                client = MediaServerClient(device)
                device.set_client( client)
                louie.send('Coherence.UPnP.ControlPoint.MediaServer.detected', None,
                                   client=client,usn=device.get_usn())

            if device.get_device_type() in [ "urn:schemas-upnp-org:device:MediaRenderer:1",
                                      "urn:schemas-upnp-org:device:MediaRenderer:2"]:    
                self.info("identified MediaRenderer", device.get_friendly_name())
                client = MediaRendererClient(device)
                device.set_client( client)
                louie.send('Coherence.UPnP.ControlPoint.MediaRenderer.detected', None,
                                   client=client,usn=device.get_usn())

    def remove_client(self, usn, client):
        self.info("removed %s %s" % (client.device_type,client.device.get_friendly_name()))
        louie.send('Coherence.UPnP.ControlPoint.%s.removed' % client.device_type, None, usn=usn)
        client.remove()
    
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


    def put_resource(self, url, path):
        def got_result(result):
            print result

        def got_error(result):
            print "error", result

        try:
            f = open(path)
            data = f.read()
            f.close()
            headers= {
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(data))
            }
            df = client.getPage(url, method="POST",
                                headers=headers, postdata=data)
            df.addCallback(got_result)
            df.addErrback(got_error)
        except IOError:
            pass


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
            d[u'device_type']=device.get_device_type()
            d[u'location']=unicode(device.get_location())
            d[u'id']=unicode(device.get_id())
            r.append(d)
        return r

    def xmlrpc_mute_device(self, device_id):
        print "mute"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.rendering_control.set_mute(desired_mute=1)
            return "Ok"
        return "Error"

    def xmlrpc_unmute_device(self, device_id):
        print "unmute", device_id
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.rendering_control.set_mute(desired_mute=0)
            return "Ok"
        return "Error"

    def xmlrpc_set_volume(self, device_id, volume):
        print "set volume"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.rendering_control.set_volume(desired_volume=volume)
            return "Ok"
        return "Error"

    def xmlrpc_play(self, device_id):
        print "play"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.av_transport.play()
            return "Ok"
        return "Error"
        
    def xmlrpc_pause(self, device_id):
        print "pause"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.av_transport.pause()
            return "Ok"
        return "Error"

    def xmlrpc_stop(self, device_id):
        print "stop"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.av_transport.stop()
            return "Ok"
        return "Error"
        
    def xmlrpc_next(self, device_id):
        print "next"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.av_transport.next()
            return "Ok"
        return "Error"
        
    def xmlrpc_previous(self, device_id):
        print "previous"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.av_transport.previous()
            return "Ok"
        return "Error"
        
    def xmlrpc_set_av_transport_uri(self, device_id, uri):
        print "set_av_transport_uri"
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.av_transport.set_av_transport_uri(current_uri=uri)
            return "Ok"
        return "Error"
    
    def xmlrpc_create_object(self, device_id, container_id, arguments):
        print "create_object", arguments
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.content_directory.create_object(container_id, arguments)
            return "Ok"
        return "Error"
    
    def xmlrpc_import_resource(self, device_id, source_uri, destination_uri):
        print "import_resource", source_uri, destination_uri
        device = self.control_point.get_device_with_id(device_id)
        if device != None:
            client = device.get_client()
            client.content_directory.import_resource(source_uri, destination_uri)
            return "Ok"
        return "Error"
    
    def xmlrpc_put_resource(self, url, path):
        print "put_resource", url, path
        self.control_point.put_resource(url, path)
        return "Ok"

    def xmlrpc_ping(self):
        print "ping"
        return "Ok"

        
def startXMLRPC( control_point, port):
    from twisted.web import server
    r = XMLRPC( control_point)
    print "XMLRPC-API on port %d ready" % port
    reactor.listenTCP(port, server.Site(r))            

                    
if __name__ == '__main__':

    from coherence.base import Coherence
    from coherence.upnp.devices.media_server_client import MediaServerClient
    from coherence.upnp.devices.media_renderer_client import MediaRendererClient
    
    config = {}
    config['logmode'] = 'warning'
    config['serverport'] = 30020

    ctrl = ControlPoint(Coherence(config))


    reactor.run()
