# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2005, Tim Potter <tpot@samba.org>
# Copyright 2006, Frank Scholz <coherence@beebits.net>

# Connection Manager service

from twisted.python import log
from twisted.web import resource, static, soap

from twisted.python import reflect

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
        for var in server._variables[0].values():
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

    def _listFunctions(self):
        """Return a list of the names of all service methods."""
        return reflect.prefixedMethodNames(self.__class__, 'soap_')
        
    def soap_GetProtocolInfo(self, *args, **kwargs):
        """Required: returns the protocol-related info that this ConnectionManager
           supports in its current state."""
        
        print 'GetProtocolInfo()', kwargs
        return { 'GetProtocolInfoResponse': { 'Source': '', 'Sink': '' }}


class ConnectionManagerServer(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        
        self.type = 'urn:schemas-upnp-org:service:ConnectionManager:2'
        self.id = 'ConnectionManager'
        self.scpd_url = 'scpd.xml'
        self.control_url = 'control'
        self.subscription_url = 'subscribe'
        
        self._actions = {}
        self._variables = { 0: {}}
        
        self.init_var_and_actions()

        self.connection_manager_control = ConnectionManagerControl()
        self.putChild(self.scpd_url, scpdXML(self, self.connection_manager_control))
        self.putChild(self.control_url, self.connection_manager_control)
        self.putChild(self.subscription_url, EventSubscriptionServer(self))
        
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the ConnectionManager</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)

    def old_init_var_and_actions(self):
        instance = 0
        
        def init_var(self, name, implementation, instance, send_events, data_type, values):
            events = ['no','yes']
            self._variables.get(instance)[name] = \
                            variable.StateVariable(self, name,
                                                    required,
                                                    instance,
                                                    send_events,
                                                    data_type, values)

        init_var(self, 'SourceProtocolInfo', 'required', instance, 'yes', 'string', [])
        init_var(self, 'SinkProtocolInfo', 'required', instance, 'yes', 'string', [])
        init_var(self, 'CurrentConnectionIDs', 'required', instance, 'yes', 'string', [])
        init_var(self, 'A_ARG_TYPE_ConnectionStatus', 'required', instance, 'no', 'string',
                        ['OK', 'ContentFormatMismatch','InsufficientBandwidth','UnreliableChannel','Unknown'])
        init_var(self, 'A_ARG_TYPE_ConnectionManager', 'required', instance, 'no', 'string', [])
        init_var(self, 'A_ARG_TYPE_Direction', 'required', instance, 'no', 'string',
                        ['Input', 'Output'])
        init_var(self, 'A_ARG_TYPE_ProtocolInfo', 'required', instance, 'no', 'string', [])
        init_var(self, 'A_ARG_TYPE_ConnectionID', 'required', instance, 'no', 'i4', [])
        init_var(self, 'A_ARG_TYPE_AVTransportID', 'required', instance, 'no', 'i4', [])
        init_var(self, 'A_ARG_TYPE_RcsID', 'required', instance, 'no', 'i4', [])
        
        def init_action(self, name, implementation, arguments):
            self._actions[name] = action.Action(self, name, implementation, arguments)

        arguments = []
        arguments.append(action.Argument('Source','out','SourceProtocolInfo'))
        arguments.append(action.Argument('Sink','out','SinkProtocolInfo'))
        init_action(self, 'GetProtocolInfo', 'required', arguments)

        arguments = []
        arguments.append(action.Argument('RemoteProtocolInfo','in','A_ARG_TYPE_ProtocolInfo'))
        arguments.append(action.Argument('PeerConnectionManager','in','A_ARG_TYPE_ConnectionManager'))
        arguments.append(action.Argument('PeerConnectionID','in','A_ARG_TYPE_ConnectionID'))
        arguments.append(action.Argument('Direction','in','A_ARG_TYPE_Direction'))
        arguments.append(action.Argument('ConnectionID','out','A_ARG_TYPE_ConnectionID'))
        arguments.append(action.Argument('AVTransportID','out','A_ARG_TYPE_AVTransportID'))
        arguments.append(action.Argument('RcsID','out','A_ARG_TYPE_RcsID'))
        init_action(self, 'PrepareForConnection', 'optional', arguments)

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
            self._variables.get(instance)[name] = variable.StateVariable(self, name,
                                                           implementation,
                                                           instance, send_events,
                                                           data_type, values)
