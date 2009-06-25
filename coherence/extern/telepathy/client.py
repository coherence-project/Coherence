
import dbus.glib
import gobject
import sys
import time
from dbus.service import method, signal, Object
from dbus import  PROPERTIES_IFACE

from telepathy.client import Channel
from telepathy.interfaces import (
        CONN_INTERFACE, CHANNEL_INTERFACE_GROUP, CHANNEL_TYPE_CONTACT_LIST,
        CHANNEL_TYPE_TEXT, CHANNEL_INTERFACE, CONNECTION_INTERFACE_REQUESTS,
        CHANNEL_INTERFACE_TUBE, CHANNEL_TYPE_DBUS_TUBE)
from telepathy.constants import (
        CONNECTION_HANDLE_TYPE_CONTACT, CONNECTION_HANDLE_TYPE_LIST,
        CONNECTION_HANDLE_TYPE_ROOM, CONNECTION_STATUS_CONNECTED,
        CONNECTION_STATUS_DISCONNECTED, CONNECTION_STATUS_CONNECTING,
        SOCKET_ACCESS_CONTROL_CREDENTIALS,
        TUBE_CHANNEL_STATE_LOCAL_PENDING, TUBE_CHANNEL_STATE_REMOTE_PENDING,
        TUBE_CHANNEL_STATE_OPEN, TUBE_CHANNEL_STATE_NOT_OFFERED)

from coherence.extern.telepathy.tubeconn import TubeConnection
from coherence.extern.telepathy.connect import tp_connect
from coherence import log

class Client(log.Loggable):
    logCategory = "tp_client"

    def __init__(self, manager, protocol,
                 account, muc_id, existing_connection=False):
        super(Client, self).__init__()
        self.account = account
        self.existing_connection = existing_connection
        self.channel_text = None
        self._unsent_messages = []
        self._tube_conns = {}
        self._tubes = {}

        if self.existing_connection:
            self.muc_id = self.existing_connection.muc_id
            self.conn = self.existing_connection.conn
            self.ready_cb(self.conn)
        else:
            self.muc_id = "%s@%s" % (muc_id, self.account["fallback-conference-server"])
            self.conn = tp_connect(manager, protocol, account, self.ready_cb)

        conn_obj = self.conn[CONN_INTERFACE]
        conn_obj.connect_to_signal('StatusChanged', self.status_changed_cb)
        conn_obj.connect_to_signal('NewChannels', self.new_channels_cb)

        self.joined = False

    def start(self):
        if not self.existing_connection:
            self.info("connecting")
            self.conn[CONN_INTERFACE].Connect()
            self.info("connected")

    def stop(self):
        if not self.existing_connection:
            try:
                self.conn[CONN_INTERFACE].Disconnect()
            except:
                pass

    def ready_cb(self, conn):
        self.conn[CONNECTION_INTERFACE_REQUESTS].connect_to_signal ("NewChannels",
                                                                    self.new_channels_cb)
        self.self_handle = self.conn[CONN_INTERFACE].GetSelfHandle()
        self.fill_roster()
        self.join_muc()

    def status_changed_cb(self, status, reason):
        self.debug("status changed to %r: %r", status, reason)
        if status == CONNECTION_STATUS_CONNECTING:
            self.info('connecting')
        elif status == CONNECTION_STATUS_CONNECTED:
            self.info('connected')
        elif status == CONNECTION_STATUS_DISCONNECTED:
            self.info('disconnected')


    def fill_roster(self):
        self.debug("Filling up the roster")
        self.roster = {}
        conn_iface = self.conn[CONN_INTERFACE]

        for name in ('subscribe', 'publish', 'hide', 'allow', 'deny', 'known'):
            try:
                chan = self._request_list_channel(name)
            except dbus.DBusException:
                self.debug("'%s' channel is not available" % name)
                continue

            group_iface = chan[CHANNEL_INTERFACE_GROUP]
            current, local_pending, remote_pending = (group_iface.GetAllMembers())
            for member in current:
                contact_id = conn_iface.InspectHandles(CONNECTION_HANDLE_TYPE_CONTACT,
                                                       [member])[0]
                self.roster[contact_id] = name
        self.debug("roster contents: %r", self.roster)

    def _request_list_channel(self, name):
        handle = self.conn[CONN_INTERFACE].RequestHandles(
            CONNECTION_HANDLE_TYPE_LIST, [name])[0]
        return self.conn.request_channel(
            CHANNEL_TYPE_CONTACT_LIST, CONNECTION_HANDLE_TYPE_LIST,
            handle, True)

    def join_muc(self):
        conn_obj = self.conn[CONN_INTERFACE]

        # workaround to be sure that the muc service is fully resolved in
        # Salut.
        if conn_obj.GetProtocol() == "local-xmpp":
            time.sleep(2)

        muc_id = self.muc_id
        self.info("joining MUC %r", muc_id)

        if self.existing_connection:
            self.channel_text = self.existing_connection.channel_text
        else:
            chan_path, props = self.conn[CONNECTION_INTERFACE_REQUESTS].CreateChannel({
                CHANNEL_INTERFACE + ".ChannelType": CHANNEL_TYPE_TEXT,
                CHANNEL_INTERFACE + ".TargetHandleType": CONNECTION_HANDLE_TYPE_ROOM,
                CHANNEL_INTERFACE + ".TargetID": muc_id})

            self.channel_text = Channel(self.conn.dbus_proxy.bus_name, chan_path)

        self.self_handle = self.channel_text[CHANNEL_INTERFACE_GROUP].GetSelfHandle()
        self.channel_text[CHANNEL_INTERFACE_GROUP].connect_to_signal(
                "MembersChanged", self.text_channel_members_changed_cb)

        if self.self_handle in self.channel_text[CHANNEL_INTERFACE_GROUP].GetMembers():
            self.joined = True
            self.muc_joined()


    def new_channels_cb(self, channels):
        for path, props in channels:
            self.debug("new channel with path %r and props %r", path, props)
            if props[CHANNEL_INTERFACE + ".ChannelType"] == CHANNEL_TYPE_DBUS_TUBE:
                tube = Channel(self.conn.dbus_proxy.bus_name, path)

                tube[CHANNEL_INTERFACE_TUBE].connect_to_signal(
                    "TubeChannelStateChanged", lambda state: self.tube_channel_state_changed_cb(tube, state))
                tube[CHANNEL_INTERFACE].connect_to_signal("Closed",
                                                          lambda: self.tube_closed_cb(tube))
                tube.props = props
                self._tubes[path] = tube
                self.got_tube(tube)

    def got_tube(self, tube):
        props = tube.props
        self.debug("got tube with props %r", props)
        initiator_id = props[CHANNEL_INTERFACE + ".InitiatorID"]
        service = props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]

        state = tube[PROPERTIES_IFACE].Get(CHANNEL_INTERFACE_TUBE, 'State')
        tube_state = {TUBE_CHANNEL_STATE_LOCAL_PENDING : 'local pending',\
                      TUBE_CHANNEL_STATE_REMOTE_PENDING : 'remote pending',\
                      TUBE_CHANNEL_STATE_OPEN : 'open',
                      TUBE_CHANNEL_STATE_NOT_OFFERED: 'not offered'}

        self.info("new D-Bus tube offered by %s. Service: %s. State: %s",
                  initiator_id, service, tube_state[state])
        if state == TUBE_CHANNEL_STATE_OPEN:
            self.tube_opened(tube)

    def tube_opened(self, tube):
        tube_path = tube.object_path
        self.info("tube %r opened", tube_path)

        group_iface = self.channel_text[CHANNEL_INTERFACE_GROUP]
        tube_address = tube.local_address
        tube_conn = TubeConnection(self.conn,
                                   tube,
                                   tube_address,
                                   group_iface=group_iface)
        self._tube_conns[tube_path] = tube_conn
        return tube_conn

    def received_cb(self, id, timestamp, sender, type, flags, text):
        channel_obj = self.channel_text[CHANNEL_TYPE_TEXT]
        channel_obj.AcknowledgePendingMessages([id])
        conn_obj = self.conn[telepathy.CONN_INTERFACE]
        contact = conn_obj.InspectHandles(telepathy.HANDLE_TYPE_CONTACT,
                                          [sender])[0]
        self.info("Received message from %s: %s", contact, text)

    def tube_channel_state_changed_cb(self, tube, state):
        if state == TUBE_CHANNEL_STATE_OPEN:
            if "local_address" in dir(tube):
                self.tube_opened(tube)

    def tube_closed_cb (self, tube):
        tube_path = tube.object_path
        self.info("tube %r closed", tube_path)
        self._tube_conns[tube_path].close()
        del self._tube_conns[tube_path]
        del self._tubes[tube_path]

    def text_channel_members_changed_cb(self, message, added, removed,
                                        local_pending, remote_pending,
                                        actor, reason):
        if self.self_handle in added and not self.joined:
            self.joined = True
            self.muc_joined()

    def muc_joined(self):
        self.info("MUC joined")
        for msg in self._unsent_messages:
            self.send_text(msg)
        self._unsent_messages = []

    def send_text(self, text):
        if self.channel_text:
            self.info("Sending text %r", text)
            channel_obj = self.channel_text[CHANNEL_TYPE_TEXT]
            channel_obj.Send(telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL, text)
        else:
            self.info("Queing text %r until muc is joined", text)
            self._unsent_messages.append(text)
