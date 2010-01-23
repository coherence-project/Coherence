# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009 Philippe Normand <phil@base-art.net>

import gobject
from dbus import PROPERTIES_IFACE

from telepathy.interfaces import CHANNEL_INTERFACE, CONNECTION_INTERFACE_REQUESTS, \
     CHANNEL_TYPE_DBUS_TUBE
from telepathy.constants import CONNECTION_HANDLE_TYPE_ROOM, \
     SOCKET_ACCESS_CONTROL_CREDENTIALS

from telepathy.interfaces import CHANNEL_INTERFACE_TUBE, CHANNEL_TYPE_DBUS_TUBE, \
     CHANNEL_INTERFACE
from telepathy.constants import TUBE_CHANNEL_STATE_LOCAL_PENDING

from coherence.extern.telepathy import client, tube, mirabeau_tube_consumer
from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE, SERVICE_IFACE
from coherence import dbus_service

from twisted.internet import task

class MirabeauTubePublisherMixin(tube.TubePublisherMixin):
    def __init__(self, tubes_to_offer, application, allowed_devices):
        tube.TubePublisherMixin.__init__(self, tubes_to_offer)
        self.coherence = application
        self.allowed_devices = allowed_devices
        self.coherence_tube = None
        self.device_tube = None
        self.service_tube = None
        self.announce_done = False
        self._ms_detected_match = None
        self._ms_removed_match = None

    def _media_server_found(self, infos, udn):
        uuid = udn[5:]
        for device in self.coherence.dbus.devices.values():
            if device.uuid == uuid:
                self._register_device(device)
                return

    def _register_device(self, device):
        if self.allowed_devices is not None and device.uuid not in self.allowed_devices:
            self.info("device not allowed: %r", device.uuid)
            return
        device.add_to_connection(self.device_tube, device.path())
        self.info("adding device %s to connection: %s",
                device.get_markup_name(), self.device_tube)

        for service in device.services:
            if getattr(service,'NOT_FOR_THE_TUBES', False):
                continue
            service.add_to_connection(self.service_tube, service.path)


    def _media_server_removed(self, udn):
        for device in self.coherence.dbus.devices.values():
            if udn == device.device.get_id():
                if self.allowed_devices != None and device.uuid not in self.allowed_devices:
                    # the device is not allowed, no reason to
                    # disconnect from the tube to which it wasn't
                    # connected in the first place anyway
                    return
                device.remove_from_connection(self.device_tube, device.path())
                self.info("remove_from_connection: %s" % device.get_friendly_name())
                for service in device.services:
                    if getattr(service,'NOT_FOR_THE_TUBES', False):
                        continue
                    service.remove_from_connection(self.service_tube, service.path)
                return

    def post_tube_offer(self, tube, tube_conn):
        service = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]
        if service == BUS_NAME:
            self.coherence.dbus.add_to_connection(tube_conn, OBJECT_PATH)
            self.coherence_tube = tube_conn
        elif service == DEVICE_IFACE:
            self.device_tube = tube_conn
        elif service == SERVICE_IFACE:
            self.service_tube = tube_conn

        if not self.announce_done and None not in (self.coherence_tube,
                                                   self.device_tube,
                                                   self.service_tube):
            self.announce_done = True
            allowed_device_types = [u'urn:schemas-upnp-org:device:MediaServer:2',
                                    u'urn:schemas-upnp-org:device:MediaServer:1']
            devices = self.coherence.dbus.devices.values()
            for device in devices:
                if device.get_device_type() in allowed_device_types:
                    self._register_device(device)

            bus = self.coherence.dbus.bus
            self._ms_detected_match = bus.add_signal_receiver(self._media_server_found,
                                                              "UPnP_ControlPoint_MediaServer_detected")
            self._ms_removed_match = bus.add_signal_receiver(self._media_server_removed,
                                                             "UPnP_ControlPoint_MediaServer_removed")

    def close_tubes(self):
        if self._ms_detected_match:
            self._ms_detected_match.remove()
            self._ms_detected_match = None
        if self._ms_removed_match:
            self._ms_removed_match.remove()
            self._ms_removed_match = None
        return tube.TubePublisherMixin.close_tubes(self)

class MirabeauTubePublisherConsumer(MirabeauTubePublisherMixin,
                                    mirabeau_tube_consumer.MirabeauTubeConsumerMixin,
                                    client.Client):
    logCategory = "mirabeau_tube_publisher"

    def __init__(self, manager, protocol, account, muc_id, conference_server, tubes_to_offer,
                 application, allowed_devices, found_peer_callback=None,
                 disapeared_peer_callback=None, got_devices_callback=None):
        MirabeauTubePublisherMixin.__init__(self, tubes_to_offer, application,
                                            allowed_devices)
        mirabeau_tube_consumer.MirabeauTubeConsumerMixin.__init__(self,
                                                                  found_peer_callback=found_peer_callback,
                                                                  disapeared_peer_callback=disapeared_peer_callback,
                                                                  got_devices_callback=got_devices_callback)
        client.Client.__init__(self, manager, protocol, account, muc_id, conference_server)

    def got_tube(self, tube):
        client.Client.got_tube(self, tube)
        initiator_handle = tube.props[CHANNEL_INTERFACE + ".InitiatorHandle"]
        if initiator_handle == self.self_handle:
            self.finish_tube_offer(tube)
        else:
            self.accept_tube(tube)

    def tube_opened(self, tube):
        tube_conn = super(MirabeauTubePublisherConsumer, self).tube_opened(tube)
        initiator_handle = tube.props[CHANNEL_INTERFACE + ".InitiatorHandle"]
        if initiator_handle == self.self_handle:
            self.post_tube_offer(tube, tube_conn)
        else:
            self.post_tube_accept(tube, tube_conn, initiator_handle)
        return tube_conn

    def stop(self):
        MirabeauTubePublisherMixin.close_tubes(self)
        return client.Client.stop(self)
