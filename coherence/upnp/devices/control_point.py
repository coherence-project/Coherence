# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006-2010 Frank Scholz <dev@coherence-project.org>

import string
import traceback

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import xmlrpc, client

from coherence.upnp.core import service
from coherence.upnp.core.event import EventServer

from coherence.upnp.devices.media_server_client import MediaServerClient
from coherence.upnp.devices.media_renderer_client import MediaRendererClient
from coherence.upnp.devices.binary_light_client import BinaryLightClient
from coherence.upnp.devices.dimmable_light_client import DimmableLightClient
from coherence.upnp.devices.internet_gateway_device_client import InternetGatewayDeviceClient

import coherence.extern.louie as louie

from coherence import log

class DeviceQuery(object):

    def __init__(self, type, pattern, callback, timeout=0, oneshot=True):
        self.type = type
        self.pattern = pattern
        self.callback = callback
        self.fired = False
        self.timeout = timeout
        self.oneshot = oneshot
        if self.type == 'uuid' and self.pattern.startswith('uuid:'):
            self.pattern = self.pattern[5:]

    def fire(self, device):
        if callable(self.callback):
            self.callback(device)
        elif isinstance(self.callback,basestring):
            louie.send(self.callback, None, device=device)
        self.fired = True

    def check(self, device):
        if self.fired and self.oneshot:
            return
        if(self.type == 'host' and
           device.host == self.pattern):
            self.fire(device)
        elif(self.type == 'friendly_name' and
           device.friendly_name == self.pattern):
            self.fire(device)
        elif(self.type == 'uuid' and
           device.get_uuid() == self.pattern):
            self.fire(device)

class ControlPoint(log.Loggable):
    logCategory = 'controlpoint'

    def __init__(self,coherence,auto_client=['MediaServer','MediaRenderer','BinaryLight','DimmableLight']):
        self.coherence = coherence

        self.info("Coherence UPnP ControlPoint starting...")
        self.event_server = EventServer(self)

        self.coherence.add_web_resource('RPC2',
                                        XMLRPC(self))

        self.auto_client = auto_client
        self.queries=[]

        for device in self.get_devices():
            self.check_device( device)

        louie.connect(self.check_device, 'Coherence.UPnP.Device.detection_completed', louie.Any)
        louie.connect(self.remove_client, 'Coherence.UPnP.Device.remove_client', louie.Any)

        louie.connect(self.completed, 'Coherence.UPnP.DeviceClient.detection_completed', louie.Any)

    def shutdown(self):
        louie.disconnect(self.check_device, 'Coherence.UPnP.Device.detection_completed', louie.Any)
        louie.disconnect(self.remove_client, 'Coherence.UPnP.Device.remove_client', louie.Any)
        louie.disconnect(self.completed, 'Coherence.UPnP.DeviceClient.detection_completed', louie.Any)

    def auto_client_append(self,device_type):
        if device_type in self.auto_client:
            return
        self.auto_client.append(device_type)
        for device in self.get_devices():
            self.check_device( device)

    def browse(self, device):
        device = self.coherence.get_device_with_usn(infos['USN'])
        if not device:
            return
        self.check_device( device)

    def process_queries(self, device):
        for query in self.queries:
            query.check(device)

    def add_query(self, query):
        for device in self.get_devices():
            query.check(device)
        if query.fired == False and query.timeout == 0:
            query.callback(None)
        else:
            self.queries.append(query)

    def connect(self,receiver,signal=louie.signal.All,sender=louie.sender.Any, weak=True):
        """ wrapper method around louie.connect
        """
        louie.connect(receiver,signal=signal,sender=sender,weak=weak)

    def disconnect(self,receiver,signal=louie.signal.All,sender=louie.sender.Any, weak=True):
        """ wrapper method around louie.disconnect
        """
        louie.disconnect(receiver,signal=signal,sender=sender,weak=weak)

    def get_devices(self):
        return self.coherence.get_devices()

    def get_device_with_id(self, id):
        return self.coherence.get_device_with_id(id)

    def get_device_by_host(self, host):
        return self.coherence.get_device_by_host(host)

    def check_device( self, device):
        if device.client == None:
            self.info("found device %s of type %s - %r" %(device.get_friendly_name(),
                                                device.get_device_type(), device.client))
            short_type = device.get_friendly_device_type()
            if short_type in self.auto_client and short_type is not None:
                self.info("identified %s %r" %
                        (short_type, device.get_friendly_name()))

                if short_type == 'MediaServer':
                    client = MediaServerClient(device)
                if short_type == 'MediaRenderer':
                    client = MediaRendererClient(device)
                if short_type == 'BinaryLight':
                    client = BinaryLightClient(device)
                if short_type == 'DimmableLight':
                    client = DimmableLightClient(device)
                if short_type == 'InternetGatewayDevice':
                    client = InternetGatewayDeviceClient(device)

                client.coherence = self.coherence
                device.set_client( client)

        self.process_queries(device)

    def completed(self, client, udn):
        self.info('sending signal Coherence.UPnP.ControlPoint.%s.detected %r' % (client.device_type, udn))
        louie.send('Coherence.UPnP.ControlPoint.%s.detected' % client.device_type, None,
                               client=client,udn=udn)

    def remove_client(self, udn, client):
        louie.send('Coherence.UPnP.ControlPoint.%s.removed' % client.device_type, None, udn=udn)
        self.info("removed %s %s" % (client.device_type,client.device.get_friendly_name()))
        client.remove()

    def propagate(self, event):
        self.info('propagate: %r', event)
        if event.get_sid() in service.subscribers.keys():
            try:
                service.subscribers[event.get_sid()].process_event(event)
            except Exception, msg:
                self.debug(msg)
                self.debug(traceback.format_exc())
                pass

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
            return df
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

    #ctrl = ControlPoint(Coherence(config),auto_client=[])
    #ctrl = ControlPoint(Coherence(config))

    def show_devices():
        print "show_devices"
        for d in ctrl.get_devices():
            print d, d.get_id()

    def the_result(r):
        print "result", r, r.get_id()

    def query_devices():
        print "query_devices"
        ctrl.add_query(DeviceQuery('host', '192.168.1.163', the_result))

    def query_devices2():
        print "query_devices with timeout"
        ctrl.add_query(DeviceQuery('host', '192.168.1.163', the_result, timeout=10, oneshot=False))

    #reactor.callLater(2, show_devices)
    #reactor.callLater(3, query_devices)
    #reactor.callLater(4, query_devices2)
    #reactor.callLater(5, ctrl.add_query, DeviceQuery('friendly_name', 'Coherence Test Content', the_result, timeout=10, oneshot=False))



    reactor.run()
