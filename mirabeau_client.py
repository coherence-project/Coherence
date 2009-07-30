import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import sys
import gobject

from coherence.dbus_constants import BUS_NAME, OBJECT_PATH, DEVICE_IFACE
from coherence.extern.telepathy.mirabeau_tube_consumer import MirabeauTubeConsumer
from coherence.extern.telepathy import connect
from coherence import log
log.init()

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
        print "got %d devices" % len(devices)
        for device in devices:
            print "got_devices", device.get_markup_name(), device.get_id()
            #
            #print "  >",
            if device.get_id() == "uuid:d5a96478-ba4b-4bf8-813b-250755d8edde":
                print "found it"
            if device.get_friendly_name() == "Phil":
                for service in device.services:
                    try:
                        actions = service.get_available_actions()
                    except:
                        actions = []
                    if "Browse" in actions:
                        print service.action("browse", {'object_id':'0', 'process_result': 'no',
                                             'starting_index':'0','requested_count': '5'})

    # FIXME: hardcoded stuff
    nickname = "client2"
    conn = connect.tp_connect("salut", "local-xmpp",
                              {"first-name": nickname,
                               "last-name": "",
                               "published-name": nickname, "nickname": nickname})
    cli = MirabeauTubeConsumer(conn, "Mirabeau",
                               found_peer_callback=found_peer,
                               disapeared_peer_callback=disappeared_peer,
                               got_devices_callback=got_devices)
    cli.start()

    try:
        loop.run()
    finally:
        cli.stop()

if __name__ == "__main__":
    sys.exit(run())
