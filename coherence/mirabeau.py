# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009 Philippe Normand <phil@base-art.net>

from telepathy.interfaces import CONN_MGR_INTERFACE, ACCOUNT_MANAGER, ACCOUNT
import dbus

from coherence.dbus_constants import BUS_NAME, DEVICE_IFACE, SERVICE_IFACE
from coherence.extern.telepathy.mirabeau_tube_publisher import MirabeauTubePublisherConsumer
from coherence.tube_service import TubeDeviceProxy
from coherence import log

class Mirabeau(log.Loggable):
    logCategory = "mirabeau"

    def __init__(self, config, coherence_instance):
        log.Loggable.__init__(self)
        self._tube_proxies = []
        self._coherence = coherence_instance

        chatroom = config['chatroom']
        manager = config['manager']
        protocol = config['protocol']

        # account dict keys are different for each protocol so we
        # assume the user gave the right account parameters depending
        # on the specified protocol.
        account = config['account']

        if isinstance(account, basestring):
            bus = dbus.SessionBus()
            account_obj = bus.get_object(ACCOUNT_MANAGER, account)
            account = account_obj.Get(ACCOUNT, 'Parameters')

        # FIXME: why isn't this info advertized ?
        if manager == "gabble" and "fallback-conference-server" not in account:
            account["fallback-conference-server"] = "conference.jabber.org"

        try:
            allowed_devices = config["allowed_devices"].split(",")
        except KeyError:
            allowed_devices = None
        tubes_to_offer = {BUS_NAME: {}, DEVICE_IFACE: {}, SERVICE_IFACE: {}}

        callbacks = dict(found_peer_callback=self.found_peer,
                         disapeared_peer_callback=self.disapeared_peer,
                         got_devices_callback=self.got_devices)
        self._tube_publisher = MirabeauTubePublisherConsumer(manager, protocol,
                                                             account, chatroom,
                                                             tubes_to_offer,
                                                             self._coherence,
                                                             allowed_devices,
                                                             **callbacks)

    def found_peer(self, peer):
        print "found", peer

    def disapeared_peer(self, peer):
        print "disapeared", peer

    def got_devices(self, devices):
        external_address = self._coherence.external_address
        for device in devices:
            uuid = device.get_id()
            print "MIRABEAU found:", uuid
            self._tube_proxies.append(TubeDeviceProxy(self._coherence, device,
                                                      external_address))

    def start(self):
        self._tube_publisher.start()

    def stop(self):
        self._tube_publisher.stop()
