# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009 Philippe Normand <phil@base-art.net>

from telepathy.interfaces import CHANNEL_INTERFACE, CONNECTION_INTERFACE_REQUESTS, \
     CHANNEL_TYPE_DBUS_TUBE
from telepathy.constants import CONNECTION_HANDLE_TYPE_ROOM, \
     SOCKET_ACCESS_CONTROL_CREDENTIALS

from coherence.extern.telepathy.client import Client

class TubePublisherMixin(object):

    def __init__(self, tubes_to_offer):
        self._tubes_to_offer = tubes_to_offer

    def muc_joined(self):
        self.info("muc joined. Offering the tubes")

        for interface in self._tubes_to_offer.keys():
            self.conn[CONNECTION_INTERFACE_REQUESTS].CreateChannel({
                CHANNEL_INTERFACE + ".ChannelType": CHANNEL_TYPE_DBUS_TUBE,
                CHANNEL_INTERFACE + ".TargetHandleType": CONNECTION_HANDLE_TYPE_ROOM,
                CHANNEL_INTERFACE + ".TargetID": self.muc_id,
                CHANNEL_TYPE_DBUS_TUBE + ".ServiceName": interface})

    def got_tube(self, tube):
        super(TubePublisherMixin, self).got_tube(tube)
        initiator_handle = tube.props[CHANNEL_INTERFACE + ".InitiatorHandle"]
        if initiator_handle == self.self_handle:
            self.finish_tube_offer(tube)

    def finish_tube_offer(self, tube):
        self.info("offering my tube located at %r", tube.object_path)
        service_name = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]
        params = self._tubes_to_offer[service_name]
        params["initiator"] = self.account["account"]
        address = tube[CHANNEL_TYPE_DBUS_TUBE].Offer(params,
                                                     SOCKET_ACCESS_CONTROL_CREDENTIALS)
        tube.local_address = address
        self.info("local tube address: %r", address)

class TubePublisher(TubePublisherMixin, Client):
    logCategory = "tube_publisher"

    def __init__(self, manager, protocol, account, muc_id, tubes_to_offer):
        TubePublisherMixin.__init__(self, tubes_to_offer)
        Client.__init__(self, manager, protocol, account, muc_id)


class TubeConsumerMixin(object):
    logCategory = "tube_consumer"

    def __init__(self, found_peer_callback=None, disapeared_peer_callback=None):
        self.found_peer_callback = found_peer_callback
        self.disapeared_peer_callback = disapeared_peer_callback

    def got_tube(self, tube):
        super(TubeConsumerMixin, self).got_tube(tube)
        self.accept_tube(tube)

    def accept_tube(self, tube):
        if self.pre_accept_tube(tube):
            self.info("accepting tube %r", tube.object_path)
            tube_iface = tube[CHANNEL_TYPE_DBUS_TUBE]
            tube.local_address = tube_iface.Accept(SOCKET_ACCESS_CONTROL_CREDENTIALS)
        else:
            self.warning("tube %r not allowed", tube)

    def pre_accept_tube(self, tube):
        return True

    def tube_closed(self, tube):
        self.disapeared_peer_callback(tube)
        super(TubeConsumerMixin, self).tube_closed(tube)

class TubeConsumer(TubeConsumerMixin, Client):
    logCategory = "tube_consumer"

    def __init__(self, manager, protocol,
                 account, muc_id, found_peer_callback=None,
                 disapeared_peer_callback=None):
        TubeConsumerMixin.__init__(self, found_peer_callback=found_peer_callback,
                                   disapeared_peer_callback=disapeared_peer_callback)
        Client.__init__(self, manager, protocol, account, muc_id)
