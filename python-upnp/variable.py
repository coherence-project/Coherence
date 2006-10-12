# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
 	
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>


class StateVariable:

    def __init__(self, service, implementation, name, instance, send_events,
                 data_type, values):
        self.service = service
        self.instance = instance
        self.name = name
        self.implementation = implementation
        self.old_value = ''
        self.value = ''
        self.send_events = send_events
        self.data_type = data_type
        self.allowed_values = values
        self._callbacks = []

    def update(self, value):
        self.old_value = self.value
        self.value = value
        self.notify()

    def subscribe(self, callback):
        self._callbacks.append(callback)
        
    def notify(self):
        for callback in self._callbacks:
            callback( self)
        
