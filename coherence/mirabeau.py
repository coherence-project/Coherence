# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2009 Philippe Normand <phil@base-art.net>

from telepathy.interfaces import ACCOUNT_MANAGER, ACCOUNT
import dbus

from coherence.dbus_constants import BUS_NAME, DEVICE_IFACE, SERVICE_IFACE
from coherence.extern.telepathy.mirabeau_tube_publisher import MirabeauTubePublisherConsumer
from coherence.tube_service import TubeDeviceProxy
from coherence import log
from coherence.upnp.devices.control_point import ControlPoint

from twisted.internet import defer

class Mirabeau(log.Loggable):
    logCategory = "mirabeau"

    def __init__(self, config, coherence_instance):
        log.Loggable.__init__(self)
        self._tube_proxies = []
        self._coherence = coherence_instance

        chatroom = config['chatroom']
        conference_server = config['account']['fallback-conference-server']
        manager = config['manager']
        protocol = config['protocol']

        # account dict keys are different for each protocol so we
        # assume the user gave the right account parameters depending
        # on the specified protocol.
        account = config['account']

        if isinstance(account, basestring):
            bus = dbus.SessionBus()
            account = bus.get_object(ACCOUNT_MANAGER, account)
            #account_obj = bus.get_object(ACCOUNT_MANAGER, account)
            #account = account_obj.Get(ACCOUNT, 'Parameters')

        try:
            allowed_devices = config["allowed_devices"].split(",")
        except KeyError:
            allowed_devices = None
        tubes_to_offer = {BUS_NAME: {}, DEVICE_IFACE: {}, SERVICE_IFACE: {}}

        callbacks = dict(found_peer_callback=self.found_peer,
                         disapeared_peer_callback=self.disapeared_peer,
                         got_devices_callback=self.got_devices)
        self.tube_publisher = MirabeauTubePublisherConsumer(manager, protocol,
                                                            account, chatroom,
                                                            conference_server,
                                                            tubes_to_offer,
                                                            self._coherence,
                                                            allowed_devices,
                                                            **callbacks)

        # set external address to our hostname, if a IGD device is
        # detected it means we are inside a LAN and the IGD will give
        # us our real external address.
        self._external_address = coherence_instance.hostname
        self._external_port = 30020
        self._portmapping_ready = False

        control_point = self._coherence.ctrl
        igd_signal_name = 'Coherence.UPnP.ControlPoint.InternetGatewayDevice'
        control_point.connect(self._igd_found, '%s.detected' % igd_signal_name)
        control_point.connect(self._igd_removed, '%s.removed' % igd_signal_name)

    def _igd_found(self, client, udn):
        print "IGD found", client.device.get_friendly_name()
        device = client.wan_device.wan_connection_device
        self._igd_service = device.wan_ppp_connection or device.wan_ip_connection
        if self._igd_service:
            self._igd_service.subscribe_for_variable('ExternalIPAddress',
                                                     callback=self.state_variable_change)
            d = self._igd_service.get_all_port_mapping_entries()
            d.addCallback(self._got_port_mappings)

    def _got_port_mappings(self, mappings):
        if mappings == None:
            self.warning("Mappings changed during query, trying again...")
            dfr = service.get_all_port_mapping_entries()
            dfr.addCallback(self._got_port_mappings)
        else:
            description = "Coherence-Mirabeau"
            for mapping in mappings:
                if mapping["NewPortMappingDescription"] == description:
                    self.warning("UPnP port-mapping available")
                    self._portmapping_ready = (mapping["NewRemoteHost"],mapping["NewExternalPort"])
                    return None

            internal_port = self._coherence.web_server_port
            self._external_port = internal_port
            internal_client = self._coherence.hostname
            service = self._igd_service
            dfr = service.add_port_mapping(remote_host='',
                                           external_port=internal_port,
                                           protocol='TCP',
                                           internal_port=internal_port,
                                           internal_client=internal_client,
                                           enabled=True,
                                           port_mapping_description=description,
                                           lease_duration=0)
            def mapping_ok(r,t):
                self._portmapping_ready = t
                self.warning("UPnP port-mapping succeeded")
                return None
            def mapping_failed(r):
                self.warning("UPnP port-mapping failed")
                return None
            dfr.addCallback(mapping_ok,('',internal_port))
            dfr.addErrback(mapping_failed)
        return dfr

    def state_variable_change(self, variable):
        if variable.name == 'ExternalIPAddress':
            print "our external IP address is %s" % variable.value
            self._external_address = variable.value

    def _igd_removed(self, udn):
        self._igd_service = None
        self._portmapping_ready = False

    def found_peer(self, peer):
        print "found", peer

    def disapeared_peer(self, peer):
        print "disapeared", peer

    def got_devices(self, devices):
        for device in devices:
            uuid = device.get_id()
            print "MIRABEAU found:", uuid
            self._tube_proxies.append(TubeDeviceProxy(self._coherence, device,
                                                      self._external_address))

    def start(self):
        self.tube_publisher.start()

    def stop(self):
        control_point = self._coherence.ctrl
        igd_signal_name = 'Coherence.UPnP.ControlPoint.InternetGatewayDevice'
        control_point.disconnect(self._igd_found, '%s.detected' % igd_signal_name)
        control_point.disconnect(self._igd_removed, '%s.removed' % igd_signal_name)

        self.tube_publisher.stop()
        if self._portmapping_ready:
            remote_host,external_port = self._portmapping_ready
            dfr = self._igd_service.delete_port_mapping(remote_host=remote_host,
                                                   external_port=external_port,
                                                   protocol='TCP')
            return dfr
