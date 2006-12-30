# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import cElementTree
import time
import urllib2
from coherence.upnp.core import action
from coherence.upnp.core import event
from coherence.upnp.core import variable

from coherence.upnp.core import utils
from coherence.upnp.core.soap_proxy import SOAPProxy
from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core.event import EventSubscriptionServer

from elementtree.ElementTree import Element, SubElement, ElementTree, parse, tostring

from twisted.web import static
from twisted.internet import defer
from twisted.python import failure, util
from twisted.internet import task

import louie

from coherence.extern.logger import Logger
log = Logger('Service')

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
        
        def gotPage(x):
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
            
        def gotError(failure, url):
            print "error requesting", url
            print failure
            
        #print 'getPage', self.get_scpd_url()
        getPage(self.get_scpd_url()).addCallbacks(gotPage, gotError, None, None, [self.get_scpd_url()], None)
            
moderated_variables = \
        {'urn:schemas-upnp-org:service:AVTransport:2':
            ['LastChange'],
         'urn:schemas-upnp-org:service:AVTransport:1':
            ['LastChange'],
         'urn:schemas-upnp-org:service:ContentDirectory:2':
            ['SystemUpdateID', 'ContainerUpdateIDs'],
         'urn:schemas-upnp-org:service:ContentDirectory:1':
            ['SystemUpdateID', 'ContainerUpdateIDs'],
         'urn:schemas-upnp-org:service:RenderingControl:2':
            ['LastChange'],
         'urn:schemas-upnp-org:service:RenderingControl:1':
            ['LastChange'],
         'urn:schemas-upnp-org:service:ScheduledRecording:1':
            ['LastChange'],
        }

class ServiceServer:

    def __init__(self, id, version, backend):
        self.id = id
        self.version = version
        self.backend = backend
        if getattr(self, "namespace", None) == None:
            self.namespace = 'schemas-upnp-org'
        self.service_type = 'urn:%s:service:%s:%d' % (self.namespace, id, self.version)
        self.scpd_url = 'scpd.xml'
        self.control_url = 'control'
        self.subscription_url = 'subscribe'
        self.event_metadata = ''
        if id == 'AVTransport':
            self.event_metadata = 'urn:schemas-upnp-org:metadata-1-0/AVT/'
        if id == 'RenderingControl':
            self.event_metadata = 'urn:schemas-upnp-org:metadata-1-0/RCS/'
        if id == 'ScheduledRecording':
            self.event_metadata = 'urn:schemas-upnp-org:av:srs-event'
            
        self._actions = {}
        self._variables = {0: {}}
        self._subscribers = {}
        
        self.last_change = None
        self.init_var_and_actions()

        try:
            if 'LastChange' in moderated_variables[self.service_type]:
                self.last_change = self._variables[0]['LastChange']
        except:
            pass

        self.putChild(self.subscription_url, EventSubscriptionServer(self))
        
        self.check_subscribers_loop = task.LoopingCall(self.check_subscribers)
        self.check_subscribers_loop.start(120.0, now=False)
        
        if moderated_variables.has_key(self.service_type):
            self.check_moderated_loop = task.LoopingCall(self.check_moderated_variables)
            #self.check_moderated_loop.start(5.0, now=False)
            self.check_moderated_loop.start(0.5, now=False)

        #simulation_loop = task.LoopingCall(self.simulate_notification)
        #simulation_loop.start(60.0, now=False)

    def get_action(self, action_name):
        return self._actions[action_name]

    def get_actions(self):
        return self._actions

    def get_variables(self):
        return self._variables

    def get_subscribers(self):
        return self._subscribers

    def new_subscriber(self, subscriber):
        instance = 0
        notify = [v for v in self._variables[instance].values() if v.send_events == True]
        log.info("new_subscriber", subscriber, notify)
        if len(notify) <= 0:
            return
        
        root = Element('propertyset')
        root.attrib['xmlns']='urn:schemas-upnp-org:event-1-0'

        for n in notify:
            e = SubElement( root, 'property')
            if n.name == 'LastChange':
                SubElement( e, n.name).text = self.build_last_change_event()
            else:
                SubElement( e, n.name).text = str(n.value)
            
        xml = tostring( root, encoding='utf-8')
        event.send_notification(subscriber, xml)
        self._subscribers[subscriber['sid']] = subscriber
        
    def get_id(self):
        return self.id
        
    def get_type(self):
        return self.service_type
        
    def set_variable(self, instance, variable_name, value):
        try:
            variable = self._variables[instance][variable_name]
            variable.update(value)
            if(variable.send_events == True and
                variable.moderated == False and
                len(self._subscribers) > 0):
                xml = self.build_single_notification(instance, variable_name, variable.value)
                for s in self._subscribers.values():
                    event.send_notification(s, xml)
        except:
            pass

    def build_single_notification(self, instance, variable_name, value):
        root = Element('propertyset')
        root.attrib['xmlns']='urn:schemas-upnp-org:event-1-0'
        e = SubElement( root, 'property')
        s = SubElement( e, variable_name).text = str(value)
        return tostring( root, encoding='utf-8')
        
    def build_last_change_event(self, instance=0):
        root = Element('Event')
        root.attrib['xmlns']=self.event_metadata
        e = SubElement( root, 'InstanceID')
        e.attrib['val']=str(instance)
        for variable in self._variables[instance].values():
            if( variable.name != 'LastChange' and
                variable.name[0:11] != 'A_ARG_TYPE_'):
                s = SubElement( e, variable.name)
                s.attrib['val'] = str(variable.value)
        return tostring( root, encoding='utf-8')
        
    def propagate_notification(self, notify):
        #print "propagate_notification", notify
        if len(self._subscribers) <= 0:
            return
        if len(notify) <= 0:
            return
            
        root = Element('propertyset')
        root.attrib['xmlns']='urn:schemas-upnp-org:event-1-0'

        if isinstance( notify, variable.StateVariable):
            notify = [notify,]

        for n in notify:
            e = SubElement( root, 'property')
            if n.name == 'LastChange':
                SubElement( e, n.name).text = self.build_last_change_event()
            else:
                SubElement( e, n.name).text = str(n.value)
            
        xml = tostring( root, encoding='utf-8')
        #print "propagate_notification", xml
        for s in self._subscribers.values():
            event.send_notification(s, xml)
        
    def check_subscribers(self):
        for s in self._subscribers.values():
            timeout = 86400
            #print s
            if s['timeout'].startswith('Second-'):
                timeout = int(s['timeout'][len('Second-'):])
            if time.time() > s['created'] + timeout:
                del s

    def check_moderated_variables(self):
        #print "check_moderated for %s" % self.id
        #print self._subscribers
        if len(self._subscribers) <= 0:
            return
        variables = moderated_variables[self.get_type()]
        #print variables
        notify = []
        for v in variables:
            #print self._variables[0][v].name, self._variables[0][v].updated
            if self._variables[0][v].updated == True:
                self._variables[0][v].updated = False
                notify.append(self._variables[0][v])
        self.propagate_notification(notify)

    def is_variable_moderated(self, name):
        try:
            variables = moderated_variables[self.get_type()]
            if name in variables:
                return True
        except:
            pass
        return False
        
    def simulate_notification(self):
        print "simulate_notification for", self.id
        self.set_variable(0, 'CurrentConnectionIDs', '0')
        
    def init_var_and_actions(self):
        desc_file = util.sibpath(__file__, 'xml-service-descriptions/%s%d.xml' % (self.id, self.version))
        tree = parse(desc_file)
        
        for action_node in tree.findall('.//action'):
            name = action_node.findtext('name')
            implementation = 'required'
            if action_node.find('Optional') != None:
                implementation = 'optional'
            arguments = []
            needs_callback = False
            for argument in action_node.findall('.//argument'):
                arg_name = argument.findtext('name')
                arg_direction = argument.findtext('direction')
                arg_state_var = argument.findtext('relatedStateVariable')
                arguments.append(action.Argument(arg_name, arg_direction,
                                                 arg_state_var))
                if( arg_state_var[0:11] == 'A_ARG_TYPE_' and
                    arg_direction == 'out'):
                    needs_callback = True
                #print arg_name, arg_direction, needs_callback
                    
            """ check for action in backend """
            callback = getattr(self.backend, "upnp_%s" % name, None)
            
            if callback == None:
                """ check for action in ServiceServer """
                callback = getattr(self, "upnp_%s" % name, None)
            
            if( needs_callback == True and
                callback == None):
                """ we have one or more 'A_ARG_TYPE_' variables
                    issue a warning for now
                """
                if implementation == 'optional':
                    log.warning('%s has a missing callback for %s action %s, action disabled' % (self.id,implementation,name))
                    continue
                else:
                    log.warning('%s has a missing callback for %s action %s, service disabled' % (self.id,implementation,name))
                    raise LookupError,"missing callback"

            new_action = action.Action(self, name, implementation, arguments)
            self._actions[name] = new_action
            if callback != None:
                new_action.set_callback(callback)
                log.info('Add callback %s for %s/%s' % (callback, self.id, name))
                    
 
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
            default_value = var_node.findtext('defaultValue')
            if default_value:
                self._variables.get(instance)[name].update(default_value)
            allowed_value_list = var_node.find('allowedValueList')
            if allowed_value_list:
                vendor_values = allowed_value_list.attrib.get(
                                    '{urn:schemas-beebits-org:service-1-0}X_withVendorDefines',
                                    False)
                self._variables.get(instance)[name].has_vendor_values = vendor_values

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
            if var.send_events == True:
                s.attrib['sendEvents'] = 'yes'
            else:
                s.attrib['sendEvents'] = 'no'
            SubElement( s, 'name').text = var.name
            SubElement( s, 'dataType').text = var.data_type
            #if(not var.has_vendor_values and len(var.allowed_values)):
            if len(var.allowed_values):
                v = SubElement( s, 'allowedValueList')
                for value in var.allowed_values:
                    SubElement( v, 'allowedValue').text = value

        self.xml = tostring( root, encoding='utf-8')
        static.Data.__init__(self, self.xml, 'text/xml')


class ServiceControl:

    def get_action_results(self, result, action):
        """ check for out arguments
            if yes: check if there are related ones to StateVariables with
                    non A_ARG_TYPE_ prefix
                    if yes: check if there is a call plugin method for this action
                            if yes: update StateVariable values with call result
                            if no:  get StateVariable values and
                                    add them to result dict
        """
        log.info('get_action_results', result)
        #print 'get_action_results', action
        r = result
        notify = []
        for argument in action.get_out_arguments():
            #print 'get_state_variable_contents', argument.name
            if argument.name[0:11] != 'A_ARG_TYPE_':
                if action.get_callback() != None:
                    variable = self.variables[0][argument.get_state_variable()]
                    variable.update(r[argument.name])
                    #print 'update state variable contents', variable.name, variable.value, variable.send_events
                    if(variable.send_events == 'yes' and variable.moderated == False):
                        notify.append(variable)
                else:
                    variable = self.variables[0][argument.get_state_variable()]
                    #print 'get state variable contents', variable.name, variable.value
                    r[argument.name] = variable.value
                    #print "r", r
            self.service.propagate_notification(notify)
        r= { '%sResponse'%action.name: r}
        log.info( 'action_results', r)
        return r
        
    def soap__generic(self, *args, **kwargs):
        """ generic UPnP service control method,
            which will be used if no soap_ACTIONNAME method
            in the server service control class can be found
        """
        try:
            action = self.actions[kwargs['soap_methodName']]
        except:
            return failure.Failure(errorCode(401))
        
        log.info("soap__generic", action, __name__, kwargs)
        del kwargs['soap_methodName']

        in_arguments = action.get_in_arguments()
        for arg_name, arg in kwargs.iteritems():
            l = [ a for a in in_arguments if arg_name == a.get_name()] 
            if len(l) > 0:
                in_arguments.remove(l[0])
            else:
                log.critical('argument %s not valid for action %s' % (arg_name,action.name))
                return failure.Failure(errorCode(402))
        if len(in_arguments) > 0:
            log.critical('argument %s missing for action %s' %
                                ([ a.get_name() for a in in_arguments],action.name))
            return failure.Failure(errorCode(402))
        
        def callit( *args, **kwargs):
            #print 'callit args', args
            #print 'callit kwargs', kwargs
            result = {}
            callback = action.get_callback()
            if callback != None:
                return callback( **kwargs)
            return result
            
        def failure(x):
            #print 'failure', x
            #log.err()
            log.error('soap__generic error during call processing')
            return x

        # call plugin method for this action
        d = defer.maybeDeferred( callit, *args, **kwargs)
        d.addCallback( self.get_action_results, action)
        d.addErrback(failure)
        return d

