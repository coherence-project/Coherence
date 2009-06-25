
import telepathy
import gobject

from telepathy.interfaces import CHANNEL_TYPE_DBUS_TUBE

from coherence.extern.telepathy import tube, client, mirabeau_tube_consumer
from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE, SERVICE_IFACE

class MirabeauTubePublisherConsumer(tube.TubePublisher):
    def __init__(self, manager, protocol,
                 account, muc_id, tubes_to_offer, application, allowed_devices,
                 found_peer_callback=None,
                 disapeared_peer_callback=None, got_devices_callback=None):
        super(MirabeauTubePublisherConsumer, self).__init__(manager, protocol,
                                                            account, muc_id, tubes_to_offer)
        self.found_peer_callback = found_peer_callback
        self.disapeared_peer_callback=disapeared_peer_callback
        self._consumer = None

        self.coherence = application
        self.allowed_devices = allowed_devices
        self.got_devices_callback = got_devices_callback
        self.coherence_tube = None
        self.device_tube = None
        self.service_tube = None

    def ready(self):
        self.info("publisher ready, now starting the consumer")
        self._consumer = mirabeau_tube_consumer.MirabeauTubeConsumer(None, None, {}, self.muc_id,
                                                                     found_peer_callback=self.found_peer_callback,
                                                                     disapeared_peer_callback=self.disapeared_peer_callback,
                                                                     got_devices_callback=self.got_devices_callback,
                                                                     existing_connection=self)
        self._consumer.start()

    def tube_opened(self, tube):
        tube_conn = super(MirabeauTubePublisherConsumer, self).tube_opened(tube)
        service = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]
        if service == BUS_NAME:
            self.coherence.dbus.add_to_connection(tube_conn, OBJECT_PATH)
            self.coherence_tube = tube_conn
        elif service == DEVICE_IFACE:
            self.device_tube = tube_conn
        elif service == SERVICE_IFACE:
            self.service_tube = tube_conn

        if None not in (self.coherence_tube,
                         self.device_tube, self.service_tube):
            for device in self.coherence.dbus.devices.values():
                self._register_device(device)
            self.coherence.dbus.bus.add_signal_receiver(self._media_server_found,
                                                        "UPnP_ControlPoint_MediaServer_detected")
            self.coherence.dbus.bus.add_signal_receiver(self._media_server_removed,
                                                        "UPnP_ControlPoint_MediaServer_removed")
            self.ready()

        return tube_conn

    def _media_server_found(self, infos, udn):
        uuid = udn[5:]
        for device in self.coherence.dbus.devices.values():
            if device.uuid == uuid:
                self._register_device(device)
                return

    def _register_device(self, device):
        name = '%s (%s)' % (device.get_friendly_name(),
                            ':'.join(device.get_device_type().split(':')[3:5]))
        self.info("device found: %s" % name)
        if self.allowed_devices != None and device.uuid not in self.allowed_devices:
            self.debug("device not allowed: %r", device.uuid)
            return
        self.debug("adding device %r to connection: %s", name, self.device_tube)
        device.add_to_connection(self.device_tube, device.path())
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
                self.debug("remove_from_connection: %s" % device.get_friendly_name())
                for service in device.services:
                    service.remove_from_connection(self.service_tube, service.path)
                return
