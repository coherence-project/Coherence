# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import task

import cElementTree
import time
import urllib2
import action
import event
import variable
import utils

from soap_proxy import SOAPProxy

from event import EventSubscriptionServer
from elementtree.ElementTree import Element, SubElement, ElementTree, parse, tostring

from twisted.web import static

import louie

global subscribers
subscribers = {}

def subscribe(service):
    subscribers[service.get_sid()] = service

def unsubscribe(service):
    if subscribers.has_key(service.get_sid()):
        del subscribers[service.get_sid()]
        
class Service:

    def __init__(self, service_type, service_id, location, control_url,
                 event_sub_url, presentation_url, scpd_url, device):
        if not control_url.startswith('/'):
            control_url = "/%s" % control_url
        if not event_sub_url.startswith('/'):
            event_sub_url = "/%s" % event_sub_url
        if presentation_url and not presentation_url.startswith('/'):
            presentation_url = "/%s" % presentation_url
        if not scpd_url.startswith('/'):
            scpd_url = "/%s" % scpd_url
            
        self.service_type = service_type
        self.detection_completed = False
        self.id = service_id
        self.control_url = control_url
        self.event_sub_url = event_sub_url
        self.presentation_url = presentation_url
        self.scpd_url = scpd_url
        self.device = device
        self._actions = {}
        self._variables = { 0: {}}
        self._var_subscribers = {}
        self.subscription_id = ""
        self.timeout = 0
        
        parsed = urllib2.urlparse.urlparse(location)
        self.url_base = "%s://%s" % (parsed[0], parsed[1])

        self.parse_actions()

    def _get_client(self, name):
        url = self.get_control_url()
        namespace = self.get_type()
        action = "%s#%s" % (namespace, name)
        client = SOAPProxy( url, namespace=("u",namespace), soapaction=action)
        return client

    def get_device(self):
        return self.device

    def get_type(self):
        return self.service_type

    def set_timeout(self, timeout):
        self.timeout = timeout

    def get_timeout(self):
        return self.timeout
        
    def get_id(self):
        return self.id

    def get_sid(self):
        return self.subscription_id

    def set_sid(self, sid):
        self.subscription_id = sid
        if sid:
            subscribe(self)
            
    def get_actions(self):
        return self._actions
        
    def get_action( self, name):
        return self.get_actions()[name]

    def get_state_variables(self, instance):
        return self._variables.get(instance)

    def get_state_variable(self, name, instance=0):
        instance = int(instance)
        return self._variables.get(instance).get(name)

    def get_control_url(self):
        return self.url_base + self.control_url

    def get_event_sub_url(self):
        #return self.url_base + self.event_sub_url
        return self.event_sub_url

    def get_presentation_url(self):
        return self.url_base + self.presentation_url

    def get_scpd_url(self):
        return self.url_base + self.scpd_url

    def get_base_url(self):
        return self.url_base
    
    def subscribe(self):
        event.subscribe(self)
        global subscribers
        subscribers[self.get_sid()] = self
        
    def unsubscribe(self):
        event.unsubscribe(self)

    def subscribe_for_variable(self, var_name, instance=0, callback=None):
        variable = self.get_state_variable(var_name)
        if variable:
            variable.subscribe(callback)
            
    def renew_subscription(self):
        event.subscribe(self)

    
    
    def parse_actions(self):

        from twisted.web.client import getPage
        
        def gotPage(  x):
            #print "gotPage"
            #print x
            tree = utils.parse_xml(x, 'utf-8').getroot()
            ns = "urn:schemas-upnp-org:service-1-0"
            
            for action_node in tree.findall('.//{%s}action' % ns):
                name = action_node.findtext('{%s}name' % ns)
                arguments = []
                for argument in action_node.findall('.//{%s}argument' % ns):
                    arg_name = argument.findtext('{%s}name' % ns)
                    arg_direction = argument.findtext('{%s}direction' % ns)
                    arg_state_var = argument.findtext('{%s}relatedStateVariable' % ns)
                    arguments.append(action.Argument(arg_name, arg_direction,
                                                     arg_state_var))
                self._actions[name] = action.Action(self, name, 'n/a', arguments)

            for var_node in tree.findall('.//{%s}stateVariable' % ns):
                send_events = var_node.attrib["sendEvents"]
                name = var_node.findtext('{%s}name' % ns)
                data_type = var_node.findtext('{%s}dataType' % ns)
                values = []
                for allowed in var_node.findall('.//{%s}allowedValue' % ns):
                    values.append(allowed.text)
                instance = 0
                self._variables.get(instance)[name] = variable.StateVariable(self, name,
                                                               'n/a',
                                                               instance, send_events,
                                                               data_type, values)
            #print 'service parse:', self, self.device
            self.detection_completed = True

            louie.send('Coherence.UPnP.Service.detection_completed', self.device, device=self.device)

        #print 'getPage', self.get_scpd_url()
        getPage(self.get_scpd_url()).addCallback( gotPage)
            
moderated_variables = \
        {'urn:schemas-upnp-org:service:AVTransport:2':
            ['LastChange'],
         'urn:schemas-upnp-org:service:ContentDirectory:2':
            ['SystemUpdateID', 'ContainerUpdateIDs'],
         'urn:schemas-upnp-org:service:RenderingControl:2':
            ['LastChange'],
         'urn:schemas-upnp-org:service:ScheduledRecording:1':
            ['LastChange'],
        }

class Server:

    def __init__(self, id):
        self.id = id
        self.service_type = 'urn:schemas-upnp-org:service:%s:2' % id
        self.scpd_url = 'scpd.xml'
        self.control_url = 'control'
        self.subscription_url = 'subscribe'
        
        self._actions = {}
        self._variables = {0: {}}

        self._subscribers = {}
        
        self.init_var_and_actions()
        self.putChild(self.subscription_url, EventSubscriptionServer(self))
        
        self.check_subscribers_loop = task.LoopingCall(self.check_subscribers)
        self.check_subscribers_loop.start(120.0)
        
        if moderated_variables.has_key(self.service_type):
            self.check_moderated_loop = task.LoopingCall(self.check_moderated_variables)
            self.check_moderated_loop.start(0.5)
            

        #simulation_loop = task.LoopingCall(self.simulate_notification)
        #simulation_loop.start(60.0)

    def get_actions(self):
        return self._actions

    def get_variables(self):
        return self._variables

    def get_subscribers(self):
        return self._subscribers

    def get_id(self):
        return self.id
        
    def get_type(self):
        return self.service_type
        
    def set_variable(self, instance, variable_name, value):
        try:
            self._variables[instance][variable_name].value = value
            if len(self._subscribers) > 0:
                xml = self.build_event(instance, variable_name, value)
                for s in self._subscribers.values():
                    event.send_notification(s, xml)
        except:
            pass

    def build_event(self, instance, variable_name, value):
        root = Element('propertyset')
        root.attrib['xmlns']='urn:schemas-upnp-org:event-1-0'
        e = SubElement( root, 'property')
        s = SubElement( e, variable_name).text = str(value)
        return tostring( root, encoding='utf-8')
        
    def propagate_notification(self, notify):
        if len(self._subscribers) <= 0:
            return
            
        root = Element('propertyset')
        root.attrib['xmlns']='urn:schemas-upnp-org:event-1-0'

        if isinstance( notify, Variable):
            notify = [notify,]

        for n in notify:
            e = SubElement( root, 'property')
            SubElement( e, n.name).text = str(n.value)
            
        xml = tostring( root, encoding='utf-8')
        for s in self._subscribers.values():
            event.send_notification(s, xml)
        
    def check_subscribers(self):
        for s in self._subscribers.values():
            timeout = 86400
            print s
            if s['timeout'].startswith('Second-'):
                timeout = int(s['timeout'][len('Second-'):])
            if time.time() > s['created'] + timeout:
                del s

    def check_moderated_variables(self):
        if len(self._subscribers) <= 0:
            return
        print "check_moderated"
        variables = mv[self.get_type()]
        notify = []
        for v in variables:
            if self._variables[0][v].update == True:
                self._variables[0][v].update = False
                notify.append(self._variables[0][v])
        self.propagate_notification(notify)

    def is_variable_moderated(self, name):
        try:
            variables = mv[self.get_type()]
            if name in variables:
                return True
        except:
            pass
        return False
        
    def simulate_notification(self):
        print "simulate_notification for", self.id
        self.set_variable(0, 'CurrentConnectionIDs', '0')
        
    def init_var_and_actions(self):
        tree = parse('xml-service-descriptions/%s2.xml' % self.id)
        
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


