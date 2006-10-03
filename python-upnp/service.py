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

import cElementTree
import urllib2
import action
import event
import variable
import utils

from soap_proxy import SOAPProxy

global subscribers
subscribers = {}

def subscribe(service):
    subscribers[service.get_sid()] = service

def unsubscribe(service):
    if subscribers.has_key(service.get_sid()):
        del subscribers[service.get_sid()]
        
class ServiceClient:
    
    def _get_client(self, action):
        action = "%s#%s" % (self.namespace, action)
        client = SOAPProxy(self.url, namespace=("u",self.namespace),
                           soapaction=action)
        return client

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

        handle = utils.url_fetch(self.get_scpd_url())
        if not handle:
            return

        tree = cElementTree.ElementTree(file=handle).getroot()

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
            self._actions[name] = action.Action(self, name, arguments)

        for var_node in tree.findall('.//{%s}stateVariable' % ns):
            events = ["no","yes"]
            send_events = events.index(var_node.attrib["sendEvents"])
            name = var_node.findtext('{%s}name' % ns)
            data_type = var_node.findtext('{%s}dataType' % ns)
            values = []
            for allowed in var_node.findall('.//{%s}allowedValue' % ns):
                values.append(allowed.text)
            instance = 0
            self._variables.get(instance)[name] = variable.StateVariable(self, name, instance, send_events,
                                                           data_type, values)
            
            
