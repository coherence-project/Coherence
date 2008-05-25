# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

class SwitchPowerClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.subscribe()
        self.service.client = self

    def remove(self):
        if self.service != None:
            self.service.remove()
        self.service = None
        self.namespace = None
        self.url = None
        del self

    def subscribe_for_variable(self, var_name, callback,signal=False):
        self.service.subscribe_for_variable(var_name, instance=0, callback=callback,signal=signal)

    def set_target(self,new_target_value=0):
        action = self.service.get_action('SetTarget')
        return action.call(NewTargetValue=new_target_value)

    def get_target(self):
        action = self.service.get_action('GetTarget')
        return action.call()

    def get_status(self):
        action = self.service.get_action('GetStatus')
        return action.call()