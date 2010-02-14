# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009 Philippe Normand <phil@base-art.net>

import telepathy
from telepathy.interfaces import CONN_MGR_INTERFACE, ACCOUNT_MANAGER, ACCOUNT, \
     CONNECTION
import dbus
from twisted.internet import defer

def to_dbus_account(account):
    for key, value in account.iteritems():
        if value.lower() in ("false", "true"):
            value = bool(value)
        else:
            try:
                value = dbus.UInt32(int(value))
            except:
                pass
        account[key] = value
    return account

def tp_connect(manager, protocol, account, ready_handler=None):
    if isinstance(account, dict):
        account = to_dbus_account(account)
        reg = telepathy.client.ManagerRegistry()
        reg.LoadManagers()

        mgr = reg.GetManager(manager)
        connection = mgr[CONN_MGR_INTERFACE].RequestConnection(protocol,
                                                               account)
        conn_bus_name, conn_object_path = connection
        client_connection = telepathy.client.Connection(conn_bus_name,
                                                        conn_object_path,
                                                        ready_handler=ready_handler)
        dfr = defer.succeed(client_connection)
    else:
        presence = dbus.Struct((dbus.UInt32(2L), dbus.String(u'available'), dbus.String(u'')),
                               signature=None, variant_level=1)

        dfr = defer.Deferred()

        def property_changed_cb(prop):
            prop = dict(prop)
            if 'CurrentPresence' in prop and prop['CurrentPresence'] == presence:
                # TODO: figure how not to hardode to gabble
                conn_bus_name = "org.freedesktop.Telepathy.ConnectionManager.gabble"
                conn_object_path = account.Get(ACCOUNT, 'Connection')
                client_connection = telepathy.client.Connection(conn_bus_name,
                                                                conn_object_path,
                                                                ready_handler=ready_handler)
                dfr.callback(client_connection)

        account.connect_to_signal('AccountPropertyChanged', property_changed_cb)
        account.Set(ACCOUNT, "RequestedPresence", presence)

    return dfr


def gabble_accounts():
    bus = dbus.SessionBus()
    account_manager = bus.get_object(ACCOUNT_MANAGER,
                                     '/org/freedesktop/Telepathy/AccountManager')

    all_accounts = account_manager.FindAccounts({}, dbus_interface='com.nokia.AccountManager.Interface.Query')

    gabble_accounts = [account for account in all_accounts if account.find("gabble") > -1]
    return gabble_accounts
