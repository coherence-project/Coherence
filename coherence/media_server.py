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
from twisted.python import log, failure, util

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from connection_manager_server import ConnectionManagerServer
from content_directory_server import ContentDirectoryServer
from media_receiver_registrar_server import MediaReceiverRegistrarServer
from media_receiver_registrar_server import FakeMediaReceiverRegistrarBackend

from fs_storage import FSStore
from elisa_storage import ElisaMediaStore

class MSRoot(resource.Resource):

    def __init__(self, server, store):
        resource.Resource.__init__(self)
        self.server = server
        self.store = store
        
    def getChildWithDefault(self, path, request):
        print 'MSRoot getChildWithDefault', path, request.uri, request.client
        if self.children.has_key(path):
            return self.children[path]
        if request.uri == '/':
            return self
        return self.getChild(path, request)
        
    def requestFinished(self, result, id):
        print "finished, remove %d from connection table" % id
        self.server.connection_manager_server.remove_connection(id)

    def getChild(self, name, request):
        print 'MSRoot getChild', name, request
        ch = self.store.get_by_id(name)
        if ch != None:
            p = ch.get_path()
            if os.path.exists(p):
                new_id = self.server.connection_manager_server.add_connection()
                print "startup, add %d to connection table" % new_id
                d = request.notifyFinish()
                d.addCallback(self.requestFinished, new_id)
                d.addErrback(self.requestFinished, new_id)
                ch = static.File(p)
        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = static.File(p)
        print 'MSRoot ch', ch
        return ch
        
    def listchilds(self, uri):
        print 'listchilds', uri
        cl = ''
        sep = ''
        if uri[-1] != '/':
            sep = '/'
        for c in self.children:
                cl += '<li><a href=%s%s%s>%s</a></li>' % (uri,sep,c,c)
        return cl

    def render_HTML(self,request):
        return '<html><p>root of the MediaServer</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)

    def render(self,request):
        return '<html><p>root of the MediaServer</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)


class RootDeviceXML(static.Data):

    def __init__(self, hostname, uuid, urlbase,
                        device_type='MediaServer',
                        version=2,
                        friendly_name='Coherence UPnP A/V MediaServer',
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
        SubElement( d, 'modelDescription').text = 'Coherence UPnP A/V MediaServer'
        SubElement( d, 'modelName').text = 'Coherence'
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

    def __init__(self, coherence, version=2):
        self.coherence = coherence
        self.device_type = 'MediaServer'
        self.version = version
        from uuid import UUID
        self.uuid = UUID()
        self.store = None
        urlbase = self.coherence.urlbase
        if urlbase[-1] != '/':
            urlbase += '/'
        self.urlbase = urlbase + str(self.uuid)[5:]

        print 'MediaServer urlbase', urlbase

        p = 'content'
        
        """ this could take some time, put it in a  thread to be sure it doesn't block
            as we can't tell for sure that every backend is implemented properly """
        d = threads.deferToThread(FSStore, 'my content', p, self.urlbase, ())
        #d = threads.deferToThread(ElisaMediaStore, 'Elisas content', 'localhost, self.urlbase, ())
        d.addCallback(self.backend_ready)
        d.addErrback(log.err)
        
    def backend_ready(self, backend):
        self._services = []
        self._devices = []
        
        self.connection_manager_server = ConnectionManagerServer(self.version, backend)
        self._services.append(self.connection_manager_server)
        
        self.content_directory_server = ContentDirectoryServer(self.version, backend)
        self._services.append(self.content_directory_server)
        
        self.media_receiver_registrar_server = MediaReceiverRegistrarServer(self.version,
                                                        FakeMediaReceiverRegistrarBackend())
        self._services.append(self.media_receiver_registrar_server)
        
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
            version -= 1

        self.web_resource.putChild('ConnectionManager', self.connection_manager_server)
        self.web_resource.putChild('ContentDirectory', self.content_directory_server)
        self.web_resource.putChild('X_MS_MediaReceiverRegistrar', self.media_receiver_registrar_server)

        self.store = backend
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

