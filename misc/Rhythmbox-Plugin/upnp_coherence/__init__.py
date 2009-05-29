# -*- Mode: python; coding: utf-8; tab-width: 8; indent-tabs-mode: t; -*-
#
# Copyright 2008, Frank Scholz <coherence@beebits.net>
# Copyright 2008, James Livingston <doclivingston@gmail.com>
#
# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php


import rhythmdb, rb
import gobject, gtk

import gconf

import coherence.extern.louie as louie

from coherence import log

# For the icon
import os.path, urllib, gnomevfs, gtk.gdk

gconf_keys = {
    # renderer
    'r_active': '/apps/rhythmbox/plugins/upnp_coherence/renderer_active',
    'r_name': '/apps/rhythmbox/plugins/upnp_coherence/renderer_name',
    'r_version': '/apps/rhythmbox/plugins/upnp_coherence/renderer_version',
    'r_uuid': '/apps/rhythmbox/plugins/upnp_coherence/renderer_uuid',
    # store
    's_active': '/apps/rhythmbox/plugins/upnp_coherence/store_active',
    's_name': '/apps/rhythmbox/plugins/upnp_coherence/store_name',
    's_uuid': '/apps/rhythmbox/plugins/upnp_coherence/store_uuid',
    's_version': '/apps/rhythmbox/plugins/upnp_coherence/store_version',
    # client
    'c_active': '/apps/rhythmbox/plugins/upnp_coherence/client_active',
     }


class CoherencePlugin(rb.Plugin, log.Loggable):

    logCategory = 'rb_coherence_plugin'

    def __init__(self):
        rb.Plugin.__init__(self)
        self.coherence = None
        self.config = gconf.client_get_default()

        if self.config.get(gconf_keys['c_active']) is None:
            print "setting defaults"
            self._set_defaults()

    def _set_defaults(self):
        for a in ('r', 's', 'c'):
            self.config.set_bool(gconf_keys['%s_active' % a], True)
        for a in ('r', 's'):
            self.config.set_int(gconf_keys['%s_version' % a], 2)
            self.config.set_string(gconf_keys['%s_name' % a], '')

    def activate(self, shell):
        from twisted.internet import gtk2reactor
        try:
            gtk2reactor.install()
        except AssertionError, e:
            # sometimes it's already installed
            print e

        self.coherence = self.get_coherence()
        if self.coherence is None:
            print "Coherence is not installed or too old, aborting"
            return

        print "coherence UPnP plugin activated"
        self.shell = shell
        self.sources = {}

        # Set up our icon
        the_icon = None
        face_path = os.path.join(os.path.expanduser('~'), ".face")
        if os.path.exists(face_path):
            url = "file://" + urllib.pathname2url(face_path)
            mimetype = gnomevfs.get_mime_type(url)
            pixbuf = gtk.gdk.pixbuf_new_from_file(face_path)
            width = "%s" % pixbuf.get_width()
            height = "%s" % pixbuf.get_height()
            depth = '24'
            the_icon = {
                'url':url,
                'mimetype':mimetype,
                'width':width,
                'height':height,
                'depth':depth
                }
        else:
            the_icon = None

        # create our own media server
        if self.config.get_bool(gconf_keys['s_active']):
            print "activating media store"

            from coherence.upnp.devices.media_server import MediaServer
            from MediaStore import MediaStore
            kw = {
                "version": self.config.get_int(gconf_keys['s_version']),
                "no_thread_needed": True,
                "db": self.shell.props.db,
                "plugin": self,
                }

            uuid = self.config.get_string(gconf_keys['s_uuid'])
            if uuid:
                kw['uuid'] = uuid

            name = self.config.get_string(gconf_keys['s_name'])
            if name:
                kw['name'] = name

            if the_icon:
                kw['icon'] = the_icon

            self.server = MediaServer(self.coherence, MediaStore, **kw)
            if not uuid:
                uuid = str(self.server.uuid)
                self.config.set_string(gconf_keys['s_uuid'], uuid)

            print "Media Store available at %s" % uuid

        if self.config.get_bool(gconf_keys['r_active']):
            print "activating media renderer" 
            # create our own media renderer
            # but only if we have a matching Coherence package installed
            if self.coherence_version < (0, 5, 2):
                print "activation faild. coherence is older than version 0.5.2"
            else:
                from coherence.upnp.devices.media_renderer import MediaRenderer
                from MediaPlayer import RhythmboxPlayer
                kw = {
                    "version": self.config.get_int(gconf_keys['r_version']),
                    "no_thread_needed": True,
                    "shell": self.shell,
                    }

                uuid = self.config.get_string(gconf_keys['r_uuid'])
                if uuid:
                    kw['uuid'] = uuid

                name = self.config.get_string(gconf_keys['r_name'])
                if name:
                    kw['name'] = name

                if the_icon:
                    kw['icon'] = the_icon

                self.renderer = MediaRenderer(self.coherence,
                        RhythmboxPlayer, **kw)

                if not uuid:
                    # first time launch
                    uuid = str(self.renderer.uuid)
                    self.config.set_string(gconf_keys['r_uuid'], uuid)

                print "Media Renderer available at %s" % uuid

        if self.config.get_bool(gconf_keys['c_active']):
            print "start observing for media servers"
            # watch for media servers
            louie.connect(self.detected_media_server,
                    'Coherence.UPnP.ControlPoint.MediaServer.detected',
                    louie.Any)
            louie.connect(self.removed_media_server,
                    'Coherence.UPnP.ControlPoint.MediaServer.removed',
                    louie.Any)


    def deactivate(self, shell):
        print "coherence UPnP plugin deactivated"
        if self.coherence is None:
            return

        self.coherence.shutdown()

        louie.disconnect(self.detected_media_server,
                'Coherence.UPnP.ControlPoint.MediaServer.detected',
                louie.Any)
        louie.disconnect(self.removed_media_server,
                'Coherence.UPnP.ControlPoint.MediaServer.removed',
                louie.Any)

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
        coherence_instance = Coherence(coherence_config)

        return coherence_instance

    def removed_media_server(self, udn):
        print "upnp server went away %s" % udn
        if self.sources.has_key(udn):
            self.sources[udn].delete_thyself()
            del self.sources[udn]

    def detected_media_server(self, client, udn):
        print "found upnp server %s (%s)"  % \
                (client.device.get_friendly_name(), udn)
        self.warning("found upnp server %s (%s)"  %
                (client.device.get_friendly_name(), udn))

        if self.server and client.device.get_id() == str(self.server.uuid):
            """ don't react on our own MediaServer"""
            return

        db = self.shell.props.db
        group = rb.rb_source_group_get_by_name("shared")
        entry_type = db.entry_register_type("CoherenceUpnp:%s" %
                 client.device.get_id()[5:])

        from UpnpSource import UpnpSource
        source = gobject.new (UpnpSource,
                    shell=self.shell,
                    entry_type=entry_type,
                    source_group=group,
                    plugin=self,
                    client=client,
                    udn=udn)

        self.sources[udn] = source

        self.shell.append_source (source, None)
