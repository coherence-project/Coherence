from twisted.internet import glib2reactor
glib2reactor.install()

import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import sys

from coherence.base import Coherence
from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE
from coherence.tube_service import TubeDeviceProxy
from coherence.extern.telepathy.mirabeau_tube_consumer import MirabeauTubeConsumer
from coherence.extern.telepathy import connect

class TubeProxy(object):

    def __init__(self):
        self.coherence = Coherence({'logmode':'error','serverport':'30021'})
        # FIXME: hardcoded stuff
        nickname = "client2"
        conn = connect.tp_connect("salut", "local-xmpp",
                                  {"first-name": nickname,
                                   "last-name": "",
                                   "published-name": nickname, "nickname": nickname})
        cli = MirabeauTubeConsumer(conn, "UPnPProxy",
                                   found_peer_callback=self.found_peer,
                                   disapeared_peer_callback=self.disappeared_peer,
                                   got_devices_callback=self.got_devices)
        reactor.addSystemEventTrigger( 'before', 'shutdown', cli.stop)

        cli.start()

    def found_peer(self,peer):
        print "found peer"
        pass

    def disappeared_peer(self,peer):
        pass

    def got_devices(self,devices):
        for device in devices:
            try:
                name = '%s (%s)' % (device.get_friendly_name(),
                                    ':'.join(device.get_device_type().split(':')[3:5]))
            except:
                continue
            print "got_devices", name, device.get_id()
            #
            #print "  >",
            if device.get_id() == "uuid:d5a96478-ba4b-4bf8-813b-250755d8edde":
                print "found it"
                TubeDeviceProxy(self.coherence,device)
            if device.get_friendly_name() == "Phil":
                for service in device.services:
                    if "Browse" in service.get_available_actions():
                        print service.action("browse", {'object_id':'0', 'process_result': 'no',
                                             'starting_index':'0','requested_count': '5'})


def run():
    t = TubeProxy()

if __name__ == "__main__":
    from twisted.internet import reactor

    reactor.callWhenRunning(run)
    reactor.run()