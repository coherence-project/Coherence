# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import xmlrpc, resource, static

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from coherence.upnp.services.servers.connection_manager_server import ConnectionManagerServer
from coherence.upnp.services.servers.rendering_control_server import RenderingControlServer
from coherence.upnp.services.servers.av_transport_server import AVTransportServer

from coherence.backends.gstreamer_audio_player import Player

from coherence.extern.logger import Logger
log = Logger('MediaRenderer')

class MRRoot(resource.Resource):

    def __init__(self, server):
        resource.Resource.__init__(self)
        self.server = server
        
    def getChildWithDefault(self, path, request):
        log.info('MSRoot %s getChildWithDefault' % self.server.device_type, path, request.uri, request.client)
        log.info( request.getAllHeaders())
        if self.children.has_key(path):
            return self.children[path]
        if request.uri == '/':
            return self
        return self.getChild(path, request)

    def getChild(self, name, request):
        log.info('MSRoot %s getChild %s' % (name, request))
        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = static.File(p)
        log.info('MSRoot ch', ch)
        return ch
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the MediaRenderer</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)


class RootDeviceXML(static.Data):

    def __init__(self, hostname, uuid, urlbase,
                        device_type='MediaRenderer',
                        version=2,
                        friendly_name='Coherence UPnP A/V MediaRenderer',
                        services=[],
                        devices=[]):
        uuid = str(uuid)
        root = Element('root')
        root.attrib['xmlns']='urn:schemas-upnp-org:device-1-0'
        device_type = 'urn:schemas-upnp-org:device:%s:%d' % (device_type, version)
        e = SubElement(root, 'specVersion')
        SubElement( e, 'major').text = '1'
        SubElement( e, 'minor').text = '0'

        SubElement(root, 'URLBase').text = urlbase

        d = SubElement(root, 'device')
        SubElement( d, 'deviceType').text = device_type
        SubElement( d, 'friendlyName').text = friendly_name
        SubElement( d, 'manufacturer').text = 'beebits.net'
        SubElement( d, 'manufacturerURL').text = 'http://coherence.beebits.net'
        SubElement( d, 'modelDescription').text = 'Coherence UPnP A/V MediaRenderer'
        SubElement( d, 'modelName').text = 'Coherence  UPnP A/V MediaRenderer'
        SubElement( d, 'modelNumber').text = '0.1'
        SubElement( d, 'modelURL').text = 'http://coherence.beebits.net'
        SubElement( d, 'serialNumber').text = '0000001'
        SubElement( d, 'UDN').text = uuid
        SubElement( d, 'UPC').text = ''
        SubElement( d, 'presentationURL').text = ''

        if len(services):
            e = SubElement( d, 'serviceList')
            for service in services:
                id = service.get_id()
                s = SubElement( e, 'service')
                try:
                    namespace = service.namespace
                except:
                    namespace = 'schemas-upnp-org'
                SubElement( s, 'serviceType').text = 'urn:%s:service:%s:%d' % (namespace, id, version)
                try:
                    namespace = service.namespace
                except:
                    namespace = 'upnp-org'
                SubElement( s, 'serviceId').text = 'urn:%s:serviceId:%s' % (namespace,id)
                SubElement( s, 'SCPDURL').text = '/' + uuid[5:] + '/' + id + '/' + service.scpd_url
                SubElement( s, 'controlURL').text = '/' + uuid[5:] + '/' + id + '/' + service.control_url
                SubElement( s, 'eventSubURL').text = '/' + uuid[5:] + '/' + id + '/' + service.subscription_url

        if len(services):
            e = SubElement( d, 'deviceList')

        #indent( root, 0)
        self.xml = tostring( root, encoding='utf-8')
        static.Data.__init__(self, self.xml, 'text/xml')
        
class MediaRenderer:

    def __init__(self, coherence, version=2):
        self.coherence = coherence
        self.device_type = 'MediaRenderer'
        self.version = version
        from coherence.upnp.core.uuid import UUID
        self.uuid = UUID()
        self.backend = None
        self._services = []
        self._devices = []
        
        self.backend = Player(self)
        
        self.connection_manager_server = ConnectionManagerServer(self)
        self._services.append(self.connection_manager_server)

        self.rendering_control_server = RenderingControlServer(self)
        self._services.append(self.rendering_control_server)

        self.av_transport_server = AVTransportServer(self)
        self._services.append(self.av_transport_server)
        
        upnp_init = getattr(self.backend, "upnp_init", None)
        if upnp_init:
            upnp_init()


        self.web_resource = MRRoot(self)
        self.coherence.add_web_resource( str(self.uuid)[5:], self.web_resource)


        version = self.version
        while version > 0:
            self.web_resource.putChild( 'description-%d.xml' % version,
                                    RootDeviceXML( self.coherence.hostname,
                                    str(self.uuid),
                                    self.coherence.urlbase,
                                    self.device_type, version,
                                    services=self._services,
                                    devices=self._devices))
            version -= 1


        self.web_resource.putChild('ConnectionManager', self.connection_manager_server)
        self.web_resource.putChild('RenderingControl', self.rendering_control_server)
        self.web_resource.putChild('AVTransport', self.av_transport_server)


        self.register()

        
    def register(self):
        s = self.coherence.ssdp_server
        uuid = str(self.uuid)
        #print '%s register' % self.device_type
        # we need to do this after the children are there, since we send notifies
        s.register('local',
                    '%s::upnp:rootdevice' % uuid,
                    'upnp:rootdevice',
                    self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % self.version)

        s.register('local',
                    uuid,
                    uuid,
                    self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % self.version)

        version = self.version
        while version > 0:
            s.register('local',
                        '%s::urn:schemas-upnp-org:device:%s:%d' % (uuid, self.device_type, version),
                        'urn:schemas-upnp-org:device:%s:%d' % (self.device_type, version),
                        self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % version)

            for service in self._services:
                try:
                    namespace = service.namespace
                except:
                    namespace = 'schemas-upnp-org'

                s.register('local',
                            '%s::urn:%s:service:%s:%d' % (uuid,namespace,service.id, version),
                            'urn:%s:service:%s:%d' % (namespace,service.id, version),
                            self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % version)

            version -= 1
