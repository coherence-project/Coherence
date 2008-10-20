#!/usr/bin/python
# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008 Frank Scholz <coherence@beebits.net>

""" Coherence and Nautilus bridge to upload files into a DLNA/UPnP MediaServer

    usable as Nautilus Extension or a Script

    for use an extension, copy it to ~/.nautilus/python-extensions
    or for a system-wide installation to /usr/lib/nautilus/extensions-2.0/python

    for us as a script put it into ~/.gnome2/nautilus-scripts with
    a describing name of maybe "upload to UPnP MediaServer"

    connection to Coherence is established via DBus

"""

import sys

import pygtk
pygtk.require("2.0")
import gtk

from coherence.ui.av_widgets import DeviceImportWidget

def show_upload_widget(files,standalone=True):

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    if standalone:
        window.connect("delete_event", gtk.main_quit)
    window.set_default_size(350, 300)
    window.set_title('Coherence DLNA/UPnP Upload')

    ui=DeviceImportWidget(standalone=standalone,root=window)

    window.add(ui.window)

    for filename in files:
        ui.add_file(filename)

    window.show_all()

try:
    import nautilus
    from urllib import unquote

    class CoherenceUploadExtension(nautilus.MenuProvider):

        def __init__(self):
            print "CoherenceUploadExtension"
            pass

        def get_file_items(self, window, files):
            if len(files) == 0:
                return

            for file in files:
                if file.is_directory() or file.get_uri_scheme() != 'file':
                    return

            item = nautilus.MenuItem('CoherenceUploadExtension::import_resources',
                                     'Upload to MediaServer...',
                                     'Upload the selected files to a DLNA/UPnP MediaServer')
            item.connect('activate', self.import_resources, files)

            return item,

        def import_resources(self, menu, files):
            if len(files) == 0:
                return

            show_upload_widget([unquote(file.get_uri()[7:]) for file in files],standalone=False)


except ImportError:
    pass

if __name__ == '__main__':

    import os.path
    files = [x for x in sys.argv[1:] if not os.path.isdir(x)]
    show_upload_widget(files)

    gtk.gdk.threads_init()
    gtk.main()