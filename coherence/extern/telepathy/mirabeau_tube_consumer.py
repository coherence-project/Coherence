from telepathy.interfaces import CHANNEL_TYPE_DBUS_TUBE, CONN_INTERFACE, \
     CHANNEL_INTERFACE

from coherence.extern.telepathy import tube
from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE, SERVICE_IFACE
from coherence import dbus_service

class MirabeauTubeConsumer(tube.TubeConsumer):
    logCategory = "mirabeau_tube_consumer"

    def __init__(self, manager, protocol, account, muc_id,
                 found_peer_callback=None, disapeared_peer_callback=None,
                 got_devices_callback=None, existing_client=False):
        super(MirabeauTubeConsumer, self).__init__(manager, protocol, account,
                                                   muc_id, existing_client=existing_client,
                                                   found_peer_callback=found_peer_callback,
                                                   disapeared_peer_callback=disapeared_peer_callback)
        self.got_devices_callback = got_devices_callback
        self.info("MirabeauTubeConsumer created")
        self._coherence_tubes = {}

    def pre_accept_tube(self, tube):
        # TODO: reimplement me
        ## initiator = tube.props["org.freedesktop.Telepathy.Channel.InitiatorHandle"]
        ## return initiator in self.roster
        return True

    def tube_opened(self, tube):
        tube_conn = super(MirabeauTubeConsumer, self).tube_opened(tube)
        service = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]
        initiator_handle = tube.props[CHANNEL_INTERFACE + ".InitiatorHandle"]

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

    def announce(self, initiator_handle):
        service_name = BUS_NAME
        pontoon_tube = self._coherence_tubes[initiator_handle][service_name]

        def cb(participants, removed):
            if participants:
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
        pontoon = pontoon_tube.get_object(initiator_bus_name, OBJECT_PATH)
        pontoon_devices = pontoon.get_devices()
        self.info("%r devices registered in remote pontoon", len(pontoon_devices))
        for device_dict in pontoon_devices:
            device_path = device_dict["path"]
            self.info("getting object at %r from %r", device_path,
                       initiator_bus_name)
            proxy = device_tube.get_object(initiator_bus_name, device_path)
            try:
                infos = proxy.get_info(dbus_interface=DEVICE_IFACE)
            except Exception, exc:
                self.warning(exc)
                continue
            service_proxies = []
            for service_path in device_dict["services"]:
                service_proxy = service_tube.get_object(initiator_bus_name,
                                                        service_path)
                service_proxies.append(service_proxy)
            proxy.services = service_proxies
            devices.append(proxy)
        self.got_devices_callback(devices)
