
import gobject
from dbus import PROPERTIES_IFACE

from telepathy.interfaces import CHANNEL_INTERFACE, CONNECTION_INTERFACE_REQUESTS, \
     CHANNEL_TYPE_DBUS_TUBE
from telepathy.constants import CONNECTION_HANDLE_TYPE_ROOM, \
     SOCKET_ACCESS_CONTROL_CREDENTIALS

from telepathy.interfaces import CHANNEL_INTERFACE_TUBE, CHANNEL_TYPE_DBUS_TUBE, \
     CHANNEL_INTERFACE
from telepathy.constants import TUBE_CHANNEL_STATE_LOCAL_PENDING

from coherence.extern.telepathy import client
from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE, SERVICE_IFACE
from coherence import dbus_service

class MirabeauTubePublisherConsumer(client.Client):
    logCategory = "mirabeau_tube_publisher"

    def __init__(self, manager, protocol, account, muc_id, tubes_to_offer,
                 application, allowed_devices, found_peer_callback=None,
                 disapeared_peer_callback=None, got_devices_callback=None):
        super(MirabeauTubePublisherConsumer, self).__init__(manager, protocol,
                                                            account, muc_id)
        self._tubes_to_offer = tubes_to_offer
        self.found_peer_callback = found_peer_callback
        self.disapeared_peer_callback=disapeared_peer_callback
        self.coherence = application
        self.allowed_devices = allowed_devices
        self.got_devices_callback = got_devices_callback
        self.coherence_tube = None
        self.device_tube = None
        self.service_tube = None
        self.announce_done = False

        self._coherence_tubes = {}


    def muc_joined(self):
        super(MirabeauTubePublisherConsumer, self).muc_joined()
        self.info("muc joined. Offering the tubes")

        for interface in self._tubes_to_offer.keys():
            self.conn[CONNECTION_INTERFACE_REQUESTS].CreateChannel({
                CHANNEL_INTERFACE + ".ChannelType": CHANNEL_TYPE_DBUS_TUBE,
                CHANNEL_INTERFACE + ".TargetHandleType": CONNECTION_HANDLE_TYPE_ROOM,
                CHANNEL_INTERFACE + ".TargetID": self.muc_id,
                CHANNEL_TYPE_DBUS_TUBE + ".ServiceName": interface})

    def got_tube(self, tube):
        super(MirabeauTubePublisherConsumer, self).got_tube(tube)
        initiator_handle = tube.props[CHANNEL_INTERFACE + ".InitiatorHandle"]
        if initiator_handle == self.self_handle:
            self.info("offering my tube located at %r", tube.object_path)
            service_name = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]
            params = self._tubes_to_offer[service_name]
            address = tube[CHANNEL_TYPE_DBUS_TUBE].Offer(params,
                                                         SOCKET_ACCESS_CONTROL_CREDENTIALS)
            tube.local_address = address
            self.info("local tube address: %r", address)
        elif self.pre_accept_tube(tube):
            self.info("accepting tube %r", tube.object_path)
            tube_iface = tube[CHANNEL_TYPE_DBUS_TUBE]
            tube.local_address = tube_iface.Accept(SOCKET_ACCESS_CONTROL_CREDENTIALS)
        else:
            self.warning("tube %r not allowed", tube)

    def pre_accept_tube(self, tube):
        return True

    def tube_opened(self, tube):
        tube_conn = super(MirabeauTubePublisherConsumer, self).tube_opened(tube)
        service = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]
        initiator_handle = tube.props[CHANNEL_INTERFACE + ".InitiatorHandle"]
        if initiator_handle == self.self_handle:
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
                for device in self.coherence.dbus.devices.values():
                    self._register_device(device)
                self.coherence.dbus.bus.add_signal_receiver(self._media_server_found,
                                                            "UPnP_ControlPoint_MediaServer_detected")
                self.coherence.dbus.bus.add_signal_receiver(self._media_server_removed,
                                                            "UPnP_ControlPoint_MediaServer_removed")
        else:
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

        return tube_conn

    def tube_closed_cb(self, tube):
        self.disapeared_peer_callback(tube)
        super(MirabeauTubePublisherConsumer, self).tube_closed_cb(tube)

    def _media_server_found(self, infos, udn):
        uuid = udn[5:]
        for device in self.coherence.dbus.devices.values():
            if device.uuid == uuid:
                self._register_device(device)
                return

    def _register_device(self, device):
        name = '%s (%s)' % (device.get_friendly_name(),
                            ':'.join(device.get_device_type().split(':')[3:5]))
        if self.allowed_devices != None and device.uuid not in self.allowed_devices:
            self.info("device not allowed: %r", device.uuid)
            return
        device.add_to_connection(self.device_tube, device.path())
        self.info("adding device %s to connection: %s", name, self.device_tube)
        for service in device.services:
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
                    service.remove_from_connection(self.service_tube, service.path)
                return

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
        pontoon.get_devices_async(reply_handler=got_devices,
                                  error_handler=got_error)
