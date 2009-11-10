# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import os

import time
import urllib2
from coherence.upnp.core import action
from coherence.upnp.core import event
from coherence.upnp.core import variable

from coherence.upnp.core import utils
from coherence.upnp.core.soap_proxy import SOAPProxy
from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core.event import EventSubscriptionServer

from coherence.extern.et import ET

from twisted.web import static
from twisted.internet import defer, reactor
from twisted.python import failure, util
from twisted.internet import task

import coherence.extern.louie as louie

from coherence import log

global subscribers
subscribers = {}

def subscribe(service):
    subscribers[service.get_sid()] = service

def unsubscribe(service):
    if subscribers.has_key(service.get_sid()):
        del subscribers[service.get_sid()]

class Service(log.Loggable):
    logCategory = 'service_client'

    def __init__(self, service_type, service_id, location, control_url,
                 event_sub_url, presentation_url, scpd_url, device):
        #if not control_url.startswith('/'):
        #    control_url = "/%s" % control_url
        #if not event_sub_url.startswith('/'):
        #    event_sub_url = "/%s" % event_sub_url
        #if presentation_url and not presentation_url.startswith('/'):
        #    presentation_url = "/%s" % presentation_url
        #if not scpd_url.startswith('/'):
        #    scpd_url = "/%s" % scpd_url

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
        self.subscription_id = None
        self.timeout = 0

        self.event_connection = None
        self.last_time_updated = None

        self.client = None

        parsed = urllib2.urlparse.urlparse(location)
        self.url_base = "%s://%s" % (parsed[0], parsed[1])

        self.parse_actions()
        self.info("%s %s %s initialized" % (self.device.friendly_name,self.service_type,self.id))

    def as_tuples(self):
        r = []

        def append(name,attribute):
            try:
                if isinstance(attribute,tuple):
                    if callable(attribute[0]):
                        v1 = attribute[0]()
                    elif hasattr(self,attribute[0]):
                        v1 = getattr(self,attribute[0])
                    else:
                        v1 = attribute[0]
                    if v1 in [None,'None']:
                        return
                    if callable(attribute[1]):
                        v2 = attribute[1]()
                    elif hasattr(self,attribute[1]):
                        v2 = getattr(self,attribute[1])
                    else:
                        v2 = attribute[1]
                    if v2 in [None,'None']:
                        return
                    if len(attribute)> 2:
                        r.append((name,(v1,v2,attribute[2])))
                    else:
                        r.append((name,(v1,v2)))
                    return
                elif callable(attribute):
                    v = attribute()
                elif hasattr(self,attribute):
                    v = getattr(self,attribute)
                else:
                    v = attribute
                if v not in [None,'None']:
                    r.append((name,v))
            except:
                import traceback
                self.debug(traceback.format_exc())

        r.append(('Location',(self.device.get_location(),self.device.get_location())))
        append('URL base',self.device.get_urlbase)
        r.append(('UDN',self.device.get_id()))
        r.append(('Type',self.service_type))
        r.append(('ID',self.id))
        append('Service Description URL',(self.scpd_url,lambda: self.device.make_fullyqualified(self.scpd_url)))
        append('Control URL',(self.control_url,lambda: self.device.make_fullyqualified(self.control_url),False))
        append('Event Subscription URL',(self.event_sub_url,lambda: self.device.make_fullyqualified(self.event_sub_url),False))

        return r

    def as_dict(self):
        d = {'type':self.service_type}
        d['actions'] = [a.as_dict() for a in self._actions.values()]
        return d

    def __repr__(self):
        return "Service %s %s" % (self.service_type,self.id)

    #def __del__(self):
    #    print "Service deleted"
    #    pass

    def _get_client(self, name):
        url = self.get_control_url()
        namespace = self.get_type()
        action = "%s#%s" % (namespace, name)
        client = SOAPProxy( url, namespace=("u",namespace), soapaction=action)
        return client

    def remove(self):
        self.info("removal of ", self.device.friendly_name, self.service_type, self.id)
        try:
            self.renew_subscription_call.cancel()
        except:
            pass
        if self.event_connection != None:
            self.event_connection.teardown()
        if self.subscription_id != None:
            self.unsubscribe()
        for name,action in self._actions.items():
            self.debug("remove", name,action)
            del self._actions[name]
            del action
        for instance,variables in self._variables.items():
            for name, variable in variables.items():
                del variables[name]
                del variable
            if variables.has_key(instance):
                del variables[instance]
            del variables
        del self

    def get_device(self):
        return self.device

    def get_type(self):
        return self.service_type

    def set_timeout(self, timeout):
        self.info("set timout for %s/%s to %d" %(self.device.friendly_name,self.service_type,int(timeout)))
        self.timeout = timeout
        try:
            self.renew_subscription_call.reset(int(self.timeout)-30)
            self.info("reset renew subscription call for %s/%s to %d" % (self.device.friendly_name,self.service_type,int(self.timeout)-30))
        except:
            self.renew_subscription_call = reactor.callLater(int(self.timeout)-30,
                                                                 self.renew_subscription)
            self.info("starting renew subscription call for %s/%s to %d" % (self.device.friendly_name,self.service_type,int(self.timeout)-30))

    def get_timeout(self):
        return self.timeout

    def get_id(self):
        return self.id

    def get_sid(self):
        return self.subscription_id

    def set_sid(self, sid):
        self.info("set subscription id for %s/%s to %s" %(self.device.friendly_name,self.service_type,sid))
        self.subscription_id = sid
        if sid is not None:
            subscribe(self)
            self.debug("add subscription for %s", self.id)

    def get_actions(self):
        return self._actions

    def get_scpdXML(self):
        return self.scpdXML

    def get_action( self, name):
        try:
            return self._actions[name]
        except KeyError:
            return None # not implemented

    def get_state_variables(self, instance):
        return self._variables.get(int(instance))

    def get_state_variable(self, name, instance=0):
        return self._variables.get(int(instance)).get(name)

    def get_control_url(self):
        return self.device.make_fullyqualified(self.control_url)

    def get_event_sub_url(self):
        return self.device.make_fullyqualified(self.event_sub_url)

    def get_presentation_url(self):
        return self.device.make_fullyqualified(self.presentation_url)

    def get_scpd_url(self):
        return self.device.make_fullyqualified(self.scpd_url)

    def get_base_url(self):
        return self.device.make_fullyqualified('.')

    def subscribe(self):
        self.debug("subscribe %s", self.id)
        event.subscribe(self)
        #global subscribers
        #subscribers[self.get_sid()] = self

    def unsubscribe(self):

        def remove_it(r, sid):
            self.debug("remove subscription for %s", self.id)
            unsubscribe(self)
            self.subscription_id = None
            #global subscribers
            #if subscribers.has_key(sid):
            #    del subscribers[sid]

        self.debug("unsubscribe %s", self.id)
        d = event.unsubscribe(self)
        d.addCallback(remove_it, self.get_sid())
        return d

    def subscribe_for_variable(self, var_name, instance=0, callback=None, signal=False):
        variable = self.get_state_variable(var_name)
        if variable:
            if callback != None:
                if signal == True:
                    callback(variable)
                    louie.connect(callback, signal='Coherence.UPnP.StateVariable.%s.changed' % var_name, sender=self)
                else:
                    variable.subscribe(callback)


    def renew_subscription(self):
        self.info("renew_subscription")
        event.subscribe(self)

    def process_event(self,event):
        self.info("process event %r %r" % (self,event))
        for var_name, var_value  in event.items():
            if var_name == 'LastChange':
                self.info("we have a LastChange event")
                self.get_state_variable(var_name, 0).update(var_value)
                tree = utils.parse_xml(var_value, 'utf-8').getroot()
                namespace_uri, tag = tree.tag[1:].split( "}", 1)
                for instance in tree.findall('{%s}InstanceID' % namespace_uri):
                    instance_id = instance.attrib['val']
                    self.info("instance_id %r %r" % (instance,instance_id))
                    for var in instance.getchildren():
                        self.info("var %r" % var)
                        namespace_uri, tag = var.tag[1:].split("}", 1)
                        self.info("%r %r %r" % (namespace_uri, tag,var.attrib['val']))
                        self.get_state_variable(tag, instance_id).update(var.attrib['val'])
                        self.info("updated var %r" % var)
                        if len(var.attrib) > 1:
                            self.info("Extended StateVariable %s - %r", var.tag, var.attrib)
                            if var.attrib.has_key('channel') and var.attrib['channel'] != 'Master':
                                # TODO handle attributes that them selves have multiple instances
                                self.info("Skipping update to %s its not for master channel %s", var.tag, var.attrib)
                                pass
                            else:
                                if not self.get_state_variables(instance_id):
                                    # TODO Create instance ?
                                    self.error("%r update failed (not self.get_state_variables(instance_id)) %r", self, instance_id)
                                elif not self.get_state_variables(instance_id).has_key(tag):
                                    # TODO Create instance StateVariable?
                                    # SONOS stuff
                                    self.error("%r update failed (not self.get_state_variables(instance_id).has_key(tag)) %r", self, tag)
                                else:
                                    val = None
                                    if var.attrib.has_key('val'):
                                        val = var.attrib['val']
                                    #self.debug("%r update %r %r %r", self,namespace_uri, tag, var.attrib['val'])
                                    self.get_state_variable(tag, instance_id).update(var.attrib['val'])
                                    self.debug("updated 'attributed' var %r", var)
                louie.send('Coherence.UPnP.DeviceClient.Service.Event.processed',None,self,(var_name,var_value,event.raw))
            else:
                self.get_state_variable(var_name, 0).update(var_value)
                louie.send('Coherence.UPnP.DeviceClient.Service.Event.processed',None,self,(var_name,var_value,event.raw))
        if self.last_time_updated == None:
            # The clients (e.g. media_server_client) check for last time to detect whether service detection is complete
            # so we need to set it here and now to avoid a potential race condition
            self.last_time_updated = time.time()
            louie.send('Coherence.UPnP.DeviceClient.Service.notified', sender=self.device, service=self)
            self.info("send signal Coherence.UPnP.DeviceClient.Service.notified for %r" % self)
        self.last_time_updated = time.time()

    def parse_actions(self):

        def gotPage(x):
            #print "gotPage"
            #print x
            self.scpdXML, headers = x
            tree = utils.parse_xml(self.scpdXML, 'utf-8').getroot()
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
                send_events = var_node.attrib.get('sendEvents','yes')
                name = var_node.findtext('{%s}name' % ns)
                data_type = var_node.findtext('{%s}dataType' % ns)
                values = []
                """ we need to ignore this, as there we don't get there our
                    {urn:schemas-beebits-net:service-1-0}X_withVendorDefines
                    attibute there
                """
                for allowed in var_node.findall('.//{%s}allowedValue' % ns):
                    values.append(allowed.text)
                instance = 0
                self._variables.get(instance)[name] = variable.StateVariable(self, name,
                                                               'n/a',
                                                               instance, send_events,
                                                               data_type, values)
                """ we need to do this here, as there we don't get there our
                    {urn:schemas-beebits-net:service-1-0}X_withVendorDefines
                    attibute there
                """
                self._variables.get(instance)[name].has_vendor_values = True


            #print 'service parse:', self, self.device
            self.detection_completed = True
            louie.send('Coherence.UPnP.Service.detection_completed', sender=self.device, device=self.device)
            self.info("send signal Coherence.UPnP.Service.detection_completed for %r" % self)
            """
            if (self.last_time_updated == None):
                if( self.id.endswith('AVTransport') or
                    self.id.endswith('RenderingControl')):
                    louie.send('Coherence.UPnP.DeviceClient.Service.notified', sender=self.device, service=self)
                    self.last_time_updated = time.time()
            """

        def gotError(failure, url):
            self.warning('error requesting', url)
            self.info('failure', failure)
            louie.send('Coherence.UPnP.Service.detection_failed', self.device, device=self.device)

        #print 'getPage', self.get_scpd_url()
        utils.getPage(self.get_scpd_url()).addCallbacks(gotPage, gotError, None, None, [self.get_scpd_url()], None)

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

class ServiceServer(log.Loggable):
    logCategory = 'service_server'

    def __init__(self, id, version, backend):
        self.id = id
        self.version = version
        self.backend = backend
        if getattr(self, "namespace", None) == None:
            self.namespace = 'schemas-upnp-org'
        if getattr(self, "id_namespace", None) == None:
            self.id_namespace = 'upnp-org'

        self.service_type = 'urn:%s:service:%s:%d' % (self.namespace, id, int(self.version))

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

        self._pending_notifications = {}

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

        self.check_moderated_loop = None
        if moderated_variables.has_key(self.service_type):
            self.check_moderated_loop = task.LoopingCall(self.check_moderated_variables)
            #self.check_moderated_loop.start(5.0, now=False)
            self.check_moderated_loop.start(0.5, now=False)

    def _release(self):
        for p in self._pending_notifications.values():
            p.disconnect()
        self._pending_notifications = {}

    def get_action(self, action_name):
        try:
            return self._actions[action_name]
        except KeyError:
            return None # not implemented

    def get_actions(self):
        return self._actions

    def get_variables(self):
        return self._variables

    def get_subscribers(self):
        return self._subscribers

    def rm_notification(self,result,d):
        del self._pending_notifications[d]

    def new_subscriber(self, subscriber):
        notify = []
        for vdict in self._variables.values():
            notify += [v for v in vdict.values() if v.send_events == True]

        self.info("new_subscriber", subscriber, notify)
        if len(notify) <= 0:
            return

        root = ET.Element('e:propertyset')
        root.attrib['xmlns:e']='urn:schemas-upnp-org:event-1-0'
        evented_variables = 0
        for n in notify:
            e = ET.SubElement( root, 'e:property')
            if n.name == 'LastChange':
                if subscriber['seq'] == 0:
                    text = self.build_last_change_event(n.instance, force=True)
                else:
                    text = self.build_last_change_event(n.instance)
                if text is not None:
                    ET.SubElement( e, n.name).text = text
                    evented_variables += 1
            else:
                ET.SubElement( e, n.name).text = str(n.value)
                evented_variables += 1

        if evented_variables > 0:
            xml = ET.tostring( root, encoding='utf-8')
            d,p = event.send_notification(subscriber, xml)
            self._pending_notifications[d] = p
            d.addBoth(self.rm_notification,d)
        self._subscribers[subscriber['sid']] = subscriber

    def get_id(self):
        return self.id

    def get_type(self):
        return self.service_type

    def create_new_instance(self, instance):
        self._variables[instance] = {}
        for v in self._variables[0].values():
            self._variables[instance][v.name] = variable.StateVariable( v.service,
                                                                        v.name,
                                                                        v.implementation,
                                                                        instance,
                                                                        v.send_events,
                                                                        v.data_type,
                                                                        v.allowed_values)
            self._variables[instance][v.name].has_vendor_values = v.has_vendor_values
            self._variables[instance][v.name].default_value = v.default_value
            #self._variables[instance][v.name].value = v.default_value # FIXME
            self._variables[instance][v.name].old_value = v.old_value
            self._variables[instance][v.name].value = v.value
            self._variables[instance][v.name].dependant_variable = v.dependant_variable

    def remove_instance(self, instance):
        if instance == 0:
            return
        del(self._variables[instance])

    def set_variable(self, instance, variable_name, value, default=False):

        def process_value(result):
            variable.update(result)
            if default == True:
                variable.default_value = variable.value
            if(variable.send_events == True and
                variable.moderated == False and
                len(self._subscribers) > 0):
                xml = self.build_single_notification(instance, variable_name, variable.value)
                for s in self._subscribers.values():
                    d,p = event.send_notification(s, xml)
                    self._pending_notifications[d] = p
                    d.addBoth(self.rm_notification,d)
        try:
            variable = self._variables[int(instance)][variable_name]
            if isinstance( value, defer.Deferred):
                value.addCallback(process_value)
            else:
                process_value(value)
        except:
            pass

    def get_variable(self, variable_name, instance=0):
        try:
            return self._variables[int(instance)][variable_name]
        except:
            return None

    def build_single_notification(self, instance, variable_name, value):
        root = ET.Element('e:propertyset')
        root.attrib['xmlns:e']='urn:schemas-upnp-org:event-1-0'
        e = ET.SubElement( root, 'e:property')
        s = ET.SubElement( e, variable_name).text = str(value)
        return ET.tostring( root, encoding='utf-8')

    def build_last_change_event(self, instance=0, force=False):
        got_one = False
        root = ET.Element('Event')
        root.attrib['xmlns']=self.event_metadata
        for instance, vdict in self._variables.items():
            e = ET.SubElement( root, 'InstanceID')
            e.attrib['val']=str(instance)
            for variable in vdict.values():
                if( variable.name != 'LastChange' and
                    variable.name[0:11] != 'A_ARG_TYPE_' and
                    variable.never_evented == False and
                    (variable.updated == True or force == True)):
                    s = ET.SubElement( e, variable.name)
                    s.attrib['val'] = str(variable.value)
                    variable.updated = False
                    got_one = True
                    if variable.dependant_variable != None:
                        dependants = variable.dependant_variable.get_allowed_values()
                        if dependants != None and len(dependants) > 0:
                            s.attrib['channel']=dependants[0]
        if got_one == True:
            return ET.tostring( root, encoding='utf-8')
        else:
            return None

    def propagate_notification(self, notify):
        #print "propagate_notification", notify
        if len(self._subscribers) <= 0:
            return
        if len(notify) <= 0:
            return

        root = ET.Element('e:propertyset')
        root.attrib['xmlns:e']='urn:schemas-upnp-org:event-1-0'

        if isinstance( notify, variable.StateVariable):
            notify = [notify,]

        evented_variables = 0
        for n in notify:
            e = ET.SubElement( root, 'e:property')
            if n.name == 'LastChange':
                text = self.build_last_change_event(instance=n.instance)
                if text is not None:
                    ET.SubElement( e, n.name).text = text
                    evented_variables += 1
            else:
                s = ET.SubElement( e, n.name).text = str(n.value)
                evented_variables += 1
                if n.dependant_variable != None:
                    dependants = n.dependant_variable.get_allowed_values()
                    if dependants != None and len(dependants) > 0:
                        s.attrib['channel']=dependants[0]

        if evented_variables == 0:
            return
        xml = ET.tostring( root, encoding='utf-8')
        #print "propagate_notification", xml
        for s in self._subscribers.values():
            d,p = event.send_notification(s,xml)
            self._pending_notifications[d] = p
            d.addBoth(self.rm_notification,d)

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
        notify = []
        for v in variables:
            #print self._variables[0][v].name, self._variables[0][v].updated
            for vdict in self._variables.values():
                if vdict[v].updated == True:
                    vdict[v].updated = False
                    notify.append(vdict[v])
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

    def get_scpdXML(self):
        if not hasattr(self,'scpdXML') or self.scpdXML == None:
            self.scpdXML = scpdXML(self)
            self.scpdXML = self.scpdXML.build_xml()
        return self.scpdXML

    def register_vendor_variable(self,name,implementation='optional',
                                      instance=0, evented='no',
                                      data_type='string',
                                      dependant_variable=None,
                                      default_value=None,
                                      allowed_values=None,has_vendor_values=False,allowed_value_range=None,
                                      moderated=False):
        """
        enables a backend to add an own, vendor defined, StateVariable to the service

        @ivar name: the name of the new StateVariable
        @ivar implementation: either 'optional' or 'required'
        @ivar instance: the instance number of the service that variable should be assigned to, usually '0'
        @ivar evented: boolean, or the special keyword 'never' if the variable doesn't show up in a LastChange event too
        @ivar data_type: 'string','boolean','bin.base64' or various number formats
        @ivar dependant_variable: the name of another StateVariable that depends on this one
        @ivar default_value: the value this StateVariable should have by default when created
                             for another instance of in the service
        @ivar allowed_values: a C{list} of values this StateVariable can have
        @ivar has_vendor_values: boolean if there are values outside the allowed_values list too
        @ivar allowed_value_range: a C{dict} of 'minimum','maximum' and 'step' values
        @ivar moderated: boolean, True if this StateVariable should only be evented via a LastChange event

        """

        # FIXME
        # we should raise an Exception when there as a StateVariable with that name already

        if evented == 'never':
            send_events = 'no'
        else:
            send_events = evented
        new_variable = variable.StateVariable(self,name,implementation,instance,send_events,
                                                   data_type,allowed_values)
        if default_value == None:
            new_variable.default_value = ''
        else:
            new_variable.default_value = new_variable.old_value = new_variable.value = default_value

        new_variable.dependant_variable = dependant_variable
        new_variable.has_vendor_values = has_vendor_values
        new_variable.allowed_value_range = allowed_value_range
        new_variable.moderated = moderated
        if evented == 'never':
            new_variable.never_evented = True
        self._variables.get(instance)[name] = new_variable
        return new_variable

    def register_vendor_action(self,name,implementation,arguments=None,needs_callback=True):
        """
        enables a backend to add an own, vendor defined, Action to the service

        @ivar name: the name of the new Action
        @ivar implementation: either 'optional' or 'required'
        @ivar arguments: a C{list} if argument C{tuples},
                         like (name,direction,relatedStateVariable)
        @ivar needs_callback: this Action needs a method in the backend or service class
        """

        # FIXME
        # we should raise an Exception when there as an Action with that name already
        # we should raise an Exception when there is no related StateVariable for an Argument

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
                self.info('%s has a missing callback for %s action %s, action disabled' % (self.id,implementation,name))
                return
            else:
                if((hasattr(self,'implementation') and self.implementation == 'required') or
                    not hasattr(self,'implementation')):
                    self.warning('%s has a missing callback for %s action %s, service disabled' % (self.id,implementation,name))
                raise LookupError,"missing callback"

        arguments_list = []
        for argument in arguments:
            arguments_list.append(action.Argument(argument[0],argument[1].lower(),argument[2]))

        new_action = action.Action(self, name, implementation, arguments_list)
        self._actions[name] = new_action
        if callback != None:
            new_action.set_callback(callback)
            self.info('Add callback %s for %s/%s' % (callback, self.id, name))
        return new_action

    def init_var_and_actions(self):
        desc_file = util.sibpath(__file__, os.path.join('xml-service-descriptions', '%s%d.xml' % (self.id, int(self.version))))
        tree = ET.parse(desc_file)

        for action_node in tree.findall('.//action'):
            name = action_node.findtext('name')
            implementation = 'required'
            needs_callback = False
            if action_node.attrib.get('{urn:schemas-beebits-net:service-1-0}X_needs_backend',
                                        None) != None:
                needs_callback = True
            if action_node.find('Optional') != None:
                implementation = 'optional'
                if(action_node.find('Optional').attrib.get(
                                        '{urn:schemas-beebits-net:service-1-0}X_needs_backend',
                                        None) != None or
                    action_node.attrib.get('{urn:schemas-beebits-net:service-1-0}X_needs_backend',
                                            None) != None):
                    needs_callback = True

            arguments = []
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
                    self.info('%s has a missing callback for %s action %s, action disabled' % (self.id,implementation,name))
                    continue
                else:
                    if((hasattr(self,'implementation') and self.implementation == 'required') or
                        not hasattr(self,'implementation')):
                        self.warning('%s has a missing callback for %s action %s, service disabled' % (self.id,implementation,name))
                    raise LookupError,"missing callback"

            new_action = action.Action(self, name, implementation, arguments)
            self._actions[name] = new_action
            if callback != None:
                new_action.set_callback(callback)
                self.info('Add callback %s for %s/%s' % (callback, self.id, name))


        backend_vendor_value_defaults = getattr(self.backend, "vendor_value_defaults", None)
        service_value_defaults = None
        if backend_vendor_value_defaults:
            service_value_defaults = backend_vendor_value_defaults.get(self.id,None)

        backend_vendor_range_defaults = getattr(self.backend, "vendor_range_defaults", None)
        service_range_defaults = None
        if backend_vendor_range_defaults:
            service_range_defaults = backend_vendor_range_defaults.get(self.id)

        for var_node in tree.findall('.//stateVariable'):
            instance = 0
            name = var_node.findtext('name')
            implementation = 'required'
            if action_node.find('Optional') != None:
                implementation = 'optional'

            #if implementation == 'optional':
            #    for action_object in self._actions.values():
            #        if name in [a.get_state_variable() for a in action_object.arguments_list]:
            #            break
            #    else:
            #        continue

            send_events = var_node.findtext('sendEventsAttribute')
            data_type = var_node.findtext('dataType')
            values = []
            for allowed in var_node.findall('.//allowedValue'):
                values.append(allowed.text)
            self._variables.get(instance)[name] = variable.StateVariable(self, name,
                                                           implementation,
                                                           instance, send_events,
                                                           data_type, values)

            dependant_variable = var_node.findtext('{urn:schemas-beebits-net:service-1-0}X_dependantVariable')
            if dependant_variable:
                self._variables.get(instance)[name].dependant_variable = dependant_variable
            default_value = var_node.findtext('defaultValue')
            if default_value:
                self._variables.get(instance)[name].set_default_value(default_value)
            if var_node.find('sendEventsAttribute') != None:
                never_evented = var_node.find('sendEventsAttribute').attrib.get(
                                        '{urn:schemas-beebits-net:service-1-0}X_no_means_never',
                                        None)
                if never_evented is not None:
                    self._variables.get(instance)[name].set_never_evented(never_evented)

            allowed_value_list = var_node.find('allowedValueList')
            if allowed_value_list != None:
                vendor_values = allowed_value_list.attrib.get(
                                    '{urn:schemas-beebits-net:service-1-0}X_withVendorDefines',
                                    None)
                if service_value_defaults:
                    variable_value_defaults = service_value_defaults.get(name, None)
                    if variable_value_defaults:
                        self.info("overwriting %s default value with %s" % (name,
                                                               variable_value_defaults))
                        self._variables.get(instance)[name].set_allowed_values(variable_value_defaults)

                if vendor_values != None:
                    self._variables.get(instance)[name].has_vendor_values = True

            allowed_value_range = var_node.find('allowedValueRange')
            if allowed_value_range:
                vendor_values = allowed_value_range.attrib.get(
                                    '{urn:schemas-beebits-net:service-1-0}X_withVendorDefines',
                                    None)
                range = {}
                for e in list(allowed_value_range):
                    range[e.tag] = e.text
                    if( vendor_values != None):
                        if service_range_defaults:
                            variable_range_defaults = service_range_defaults.get(name)
                            if( variable_range_defaults != None and
                                variable_range_defaults.get(e.tag) != None):
                                self.info("overwriting %s attribute %s with %s" % (name,
                                                               e.tag, str(variable_range_defaults[e.tag])))
                                range[e.tag] = variable_range_defaults[e.tag]
                            elif e.text == None:
                                self.info("missing vendor definition for %s, attribute %s" % (name, e.tag))
                self._variables.get(instance)[name].set_allowed_value_range(**range)
                if vendor_values != None:
                    self._variables.get(instance)[name].has_vendor_values = True
            elif service_range_defaults:
                variable_range_defaults = service_range_defaults.get(name)
                if variable_range_defaults != None:
                    self._variables.get(instance)[name].set_allowed_value_range(**variable_range_defaults)
                    self._variables.get(instance)[name].has_vendor_values = True

        for v in self._variables.get(0).values():
            if isinstance( v.dependant_variable, str):
                v.dependant_variable = self._variables.get(instance).get(v.dependant_variable)

class scpdXML(static.Data):

    def __init__(self, server, control=None):
        self.service_server = server
        self.control = control
        static.Data.__init__(self, None, 'text/xml')

    def render(self, request):
        if self.data == None:
            self.data = self.build_xml()
        return static.Data.render(self,request)

    def build_xml(self):
        root = ET.Element('scpd')
        root.attrib['xmlns']='urn:schemas-upnp-org:service-1-0'
        e = ET.SubElement(root, 'specVersion')
        ET.SubElement( e, 'major').text = '1'
        ET.SubElement( e, 'minor').text = '0'

        e = ET.SubElement( root, 'actionList')
        for action in self.service_server._actions.values():
            s = ET.SubElement( e, 'action')
            ET.SubElement( s, 'name').text = action.get_name()
            al = ET.SubElement( s, 'argumentList')
            for argument in action.get_arguments_list():
                a = ET.SubElement( al, 'argument')
                ET.SubElement( a, 'name').text = argument.get_name()
                ET.SubElement( a, 'direction').text = argument.get_direction()
                ET.SubElement( a, 'relatedStateVariable').text = argument.get_state_variable()

        e = ET.SubElement( root, 'serviceStateTable')
        for var in self.service_server._variables[0].values():
            s = ET.SubElement( e, 'stateVariable')
            if var.send_events == True:
                s.attrib['sendEvents'] = 'yes'
            else:
                s.attrib['sendEvents'] = 'no'
            ET.SubElement( s, 'name').text = var.name
            ET.SubElement( s, 'dataType').text = var.data_type
            if(not var.has_vendor_values and len(var.allowed_values)):
            #if len(var.allowed_values):
                v = ET.SubElement( s, 'allowedValueList')
                for value in var.allowed_values:
                    ET.SubElement( v, 'allowedValue').text = value

            if( var.allowed_value_range != None and
                len(var.allowed_value_range) > 0):
                complete = True
                for name,value in var.allowed_value_range.items():
                    if value == None:
                        complete = False
                if complete == True:
                    avl = ET.SubElement( s, 'allowedValueRange')
                    for name,value in var.allowed_value_range.items():
                         if value != None:
                            ET.SubElement( avl, name).text = str(value)

        return """<?xml version="1.0" encoding="utf-8"?>""" + ET.tostring( root, encoding='utf-8')

from twisted.python.util import OrderedDict

class ServiceControl:

    def get_action_results(self, result, action, instance):
        """ check for out arguments
            if yes: check if there are related ones to StateVariables with
                    non A_ARG_TYPE_ prefix
                    if yes: check if there is a call plugin method for this action
                            if yes: update StateVariable values with call result
                            if no:  get StateVariable values and
                                    add them to result dict
        """
        self.debug('get_action_results', result)
        #print 'get_action_results', action, instance
        r = result
        notify = []
        for argument in action.get_out_arguments():
            #print 'get_state_variable_contents', argument.name
            if argument.name[0:11] != 'A_ARG_TYPE_':
                if action.get_callback() != None:
                    variable = self.variables[instance][argument.get_state_variable()]
                    variable.update(r[argument.name])
                    #print 'update state variable contents', variable.name, variable.value, variable.send_events
                    if(variable.send_events == 'yes' and variable.moderated == False):
                        notify.append(variable)
                else:
                    variable = self.variables[instance][argument.get_state_variable()]
                    #print 'get state variable contents', variable.name, variable.value
                    r[argument.name] = variable.value
                    #print "r", r
            self.service.propagate_notification(notify)
        #r= { '%sResponse'%action.name: r}
        self.info( 'action_results unsorted', action.name, r)
        if len(r) == 0:
            return r
        ordered_result = OrderedDict()
        for argument in action.get_out_arguments():
            ordered_result[argument.name] = r[argument.name]
        self.info( 'action_results sorted', action.name, ordered_result)
        return ordered_result

    def soap__generic(self, *args, **kwargs):
        """ generic UPnP service control method,
            which will be used if no soap_ACTIONNAME method
            in the server service control class can be found
        """
        try:
            action = self.actions[kwargs['soap_methodName']]
        except:
            return failure.Failure(errorCode(401))

        try:
            instance = int(kwargs['InstanceID'])
        except:
            instance = 0

        self.info("soap__generic", action, __name__, kwargs)
        del kwargs['soap_methodName']
        if( kwargs.has_key('X_UPnPClient') and
                kwargs['X_UPnPClient'] == 'XBox'):
            if(action.name == 'Browse' and
                    kwargs.has_key('ContainerID')):
                """ XXX: THIS IS SICK """
                kwargs['ObjectID'] = kwargs['ContainerID']
                del kwargs['ContainerID']

        in_arguments = action.get_in_arguments()
        for arg_name, arg in kwargs.iteritems():
            if arg_name.find('X_') == 0:
                continue
            l = [ a for a in in_arguments if arg_name == a.get_name()]
            if len(l) > 0:
                in_arguments.remove(l[0])
            else:
                self.critical('argument %s not valid for action %s' % (arg_name,action.name))
                return failure.Failure(errorCode(402))
        if len(in_arguments) > 0:
            self.critical('argument %s missing for action %s' %
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

        def got_error(x):
            #print 'failure', x
            self.info('soap__generic error during call processing')
            return x

        # call plugin method for this action
        d = defer.maybeDeferred( callit, *args, **kwargs)
        d.addCallback( self.get_action_results, action, instance)
        d.addErrback(got_error)
        return d
