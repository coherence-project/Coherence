# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Connection Manager service

from twisted.python import log
from twisted.web import resource, static, soap
from twisted.internet import defer

from elementtree.ElementTree import Element, SubElement, ElementTree, parse, tostring

from soap_service import UPnPPublisher
import action 
import variable

from event import EventSubscriptionServer

class scpdXML(static.Data):

    def __init__(self, server, control):
    
        root = Element('scpd')
        root.attrib['xmlns']='urn:schemas-upnp-org:service-1-0'
        e = SubElement(root, 'specVersion')
        SubElement( e, 'major').text = '1'
        SubElement( e, 'minor').text = '0'

        e = SubElement( root, 'actionList')
        for action in server._actions.values():
            s = SubElement( e, 'action')
            SubElement( s, 'name').text = action.get_name()
            al = SubElement( s, 'argumentList')
            for argument in action.get_arguments_list():
                a = SubElement( al, 'argument')
                SubElement( a, 'name').text = argument.get_name()
                SubElement( a, 'direction').text = argument.get_direction()
                SubElement( a, 'relatedStateVariable').text = argument.get_state_variable()

        e = SubElement( root, 'serviceStateTable')
        for var in server._variables.values():
            s = SubElement( e, 'stateVariable')
            s.attrib['sendEvents'] = var.send_events
            SubElement( s, 'name').text = var.name
            SubElement( s, 'dataType').text = var.data_type
            if len(var.allowed_values):
                v = SubElement( s, 'allowedValueList')
                for value in var.allowed_values:
                    SubElement( v, 'allowedValue').text = value

        self.xml = tostring( root, encoding='utf-8')
        static.Data.__init__(self, self.xml, 'text/xml')


class ConnectionManagerControl(UPnPPublisher):

    def __init__(self, server):
        self.variables = server.get_variables()
        self.actions = server.get_actions()
        
    def get_action_results(self, result, action):
        """ check for out arguments
            if yes: check if there are related ones to StateVariables with
                    A_ARG_TYPE_ prefix
                    if yes: call plugin method for this action
                            add return value to result dict
            if yes: add StateVariables without A_ARG_TYPE_ prefix to the result dict
        """
        print 'get_action_results', result
        print 'get_action_results', action
        r = result
        for argument in action.get_out_arguments():
            print 'get_state_variable_contents', argument.name
            if argument.name[0:11] != 'A_ARG_TYPE_':
                if action.get_callback() != None:
                    variable = self.variables[argument.get_state_variable()]
                    variable.value = r[argument.name];
                    print 'get_state_variable_contents', 'update', variable.name, variable.value
                else:
                    variable = self.variables[argument.get_state_variable()]
                    print 'get_state_variable_contents', variable.name, variable.value
                    r[argument.name] = variable.value
        return { '%sResponse'%action.name: r}
        
    def get_state_variable_contents(self, action):
        """ check for out arguments
            if yes: check if there are related ones to StateVariables with
                    A_ARG_TYPE_ prefix
                    if yes: call plugin method for this action
                            add return value to result dict
            if yes: add StateVariables without A_ARG_TYPE_ prefix to the result dict
        """
        r = {}
        for argument in action.get_out_arguments():
            print 'get_state_variable_contents', argument.name
            if argument.name[0:11] != 'A_ARG_TYPE_':
                variable = self.variables[argument.get_state_variable()]
                print 'get_state_variable_contents', variable.name, variable.value
                r[argument.name] = variable.value
        return r
                
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

    def soap_XXXGetProtocolInfo(self, *args, **kwargs):
        """Required: returns the protocol-related info that this ConnectionManager
           supports in its current state."""
        action = 'GetProtocolInfo'
        print action, __name__, kwargs
        
        def callit( r):
            print 'callit', r
            result = {}
            result.update(self.get_state_variable_contents(self.actions[action]))
            print 'callit', result
            return result
            
        # call plugin method for this action
        d = defer.maybeDeferred( callit, kwargs)
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
        return { 'GetCurrentConnectionIDsResponse': { 'ConnectionIDs': self.variables['CurrentConnectionIDs'] }}

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

        
class ConnectionManagerServer(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        
        self.type = 'urn:schemas-upnp-org:service:ConnectionManager:2'
        self.id = 'ConnectionManager'
        self.scpd_url = 'scpd.xml'
        self.control_url = 'control'
        self.subscription_url = 'subscribe'
        
        self._actions = {}
        self._variables = {}
        
        self.init_var_and_actions()

        self.connection_manager_control = ConnectionManagerControl(self)
        self.putChild(self.scpd_url, scpdXML(self, self.connection_manager_control))
        self.putChild(self.control_url, self.connection_manager_control)
        self.putChild(self.subscription_url, EventSubscriptionServer(self))
        
        self._variables['SourceProtocolInfo'].value = 'http-get:*:audio/mpeg:*'
        self._variables['SinkProtocolInfo'].value = ''
        self._variables['CurrentConnectionIDs'].value = '0'
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl
        
    def get_actions(self):
        return self._actions

    def get_variables(self):
        return self._variables

    def render(self,request):
        return '<html><p>root of the ConnectionManager</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)

    def init_var_and_actions(self):

        tree = parse('xml-service-descriptions/ConnectionManager2.xml')
        
        for action_node in tree.findall('.//action'):
            name = action_node.findtext('name')
            implementation = 'required'
            if action_node.find('Optional') != None:
                implementation = 'optional'
            arguments = []
            for argument in action_node.findall('.//argument'):
                arg_name = argument.findtext('name')
                arg_direction = argument.findtext('direction')
                arg_state_var = argument.findtext('relatedStateVariable')
                arguments.append(action.Argument(arg_name, arg_direction,
                                                 arg_state_var))
            self._actions[name] = action.Action(self, name, implementation, arguments)
            
        for var_node in tree.findall('.//stateVariable'):
            instance = 0
            name = var_node.findtext('name')
            implementation = 'required'
            if action_node.find('Optional') != None:
                implementation = 'optional'
            send_events = var_node.findtext('sendEventsAttribute')
            data_type = var_node.findtext('dataType')
            values = []
            for allowed in var_node.findall('.//allowedValue'):
                values.append(allowed.text)
            self._variables[name] = variable.StateVariable(self, name,
                                                           implementation,
                                                           0, send_events,
                                                           data_type, values)
