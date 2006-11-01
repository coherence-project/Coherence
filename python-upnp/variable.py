# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import service

class StateVariable:

    def __init__(self, upnp_service, name, implementation, instance, send_events,
                 data_type, values):
        self.service = upnp_service
        self.instance = instance
        self.name = name
        self.implementation = implementation
        self.old_value = ''
        self.value = ''
        self.send_events = send_events
        self.data_type = data_type
        self.allowed_values = values
        self._callbacks = []
        if isinstance( self.service, service.Server):
            self.moderated = check_for_moderation(self.service.get_type(), name)
            self.updated = False


    def update(self, value):
        self.old_value = self.value
        self.value = value
        if isinstance( self.service, service.Service):
            self.notify()
        elif self.moderated:
            self.updated = True

    def subscribe(self, callback):
        self._callbacks.append(callback)
        
    def notify(self):
        for callback in self._callbacks:
            callback( self)
        
def check_for_moderation(service_type, name):
    t = {'urn:schemas-upnp-org:service:AVTransport:2':
            ['LastChange'],
         'urn:schemas-upnp-org:service:ContentDirectory:2':
            ['SystemUpdateID', 'ContainerUpdateIDs'],
         'urn:schemas-upnp-org:service:RenderingControl:2':
            ['LastChange'],
         'urn:schemas-upnp-org:service:ScheduledRecording:1':
            ['LastChange'],
        }
    try:
        variables = t[service_type]
        if name in variables:
            return True
    except:
        pass
    return False