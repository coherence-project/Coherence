from telepathy.interfaces import CHANNEL_TYPE_DBUS_TUBE, CONN_INTERFACE
from telepathy.constants import CONNECTION_HANDLE_TYPE_CONTACT

from coherence.extern.telepathy import tube
from coherence.extern.telepathy import client
from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE, SERVICE_IFACE
from coherence import dbus_service


class MirabeauTubeConsumerMixin(tube.TubeConsumerMixin):
    pontoon = None
    device_peer = None
    service_peer = None
    initial_announce_done = False

    def __init__(self, found_peer_callback=None,
                 disapeared_peer_callback=None, got_devices_callback=None):
        super(MirabeauTubeConsumerMixin, self).__init__(found_peer_callback=found_peer_callback,
                                                        disapeared_peer_callback=disapeared_peer_callback)
        self.got_devices_callback = got_devices_callback
        self.debug("MirabeauTubeConsumer __init__")
        self.pontoon_tube = None
        self.device_tube = None
        self.service_tube = None
        self.initial_announce_done = False

    def pre_accept_tube(self, tube):
        # TODO: reimplement me
        ## initiator = tube.props["org.freedesktop.Telepathy.Channel.InitiatorHandle"]
        ## return initiator in self.roster
        return True

    def tube_opened(self, tube):
        tube_conn = super(MirabeauTubeConsumerMixin, self).tube_opened(tube)
        service = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]
        if service == BUS_NAME:
            tube.remote_object = dbus_service.DBusPontoon(None, tube_conn)
            self.pontoon_tube = tube
        elif service == DEVICE_IFACE:
            tube.remote_object = dbus_service.DBusDevice(None, tube_conn)
            self.device_tube = tube
        elif service == SERVICE_IFACE:
            tube.remote_object = dbus_service.DBusService(None, None, tube_conn)
            self.service_tube = tube

        if not self.initial_announce_done:
            if None not in (self.pontoon_tube, self.service_tube, self.device_tube):
                self.announce()
                self.initial_announce_done = True

        return tube_conn

    def announce(self):
        initiator = self.pontoon_tube.props["org.freedesktop.Telepathy.Channel.InitiatorHandle"]
        service_name = self.pontoon_tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]

        def cb(participants, removed):
            if participants:
                initiator_contact = participants[initiator]
                self.info("contact %r for service %r", initiator_contact,
                          service_name)
                if initiator_contact is not None:
                    self.found_devices(initiator_contact)

        self.pontoon_tube.remote_object.tube.watch_participants(cb)

    def found_devices(self, initiator_contact):
        devices = []
        device_tube = self.device_tube.remote_object.tube
        service_tube = self.service_tube.remote_object.tube
        pontoon = self.pontoon_tube.remote_object.tube.get_object(initiator_contact,
                                                                  OBJECT_PATH)
        pontoon_devices = pontoon.get_devices()
        self.debug("%r devices registered in remote pontoon", len(pontoon_devices))
        for device_dict in pontoon_devices:
            device_path = device_dict["path"]
            self.debug("Getting object at %r from %r", device_path,
                       initiator_contact)
            proxy = device_tube.get_object(initiator_contact, device_path)
            try:
                infos = proxy.get_info(dbus_interface=DEVICE_IFACE)
            except Exception, exc:
                self.warning(exc)
                continue
            service_proxies = []
            for service_path in device_dict["services"]:
                service_proxy = service_tube.get_object(initiator_contact,
                                                        service_path)
                service_proxies.append(service_proxy)
            proxy.services = service_proxies
            devices.append(proxy)
        self.got_devices_callback(devices)

class MirabeauTubeConsumer(MirabeauTubeConsumerMixin, client.Client):

    def __init__(self, manager, protocol,
                 account, muc_id, found_peer_callback=None,
                 disapeared_peer_callback=None, got_devices_callback=None,
                 existing_connection=False):
        MirabeauTubeConsumerMixin.__init__(self, found_peer_callback=found_peer_callback,
                                           disapeared_peer_callback=disapeared_peer_callback,
                                           got_devices_callback=got_devices_callback)
        client.Client.__init__(self, manager, protocol,
                               account, muc_id, existing_connection=existing_connection)
