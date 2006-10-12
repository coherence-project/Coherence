# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php
 	
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

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
        out_arguments = self.get_out_arguments()
        # print "call %s (instance %d) returns %d arguments: %r" % (self.name,
        #                                                            instance_id,
        #                                                            len(out_arguments),
        #                                                            results)
        #
        #
        # XXX A_ARG_TYPE_ arguments probably don't need a variable update
        if len(out_arguments) == 1:
            self.service.get_state_variable(out_arguments[0].get_state_variable(), instance_id).update(results)
        elif len(out_arguments) > 1:
            for arg_name, value in results._asdict().items():
                state_variable_name = [a.get_state_variable() for a in out_arguments if a.get_name() == arg_name]
                self.service.get_state_variable(state_variable_name[0], instance_id).update(value)
                
        return results
        
    def __repr__(self):
        return "Action: %s [%s], (%s args)" % (self.get_name(), self.get_implementation(),
                                         len(self.get_arguments_list()))
