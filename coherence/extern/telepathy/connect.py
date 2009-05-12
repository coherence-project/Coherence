
import telepathy
from telepathy.interfaces import CONN_MGR_INTERFACE
import dbus

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

def tp_connect(manager, protocol, account):
    account = to_dbus_account(account)
    reg = telepathy.client.ManagerRegistry()
    reg.LoadManagers()

    mgr = reg.GetManager(manager)
    connection = mgr[CONN_MGR_INTERFACE].RequestConnection(protocol,
                                                           account)
    conn_bus_name, conn_object_path = connection
    client_connection = telepathy.client.Connection(conn_bus_name,
                                                    conn_object_path,
                                                    ready_handler=None)
    return client_connection

