# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009 Philippe Normand <phil@base-art.net>

import time

import dbus.glib
from dbus import PROPERTIES_IFACE

from telepathy.client import Channel
from telepathy.interfaces import CONN_INTERFACE, CHANNEL_INTERFACE_GROUP, \
     CHANNEL_TYPE_CONTACT_LIST, CHANNEL_TYPE_TEXT, CHANNEL_INTERFACE, \
     CONNECTION, CONNECTION_INTERFACE_ALIASING, CHANNEL, CONNECTION_INTERFACE_CONTACTS, \
     CONNECTION_INTERFACE_SIMPLE_PRESENCE, CHANNEL_INTERFACE_MESSAGES, \
     CONNECTION_INTERFACE_REQUESTS, CHANNEL_INTERFACE_TUBE, CHANNEL_TYPE_DBUS_TUBE
from telepathy.constants import CONNECTION_HANDLE_TYPE_CONTACT, \
     CONNECTION_HANDLE_TYPE_LIST, CONNECTION_HANDLE_TYPE_ROOM, \
     CONNECTION_STATUS_CONNECTED, CONNECTION_STATUS_DISCONNECTED, \
     CONNECTION_STATUS_CONNECTING, TUBE_CHANNEL_STATE_LOCAL_PENDING, \
     TUBE_CHANNEL_STATE_REMOTE_PENDING, TUBE_CHANNEL_STATE_OPEN, \
     TUBE_CHANNEL_STATE_NOT_OFFERED, HANDLE_TYPE_LIST

from coherence.extern.telepathy.tubeconn import TubeConnection
from coherence.extern.telepathy.connect import tp_connect
from coherence import log

from twisted.internet import defer

TUBE_STATE = {TUBE_CHANNEL_STATE_LOCAL_PENDING : 'local pending',
              TUBE_CHANNEL_STATE_REMOTE_PENDING : 'remote pending',
              TUBE_CHANNEL_STATE_OPEN : 'open',
              TUBE_CHANNEL_STATE_NOT_OFFERED: 'not offered'}

DBUS_PROPERTIES = 'org.freedesktop.DBus.Properties'

class Client(log.Loggable):
    logCategory = "tp_client"

    def __init__(self, manager, protocol,
                 account, muc_id, conference_server=None, existing_client=False):
        log.Loggable.__init__(self)
        self.account = account
        self.existing_client = existing_client
        self.channel_text = None
        self._unsent_messages = []
        self._tube_conns = {}
        self._tubes = {}
        self._channels = []
        self._pending_tubes = {}
        self._text_channels = {}
        self.joined = False

        if self.existing_client:
            self.muc_id = self.existing_client.muc_id
            self.conn = self.existing_client.conn
            self.ready_cb(self.conn)
            self.connection_dfr = defer.succeed(self.conn)
        else:
            if protocol == 'local-xmpp':
                self.muc_id = muc_id
            else:
                self.muc_id = "%s@%s" % (muc_id, conference_server)
            self.connection_dfr = tp_connect(manager, protocol, account, self.ready_cb)
            self.connection_dfr.addCallbacks(self._got_connection, self.error_cb)

    def _got_connection(self, connection):
        self.conn = connection
        if connection.GetStatus() == CONNECTION_STATUS_DISCONNECTED:
            connection.Connect()
        return connection

    def start(self):
        pass

    def stop(self):
        if not self.existing_client:
            try:
                self.conn[CONNECTION].Disconnect()
            except Exception, exc:
                self.warning("Error while disconnecting: %s", exc)

    def ready_cb(self, conn):
        self.debug("ready callback")
        self.self_handle = self.conn[CONN_INTERFACE].GetSelfHandle()
        self.conn[CONNECTION_INTERFACE_REQUESTS].connect_to_signal("NewChannels",
                                                                   self.new_channels_cb)
        self.conn[CONNECTION].connect_to_signal('StatusChanged', self.status_changed_cb)
        if not self.existing_client:
            self.debug("connecting...")
            self.conn[CONNECTION].Connect()
        self.conn[CONNECTION].GetInterfaces(reply_handler=self.get_interfaces_cb,
                                            error_handler=self.error_cb)

    def error_cb(self, error):
        print "Error:", error

    def status_changed_cb(self, status, reason):
        self.debug("status changed to %r: %r", status, reason)
        if status == CONNECTION_STATUS_CONNECTING:
            self.info('connecting')
        elif status == CONNECTION_STATUS_CONNECTED:
            self.info('connected')
        elif status == CONNECTION_STATUS_DISCONNECTED:
            self.info('disconnected')

    def get_interfaces_cb(self, interfaces):
        self.fill_roster()

    def fill_roster(self):
        self.info("Filling up the roster")
        self.roster = {}
        conn = self.conn

        class ensure_channel_cb(object):
            def __init__(self, parent, group):
                self.parent = parent
                self.group = group

            def __call__(self, yours, path, properties):
                channel = Channel(conn.service_name, path)
                self.channel = channel

                # request the list of members
                channel[DBUS_PROPERTIES].Get(CHANNEL_INTERFACE_GROUP,
                                             'Members',
                                             reply_handler = self.members_cb,
                                             error_handler = self.parent.error_cb)

            def members_cb(self, handles):
                # request information for this list of handles using the
                # Contacts interface
                conn[CONNECTION_INTERFACE_CONTACTS].GetContactAttributes(
                    handles, [
                        CONNECTION,
                        CONNECTION_INTERFACE_ALIASING,
                        CONNECTION_INTERFACE_SIMPLE_PRESENCE,
                    ],
                    False,
                    reply_handler = self.get_contact_attributes_cb,
                    error_handler = self.parent.error_cb)

            def get_contact_attributes_cb(self, attributes):
                self.parent.roster[self.group] = attributes
                if 'subscribe' in self.parent.roster and \
                   'publish' in self.parent.roster:
                    self.parent.join_muc()

        def no_channel_available(error):
            print error

        for name in ('subscribe', 'publish'):
            conn[CONNECTION_INTERFACE_REQUESTS].EnsureChannel({
                CHANNEL + '.ChannelType'     : CHANNEL_TYPE_CONTACT_LIST,
                CHANNEL + '.TargetHandleType': HANDLE_TYPE_LIST,
                CHANNEL + '.TargetID'        : name,
                },
                reply_handler = ensure_channel_cb(self, name),
                error_handler = no_channel_available)

    def join_muc(self):
        conn_obj = self.conn[CONN_INTERFACE]

        # workaround to be sure that the muc service is fully resolved in
        # Salut.
        if conn_obj.GetProtocol() == "local-xmpp":
            time.sleep(2)

        muc_id = self.muc_id
        self.info("joining MUC %r", muc_id)

        if self.existing_client:
            self.channel_text = self.existing_client.channel_text
            self._text_channel_available()
            self.new_channels_cb(self.existing_client._channels)
            self._tubes = self.existing_client._pending_tubes
            for path, tube in self._tubes.iteritems():
                self.connect_tube_signals(tube)
                self.got_tube(tube)
        else:
            conn_iface = self.conn[CONNECTION_INTERFACE_REQUESTS]
            params = {CHANNEL_INTERFACE+".ChannelType": CHANNEL_TYPE_TEXT,
                      CHANNEL_INTERFACE+".TargetHandleType": CONNECTION_HANDLE_TYPE_ROOM,
                      CHANNEL_INTERFACE+".TargetID": muc_id}

            def got_channel(chan_path, props):
                self.channel_text = Channel(self.conn.dbus_proxy.bus_name, chan_path)
                self._text_channel_available()

            def got_error(exception):
                self.warning("Could not join MUC: %s", exception)

            conn_iface.CreateChannel(params,reply_handler=got_channel,
                                     error_handler=got_error)

    def _text_channel_available(self):
        room_iface = self.channel_text[CHANNEL_INTERFACE_GROUP]
        self.self_handle = room_iface.GetSelfHandle()
        room_iface.connect_to_signal("MembersChanged", self.text_channel_members_changed_cb)

        if self.self_handle in room_iface.GetMembers():
            self.joined = True
            self.muc_joined()


    def new_channels_cb(self, channels):
        self.debug("new channels %r", channels)
        self._channels.extend(channels)
        for path, props in channels:
            self.debug("new channel with path %r and props %r", path, props)
            channel_type = props[CHANNEL_INTERFACE + ".ChannelType"]
            if channel_type == CHANNEL_TYPE_DBUS_TUBE:
                tube = Channel(self.conn.dbus_proxy.bus_name, path)
                self.connect_tube_signals(tube)
                tube.props = props
                self._tubes[path] = tube
                self.got_tube(tube)

    def connect_tube_signals(self, tube):
        tube_iface = tube[CHANNEL_INTERFACE_TUBE]
        state_changed = lambda state: self.tube_channel_state_changed_cb(tube,
                                                                         state)
        tube_iface.connect_to_signal("TubeChannelStateChanged", state_changed)
        channel_iface = tube[CHANNEL_INTERFACE]
        channel_iface.connect_to_signal("Closed",
                                        lambda: self.tube_closed(tube))

    def got_tube(self, tube):
        props = tube.props
        self.debug("got tube with props %r", props)
        initiator_id = props[CHANNEL_INTERFACE + ".InitiatorID"]
        service = props[CHANNEL_TYPE_DBUS_TUBE + ".ServiceName"]

        state = tube[PROPERTIES_IFACE].Get(CHANNEL_INTERFACE_TUBE, 'State')

        self.info("new D-Bus tube offered by %s. Service: %s. State: %s",
                  initiator_id, service, TUBE_STATE[state])

    def tube_opened(self, tube):
        tube_path = tube.object_path
        state = tube[PROPERTIES_IFACE].Get(CHANNEL_INTERFACE_TUBE, 'State')
        self.info("tube %r opened (state: %s)", tube_path, TUBE_STATE[state])

        group_iface = self.channel_text[CHANNEL_INTERFACE_GROUP]
        tube_address = tube.local_address
        tube_conn = TubeConnection(self.conn, tube, tube_address,
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
            self.tube_opened(tube)

    def tube_closed(self, tube):
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

    def send_message(self, target_handle, message):
        channel = self._text_channels.get(target_handle)
        if not channel:
            conn_iface = self.conn[CONNECTION_INTERFACE_REQUESTS]
            params = {CHANNEL_INTERFACE+".ChannelType": CHANNEL_TYPE_TEXT,
                      CHANNEL_INTERFACE+".TargetHandleType": CONNECTION_HANDLE_TYPE_CONTACT,
                      CHANNEL_INTERFACE+ ".TargetHandle": target_handle}

            def got_channel(chan_path, props):
                channel = Channel(self.conn.dbus_proxy.bus_name, chan_path)
                self._text_channels[target_handle] = channel
                self.send_message(target_handle, message)

            def got_error(exception):
                print exception

            conn_iface.CreateChannel(params, reply_handler=got_channel, error_handler=got_error)
        else:
            new_message = [
                {}, # let the CM fill in the headers
                {
                    'content': message,
                    'content-type': 'text/plain',
                    },
                ]

            channel[CHANNEL_INTERFACE_MESSAGES].SendMessage(new_message, 0,
                                                            reply_handler=self.send_message_cb,
                                                            error_handler=self.error_cb)

    def send_message_cb (self, token):
        print "Sending message with token %s" % token
