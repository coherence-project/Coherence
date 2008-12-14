# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

import coherence.extern.louie as louie

from coherence.upnp.core.utils import generalise_boolean

from coherence.backend import Backend

class SimpleLight(Backend):

    """ this is a backend for a simple light
        that only can be switched on or off

        therefore we need to inform Coherence
        about the state, and a method to change it

        everything else is done by Coherence
    """

    implements = ['BinaryLight']
    logCategory = 'simple_light'

    def __init__(self, server, **kwargs):
        self.name = kwargs.get('name','SimpleLight')
        self.server = server
        self.state = 0 # we start switched off
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def upnp_init(self):
        if self.server:
            self.server.switch_power_server.set_variable(0, 'Target', self.state)
            self.server.switch_power_server.set_variable(0, 'Status', self.state)

    def upnp_SetTarget(self,**kwargs):
        self.info('upnp_SetTarget %r', kwargs)
        self.state = int(generalise_boolean(kwargs['NewTargetValue']))
        if self.server:
            self.server.switch_power_server.set_variable(0, 'Target', self.state)
            self.server.switch_power_server.set_variable(0, 'Status', self.state)
        print "we have been switched to state", self.state
        return {}


class BetterLight(Backend):

    implements = ['DimmableLight']
    logCategory = 'better_light'

    def __init__(self, server, **kwargs):
        self.name = kwargs.get('name','BetterLight')
        self.server = server
        self.state = 0 # we start switched off
        self.loadlevel = 50 # we start with 50% brightness

        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def upnp_init(self):
        if self.server:
            self.server.switch_power_server.set_variable(0, 'Target', self.state)
            self.server.switch_power_server.set_variable(0, 'Status', self.state)
            self.server.dimming_server.set_variable(0, 'LoadLevelTarget', self.loadlevel)
            self.server.dimming_server.set_variable(0, 'LoadLevelStatus', self.loadlevel)

    def upnp_SetTarget(self,**kwargs):
        self.info('upnp_SetTarget %r', kwargs)
        self.state = int(generalise_boolean(kwargs['NewTargetValue']))
        if self.server:
            self.server.switch_power_server.set_variable(0, 'Target', self.state)
            self.server.switch_power_server.set_variable(0, 'Status', self.state)
        print "we have been switched to state", self.state
        return {}

    def upnp_SetLoadLevelTarget(self,**kwargs):
        self.info('SetLoadLevelTarget %r', kwargs)
        self.loadlevel = int(kwargs['NewLoadlevelTarget'])
        self.loadlevel = min(max(0,self.loadlevel),100)
        if self.server:
            self.server.dimming_server.set_variable(0, 'LoadLevelTarget', self.loadlevel)
            self.server.dimming_server.set_variable(0, 'LoadLevelStatus', self.loadlevel)
        print "we have been dimmed to level", self.loadlevel
        return {}


if __name__ == '__main__':

    from coherence.base import Coherence

    def main():
        config = {}
        config['logmode'] = 'warning'
        c = Coherence(config)
        f = c.add_plugin('SimpleLight')
        f = c.add_plugin('BetterLight')

    from twisted.internet import reactor
    reactor.callWhenRunning(main)
    reactor.run()
