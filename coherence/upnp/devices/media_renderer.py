# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006,2007 Frank Scholz <coherence@beebits.net>

import os.path

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import resource, static

from coherence import __version__

from coherence.extern.et import ET, indent

from coherence.upnp.core.utils import StaticFile

from coherence.upnp.services.servers.connection_manager_server import ConnectionManagerServer
from coherence.upnp.services.servers.rendering_control_server import RenderingControlServer
from coherence.upnp.services.servers.av_transport_server import AVTransportServer

from coherence.upnp.devices.basics import RootDeviceXML, DeviceHttpRoot, BasicDeviceMixin

from coherence import log

class HttpRoot(DeviceHttpRoot):
    logCategory = 'mediarenderer'


class MediaRenderer(log.Loggable,BasicDeviceMixin):
    logCategory = 'mediarenderer'
    device_type = 'MediaRenderer'

    def fire(self,backend,**kwargs):

        if kwargs.get('no_thread_needed',False) == False:
            """ this could take some time, put it in a  thread to be sure it doesn't block
                as we can't tell for sure that every backend is implemented properly """

            from twisted.internet import threads
            d = threads.deferToThread(backend, self, **kwargs)

            def backend_ready(backend):
                self.backend = backend

            def backend_failure(x):
                self.warning('backend %s not installed, %s activation aborted - %s' % (backend, self.device_type, x.getErrorMessage()))
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


        self.web_resource = HttpRoot(self)
        self.coherence.add_web_resource( str(self.uuid)[5:], self.web_resource)

        try:
            dlna_caps = self.backend.dlna_caps
        except AttributeError:
            dlna_caps = []


        version = self.version
        while version > 0:
            self.web_resource.putChild( 'description-%d.xml' % version,
                                    RootDeviceXML( self.coherence.hostname,
                                    str(self.uuid),
                                    self.coherence.urlbase,
                                    device_type=self.device_type,
                                    version=version,
                                    #presentation_url='/'+str(self.uuid)[5:],
                                    friendly_name=self.backend.name,
                                    model_description='Coherence UPnP A/V %s' % self.device_type,
                                    model_name='Coherence UPnP A/V %s' % self.device_type,
                                    services=self._services,
                                    devices=self._devices,
                                    icons=self.icons,
                                    dlna_caps=dlna_caps))
            version -= 1


        self.web_resource.putChild('ConnectionManager', self.connection_manager_server)
        self.web_resource.putChild('RenderingControl', self.rendering_control_server)
        self.web_resource.putChild('AVTransport', self.av_transport_server)

        for icon in self.icons:
            if icon.has_key('url'):
                if icon['url'].startswith('file://'):
                    if os.path.exists(icon['url'][7:]):
                        self.web_resource.putChild(os.path.basename(icon['url']),
                                                   StaticFile(icon['url'][7:],defaultType=icon['mimetype']))
                elif icon['url'] == '.face':
                    face_path = os.path.abspath(os.path.join(os.path.expanduser('~'), ".face"))
                    if os.path.exists(face_path):
                        self.web_resource.putChild('face-icon.png',StaticFile(face_path,defaultType=icon['mimetype']))
                else:
                    from pkg_resources import resource_filename
                    icon_path = os.path.abspath(resource_filename(__name__, os.path.join('..','..','..','misc','device-icons',icon['url'])))
                    if os.path.exists(icon_path):
                        self.web_resource.putChild(icon['url'],StaticFile(icon_path,defaultType=icon['mimetype']))


        self.register()
        self.warning("%s %s (%s) activated with %s" % (self.backend.name, self.device_type, self.backend, str(self.uuid)[5:]))
