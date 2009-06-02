import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import sys
import gobject

from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE
from coherence.extern.telepathy.mirabeau_tube_consumer import MirabeauTubeConsumer
from coherence.extern.telepathy import connect

def run(args=None):
    if not args:
        args = sys.argv[1:]

    loop = gobject.MainLoop()

    def found_peer(peer):
        print "found peer"
        pass

    def disappeared_peer(peer):
        pass

    def got_devices(devices):
        for device in devices:
            try:
                name = '%s (%s)' % (device.get_friendly_name(),
                                    ':'.join(device.get_device_type().split(':')[3:5]))
            except:
                continue
            print name
            #
            #print "  >",
            if device.get_friendly_name() == "Phil":
                for service in device.services:
                    if "Browse" in service.get_available_actions():
                        print service.action("browse", {'object_id':'0', 'process_result': 'no',
                                             'starting_index':'0','requested_count': '5'})

    # FIXME: hardcoded stuff
    nickname = "client2"
    conn = connect.tp_connect("salut", "local-xmpp",
                              {"first-name": nickname,
                               "last-name": "",
                               "published-name": nickname, "nickname": nickname})
    cli = MirabeauTubeConsumer(conn, "UPnPProxy",
                               found_peer_callback=found_peer,
                               disappeared_peer_callback=disappeared_peer,
                               got_devices_callback=got_devices)
    cli.start()

    try:
        loop.run()
    finally:
        cli.stop()

if __name__ == "__main__":
    sys.exit(run())
