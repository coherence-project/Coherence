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

from soap_proxy import SOAPProxy

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

class Action:

    def __init__(self, service, name, arguments_list):
        self.service = service
        self.name = name
        self.arguments_list = arguments_list
        
    def _get_client(self):
        url = self.service.get_control_url()
        namespace = self.service.get_type()
        action = "%s#%s" % (namespace, self.name)
        client = SOAPProxy( url, namespace=("u",namespace), soapaction=action)
        return client


    def get_name(self):
        return self.name

    def get_arguments_list(self):
        return self.arguments_list
        
    def get_in_arguments(self):
        return [arg for arg in self.arguments_list if arg.get_direction() == 'in']
        
    def get_out_arguments(self):
        return [arg for arg in self.arguments_list if arg.get_direction() == 'out']
            
    def get_service(self):
        return self.service

    def call(self, *args, **kwargs):
        #print "calling", self.name
        in_arguments = self.get_in_arguments()
        #print "in arguments", [a.get_name() for a in in_arguments]
        instance_id = 0
        for arg_name, arg in kwargs.iteritems():
            l = [ a for a in in_arguments if arg_name == a.get_name()] 
            if len(l) > 0:
                in_arguments.remove(l[0])
            else:
                print "argument %s not valid for action %s" % (arg_name,self.name)
                return
            if arg_name == 'InstanceID':
                instance_id = arg
        if len(in_arguments) > 0:
            print "argument %s missing for action %s" % ([ a.get_name() for a in in_arguments],self.name)
            return
        client = self._get_client()
        d = client.callRemote( self.name,
                                    **kwargs)
        d.addCallback( self.got_results, instance_id=instance_id)
        return d

    def got_results( self, results, instance_id):
        #print "call %s (instance %d) returns: %r" % (self.name, instance_id, results)
        out_arguments = self.get_out_arguments()
        if len(out_arguments) == 0:
            pass
        elif len(out_arguments) == 1:
            self.service.get_state_variable(out_arguments[0].get_state_variable(), instance_id).update(results)
        else:
            for arg_name, value in results._asdict().items():
                state_variable_name = [a.get_state_variable() for a in out_arguments if a.get_name() == arg_name]
                self.service.get_state_variable(state_variable_name[0], instance_id).update(value)
        
    def __repr__(self):
        return "Action: %s (%s args)" % (self.get_name(),
                                         len(self.get_arguments_list()))
