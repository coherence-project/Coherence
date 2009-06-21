from telepathy.interfaces import CONN_INTERFACE, CHANNEL_INTERFACE_GROUP, \
     CHANNEL_TYPE_TUBES, CONNECTION_INTERFACE_ALIASING, CHANNEL_TYPE_TEXT, \
     CHANNEL_INTERFACE
from telepathy.constants import TUBE_STATE_LOCAL_PENDING
from telepathy.constants import CONNECTION_HANDLE_TYPE_CONTACT
from telepathy.constants import TUBE_TYPE_DBUS, TUBE_TYPE_STREAM
from telepathy.constants import SOCKET_ADDRESS_TYPE_IPV4, \
     SOCKET_ACCESS_CONTROL_LOCALHOST

import telepathy

from coherence.extern.telepathy.client import Client, DBUS_PROPERTIES

class TubePublisherMixin(object):
    logCategory = "tube_publisher"

    def __init__(self, tubes_to_offer):
        self._tubes_to_offer = tubes_to_offer

    def muc_joined(self):
        super(TubePublisherMixin, self).muc_joined()
        self.info("muc joined. Offering the tubes")

        conn_obj = self.conn[CONN_INTERFACE]
        self_handle = conn_obj.GetSelfHandle()
        my_name = conn_obj.InspectHandles(CONNECTION_HANDLE_TYPE_CONTACT,
                                          [self_handle])[0]

        tubes_obj = self.channel_tubes[CHANNEL_TYPE_TUBES]
        for interface, params in self._tubes_to_offer.iteritems():
            # FIXME: storing my name in params... This could be
            # avoided by correctly retrieving tube offerrer from
            # client side
            params["initiator"] = my_name
            tubes_obj.OfferDBusTube(interface, params)

    def offer_stream_tube(self, service, params, socket_address):
        tubes_obj = self.channel_tubes[CHANNEL_TYPE_TUBES]
        tubes_obj.OfferStreamTube(service,
                                  params, SOCKET_ADDRESS_TYPE_IPV4,
                                  socket_address,
                                  SOCKET_ACCESS_CONTROL_LOCALHOST, "")

class TubePublisher(TubePublisherMixin, Client):
    def __init__(self, connection, muc_id, tubes_to_offer):
        TubePublisherMixin.__init__(self, tubes_to_offer)
        Client.__init__(self, connection, muc_id)

class Peer:

    def __init__(self, tube_id, initiator, service, tube_type, params):
        self.tube_id = tube_id
        self.initiator = initiator
        self.initiator_contact = None
        self.service = service
        self.tube_type = tube_type
        self.params = params
        self.remote_object = None
        self.remote_object_proxy = None


class TubeConsumerMixin(object):
    logCategory = "tube_consumer"

    def __init__(self, found_peer_callback=None, disapeared_peer_callback=None):
        self.found_peer_callback = found_peer_callback
        self.disapeared_peer_callback = disapeared_peer_callback
        self._peers = {}

    def new_tube_cb(self, id, initiator, tube_type, service, params, state):
        peer = Peer(id, initiator, service, tube_type, params)
        self._peers[id] = peer

        super(TubeConsumerMixin, self).new_tube_cb(id, initiator, tube_type, service,
                                                   params, state)
        if state == TUBE_STATE_LOCAL_PENDING:
            can_accept = self.pre_accept_tube(peer)
            if not can_accept:
               self.info("Can't accept tube")
               return
            self.info("accepting tube %r", id)
            tubes_channel = self.channel_tubes[CHANNEL_TYPE_TUBES]
            if tube_type == TUBE_TYPE_DBUS:
                tubes_channel.AcceptDBusTube(id)
            else:
                tubes_channel.AcceptStreamTube(id,
                                               SOCKET_ADDRESS_TYPE_IPV4,
                                               SOCKET_ACCESS_CONTROL_LOCALHOST,
                                               "")

    def pre_accept_tube(self, peer):
        return True

    def _create_peer_remote_object(self, peer, interface):
        pass

    def _create_peer_object_proxy(self, peer, interface):
        pass

    def plug_stream(self, address):
        self.info("tube opened. Clients can connect to %s", address)

    def tube_opened(self, id):
        super(TubeConsumerMixin, self).tube_opened(id)

        peer = self._peers[id]
        service = peer.service
        initiator = peer.initiator
        tube_type = peer.tube_type

        # skip tubes offered by myself
        conn_obj = self.conn[CONN_INTERFACE]
        self_handle = conn_obj.GetSelfHandle()
        my_name = conn_obj.InspectHandles(CONNECTION_HANDLE_TYPE_CONTACT,
                                          [self_handle])[0]
        self.info('initiator: %r myself: %r params: %r' % (initiator, my_name,
                                                           peer.params))
        if "initiator" in peer.params and peer.params["initiator"] == my_name:
            return

        if tube_type == TUBE_TYPE_STREAM:
            channel_obj = self.channel_tubes[CHANNEL_TYPE_TUBES]
            address_type, address = channel_obj.GetStreamTubeSocketAddress(id,
                                                                           byte_arrays=True)
            self.plug_stream(address)
            return

        def find_initiator_contact(contact_list):
            initiator_contact = None
            for contact in contact_list:
                if contact[0] == initiator:
                    initiator_contact = contact[1]
                    name = conn_obj.InspectHandles(CONNECTION_HANDLE_TYPE_CONTACT,
                                                   [initiator])[0]
                    break
            return initiator_contact

        def cb(participants, removed):
            if participants:
                initiator_contact = find_initiator_contact(participants)
                self.info("contact %r for service %r", initiator_contact,
                          service)
                if initiator_contact is not None:
                    peer.initiator_contact = initiator_contact
                    self._create_peer_object_proxy(peer, service)

        self._create_peer_remote_object(peer, service)

        peer.remote_object.tube.watch_participants(cb,
                                                   callback_id="find_initiator")

    def tube_closed_cb (self, id):
        super(TubeConsumerMixin, self).tube_closed_cb(id)
        peer = self._peers[id]
        self.disapeared_peer_callback(peer)
        del self._peers[id]

class TubeConsumer(TubeConsumerMixin, Client):

    def __init__(self, connection, muc_id, found_peer_callback=None,
                 disapeared_peer_callback=None):
        TubeConsumerMixin.__init__(self, found_peer_callback=found_peer_callback,
                                   disapeared_peer_callback=disapeared_peer_callback)
        Client.__init__(self, connection, muc_id)

class TubePublisherConsumer(TubePublisherMixin, TubeConsumerMixin, Client):
    def __init__(self, connection, muc_id, tubes_to_offer, found_peer_callback=None,
                 disapeared_peer_callback=None):
        TubePublisherMixin.__init__(self, tubes_to_offer)
        TubeConsumerMixin.__init__(self, found_peer_callback=found_peer_callback,
                                   disapeared_peer_callback=disapeared_peer_callback)
        Client.__init__(self, connection, muc_id)

    def tube_opened(self, id):
        Client.tube_opened(self, id)
        TubePublisherMixin.tube_opened(self, id)
        TubeConsumerMixin.tube_opened(self, id)
