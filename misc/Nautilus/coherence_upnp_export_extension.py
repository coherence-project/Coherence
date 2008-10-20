#!/usr/bin/python
# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008 Frank Scholz <coherence@beebits.net>

""" Coherence and Nautilus bridge to export folders as a DLNA/UPnP MediaServer

    usable as Nautilus Extension or a Script

    for use an extension, copy it to ~/.nautilus/python-extensions
    or for a system-wide installation to /usr/lib/nautilus/extensions-2.0/python

    for us as a script put it into ~/.gnome2/nautilus-scripts with
    a describing name of maybe "export as UPnP MediaServer"

    connection to Coherence is established via DBus

    when used as a script it will export every folder as
    a separate MediaServer

    the extension will use the same MediaServer over the lifetime of Nautilus
    and just add new folders

"""

import sys

import dbus

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import dbus.service

BUS_NAME = 'org.Coherence'
OBJECT_PATH = '/org/Coherence'

def do_export(name,directories):

    bus = dbus.SessionBus()
    coherence = bus.get_object(BUS_NAME,OBJECT_PATH)

    r = coherence.add_plugin('FSStore',
                             {'name': name,
                              'content':','.join(directories)},
                             dbus_interface=BUS_NAME)
    return r

try:
    import nautilus
    from urllib import unquote

    class CoherenceExportExtension(nautilus.MenuProvider):

        def __init__(self):
            print "CoherenceExportExtension"
            from coherence.ui.av_widgets import DeviceExportWidget
            self.ui = DeviceExportWidget(standalone=False)
            self.ui_create()

        def ui_destroy(self,*args):
            self.window = None

        def ui_create(self):
            import pygtk
            pygtk.require("2.0")
            import gtk

            self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
            self.window.set_default_size(350, 300)
            self.window.set_title('Coherence DLNA/UPnP Share')

            self.window.connect("delete_event", self.ui_destroy)

            self.window.add(self.ui.build_ui(root=self.window))

        def get_file_items(self, window, files):
            if len(files) == 0:
                return

            for file in files:
                if not file.is_directory():
                    return

            item = nautilus.MenuItem('CoherenceExportExtension::export_resources',
                                     'Sharing as a MediaServer...',
                                     'Share the selected folders as a DLNA/UPnP MediaServer')
            item.connect('activate', self.export_resources, files)

            return item,

        def export_resources(self, menu, files):
            if len(files) == 0:
                return

            if self.window == None:
                self.ui_create()

            self.ui.add_files([unquote(file.get_uri()[7:]) for file in files])
            self.window.show_all()


except ImportError:
    pass

if __name__ == '__main__':

    import os.path
    files = [x for x in sys.argv[1:] if os.path.isdir(x)]
    do_export('Nautilus',files)
