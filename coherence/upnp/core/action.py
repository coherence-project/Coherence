# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006,2007,2008,2009 Frank Scholz <coherence@beebits.net>

from twisted.python import failure
from twisted.python.util import OrderedDict

from coherence import log

class Argument:

    def __init__(self, name, direction, state_variable):
        self.name = name
        self.direction = direction
        self.state_variable = state_variable

    def get_name(self):
        return self.name

    def get_direction(self):
        return self.direction

    def get_state_variable(self):
        return self.state_variable

    def __repr__(self):
        return "Argument: %s, %s, %s" % (self.get_name(),
                                         self.get_direction(), self.get_state_variable())

    def as_tuples(self):
        r = []
        r.append(('Name',self.name))
        r.append(('Direction',self.direction))
        r.append(('Related State Variable',self.state_variable))
        return r

    def as_dict(self):
        return {'name':self.name,'direction':self.direction,'related_state_variable':self.state_variable}


class Action(log.Loggable):
    logCategory = 'action'

    def __init__(self, service, name, implementation, arguments_list):
        self.service = service
        self.name = name
        self.implementation = implementation
        self.arguments_list = arguments_list

    def _get_client(self):
        client = self.service._get_client( self.name)
        return client

    def get_name(self):
        return self.name

    def get_implementation(self):
        return self.implementation

    def get_arguments_list(self):
        return self.arguments_list

    def get_in_arguments(self):
        return [arg for arg in self.arguments_list if arg.get_direction() == 'in']

    def get_out_arguments(self):
        return [arg for arg in self.arguments_list if arg.get_direction() == 'out']

    def get_service(self):
        return self.service

    def set_callback(self, callback):
        self.callback = callback

    def get_callback(self):
        try:
            return self.callback
        except:
            return None

    def call(self, *args, **kwargs):
        self.info("calling %s", self.name)
        in_arguments = self.get_in_arguments()
        self.info("in arguments %s", [a.get_name() for a in in_arguments])
        instance_id = 0
        for arg_name, arg in kwargs.iteritems():
            l = [ a for a in in_arguments if arg_name == a.get_name()]
            if len(l) > 0:
                in_arguments.remove(l[0])
            else:
                self.error("argument %s not valid for action %s" % (arg_name,self.name))
                return
            if arg_name == 'InstanceID':
                instance_id = int(arg)
        if len(in_arguments) > 0:
            self.error("argument %s missing for action %s" % ([ a.get_name() for a in in_arguments],self.name))
            return

        action_name = self.name

        if(hasattr(self.service.device.client, 'overlay_actions') and
           self.service.device.client.overlay_actions.has_key(self.name)):
            self.info("we have an overlay method %r for action %r", self.service.device.client.overlay_actions[self.name], self.name)
            action_name, kwargs = self.service.device.client.overlay_actions[self.name](**kwargs)
            self.info("changing action to %r %r", action_name, kwargs)

        def got_error(failure):
            self.warning("error on %s request with %s %s" % (self.name,self.
                                                            service.service_type,
                                                            self.service.control_url))
            self.info(failure)
            return failure

        if hasattr(self.service.device.client, 'overlay_headers'):
            self.info("action call has headers %r", kwargs.has_key('headers'))
            if kwargs.has_key('headers'):
                kwargs['headers'].update(self.service.device.client.overlay_headers)
            else:
                kwargs['headers'] = self.service.device.client.overlay_headers
            self.info("action call with new/updated headers %r", kwargs['headers'])

        client = self._get_client()

        ordered_arguments = OrderedDict()
        for argument in self.get_in_arguments():
            ordered_arguments[argument.name] = kwargs[argument.name]

        d = client.callRemote(action_name, ordered_arguments)
        d.addCallback(self.got_results, instance_id=instance_id, name=action_name)
        d.addErrback(got_error)
        return d

    def got_results( self, results, instance_id, name):
        instance_id = int(instance_id)
        out_arguments = self.get_out_arguments()
        self.info( "call %s (instance %d) returns %d arguments: %r" % (name,
                                                                    instance_id,
                                                                    len(out_arguments),
                                                                    results))

        # XXX A_ARG_TYPE_ arguments probably don't need a variable update
        #if len(out_arguments) == 1:
        #    self.service.get_state_variable(out_arguments[0].get_state_variable(), instance_id).update(results)
        #elif len(out_arguments) > 1:

        if len(out_arguments) > 0:
            for arg_name, value in results.items():
                state_variable_name = [a.get_state_variable() for a in out_arguments if a.get_name() == arg_name]
                self.service.get_state_variable(state_variable_name[0], instance_id).update(value)

        return results

    def __repr__(self):
        return "Action: %s [%s], (%s args)" % (self.get_name(), self.get_implementation(),
                                         len(self.get_arguments_list()))

    def as_tuples(self):
        r = []
        r.append(('Name',self.get_name()))
        r.append(("Number of 'in' arguments",len(self.get_in_arguments())))
        r.append(("Number of 'out' arguments",len(self.get_out_arguments())))
        return r

    def as_dict(self):
        return {'name': self.get_name(),'arguments':[a.as_dict() for a in self.arguments_list]}
