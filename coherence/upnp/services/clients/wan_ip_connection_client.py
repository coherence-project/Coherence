# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2010, Frank Scholz <dev@coherence-project.org>

from twisted.internet import defer


class WANIPConnectionClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.subscribe()
        self.service.client = self

    def remove(self):
        if self.service != None:
            self.service.remove()
        self.service = None
        self.namespace = None
        self.url = None
        del self

    def subscribe_for_variable(self, var_name, callback,signal=False):
        self.service.subscribe_for_variable(var_name, instance=0, callback=callback,signal=signal)

    def get_external_ip_address(self):
        action = self.service.get_action('GetExternalIPAddress')
        return action.call()

    def get_all_port_mapping_entries(self):
        l = []

        def handle_error(f):
            return f

        variable = self.service.get_state_variable('PortMappingNumberOfEntries')
        if variable.value != '':
            for i in range(int(variable.value)):
                action = variable.service.get_action('GetGenericPortMappingEntry')
                d = self.get_generic_port_mapping_entry(i)

                def add_index(r,index):
                    r['NewPortMappingIndex'] = index
                    return r
                d.addCallback(add_index,i+1)
                d.addErrback(handle_error)
                l.append(d)

        def request_cb(r,last_updated_timestamp,v):
            if last_updated_timestamp == v.last_time_touched:
                mappings = [m[1] for m in r if m[0] == True]
                mappings.sort(cmp=lambda x,y : cmp(x['NewPortMappingIndex'],y['NewPortMappingIndex']))
                return mappings
            else:
                #FIXME - we should raise something here, as the mappings have changed during our query
                return None

        dl = defer.DeferredList(l)
        dl.addCallback(request_cb,variable.last_time_touched,variable)
        dl.addErrback(handle_error)
        return dl


    def get_generic_port_mapping_entry(self,port_mapping_index):
        action = self.service.get_action('GetGenericPortMappingEntry')
        return action.call(NewPortMappingIndex=port_mapping_index)

    def get_specific_port_mapping_entry(self,remote_host='',
                                             external_port=0,
                                             protocol='TCP'):
        action = self.service.get_action('GetSpecificPortMappingEntry')
        return action.call(NewRemoteHost=remote_host,
                           NewExternalPort=int(external_port),
                           NewProtocol=protocol)

    def add_port_mapping(self,remote_host='',
                              external_port=0,
                              protocol='TCP',
                              internal_port=None,
                              internal_client=None,
                              enabled=False,
                              port_mapping_description='',
                              lease_duration=60):
        action = self.service.get_action('AddPortMapping')
        return action.call(NewRemoteHost=remote_host,
                           NewExternalPort=int(external_port),
                           NewProtocol=protocol,
                           NewInternalPort=int(internal_port),
                           NewInternalClient=str(internal_client),
                           NewEnabled=enabled,
                           NewPortMappingDescription=port_mapping_description,
                           NewLeaseDuration=int(lease_duration))

    def delete_port_mapping(self,remote_host='',
                              external_port=0,
                              protocol='TCP'):
        action = self.service.get_action('DeletePortMapping')
        return action.call(NewRemoteHost=remote_host,
                           NewExternalPort=int(external_port),
                           NewProtocol=protocol)