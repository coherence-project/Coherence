# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import os
import urllib, urlparse

from twisted.internet import task
from twisted.internet import reactor
from twisted.internet import threads
from twisted.web import xmlrpc, static
from twisted.web import resource, server
from twisted.python import util

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from coherence.upnp.core.service import ServiceServer

from coherence.upnp.services.servers.connection_manager_server import ConnectionManagerServer
from coherence.upnp.services.servers.content_directory_server import ContentDirectoryServer
from coherence.upnp.services.servers.media_receiver_registrar_server import MediaReceiverRegistrarServer
from coherence.upnp.services.servers.media_receiver_registrar_server import FakeMediaReceiverRegistrarBackend

from coherence.backends.fs_storage import FSStore
from coherence.backends.elisa_storage import ElisaMediaStore

from coherence.extern.logger import Logger
log = Logger('MediaServer')

class MSRoot(resource.Resource):

    def __init__(self, server, store):
        resource.Resource.__init__(self)
        self.server = server
        self.store = store
        
    def getChildWithDefault(self, path, request):
        log.info('%s getChildWithDefault, %s, %s %s' % (self.server.device_type,
                                path, request.uri, request.client))
        headers = request.getAllHeaders()
        log.msg( request.getAllHeaders())
        
        if( headers.has_key('user-agent') and
            headers['user-agent'].find('Xbox/') == 0 and
            path in ['description-1.xml','description-2.xml']):
            log.info('XBox alert, we need to simulate a Windows Media Connect server')
            if self.children.has_key('xbox-description-1.xml'):
                log.msg( 'returning xbox-description-1.xml')
                return self.children['xbox-description-1.xml']

        if self.children.has_key(path):
            return self.children[path]
        if request.uri == '/':
            return self
        return self.getChild(path, request)
        
    def requestFinished(self, result, id):
        log.info("finished, remove %d from connection table" % id)
        self.server.connection_manager_server.remove_connection(id)

    def getChild(self, name, request):
        log.info('getChild %s, %s' % (name, request))
        ch = self.store.get_by_id(name)
        if ch != None:
            p = ch.get_path()
            if os.path.exists(p):
                new_id,_,_ = self.server.connection_manager_server.add_connection('',
                                                                            'Output',
                                                                            -1,
                                                                            '')
                log.msg("startup, add %d to connection table" % new_id)
                d = request.notifyFinish()
                d.addCallback(self.requestFinished, new_id)
                d.addErrback(self.requestFinished, new_id)
                ch = static.File(p)
        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = static.File(p)
        log.info('MSRoot ch', ch)
        return ch
        
    def listchilds(self, uri):
        log.info('listchilds %s' % uri)
        cl = ''
        sep = ''
        if uri[-1] != '/':
            sep = '/'
        for c in self.children:
                cl += '<li><a href=%s%s%s>%s</a></li>' % (uri,sep,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the MediaServer</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)


class RootDeviceXML(static.Data):

    def __init__(self, hostname, uuid, urlbase,
                        device_type='MediaServer',
                        version=2,
                        friendly_name='Coherence UPnP A/V MediaServer',
                        xbox_hack=False,
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
        x = SubElement( d, 'dlna:X_DLNADOC')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'DMS-1.50'
        x = SubElement( d, 'dlna:X_DLNADOC')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'M-DMS-1.50'
        x=SubElement( d, 'dlna:X_DLNACAP')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'av-upload,image-upload,audio-upload'
        SubElement( d, 'deviceType').text = device_type
        if xbox_hack == False:
            SubElement( d, 'modelName').text = 'Coherence UPnP A/V MediaServer'
            SubElement( d, 'friendlyName').text = friendly_name
        else:
            SubElement( d, 'modelName').text = 'Windows Media Connect'
            SubElement( d, 'friendlyName').text = friendly_name + ' : 1 : Windows Media Connect'
        SubElement( d, 'manufacturer').text = 'beebits.net'
        SubElement( d, 'manufacturerURL').text = 'http://coherence.beebits.net'
        SubElement( d, 'modelDescription').text = 'Coherence UPnP A/V MediaServer'
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

        self.xml = tostring( root, encoding='utf-8')
        static.Data.__init__(self, self.xml, 'text/xml')
        
class MediaServer:

    def __init__(self, coherence, backend, **kwargs):
        self.coherence = coherence
        self.device_type = 'MediaServer'
        self.version = kwargs.get('version',2)
        from coherence.upnp.core.uuid import UUID
        self.uuid = UUID()
        self.backend = None
        urlbase = self.coherence.urlbase
        if urlbase[-1] != '/':
            urlbase += '/'
        self.urlbase = urlbase + str(self.uuid)[5:]
        
        log.msg('MediaServer urlbase %s' % self.urlbase)
        
        kwargs['urlbase'] = self.urlbase

        """ this could take some time, put it in a  thread to be sure it doesn't block
            as we can't tell for sure that every backend is implemented properly """
        d = threads.deferToThread(backend, self, **kwargs)
        #d = threads.deferToThread(ElisaMediaStore, 'Elisas content', localhost, self.urlbase, (), self)
        
        def backend_failure(x):
            log.critical('backend not installed, MediaServer activation aborted')
            
        def service_failure(x):
            print x
            log.critical('required service not available, MediaServer activation aborted')
            
        d.addCallback(self.backend_ready).addErrback(service_failure)
        d.addErrback(backend_failure)
        
    def backend_ready(self, backend):
        self._services = []
        self._devices = []
        
        self.backend = backend
        
        try:
            self.connection_manager_server = ConnectionManagerServer(self)
            self._services.append(self.connection_manager_server)
        except LookupError,msg:
            log.warning( 'ConnectionManagerServer', msg)
            raise LookupError,msg
        
        try:
            self.content_directory_server = ContentDirectoryServer(self)
            self._services.append(self.content_directory_server)
        except LookupError,msg:
            log.warning( 'ContentDirectoryServer', msg)
            raise LookupError,msg
        
        try:
            self.media_receiver_registrar_server = MediaReceiverRegistrarServer(self,
                                                        backend=FakeMediaReceiverRegistrarBackend())
            self._services.append(self.media_receiver_registrar_server)
        except LookupError,msg:
            log.warning( 'MediaReceiverRegistrarServer (optional)', msg)
        
        upnp_init = getattr(self.backend, "upnp_init", None)
        if upnp_init:
            upnp_init()
        
        self.web_resource = MSRoot( self, backend)
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
            self.web_resource.putChild( 'xbox-description-%d.xml' % version,
                                    RootDeviceXML( self.coherence.hostname,
                                    str(self.uuid),
                                    self.coherence.urlbase,
                                    self.device_type, version,
                                    xbox_hack=True,
                                    services=self._services,
                                    devices=self._devices))
            version -= 1

        self.web_resource.putChild('ConnectionManager', self.connection_manager_server)
        self.web_resource.putChild('ContentDirectory', self.content_directory_server)
        self.web_resource.putChild('X_MS_MediaReceiverRegistrar', self.media_receiver_registrar_server)

        self.register()

    def register(self):
        s = self.coherence.ssdp_server
        uuid = str(self.uuid)
        log.msg('%s register' % self.device_type)
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

