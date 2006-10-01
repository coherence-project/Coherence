# Elisa - Home multimedia server
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# All rights reserved.
# 
# This software is available under three license agreements.
# 
# There are various plugins and extra modules for Elisa licensed
# under the MIT license. For instance our upnp module uses this license.
# 
# The core of Elisa is licensed under GPL version 2.
# See "LICENSE.GPL" in the root of this distribution including a special 
# exception to use Elisa with Fluendo's plugins.
# 
# The GPL part is also available under a commerical licensing
# agreement.
# 
# The second license is the Elisa Commercial License Agreement.
# This license agreement is available to licensees holding valid
# Elisa Commercial Agreement licenses.
# See "LICENSE.Elisa" in the root of this distribution.


class StateVariable:

    def __init__(self, service, name, send_events,
                 data_type, values):
        self.service = service
        self.name = name
        self.send_events = send_events
        self.data_type = data_type
        self.allowed_values = values
        self._callbacks = []

    def update(self, value):
        self.value = value
        self.notify(value)

    def subscribe(self, callback):
        self._callbacks.append(callback)
        
    def notify(self, new_value):
        for callback in self._callbacks:
            callback(self.service, new_value)
        
