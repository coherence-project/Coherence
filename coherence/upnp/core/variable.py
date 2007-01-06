# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from coherence.upnp.core import utils
try:
    #FIXME:
    # there is some circular import, service imports variable, variable imports service
    # how is this done properly?
    #
    from coherence.upnp.core import service
except ImportError:
    import service
    
from coherence.extern.logger import Logger
log = Logger('Variable')

class StateVariable:

    def __init__(self, upnp_service, name, implementation, instance, send_events,
                 data_type, values):
        self.service = upnp_service
        self.instance = instance
        self.name = name
        self.implementation = implementation
        self.data_type = data_type
        self.allowed_values = values
        self.has_vendor_values = False
        self.default_value = ''
        self.old_value = ''
        self.value = ''
        if send_events in [True,1,'1','true','True','yes','Yes']:
            self.send_events = True
        else:
            self.send_events = False
        self._callbacks = []
        if isinstance( self.service, service.ServiceServer):
            self.moderated = self.service.is_variable_moderated(name)
            self.updated = False

    def set_default_value(self, value):
        self.update(value)
        self.default_value = self.value
        
    def update(self, value):
        self.old_value = self.value
        # MOD if value == self.value:
        #    return
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
                        if self.has_vendor_values:
                            self.value = value
                        elif value.upper() in [v.upper() for v in self.allowed_values]:
                            self.value = value
                        else:
                            log.warning("Variable %s update, value %s doesn't fit for variable" % (self.name, value))
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
        else:
            self.updated = True
            #print self.service.last_change
            if self.service.last_change != None:
                self.service.last_change.updated = True
                #print self.service.last_change.updated
        #print "variable update", self.name, self.value, self.moderated

    def subscribe(self, callback):
        self._callbacks.append(callback)
        
    def notify(self):
        for callback in self._callbacks:
            callback( self)
            
    def __repr__(self):
        return "Variable: %s, %s, %d, %s, %s, %s, %s, %s, %s" % \
                        (self.name,
                         str(self.service),
                         self.instance,
                         self.implementation,
                         self.data_type,
                         str(self.allowed_values),
                         str(self.default_value),
                         str(self.value),
                         str(self.send_events))

