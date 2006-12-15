# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from coherence.upnp.core import utils
try:
    #FIXME
    # there is some circular import, service imports variable, variable imports service
    # how is this done properly
    #
    from coherence.upnp.core import service
except ImportError:
    import service

class StateVariable:

    def __init__(self, upnp_service, name, implementation, instance, send_events,
                 data_type, values):
        self.service = upnp_service
        self.instance = instance
        self.name = name
        self.implementation = implementation
        self.data_type = data_type
        self.allowed_values = values
        self.old_value = ''
        self.value = ''
        self.send_events = send_events
        self._callbacks = []
        if isinstance( self.service, service.Server):
            self.moderated = self.service.is_variable_moderated(name)
            self.updated = False

    def update(self, value):
        self.old_value = self.value
        #print "variable update", self.name, value, self.service
        if not isinstance( self.service, service.Service):
            if self.name == 'ContainerUpdateIDs':
                if self.updated == True:
                    if isinstance( value, tuple):
                        v = self.value.split(',')
                        i = 0
                        while i < len(v):
                            if v[i] == str(value[0]):
                                del v[i:i+2]
                                self.value = ','.join(v)
                                break;
                            i += 2
                        if len(self.value):
                            self.value = self.value + ',' + str(value[0]) + ',' + str(value[1])
                        else:
                            self.value = str(value[0]) + ',' + str(value[1])
                    else:
                        if len(self.value):
                            self.value = str(self.value) + ',' + str(value)
                        else:
                            self.value = str(value)
                else:
                    if isinstance( value, tuple):
                        self.value = str(value[0]) + ',' + str(value[1])
                    else:
                        self.value = value
            else:
                if self.data_type == 'string':
                    value = str(value)
                    if len(self.allowed_values):
                        if value.upper() in [v.upper() for v in self.allowed_values]:
                            self.value = value
                        else:
                            print "Variable %s update, value %s doesn't fit for variable" % (self.name, value)
                    else:
                        self.value = value
                elif self.data_type == 'boolean':
                    if value in [1,'1','true','True','yes','Yes']:
                        self.value = '1'
                    else:
                        self.value = '0'
                else:
                    self.value = int(value)
        else:
            if self.data_type == 'string':
                value = str(value)
                if len(self.allowed_values):
                    if value.upper() in [v.upper() for v in self.allowed_values]:
                        self.value = value
                else:
                    self.value = value
            elif self.data_type == 'boolean':
                if value in [1,'true','True','yes','Yes']:
                    self.value = '1'
                else:
                    self.value = '0'
            else:
                self.value = int(value)
        if isinstance( self.service, service.Service):
            self.notify()
        elif self.moderated:
            self.updated = True
            if self.service.last_change:
                self.service.last_change.updated = True
        #print "variable update", self.name, self.value, self.moderated

    def subscribe(self, callback):
        self._callbacks.append(callback)
        
    def notify(self):
        for callback in self._callbacks:
            callback( self)
        