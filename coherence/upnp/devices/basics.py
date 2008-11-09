# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008 Frank Scholz <coherence@beebits.net>

import os.path

from twisted.python import util
from twisted.web import resource, static
from twisted.internet import reactor

from coherence import __version__

from coherence.extern.et import ET, indent

import coherence.extern.louie as louie


from coherence import log


class DeviceHttpRoot(resource.Resource, log.Loggable):
    logCategory = 'basicdevice'

    def __init__(self, server):
        resource.Resource.__init__(self)
        self.server = server

    def getChildWithDefault(self, path, request):
        self.info('DeviceHttpRoot %s getChildWithDefault' % self.server.device_type, path, request.uri, request.client)
        self.info( request.getAllHeaders())
        if self.children.has_key(path):
            return self.children[path]
        if request.uri == '/':
            return self
        return self.getChild(path, request)

    def getChild(self, name, request):
        self.info('DeviceHttpRoot %s getChild %s' % (name, request))
        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = static.File(p)
        self.info('DeviceHttpRoot ch', ch)
        return ch

    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the %s %s</p><p><ul>%s</ul></p></html>'% (self.server.backend.name,
                                                                           self.server.device_type,
                                                                           self.listchilds(request.uri))

class RootDeviceXML(static.Data):

    def __init__(self, hostname, uuid, urlbase,
                        device_type='BasicDevice',
                        version=2,
                        friendly_name='Coherence UPnP BasicDevice',
                        model_description='Coherence UPnP BasicDevice',
                        model_name='Coherence UPnP BasicDevice',
                        presentation_url='',
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
        ET.SubElement( d, 'modelDescription').text = model_description
        ET.SubElement( d, 'modelName').text = model_name
        ET.SubElement(d, 'modelNumber').text = __version__
        ET.SubElement( d, 'modelURL').text = 'http://coherence.beebits.net'
        ET.SubElement( d, 'serialNumber').text = '0000001'
        ET.SubElement( d, 'UDN').text = uuid
        ET.SubElement( d, 'UPC').text = ''
        ET.SubElement( d, 'presentationURL').text = presentation_url

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

class BasicDeviceMixin(object):

    def __init__(self, coherence, backend, **kwargs):
        self.coherence = coherence
        if not hasattr(self,'version'):
            self.version = int(kwargs.get('version',self.coherence.config.get('version',2)))

        try:
            self.uuid = kwargs['uuid']
            if not self.uuid.startswith('uuid:'):
                self.uuid = 'uuid:' + self.uuid
        except KeyError:
            from coherence.upnp.core.uuid import UUID
            self.uuid = UUID()

        self.backend = None
        urlbase = self.coherence.urlbase
        if urlbase[-1] != '/':
            urlbase += '/'
        self.urlbase = urlbase + str(self.uuid)[5:]

        kwargs['urlbase'] = self.urlbase
        self.icons = kwargs.get('iconlist', kwargs.get('icons', []))
        if len(self.icons) == 0:
            if kwargs.has_key('icon'):
                if isinstance(kwargs['icon'],dict):
                    self.icons.append(kwargs['icon'])
                else:
                    self.icons = kwargs['icon']

        louie.connect( self.init_complete, 'Coherence.UPnP.Backend.init_completed', louie.Any)
        louie.connect( self.init_failed, 'Coherence.UPnP.Backend.init_failed', louie.Any)
        reactor.callLater(0.2, self.fire, backend, **kwargs)

    def init_failed(self, backend, msg):
        if self.backend != backend:
            return
        self.warning('backend not installed, %s activation aborted - %s' % (self.device_type,msg.getErrorMessage()))
        self.debug(msg)
        try:
            del self.coherence.active_backends[str(self.uuid)]
        except KeyError:
            pass

    def register(self):
        s = self.coherence.ssdp_server
        uuid = str(self.uuid)
        host = self.coherence.hostname
        self.msg('%s register' % self.device_type)
        # we need to do this after the children are there, since we send notifies
        s.register('local',
                    '%s::upnp:rootdevice' % uuid,
                    'upnp:rootdevice',
                    self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % self.version,
                    host=host)

        s.register('local',
                    uuid,
                    uuid,
                    self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % self.version,
                    host=host)

        version = self.version
        while version > 0:
            if version == self.version:
                silent = False
            else:
                silent = True
            s.register('local',
                        '%s::urn:schemas-upnp-org:device:%s:%d' % (uuid, self.device_type, version),
                        'urn:schemas-upnp-org:device:%s:%d' % (self.device_type, version),
                        self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % version,
                        silent=silent,
                        host=host)
            version -= 1


        for service in self._services:
            device_version = self.version
            service_version = self.version
            if hasattr(service,'version'):
                service_version = service.version
            silent = False

            while service_version > 0:
                try:
                    namespace = service.namespace
                except:
                    namespace = 'schemas-upnp-org'

                s.register('local',
                            '%s::urn:%s:service:%s:%d' % (uuid,namespace,service.id, service_version),
                            'urn:%s:service:%s:%d' % (namespace,service.id, service_version),
                            self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % device_version,
                            silent=silent,
                            host=host)

                silent = True
                service_version -= 1
                device_version -= 1

    def unregister(self):

        if self.backend != None and hasattr(self.backend,'release'):
            self.backend.release()

        if not hasattr(self,'_services'):
            """ seems we never made it to actually
                completing that device
            """
            return

        for service in self._services:
            try:
                service.check_subscribers_loop.stop()
            except:
                pass
            if hasattr(service,'check_moderated_loop') and service.check_moderated_loop != None:
                try:
                    service.check_moderated_loop.stop()
                except:
                    pass
            if hasattr(service,'release'):
                service.release()
            if hasattr(service,'_release'):
                service._release()

        s = self.coherence.ssdp_server
        uuid = str(self.uuid)
        self.coherence.remove_web_resource(uuid[5:])

        version = self.version
        while version > 0:
            s.doByebye('%s::urn:schemas-upnp-org:device:%s:%d' % (uuid, self.device_type, version))
            for service in self._services:
                if hasattr(service,'version') and service.version < version:
                    continue
                try:
                    namespace = service.namespace
                except AttributeError:
                    namespace = 'schemas-upnp-org'
                s.doByebye('%s::urn:%s:service:%s:%d' % (uuid,namespace,service.id, version))

            version -= 1

        s.doByebye(uuid)
        s.doByebye('%s::upnp:rootdevice' % uuid)