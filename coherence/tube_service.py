# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009 - Frank Scholz <coherence@beebits.net>

""" TUBE service classes

"""

import urllib, urlparse

import dbus


from twisted.web import resource
from twisted.internet import defer
from twisted.python.util import OrderedDict

from coherence.upnp.core.utils import parse_xml

from coherence.upnp.devices.basics import RootDeviceXML, DeviceHttpRoot
from coherence.upnp.core import service
from coherence.upnp.core.soap_service import UPnPPublisher

from coherence.upnp.core import action
from coherence.upnp.core import variable

from coherence.upnp.core import DIDLLite
from coherence.upnp.core.utils import ReverseProxyUriResource

from coherence import log

class MirabeauProxy(resource.Resource, log.Loggable):
    logCategory = 'mirabeau'

    def __init__(self):
        resource.Resource.__init__(self)
        log.Loggable.__init__(self)
        self.isLeaf = 0

    def getChildWithDefault(self, path, request):
        self.info('MiraBeau getChildWithDefault %s, %s, %s %s' % (request.method, path, request.uri, request.client))
        uri = urllib.unquote_plus(path)
        self.info('MiraBeau  uri %r' % uri)
        return ReverseProxyUriResource(uri)


class TubeServiceControl(UPnPPublisher, log.Loggable):
    logCategory = 'mirabeau'

    def __init__(self, server):
        self.service = server
        self.variables = server.get_variables()
        self.actions = server.get_actions()

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
        notify = []
        for argument in action.get_out_arguments():
            #print 'get_state_variable_contents', argument.name
            if argument.name[0:11] != 'A_ARG_TYPE_':
                variable = self.variables[instance][argument.get_state_variable()]
                variable.update(result[argument.name].decode('utf-8').encode('utf-8'))
                #print 'update state variable contents', variable.name, variable.value, variable.send_events
                if(variable.send_events == 'yes' and variable.moderated == False):
                    notify.append(variable)

            self.service.propagate_notification(notify)
        self.info( 'action_results unsorted', action.name, result)
        if len(result) == 0:
            return result
        ordered_result = OrderedDict()
        for argument in action.get_out_arguments():
            if action.name  == 'XXXBrowse' and argument.name == 'Result':
                didl = DIDLLite.DIDLElement.fromString(result['Result'].decode('utf-8'))
                changed = False
                for item in didl.getItems():
                    new_res = DIDLLite.Resources()
                    for res in item.res:
                        remote_protocol,remote_network,remote_content_format,_ = res.protocolInfo.split(':')
                        if remote_protocol == 'http-get' and remote_network == '*':
                            quoted_url = urllib.quote_plus(res.data)
                            print "modifying", res.data
                            res.data = urlparse.urlunsplit(('http', self.service.device.external_address,'mirabeau',quoted_url,""))
                            print "--->", res.data
                            new_res.append(res)
                            changed = True
                    item.res = new_res
                if changed == True:
                    didl.rebuild()
                    ordered_result[argument.name] = didl.toString() #.replace('<ns0:','<')
                else:
                    ordered_result[argument.name] = result[argument.name].decode('utf-8')
            else:
                ordered_result[argument.name] = result[argument.name].decode('utf-8').encode('utf-8')
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


        def got_error(x):
            self.info('dbus error during call processing')
            return x

        # call plugin method for this action
        #print 'callit args', args
        #print 'callit kwargs', kwargs
        #print 'callit action', action
        #print 'callit dbus action', self.service.service.action
        d = defer.Deferred()
        self.service.service.call_action( action.name, dbus.Dictionary(kwargs,signature='ss'), reply_handler = d.callback, error_handler = d.errback,utf8_strings=True)
        d.addCallback( self.get_action_results, action, instance)
        d.addErrback(got_error)
        return d

class TubeServiceProxy(service.ServiceServer, resource.Resource,
                              log.Loggable):
    logCategory = 'mirabeau'

    def __init__(self, tube_service, device, backend=None):
        self.device = device
        self.service = tube_service
        resource.Resource.__init__(self)
        id = self.service.get_id().split(':')[3]
        service.ServiceServer.__init__(self, id, self.device.version, None)

        self.control = TubeServiceControl(self)
        self.putChild(self.scpd_url, service.scpdXML(self, self.control))
        self.putChild(self.control_url, self.control)
        self.device.web_resource.putChild(id, self)


    def init_var_and_actions(self):
        """ retrieve all actions and create the Action
            classes for our (proxy) server

            retrieve all variables and create the StateVariable
            classes for our (proxy) server
        """
        xml = self.service.get_scpd_xml()
        tree = parse_xml(xml, 'utf-8').getroot()
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


class TubeDeviceProxy(log.Loggable):
    logCategory = 'dbus'

    def __init__(self, coherence, tube_device,external_address):
        log.Loggable.__init__(self)
        self.device = tube_device
        self.coherence = coherence
        self.external_address = external_address
        self.uuid = self.device.get_id().split('-')
        self.uuid[1] = 'tube'
        self.uuid = '-'.join(self.uuid)
        self.friendly_name = self.device.get_friendly_name()
        self.device_type = self.device.get_friendly_device_type()
        self.version = int(self.device.get_device_type_version())

        self._services = []
        self._devices = []
        self.icons = []

        self.info("uuid: %s, name: %r, device type: %r, version: %r",
                  self.uuid, self.friendly_name, self.device_type, self.version)

        """ create the http entrypoint """

        self.web_resource = DeviceHttpRoot(self)
        self.coherence.add_web_resource( str(self.uuid)[5:], self.web_resource)


        """ create the Service proxy(s) """

        for service in self.device.services:
            self.debug("Proxying service %r", service)
            new_service = TubeServiceProxy(service, self)
            self._services.append(new_service)

        """ create a device description xml file(s) """

        version = self.version
        while version > 0:
            self.web_resource.putChild( 'description-%d.xml' % version,
                                    RootDeviceXML( self.coherence.hostname,
                                    str(self.uuid),
                                    self.coherence.urlbase,
                                    device_type=self.device_type, version=version,
                                    friendly_name=self.friendly_name,
                                    model_description='Coherence UPnP %s' % self.device_type,
                                    model_name='Coherence UPnP %s' % self.device_type,
                                    services=self._services,
                                    devices=self._devices,
                                    icons=self.icons))
            version -= 1


        """ and register with SSDP server """
        self.register()

    def register(self):
        s = self.coherence.ssdp_server
        uuid = str(self.uuid)
        host = self.coherence.hostname
        self.msg('%s register' % self.device_type)
        # we need to do this after the children are there, since we send notifies
        s.register('local',
                    '%s::upnp:rootdevice' % uuid,
                    'upnp:rootdevice',
                    self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % self.version,
                    host=host)

        s.register('local',
                    uuid,
                    uuid,
                    self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % self.version,
                    host=host)

        version = self.version
        while version > 0:
            if version == self.version:
                silent = False
            else:
                silent = True
            s.register('local',
                        '%s::urn:schemas-upnp-org:device:%s:%d' % (uuid, self.device_type, version),
                        'urn:schemas-upnp-org:device:%s:%d' % (self.device_type, version),
                        self.coherence.urlbase + uuid[5:] + '/' + 'description-%d.xml' % version,
                        silent=silent,
                        host=host)
            version -= 1


        for service in self._services:
            device_version = self.version
            service_version = self.version
            if hasattr(service,'version'):
                service_version = service.version
            silent = False

            while service_version > 0:
                try:
                    namespace = service.namespace
                except:
                    namespace = 'schemas-upnp-org'

                device_description_tmpl = 'description-%d.xml'  % device_version
                if hasattr(service,'device_description_tmpl'):
                    device_description_tmpl = service.device_description_tmpl

                s.register('local',
                            '%s::urn:%s:service:%s:%d' % (uuid,namespace,service.id, service_version),
                            'urn:%s:service:%s:%d' % (namespace,service.id, service_version),
                            self.coherence.urlbase + uuid[5:] + '/' + device_description_tmpl,
                            silent=silent,
                            host=host)

                silent = True
                service_version -= 1
                device_version -= 1
