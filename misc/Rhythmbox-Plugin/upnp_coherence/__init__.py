# -*- Mode: python; coding: utf-8; tab-width: 8; indent-tabs-mode: t; -*-
#
# Copyright 2008-2010, Frank Scholz <dev@coherence-project.org>
# Copyright 2008, James Livingston <doclivingston@gmail.com>
#
# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php


import rhythmdb, rb
import gobject
gobject.threads_init()

import gconf

import coherence.extern.louie as louie

from coherence import log

# for the icon
import os.path, urllib, gio, gtk.gdk

# the gconf configuration
gconf_keys = {
    'port': "/apps/rhythmbox/plugins/coherence/port",
    'interface': "/apps/rhythmbox/plugins/coherence/interface",
    # DMS
    'dms_uuid': "/apps/rhythmbox/plugins/coherence/dms/uuid",
    'dms_active': "/apps/rhythmbox/plugins/coherence/dms/active",
    'dms_version': "/apps/rhythmbox/plugins/coherence/dms/version",
    'dms_name': "/apps/rhythmbox/plugins/coherence/dms/name",
    # DMR
    'dmr_uuid': "/apps/rhythmbox/plugins/coherence/dmr/uuid",
    'dmr_active': "/apps/rhythmbox/plugins/coherence/dmr/active",
    'dmr_version': "/apps/rhythmbox/plugins/coherence/dmr/version",
    'dmr_name': "/apps/rhythmbox/plugins/coherence/dmr/name",
    # DMC
    'dmc_active': "/apps/rhythmbox/plugins/coherence/dmc/active",
}

class CoherenceUpnpEntryType(rhythmdb.EntryType): 
    def __init__(self, client_id): 
        entry_name = "CoherenceUpnp:%s", client_id 
        rhythmdb.EntryType.__init__(self, name=entry_name) 

class CoherencePlugin(rb.Plugin, log.Loggable):

    logCategory = 'rb_coherence_plugin'

    def __init__(self):
        rb.Plugin.__init__(self)
        self.coherence = None
        self.config = gconf.client_get_default()

        if self.config.get(gconf_keys['dmc_active']) is None:
            # key not yet found represented by "None"
            self._set_defaults()

    def _set_defaults(self):
        for a in ('r', 's'):
            self.config.set_bool(gconf_keys['dm%s_active' % a], True)
            self.config.set_int(gconf_keys['dm%s_version' % a], 2)

        self.config.set_string(gconf_keys['dmr_name'], "Rhythmbox UPnP MediaRenderer on {host}")
        self.config.set_string(gconf_keys['dms_name'], "Rhythmbox UPnP MediaServer on {host}")

        self.config.set_bool(gconf_keys['dmc_active'], True)

    def activate(self, shell):
        from twisted.internet import gtk2reactor
        try:
            gtk2reactor.install()
        except AssertionError, e:
            # sometimes it's already installed
            self.warning("gtk2reactor already installed %r" % e)

        self.coherence = self.get_coherence()
        if self.coherence is None:
            self.warning("Coherence is not installed or too old, aborting")
            return

        self.warning("Coherence UPnP plugin activated")

        self.shell = shell
        self.sources = {}

        # Set up our icon
        the_icon = None
        face_path = os.path.join(os.path.expanduser('~'), ".face")
        if os.path.exists(face_path):
            file = gio.File(path=face_path);
            url = file.get_uri();
            info = file.query_info("standard::fast-content-type");
            mimetype = info.get_attribute_as_string("standard::fast-content-type");
            pixbuf = gtk.gdk.pixbuf_new_from_file(face_path)
            width = "%s" % pixbuf.get_width()
            height = "%s" % pixbuf.get_height()
            depth = '24'
            the_icon = {
                'url': url,
                'mimetype': mimetype,
                'width': width,
                'height': height,
                'depth': depth
                }

        if self.config.get_bool(gconf_keys['dms_active']):
            # create our own media server
            from coherence.upnp.devices.media_server import MediaServer
            from MediaStore import MediaStore

            kwargs = {
                    'version': self.config.get_int(gconf_keys['dms_version']),
                    'no_thread_needed': True,
                    'db': self.shell.props.db,
                    'plugin': self}

            if the_icon:
                kwargs['icon'] = the_icon

            dms_uuid = self.config.get_string(gconf_keys['dms_uuid'])
            if dms_uuid:
                kwargs['uuid'] = dms_uuid

            name = self.config.get_string(gconf_keys['dms_name'])
            if name:
                name = name.replace('{host}',self.coherence.hostname)
                kwargs['name'] = name

            self.server = MediaServer(self.coherence, MediaStore, **kwargs)

            if dms_uuid is None:
                self.config.set_string(gconf_keys['dms_uuid'], str(self.server.uuid))

            self.warning("Media Store available with UUID %s" % str(self.server.uuid))

        if self.config.get_bool(gconf_keys['dmr_active']):
            # create our own media renderer
            # but only if we have a matching Coherence package installed
            if self.coherence_version < (0, 5, 2):
                print "activation faild. Coherence is older than version 0.5.2"
            else:
                from coherence.upnp.devices.media_renderer import MediaRenderer
                from MediaPlayer import RhythmboxPlayer
                kwargs = {
                    "version": self.config.get_int(gconf_keys['dmr_version']),
                    "no_thread_needed": True,
                    "shell": self.shell,
                    'dmr_uuid': gconf_keys['dmr_uuid']
                    }

                if the_icon:
                    kwargs['icon'] = the_icon

                dmr_uuid = self.config.get_string(gconf_keys['dmr_uuid'])
                if dmr_uuid:
                    kwargs['uuid'] = dmr_uuid

                name = self.config.get_string(gconf_keys['dmr_name'])
                if name:
                    name = name.replace('{host}',self.coherence.hostname)
                    kwargs['name'] = name

                self.renderer = MediaRenderer(self.coherence,
                        RhythmboxPlayer, **kwargs)

                if dmr_uuid is None:
                    self.config.set_string(gconf_keys['dmr_uuid'], str(self.renderer.uuid))

                self.warning("Media Renderer available with UUID %s" % str(self.renderer.uuid))

        if self.config.get_bool(gconf_keys['dmc_active']):
            self.warning("start looking for media servers")
            # watch for media servers
            louie.connect(self.detected_media_server,
                    'Coherence.UPnP.ControlPoint.MediaServer.detected',
                    louie.Any)
            louie.connect(self.removed_media_server,
                    'Coherence.UPnP.ControlPoint.MediaServer.removed',
                    louie.Any)

    def deactivate(self, shell):
        self.info("Coherence UPnP plugin deactivated")
        if self.coherence is None:
            return

        self.coherence.shutdown()

        try:
            louie.disconnect(self.detected_media_server,
                    'Coherence.UPnP.ControlPoint.MediaServer.detected',
                    louie.Any)
        except louie.error.DispatcherKeyError:
            pass
        try:
            louie.disconnect(self.removed_media_server,
                    'Coherence.UPnP.ControlPoint.MediaServer.removed',
                    louie.Any)
        except louie.error.DispatcherKeyError:
            pass

        del self.shell
        del self.coherence

        for usn, source in self.sources.iteritems():
            source.delete_thyself()
        del self.sources

        # uninstall twisted reactor? probably not, since other things may have used it


    def get_coherence (self):
        coherence_instance = None
        required_version = (0, 5, 7)

        try:
            from coherence.base import Coherence
            from coherence import __version_info__
        except ImportError, e:
            print "Coherence not found"
            return None

        if __version_info__ < required_version:
            required = '.'.join([str(i) for i in required_version])
            found = '.'.join([str(i) for i in __version_info__])
            print "Coherence %s required. %s found. Please upgrade" % (required, found)
            return None

        self.coherence_version = __version_info__

        coherence_config = {
            #'logmode': 'info',
            'controlpoint': 'yes',
            'plugins': {},
        }

        serverport = self.config.get_int(gconf_keys['port'])
        if serverport:
            coherence_config['serverport'] = serverport

        interface = self.config.get_string(gconf_keys['interface'])
        if interface:
            coherence_config['interface'] = interface

        coherence_instance = Coherence(coherence_config)

        return coherence_instance

    def removed_media_server(self, udn):
        self.info("upnp server went away %s" % udn)
        if self.sources.has_key(udn):
            self.sources[udn].delete_thyself()
            del self.sources[udn]

    def detected_media_server(self, client, udn):
        self.warning("found upnp server %s (%s)"  %  (client.device.get_friendly_name(), udn))

        """ don't react on our own MediaServer"""
        if hasattr(self, 'server') and client.device.get_id() == str(self.server.uuid):
            return

        db = self.shell.props.db
        group = rb.rb_display_page_group_get_by_id ("shared")
        
        from CoherenceUpnpEntryType import CoherenceUpnpEntryType
        entry_type = CoherenceUpnpEntryType(client.device.get_id()[5:])
        db.register_entry_type(entry_type)

        from UpnpSource import UpnpSource
        source = gobject.new (UpnpSource,
                    shell=self.shell,
                    entry_type=entry_type,
                    plugin=self,
                    client=client,
                    udn=udn)

        self.sources[udn] = source

        self.shell.append_display_page (source, group)

    def create_configure_dialog(self, dialog=None):
        if dialog is None:

            def store_config(dialog,port_spinner,interface_entry,
                                    dms_check,dms_name_entry,dms_version_entry,dms_uuid_entry,
                                    dmr_check,dmr_name_entry,dmr_version_entry,dmr_uuid_entry,
                                    dmc_check):
                port = port_spinner.get_value_as_int()
                self.config.set_int(gconf_keys['port'],port)
                interface = interface_entry.get_text()
                if len(interface) != 0:
                    self.config.set_string(gconf_keys['interface'],interface)
                self.config.set_bool(gconf_keys['dms_active'],dms_check.get_active())
                self.config.set_string(gconf_keys['dms_name'],dms_name_entry.get_text())
                self.config.set_int(gconf_keys['dms_version'],int(dms_version_entry.get_active_text()))
                self.config.set_string(gconf_keys['dms_uuid'],dms_uuid_entry.get_text())

                self.config.set_bool(gconf_keys['dmr_active'],dmr_check.get_active())
                self.config.set_string(gconf_keys['dmr_name'],dmr_name_entry.get_text())
                self.config.set_int(gconf_keys['dmr_version'],int(dmr_version_entry.get_active_text()))
                self.config.set_string(gconf_keys['dmr_uuid'],dmr_uuid_entry.get_text())

                self.config.set_bool(gconf_keys['dmc_active'],dmc_check.get_active())
                dialog.hide()

            dialog = gtk.Dialog(title='DLNA/UPnP Configuration',
                            parent=None,flags=0,buttons=None)
            dialog.set_default_size(500,350)

            table = gtk.Table(rows=2, columns=2, homogeneous=False)
            dialog.vbox.pack_start(table, False, False, 0)

            label = gtk.Label("Port:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 0, 1)

            value = 0
            if self.config.get_int(gconf_keys['port']) != None:
                value = self.config.get_int(gconf_keys['port'])
            adj = gtk.Adjustment(value, 0, 65535, 1, 100, 0)
            port_spinner = gtk.SpinButton(adj, 0, 0)
            port_spinner.set_wrap(True)
            port_spinner.set_numeric(True)
            table.attach(port_spinner, 1, 2, 0, 1,
                         xoptions=gtk.FILL|gtk.EXPAND,yoptions=gtk.FILL|gtk.EXPAND,xpadding=5,ypadding=5)

            label = gtk.Label("Interface:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 1, 2)
            interface_entry = gtk.Entry()
            interface_entry.set_max_length(16)
            if self.config.get_string(gconf_keys['interface']) != None:
                interface_entry.set_text(self.config.get_string(gconf_keys['interface']))
            else:
                interface_entry.set_text('')
            table.attach(interface_entry, 1, 2, 1, 2,
                         xoptions=gtk.FILL|gtk.EXPAND,yoptions=gtk.FILL|gtk.EXPAND,xpadding=5,ypadding=5)

            frame = gtk.Frame('MediaServer')
            dialog.vbox.add(frame)
            vbox = gtk.VBox(False, 0)
            vbox.set_border_width(5)
            frame.add(vbox)
            table = gtk.Table(rows=4, columns=2, homogeneous=True)
            vbox.pack_start(table, False, False, 0)

            label = gtk.Label("enabled:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 0, 1)
            dms_check = gtk.CheckButton()
            dms_check.set_active(self.config.get_bool(gconf_keys['dms_active']))
            table.attach(dms_check, 1, 2, 0, 1)

            label = gtk.Label("Name:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 1, 2)
            dms_name_entry = gtk.Entry()
            if self.config.get_string(gconf_keys['dms_name']) != None:
                dms_name_entry.set_text(self.config.get_string(gconf_keys['dms_name']))
            else:
                dms_name_entry.set_text('')
            table.attach(dms_name_entry, 1, 2, 1, 2)

            label = gtk.Label("UPnP version:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 3, 4)

            dms_version_entry = gtk.combo_box_new_text()
            dms_version_entry.insert_text(0,'2')
            dms_version_entry.insert_text(1,'1')
            dms_version_entry.set_active(0)
            if self.config.get_int(gconf_keys['dms_version']) != None:
                if self.config.get_int(gconf_keys['dms_version']) == 1:
                    dms_version_entry.set_active(1)
            table.attach(dms_version_entry, 1, 2, 3, 4)

            label = gtk.Label("UUID:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 2, 3)
            dms_uuid_entry = gtk.Entry()
            if self.config.get_string(gconf_keys['dms_uuid']) != None:
                dms_uuid_entry.set_text(self.config.get_string(gconf_keys['dms_uuid']))
            else:
                dms_uuid_entry.set_text('')
            table.attach(dms_uuid_entry, 1, 2, 2, 3)

            frame = gtk.Frame('MediaRenderer')
            dialog.vbox.add(frame)
            vbox = gtk.VBox(False, 0)
            vbox.set_border_width(5)
            frame.add(vbox)
            table = gtk.Table(rows=4, columns=2, homogeneous=True)
            vbox.pack_start(table, False, False, 0)

            label = gtk.Label("enabled:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 0, 1)
            dmr_check = gtk.CheckButton()
            dmr_check.set_active(self.config.get_bool(gconf_keys['dmr_active']))
            table.attach(dmr_check, 1, 2, 0, 1)

            label = gtk.Label("Name:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 1, 2)
            dmr_name_entry = gtk.Entry()
            if self.config.get_string(gconf_keys['dmr_name']) != None:
                dmr_name_entry.set_text(self.config.get_string(gconf_keys['dmr_name']))
            else:
                dmr_name_entry.set_text('')
            table.attach(dmr_name_entry, 1, 2, 1, 2)

            label = gtk.Label("UPnP version:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 3, 4)

            dmr_version_entry = gtk.combo_box_new_text()
            dmr_version_entry.insert_text(0,'2')
            dmr_version_entry.insert_text(1,'1')
            dmr_version_entry.set_active(0)
            if self.config.get_int(gconf_keys['dmr_version']) != None:
                if self.config.get_int(gconf_keys['dmr_version']) == 1:
                    dmr_version_entry.set_active(1)
            table.attach(dmr_version_entry, 1, 2, 3, 4)

            label = gtk.Label("UUID:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 2, 3)
            dmr_uuid_entry = gtk.Entry()
            if self.config.get_string(gconf_keys['dmr_uuid']) != None:
                dmr_uuid_entry.set_text(self.config.get_string(gconf_keys['dmr_uuid']))
            else:
                dmr_uuid_entry.set_text('')
            table.attach(dmr_uuid_entry, 1, 2, 2, 3)


            frame = gtk.Frame('MediaClient')
            dialog.vbox.add(frame)
            vbox = gtk.VBox(False, 0)
            vbox.set_border_width(5)
            frame.add(vbox)
            table = gtk.Table(rows=1, columns=2, homogeneous=True)
            vbox.pack_start(table, False, False, 0)

            label = gtk.Label("enabled:")
            label.set_alignment(0,0.5)
            table.attach(label, 0, 1, 0, 1)
            dmc_check = gtk.CheckButton()
            dmc_check.set_active(self.config.get_bool(gconf_keys['dmc_active']))
            table.attach(dmc_check, 1, 2, 0, 1)


            button = gtk.Button(stock=gtk.STOCK_CANCEL)
            dialog.action_area.pack_start(button, True, True, 5)
            button.connect("clicked", lambda w: dialog.hide())
            button = gtk.Button(stock=gtk.STOCK_OK)
            button.connect("clicked", lambda w: store_config(dialog,port_spinner,interface_entry,
                                                             dms_check,dms_name_entry,dms_version_entry,dms_uuid_entry,
                                                             dmr_check,dmr_name_entry,dmr_version_entry,dmr_uuid_entry,
                                                             dmc_check))
            dialog.action_area.pack_start(button, True, True, 5)
            dialog.show_all()


        dialog.present()
        return dialog
