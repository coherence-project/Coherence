# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006,2007 Frank Scholz <coherence@beebits.net>

import os
import re
import traceback
from StringIO import StringIO
import urllib

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import static
from twisted.web import resource, server
from twisted.web import proxy
from twisted.python import util
from twisted.python.filepath import FilePath

from coherence.extern.et import ET, indent

from coherence import __version__

from coherence.upnp.core.service import ServiceServer
from coherence.upnp.core.utils import StaticFile
#from coherence.upnp.core.utils import ReverseProxyResource

from coherence.upnp.services.servers.connection_manager_server import ConnectionManagerServer
from coherence.upnp.services.servers.content_directory_server import ContentDirectoryServer
from coherence.upnp.services.servers.media_receiver_registrar_server import MediaReceiverRegistrarServer
from coherence.upnp.services.servers.media_receiver_registrar_server import FakeMediaReceiverRegistrarBackend

from coherence.upnp.devices.basics import BasicDeviceMixin

import louie

from coherence import log

COVER_REQUEST_INDICATOR = re.compile(".*?cover\.[A-Z|a-z]{3,4}$")

ATTACHMENT_REQUEST_INDICATOR = re.compile(".*?attachment=.*$")

class MSRoot(resource.Resource, log.Loggable):
    logCategory = 'mediaserver'

    def __init__(self, server, store):
        resource.Resource.__init__(self)
        log.Loggable.__init__(self)
        self.server = server
        self.store = store

    def getChildWithDefault(self, path, request):
        self.info('%s getChildWithDefault, %s, %s, %s %s' % (self.server.device_type,
                                request.method, path, request.uri, request.client))
        headers = request.getAllHeaders()
        self.msg( request.getAllHeaders())

        if request.method == 'GET':
            if COVER_REQUEST_INDICATOR.match(request.uri):
                self.info("request cover for id %s" % path)
                ch = self.store.get_by_id(path)
                if ch is not None:
                    request.setResponseCode(200)
                    file = ch.get_cover()
                    if os.path.exists(file):
                        self.info("got cover %s" % file)
                        return StaticFile(file)
                request.setResponseCode(404)
                return static.Data('<html><p>cover requested not found</p></html>','text/html')

            if ATTACHMENT_REQUEST_INDICATOR.match(request.uri):
                self.info("request attachment %r for id %s" % (request.args,path))
                ch = self.store.get_by_id(path)
                try:
                    return ch.item.attachments[request.args['attachment'][0]]
                except:
                    request.setResponseCode(404)
                    return static.Data('<html><p>the requested attachment was not found</p></html>','text/html')

        if(request.method == 'POST' and
           request.uri.endswith('?import')):
            self.import_file(path,request)
            return self.import_response(path)

        if(headers.has_key('user-agent') and
           (headers['user-agent'].find('Xbox/') == 0 or      # XBox
            headers['user-agent'].startswith("""Mozilla/4.0 (compatible; UPnP/1.0; Windows""")) and  # wmp11
           path in ['description-1.xml','description-2.xml']):
            self.info('XBox/WMP alert, we need to simulate a Windows Media Connect server')
            if self.children.has_key('xbox-description-1.xml'):
                self.msg( 'returning xbox-description-1.xml')
                return self.children['xbox-description-1.xml']

        if self.children.has_key(path):
            return self.children[path]
        if request.uri == '/':
            return self
        return self.getChild(path, request)

    def requestFinished(self, result, id, request):
        self.info("finished, remove %d from connection table" % id)
        self.info("finished, sentLength: %d chunked: %d code: %d" % (request.sentLength, request.chunked, request.code))
        self.info("finished %r" % request.headers)
        self.server.connection_manager_server.remove_connection(id)

    def import_file(self,name,request):
        self.info("import file, id %s" % name)
        ch = self.store.get_by_id(name)
        if ch is not None:
            try:
                f = open(ch.get_path(), 'w+b')
                f.write(request.content.read()) #FIXME: is this the right way?
                f.close()
                request.setResponseCode(200)
                return
            except IOError:
                self.warning("import of file %s failed" % ch.get_path())

        request.setResponseCode(404)

    def getChild(self, name, request):
        self.info('getChild %s, %s' % (name, request))
        ch = self.store.get_by_id(name)
        if ch != None:
            self.info('Child found', ch)
            if(request.method == 'GET' or
               request.method == 'HEAD'):
                headers = request.getAllHeaders()
                if headers.has_key('content-length'):
                    self.warning('%s request with content-length %s header - sanitizing' % (
                                    request.method,
                                    headers['content-length']))
                    del request.received_headers['content-length']
                self.debug('data', )
                if len(request.content.getvalue()) > 0:
                    """ shall we remove that?
                        can we remove that?
                    """
                    self.warning('%s request with %d bytes of message-body - sanitizing' % (
                                    request.method,
                                    len(request.content.getvalue())))
                    request.content = StringIO()

            if hasattr(ch, "location"):
                if isinstance(ch.location, proxy.ReverseProxyResource):
                    self.info('getChild proxy %s to %s' % (name, ch.location.uri))
                    new_id,_,_ = self.server.connection_manager_server.add_connection('',
                                                                                'Output',
                                                                                -1,
                                                                                '')
                    self.info("startup, add %d to connection table" % new_id)
                    d = request.notifyFinish()
                    d.addBoth(self.requestFinished, new_id, request)
                    request.setHeader('transferMode.dlna.org', 'Streaming')
                    if hasattr(ch.item, 'res'):
                        if ch.item.res[0].protocolInfo is not None:
                            _,_,_,additional_info = ch.item.res[0].protocolInfo.split(':')
                            if additional_info != '*':
                                request.setHeader('contentFeatures.dlna.org', additional_info)
                    return ch.location
            try:
                p = ch.get_path()
            except Exception, msg:
                self.debug("error accessing items path %r" % msg)
                self.debug(traceback.format_exc())
                return self.list_content(name, ch, request)
            if p != None and os.path.exists(p):
                self.info("accessing path %r" % p)
                new_id,_,_ = self.server.connection_manager_server.add_connection('',
                                                                            'Output',
                                                                            -1,
                                                                            '')
                self.info("startup, add %d to connection table" % new_id)
                d = request.notifyFinish()
                d.addBoth(self.requestFinished, new_id, request)
                request.setHeader('transferMode.dlna.org', 'Streaming')
                if hasattr(ch, 'item') and hasattr(ch.item, 'res'):
                    if ch.item.res[0].protocolInfo is not None:
                        _,_,_,additional_info = ch.item.res[0].protocolInfo.split(':')
                        if additional_info != '*':
                            request.setHeader('contentFeatures.dlna.org', additional_info)
                ch = StaticFile(p)
            else:
                self.debug("accessing path %r failed" % p)
                return self.list_content(name, ch, request)

        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = StaticFile(p)
        self.info('MSRoot ch', ch)
        return ch

    def list_content(self, name, item, request):
        self.info('list_content', name, item, request)
        page = """<html><head><title>%s</title></head><body><p>%s</p>"""% \
                                            (item.get_name().encode('ascii','xmlcharrefreplace'),
                                             item.get_name().encode('ascii','xmlcharrefreplace'))

        if( hasattr(item,'mimetype') and item.mimetype in ['directory','root']):
            uri = request.uri
            if uri[-1] != '/':
                uri += '/'

            page += """<ul>"""
            for c in item.get_children():
                if hasattr(c,'get_url'):
                    path = c.get_url()
                    self.debug('has get_url', path)
                elif hasattr(c,'get_path'):
                    #path = c.get_path().encode('utf-8').encode('string_escape')
                    path = c.get_path()
                    if isinstance(path,unicode):
                        path = path.encode('ascii','xmlcharrefreplace')
                    else:
                        path = path.decode('utf-8').encode('ascii','xmlcharrefreplace')
                    self.debug('has get_path', path)
                else:
                    path = request.uri.split('/')
                    path[-1] = str(c.get_id())
                    path = '/'.join(path)
                    self.debug('got path', path)
                title = c.get_name()
                self.debug( 'title is:', type(title))
                try:
                    if isinstance(title,unicode):
                        title = title.encode('ascii','xmlcharrefreplace')
                    else:
                        title = title.decode('utf-8').encode('ascii','xmlcharrefreplace')
                except (UnicodeEncodeError,UnicodeDecodeError):
                    title = c.get_name().encode('utf-8').encode('string_escape')
                page += '<li><a href="%s">%s</a></li>' % \
                                    (path, title)
            page += """</ul>"""
        elif( hasattr(item,'mimetype') and item.mimetype.find('image/') == 0):
            #path = item.get_path().encode('utf-8').encode('string_escape')
            path = urllib.quote(item.get_path().encode('utf-8'))
            title = item.get_name().decode('utf-8').encode('ascii','xmlcharrefreplace')
            page += """<p><img src="%s" alt="%s"></p>""" % \
                                    (path, title)
        else:
            pass
        page += """</body></html>"""
        return static.Data(page,'text/html')

    def listchilds(self, uri):
        self.info('listchilds %s' % uri)
        if uri[-1] != '/':
            uri += '/'
        cl = '<p><a href=%s0>content</a></p>' % uri
        for c in self.children:
                cl += '<li><a href=%s%s>%s</a></li>' % (uri,c,c)
        return cl

    def import_response(self,id):
        return static.Data('<html><p>import of %s finished</p></html>'% id,'text/html')

    def render(self,request):
        #print "render", request
        return '<html><p>root of the %s MediaServer</p><p><ul>%s</ul></p></html>'% \
                                        (self.server.backend,
                                         self.listchilds(request.uri))


class RootDeviceXML(static.Data):

    def __init__(self, hostname, uuid, urlbase,
                        device_type='MediaServer',
                        version=2,
                        friendly_name='Coherence UPnP A/V MediaServer',
                        xbox_hack=False,
                        services=[],
                        devices=[],
                        icons=[]):
        uuid = str(uuid)
        root = ET.Element('root')
        root.attrib['xmlns']='urn:schemas-upnp-org:device-1-0'
        device_type = 'urn:schemas-upnp-org:device:%s:%d' % (device_type, int(version))
        e = ET.SubElement(root, 'specVersion')
        ET.SubElement(e, 'major').text = '1'
        ET.SubElement(e, 'minor').text = '0'

        ET.SubElement(root, 'URLBase').text = urlbase

        d = ET.SubElement(root, 'device')
        x = ET.SubElement(d, 'dlna:X_DLNADOC')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'DMS-1.50'
        x = ET.SubElement(d, 'dlna:X_DLNADOC')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'M-DMS-1.50'
        x=ET.SubElement(d, 'dlna:X_DLNACAP')
        x.attrib['xmlns:dlna']='urn:schemas-dlna-org:device-1-0'
        x.text = 'av-upload,image-upload,audio-upload'
        ET.SubElement(d, 'deviceType').text = device_type
        if xbox_hack == False:
            ET.SubElement(d, 'modelName').text = 'Coherence UPnP A/V MediaServer'
            ET.SubElement(d, 'friendlyName').text = friendly_name
        else:
            ET.SubElement(d, 'modelName').text = 'Windows Media Connect'
            ET.SubElement(d, 'friendlyName').text = friendly_name + ' : 1 : Windows Media Connect'
        ET.SubElement(d, 'manufacturer').text = 'beebits.net'
        ET.SubElement(d, 'manufacturerURL').text = 'http://coherence.beebits.net'
        ET.SubElement(d, 'modelDescription').text = 'Coherence UPnP A/V MediaServer'
        ET.SubElement(d, 'modelNumber').text = __version__
        ET.SubElement(d, 'modelURL').text = 'http://coherence.beebits.net'
        ET.SubElement(d, 'serialNumber').text = '0000001'
        ET.SubElement(d, 'UDN').text = uuid
        ET.SubElement(d, 'UPC').text = ''
        ET.SubElement(d, 'presentationURL').text = ''

        if len(services):
            e = ET.SubElement(d, 'serviceList')
            for service in services:
                id = service.get_id()
                s = ET.SubElement(e, 'service')
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
                ET.SubElement(s, 'serviceId').text = 'urn:%s:serviceId:%s' % (namespace,id)
                ET.SubElement(s, 'SCPDURL').text = '/' + uuid[5:] + '/' + id + '/' + service.scpd_url
                ET.SubElement(s, 'controlURL').text = '/' + uuid[5:] + '/' + id + '/' + service.control_url
                ET.SubElement(s, 'eventSubURL').text = '/' + uuid[5:] + '/' + id + '/' + service.subscription_url

        if len(devices):
            e = ET.SubElement(d, 'deviceList')

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

class MediaServer(log.Loggable,BasicDeviceMixin):
    logCategory = 'mediaserver'

    def __init__(self, coherence, backend, **kwargs):
        self.coherence = coherence
        self.device_type = 'MediaServer'
        self.version = int(kwargs.get('version',self.coherence.config.get('version',2)))

        try:
            self.uuid = kwargs['uuid']
        except KeyError:
            from coherence.upnp.core.uuid import UUID
            self.uuid = UUID()

        self.backend = None
        urlbase = self.coherence.urlbase
        if urlbase[-1] != '/':
            urlbase += '/'
        self.urlbase = urlbase + str(self.uuid)[5:]

        self.msg('MediaServer urlbase %s' % self.urlbase)

        kwargs['urlbase'] = self.urlbase
        self.icons = kwargs.get('iconlist', kwargs.get('icons', []))
        if len(self.icons) == 0:
            if kwargs.has_key('icon'):
                self.icons.append(kwargs['icon'])

        louie.connect( self.init_complete, 'Coherence.UPnP.Backend.init_completed', louie.Any)
        louie.connect( self.init_failed, 'Coherence.UPnP.Backend.init_failed', louie.Any)
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
                self.warning('backend %s not installed, MediaServer activation aborted - %s', backend, x.getErrorMessage())
                self.debug(x)

            d.addCallback(backend_ready)
            d.addErrback(backend_failure)

            # FIXME: we need a timeout here so if the signal we wait for not arrives we'll
            #        can close down this device
        else:
            self.backend = backend(self, **kwargs)

    def init_failed(self, backend, msg):
        if self.backend != backend:
            return
        self.warning('backend not installed, MediaServer activation aborted - %s', msg.getErrorMessage())
        self.debug(msg)
        del self.coherence.active_backends[str(self.uuid)]

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
            self.content_directory_server = ContentDirectoryServer(self)
            self._services.append(self.content_directory_server)
        except LookupError,msg:
            self.warning( 'ContentDirectoryServer', msg)
            raise LookupError,msg

        try:
            self.media_receiver_registrar_server = MediaReceiverRegistrarServer(self,
                                                        backend=FakeMediaReceiverRegistrarBackend())
            self._services.append(self.media_receiver_registrar_server)
        except LookupError,msg:
            self.warning( 'MediaReceiverRegistrarServer (optional)', msg)

        upnp_init = getattr(self.backend, "upnp_init", None)
        if upnp_init:
            upnp_init()

        self.web_resource = MSRoot( self, backend)
        self.coherence.add_web_resource( str(self.uuid)[5:], self.web_resource)

        version = int(self.version)
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
            self.web_resource.putChild( 'xbox-description-%d.xml' % version,
                                    RootDeviceXML( self.coherence.hostname,
                                    str(self.uuid),
                                    self.coherence.urlbase,
                                    self.device_type, version,
                                    friendly_name=self.backend.name,
                                    xbox_hack=True,
                                    services=self._services,
                                    devices=self._devices,
                                    icons=self.icons))
            version -= 1

        self.web_resource.putChild('ConnectionManager', self.connection_manager_server)
        self.web_resource.putChild('ContentDirectory', self.content_directory_server)
        self.web_resource.putChild('X_MS_MediaReceiverRegistrar', self.media_receiver_registrar_server)

        for icon in self.icons:
            if icon.has_key('url'):
                if icon['url'].startswith('file://'):
                    self.web_resource.putChild(os.path.basename(icon['url']),
                                               StaticFile(icon['url'][7:]))

        self.register()
        self.info("%s MediaServer (%s) activated" % (self.backend.name, self.backend))
