# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

class DimmingClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.subscribe()
        self.service.client = self

    def remove(self):
        self.service.remove()
        self.service = None
        self.namespace = None
        self.url = None
        del self

    def subscribe_for_variable(self, var_name, callback,signal=False):
        self.service.subscribe_for_variable(var_name, instance=0, callback=callback,signal=signal)

    def set_load_level_target(self,new_load_level_target=0):
        action = self.service.get_action('SetLoadLevelTarget')
        return action.call(NewLoadLevelTarget=new_load_level_target)

    def get_load_level_target(self):
        action = self.service.get_action('GetLoadLevelTarget')
        return action.call()

    def get_load_level_status(self):
        action = self.service.get_action('GetLoadLevelStatus')
        return action.call()
