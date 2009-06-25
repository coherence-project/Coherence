from telepathy.interfaces import CONN_INTERFACE, CHANNEL_INTERFACE_GROUP, \
     CHANNEL_TYPE_TUBES, CONNECTION_INTERFACE_ALIASING, CHANNEL_TYPE_TEXT, \
     CHANNEL_INTERFACE, CONNECTION_INTERFACE_REQUESTS, CHANNEL_TYPE_DBUS_TUBE
from telepathy.constants import TUBE_STATE_LOCAL_PENDING
from telepathy.constants import CONNECTION_HANDLE_TYPE_CONTACT
from telepathy.constants import TUBE_TYPE_DBUS, TUBE_TYPE_STREAM
from telepathy.constants import SOCKET_ADDRESS_TYPE_IPV4, \
     SOCKET_ACCESS_CONTROL_LOCALHOST
from telepathy.constants import (
        CONNECTION_HANDLE_TYPE_CONTACT, CONNECTION_HANDLE_TYPE_LIST,
        CONNECTION_HANDLE_TYPE_ROOM, CONNECTION_STATUS_CONNECTED,
        CONNECTION_STATUS_DISCONNECTED, CONNECTION_STATUS_CONNECTING,
        SOCKET_ACCESS_CONTROL_CREDENTIALS,
        TUBE_CHANNEL_STATE_LOCAL_PENDING, TUBE_CHANNEL_STATE_REMOTE_PENDING,
        TUBE_CHANNEL_STATE_OPEN, TUBE_CHANNEL_STATE_NOT_OFFERED)

import telepathy

from coherence.extern.telepathy.client import Client

class TubePublisherMixin(object):
    logCategory = "tube_publisher"

    def __init__(self, tubes_to_offer):
        self._tubes_to_offer = tubes_to_offer

    def muc_joined(self):
        super(TubePublisherMixin, self).muc_joined()
        self.info("muc joined. Offering the tubes")

        for interface in self._tubes_to_offer.keys():
            self.conn[CONNECTION_INTERFACE_REQUESTS].CreateChannel({
                CHANNEL_INTERFACE + ".ChannelType": CHANNEL_TYPE_DBUS_TUBE,
                CHANNEL_INTERFACE + ".TargetHandleType": CONNECTION_HANDLE_TYPE_ROOM,
                CHANNEL_INTERFACE + ".TargetID": self.muc_id,
                CHANNEL_TYPE_DBUS_TUBE + ".ServiceName": interface})

    def got_tube(self, tube):
        super(TubePublisherMixin, self).got_tube(tube)
        service_name = tube.props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]
        params = self._tubes_to_offer[service_name]
        try:
            address = tube[CHANNEL_TYPE_DBUS_TUBE].Offer(params,
                                                         SOCKET_ACCESS_CONTROL_CREDENTIALS)
        except:
            pass
        else:
            tube.local_address = address


class TubePublisher(TubePublisherMixin, Client):
    def __init__(self, manager, protocol,
                 account, muc_id, tubes_to_offer):
        TubePublisherMixin.__init__(self, tubes_to_offer)
        Client.__init__(self, manager, protocol,
                        account, muc_id)

class TubeConsumerMixin(object):
    logCategory = "tube_consumer"

    def __init__(self, found_peer_callback=None, disapeared_peer_callback=None):
        self.found_peer_callback = found_peer_callback
        self.disapeared_peer_callback = disapeared_peer_callback

    def got_tube(self, tube):
        super(TubeConsumerMixin, self).got_tube(tube)
        if self.pre_accept_tube(tube):
            self.debug("accepting tube %r", tube)
            tube_iface = tube[CHANNEL_TYPE_DBUS_TUBE]
            tube.local_address = tube_iface.Accept(SOCKET_ACCESS_CONTROL_CREDENTIALS)
        else:
            self.warning("tube %r not allowed", tube)

    def pre_accept_tube(self, tube):
        return True

    def _create_peer_remote_object(self, peer, interface):
        pass

    def _create_peer_object_proxy(self, peer, interface):
        pass

    def tube_closed_cb (self, tube):
        self.disapeared_peer_callback(tube)
        super(TubeConsumerMixin, self).tube_closed_cb(tube)

class TubeConsumer(TubeConsumerMixin, Client):

    def __init__(self, manager, protocol,
                 account, muc_id, found_peer_callback=None,
                 disapeared_peer_callback=None, existing_connection=False):
        TubeConsumerMixin.__init__(self, found_peer_callback=found_peer_callback,
                                   disapeared_peer_callback=disapeared_peer_callback)
        Client.__init__(self, manager, protocol,
                        account, muc_id, existing_connection=existing_connection)

