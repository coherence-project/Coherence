# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009 Philippe Normand <phil@base-art.net>

from dbus import PROPERTIES_IFACE

from telepathy.interfaces import CHANNEL_TYPE_DBUS_TUBE, CONN_INTERFACE, \
     CHANNEL_INTERFACE, CHANNEL_INTERFACE_TUBE, CONNECTION

from coherence.extern.telepathy import client, tube
from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE, SERVICE_IFACE
from coherence import dbus_service

class MirabeauTubeConsumerMixin(tube.TubeConsumerMixin):

    def __init__(self, found_peer_callback=None, disapeared_peer_callback=None,
                 got_devices_callback=None):
        tube.TubeConsumerMixin.__init__(self,
                                        found_peer_callback=found_peer_callback,
                                        disapeared_peer_callback=disapeared_peer_callback)
        self.got_devices_callback = got_devices_callback
        self.info("MirabeauTubeConsumer created")
        self._coherence_tubes = {}

    def pre_accept_tube(self, tube):
        params = tube[PROPERTIES_IFACE].Get(CHANNEL_INTERFACE_TUBE, 'Parameters')
        initiator = params.get("initiator")
        for group in ("publish", "subscribe"):
            try:
                contacts = self.roster[group]
            except KeyError:
                self.debug("Group %r not in roster...", group)
                continue
            for contact_handle, contact in contacts.iteritems():
                if contact[CONNECTION + "/contact-id"] == initiator:
                    return True
        return False

    def post_tube_accept(self, tube, tube_conn, initiator_handle):
        service = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]

        if service == BUS_NAME:
            tube.remote_object = dbus_service.DBusPontoon(None, tube_conn)
        elif service == DEVICE_IFACE:
            tube.remote_object = dbus_service.DBusDevice(None, tube_conn)
        elif service == SERVICE_IFACE:
            tube.remote_object = dbus_service.DBusService(None, None, tube_conn)
        else:
            self.info("tube %r is not coming from Coherence", service)
            return tube_conn

        if initiator_handle not in self._coherence_tubes:
            self._coherence_tubes[initiator_handle] = {}
        self._coherence_tubes[initiator_handle][service] = tube

        if len(self._coherence_tubes[initiator_handle]) == 3:
            self.announce(initiator_handle)

    def tube_closed(self, tube):
        self.disapeared_peer_callback(tube)
        super(MirabeauTubeConsumerMixin, self).tube_closed(tube)

    def announce(self, initiator_handle):
        service_name = BUS_NAME
        pontoon_tube = self._coherence_tubes[initiator_handle][service_name]

        def cb(participants, removed):
            if participants and initiator_handle in participants:
                initiator_bus_name = participants[initiator_handle]
                self.info("bus name %r for service %r", initiator_bus_name,
                          service_name)
                if initiator_bus_name is not None:
                    self.found_devices(initiator_handle, initiator_bus_name)
            for handle in removed:
                try:
                    tube_channels = self._coherence_tubes[handle]
                except KeyError:
                    self.debug("tube with handle %d not registered", handle)
                else:
                    for service_iface_name, channel in tube_channels.iteritems():
                        channel[CHANNEL_INTERFACE].Close()
                    del self._coherence_tubes[handle]

        pontoon_tube.remote_object.tube.watch_participants(cb)

    def found_devices(self, initiator_handle, initiator_bus_name):
        devices = []
        tubes = self._coherence_tubes[initiator_handle]
        pontoon_tube = tubes[BUS_NAME].remote_object.tube
        device_tube = tubes[DEVICE_IFACE].remote_object.tube
        service_tube = tubes[SERVICE_IFACE].remote_object.tube
        self.info("using pontoon tube at %r", tubes[BUS_NAME].object_path)

        def got_devices(pontoon_devices):
            self.info("%r devices registered in remote pontoon", len(pontoon_devices))
            for device_dict in pontoon_devices:
                device_path = device_dict["path"]
                self.info("getting object at %r from %r", device_path,
                           initiator_bus_name)
                proxy = device_tube.get_object(initiator_bus_name, device_path)
                infos = proxy.get_info(dbus_interface=DEVICE_IFACE)
                service_proxies = []
                for service_path in device_dict["services"]:
                    service_proxy = service_tube.get_object(initiator_bus_name,
                                                            service_path)
                    service_proxies.append(service_proxy)
                proxy.services = service_proxies
                devices.append(proxy)
            self.got_devices_callback(devices)

        def got_error(exception):
            print ">>>", exception

        pontoon = pontoon_tube.get_object(initiator_bus_name, OBJECT_PATH)
        pontoon.get_devices_async(1, reply_handler=got_devices,
                                  error_handler=got_error)

class MirabeauTubeConsumer(MirabeauTubeConsumerMixin, client.Client):
    logCategory = "mirabeau_tube_consumer"

    def __init__(self, manager, protocol, account, muc_id, conference_server,
                 found_peer_callback=None, disapeared_peer_callback=None,
                 got_devices_callback=None):
        MirabeauTubeConsumerMixin.__init__(self,
                                           found_peer_callback=found_peer_callback,
                                           disapeared_peer_callback=disapeared_peer_callback,
                                           got_devices_callback=got_devices_callback)
        client.Client.__init__(self, manager, protocol, account, muc_id, conference_server)

    def got_tube(self, tube):
        client.Client.got_tube(self, tube)
        self.accept_tube(tube)

    def tube_opened(self, tube):
        tube_conn = super(MirabeauTubePublisherConsumer, self).tube_opened(tube)
        self.post_tube_accept(tube, tube_conn)
        return tube_conn
