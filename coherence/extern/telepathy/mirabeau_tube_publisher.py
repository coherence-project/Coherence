
import telepathy

from coherence.extern.telepathy import tube
from coherence.dbus_constants import BUS_NAME, OBJECT_PATH

class MirabeauTubePublisher(tube.TubePublisher):
    def __init__(self, connection, chatroom, tubes_to_offer, application):
        super(MirabeauTubePublisher, self).__init__(connection, chatroom,
                                                    tubes_to_offer)
        self.coherence = application

    def tube_opened(self, id):
        super(MirabeauTubePublisher, self).tube_opened(id)
        self.coherence.dbus.add_to_connection(self.tube_conn, OBJECT_PATH)
        for device in self.coherence.dbus.devices:
            device.add_to_connection(self.tube_conn, device.path())
            for service in device.services:
                service.add_to_connection(self.tube_conn, service.path)

    def device_found(self, device):
        name = '%s (%s)' % (device.get_friendly_name(),
                            ':'.join(device.get_device_type().split(':')[3:5]))
        print "device found: %s" % name
        # TODO: call add_to_connection() to publish device in the tube
        #device.add_to_connection(self.tube_conn, device.path())

    def device_removed(self, usn):
        pass
