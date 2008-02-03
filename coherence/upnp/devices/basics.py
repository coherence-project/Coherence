# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008 Frank Scholz <coherence@beebits.net>

class BasicAVMixin(object):
    
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
                            self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % self.version,
                            silent=silent,
                            host=host)

                silent = True
                service_version -= 1

    def unregister(self):
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