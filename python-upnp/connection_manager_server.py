# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Connection Manager service

from twisted.python import log
from twisted.web import resource, static, soap
from twisted.internet import defer

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from soap_service import UPnPPublisher

import service

class ConnectionManagerControl(UPnPPublisher):

    def __init__(self, server):
        self.server = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()
        
    def get_action_results(self, result, action):
        """ check for out arguments
            if yes: check if there are related ones to StateVariables with
                    non A_ARG_TYPE_ prefix
                    if yes: check if there is a call plugin method for this action
                            if yes: update StateVariable values with call result
                            if no:  get StateVariable values and
                                    add them to result dict
        """
        print 'get_action_results', result
        print 'get_action_results', action
        r = result
        notify = []
        for argument in action.get_out_arguments():
            print 'get_state_variable_contents', argument.name
            if argument.name[0:11] != 'A_ARG_TYPE_':
                if action.get_callback() != None:
                    variable = self.variables[0][argument.get_state_variable()]
                    variable.update(r[argument.name])
                    #print 'update state variable contents', variable.name, variable.value
                    #self.server.set_variable( 0, argument.get_state_variable(), r[argument.name])
                    notify.append(variable)
                else:
                    variable = self.variables[0][argument.get_state_variable()]
                    print 'get state variable contents', variable.name, variable.value
                    r[argument.name] = variable.value
            self.server.propagate_notification(notify)
        return { '%sResponse'%action.name: r}
        
    def soap__generic(self, *args, **kwargs):
        """Required: returns the protocol-related info that this ConnectionManager
           supports in its current state."""
        action = kwargs['soap_methodName']
        #print action, __name__, kwargs
        
        def callit( *args, **kwargs):
            print 'callit args', args
            print 'callit kwargs', kwargs
            result = {}
            print 'callit before callback', result
            callback = self.actions[action].get_callback()
            if callback != None:
                result.update( callback( **kwargs))
            print 'callit after callback', result
            return result
            
        # call plugin method for this action
        d = defer.maybeDeferred( callit, **kwargs)
        d.addCallback( self.get_action_results, self.actions[action])
        return d

    def soap_PrepareForConnection(self, *args, **kwargs):
        """Optional: this action is used to allow the device to prepare itself to connect
           to the network for the purposes of sending or receiving media content."""
        
        print 'PrepareForConnection()', kwargs
        return { 'PrepareForConnectionResponse': { 'ConnectionID': 0,
                                                    'AVTransportID': 0,
                                                    'RcsID': 0}}

    def soap_ConnectionComplete(self, *args, **kwargs):
        """Optional: this action removes the connection referenced by argument
           ConnectionID by modifying state variable CurrentConnectionIDs, and
           (if necessary) performs any protocol-specific cleanup actions such
           as releasing network resources."""
        
        print 'ConnectionComplete()', kwargs
        return { 'ConnectionCompleteResponse': {}}

    def soap_GetCurrentConnectionIDs(self, *args, **kwargs):
        """Required: this action returns a Comma-Separated Value list of ConnectionIDs
           of currently ongoing Connections. A ConnectionID can be used to manually
           terminate a Connection via action ConnectionComplete(), or to retrieve
           additional information about the ongoing Connection via action
           GetCurrentConnectionInfo(). If a device does not implement PrepareForConnection(),
           this action MUST return the single value '0'."""
        
        print 'GetCurrentConnectionIDs()', kwargs
        return { 'GetCurrentConnectionIDsResponse': { 'ConnectionIDs': self.variables[0]['CurrentConnectionIDs'] }}

    def soap_GetCurrentConnectionInfo(self, *args, **kwargs):
        """Required: this action returns associated information of the connection
           referred to by the ConnectionID input argument. The AVTransportID argument
           MAY be the reserved value -1 and the PeerConnectionManager argument MAY
           be the empty string in cases where the connection has been setup completely
           out of band, not involving a PrepareForConnection() action."""
        
        print 'GetCurrentConnectionInfo()', kwargs
        return { 'GetCurrentConnectionInfoResponse': { 'RcsID': -1,
                                                       'AVTransportID': -1,
                                                       'ProtocolInfo': '',
                                                       'PeerConnectionManager': '',
                                                       'PeerConnectionID': -1,
                                                       'Direction': 'Output',
                                                       'Status': 'OK',
                                                       }}

        
class ConnectionManagerServer(service.Server, resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        service.Server.__init__(self, 'ConnectionManager')

        self.connection_manager_control = ConnectionManagerControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.connection_manager_control))
        self.putChild(self.control_url, self.connection_manager_control)
        
        self.set_variable(0, 'SourceProtocolInfo', 'http-get:*:audio/mpeg:*')
        self.set_variable(0, 'SinkProtocolInfo', '')
        self.set_variable(0, 'CurrentConnectionIDs', '0')
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl
        
    def render(self,request):
        return '<html><p>root of the ConnectionManager</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)

