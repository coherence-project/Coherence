# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006,2007 Frank Scholz <coherence@beebits.net>

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import resource, static

from coherence import __version__

from coherence.extern.et import ET, indent

from coherence.upnp.services.servers.connection_manager_server import ConnectionManagerServer
from coherence.upnp.services.servers.rendering_control_server import RenderingControlServer
from coherence.upnp.services.servers.av_transport_server import AVTransportServer

from coherence.upnp.devices.basics import BasicAVMixin

import louie

from coherence import log

class MRRoot(resource.Resource, log.Loggable):
    logCategory = 'mediarenderer'

    def __init__(self, server):
        resource.Resource.__init__(self)
        self.server = server

    def getChildWithDefault(self, path, request):
        self.info('MSRoot %s getChildWithDefault' % self.server.device_type, path, request.uri, request.client)
        self.info( request.getAllHeaders())
        if self.children.has_key(path):
            return self.children[path]
        if request.uri == '/':
            return self
        return self.getChild(path, request)

    def getChild(self, name, request):
        self.info('MSRoot %s getChild %s' % (name, request))
        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = static.File(p)
        self.info('MSRoot ch', ch)
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
                        devices=[],
                        icons=[]):
        uuid = str(uuid)
        root = ET.Element('root')
        root.attrib['xmlns']='urn:schemas-upnp-org:device-1-0'
        device_type = 'urn:schemas-upnp-org:device:%s:%d' % (device_type, version)
        e = ET.SubElement(root, 'specVersion')
        ET.SubElement( e, 'major').text = '1'
        ET.SubElement( e, 'minor').text = '0'

        ET.SubElement(root, 'URLBase').text = urlbase

        d = ET.SubElement(root, 'device')
        ET.SubElement( d, 'deviceType').text = device_type
        ET.SubElement( d, 'friendlyName').text = friendly_name
        ET.SubElement( d, 'manufacturer').text = 'beebits.net'
        ET.SubElement( d, 'manufacturerURL').text = 'http://coherence.beebits.net'
        ET.SubElement( d, 'modelDescription').text = 'Coherence UPnP A/V MediaRenderer'
        ET.SubElement( d, 'modelName').text = 'Coherence UPnP A/V MediaRenderer'
        ET.SubElement(d, 'modelNumber').text = __version__
        ET.SubElement( d, 'modelURL').text = 'http://coherence.beebits.net'
        ET.SubElement( d, 'serialNumber').text = '0000001'
        ET.SubElement( d, 'UDN').text = uuid
        ET.SubElement( d, 'UPC').text = ''
        ET.SubElement( d, 'presentationURL').text = ''

        if len(services):
            e = ET.SubElement( d, 'serviceList')
            for service in services:
                id = service.get_id()
                s = ET.SubElement( e, 'service')
                try:
                    namespace = service.namespace
                except:
                    namespace = 'schemas-upnp-org'
                if( hasattr(service,'version') and
                    service.version < version):
                    v = service.version
                else:
                    v = version
                ET.SubElement(s, 'serviceType').text = 'urn:%s:service:%s:%d' % (namespace, id, int(v))
                try:
                    namespace = service.id_namespace
                except:
                    namespace = 'upnp-org'
                ET.SubElement( s, 'serviceId').text = 'urn:%s:serviceId:%s' % (namespace,id)
                ET.SubElement( s, 'SCPDURL').text = '/' + uuid[5:] + '/' + id + '/' + service.scpd_url
                ET.SubElement( s, 'controlURL').text = '/' + uuid[5:] + '/' + id + '/' + service.control_url
                ET.SubElement( s, 'eventSubURL').text = '/' + uuid[5:] + '/' + id + '/' + service.subscription_url

        if len(devices):
            e = ET.SubElement( d, 'deviceList')

        if len(icons):
            e = ET.SubElement(d, 'iconList')
            for icon in icons:
                i = ET.SubElement(e, 'icon')
                for k,v in icon.items():
                    if k == 'url':
                        if v.startswith('file://'):
                            ET.SubElement(i, k).text = '/'+uuid[5:]+'/'+os.path.basename(v)
                            continue
                    ET.SubElement(i, k).text = str(v)

        #if self.has_level(LOG_DEBUG):
        #    indent( root)

        self.xml = """<?xml version="1.0" encoding="utf-8"?>""" + ET.tostring( root, encoding='utf-8')
        static.Data.__init__(self, self.xml, 'text/xml')

class MediaRenderer(log.Loggable,BasicAVMixin):
    logCategory = 'mediarenderer'

    def __init__(self, coherence, backend, **kwargs):
        self.coherence = coherence
        self.device_type = 'MediaRenderer'
        self.version = int(kwargs.get('version',self.coherence.config.get('version',2)))
        #log.Loggable.__init__(self)

        try:
            self.uuid = kwargs['uuid']
        except KeyError:
            from coherence.upnp.core.uuid import UUID
            self.uuid = UUID()

        self.backend = None

        self.icons = kwargs.get('iconlist', kwargs.get('icons', []))
        if len(self.icons) == 0:
            if kwargs.has_key('icon'):
                self.icons.append(kwargs['icon'])

        louie.connect( self.init_complete, 'Coherence.UPnP.Backend.init_completed', louie.Any)
        reactor.callLater(0.2, self.fire, backend, **kwargs)

    def fire(self,backend,**kwargs):
        if kwargs.get('no_thread_needed',False) == False:
            """ this could take some time, put it in a  thread to be sure it doesn't block
                as we can't tell for sure that every backend is implemented properly """

            from twisted.internet import threads
            d = threads.deferToThread(backend, self, **kwargs)

            def backend_ready(backend):
                self.backend = backend

            def backend_failure(x):
                self.warning('backend not installed, MediaRenderer activation aborted')
                self.debug(x)

            d.addCallback(backend_ready)
            d.addErrback(backend_failure)

            # FIXME: we need a timeout here so if the signal we wait for not arrives we'll
            #        can close down this device
        else:
            self.backend = backend(self, **kwargs)

    def init_complete(self, backend):
        if self.backend != backend:
            return
        self._services = []
        self._devices = []

        try:
            self.connection_manager_server = ConnectionManagerServer(self)
            self._services.append(self.connection_manager_server)
        except LookupError,msg:
            self.warning( 'ConnectionManagerServer', msg)
            raise LookupError,msg

        try:
            self.rendering_control_server = RenderingControlServer(self)
            self._services.append(self.rendering_control_server)
        except LookupError,msg:
            self.warning( 'RenderingControlServer', msg)
            raise LookupError,msg

        try:
            self.av_transport_server = AVTransportServer(self)
            self._services.append(self.av_transport_server)
        except LookupError,msg:
            self.warning( 'AVTransportServer', msg)
            raise LookupError,msg

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
                                    friendly_name=self.backend.name,
                                    services=self._services,
                                    devices=self._devices,
                                    icons=self.icons))
            version -= 1


        self.web_resource.putChild('ConnectionManager', self.connection_manager_server)
        self.web_resource.putChild('RenderingControl', self.rendering_control_server)
        self.web_resource.putChild('AVTransport', self.av_transport_server)

        for icon in self.icons:
            if icon.has_key('url'):
                if icon['url'].startswith('file://'):
                    self.web_resource.putChild(os.path.basename(icon['url']),
                                               static.File(icon['url'][7:]))

        self.register()
        self.info("%s MediaRenderer (%s) activated" % (self.backend.name, self.backend))
