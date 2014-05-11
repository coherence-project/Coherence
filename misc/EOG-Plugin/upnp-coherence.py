# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

import pygtk
pygtk.require("2.0")
import gtk

from coherence.ui.av_widgets import TreeWidget
from coherence.ui.av_widgets import UDN_COLUMN, UPNP_CLASS_COLUMN, SERVICE_COLUMN

import eog


class UPnPClient(eog.Plugin):

    def __init__ (self):
        eog.Plugin.__init__(self)

    def button_pressed(self, widget, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            try:
                row_path, column, _, _ = self.ui.treeview.get_path_at_pos(x, y)
                selection = self.ui.treeview.get_selection()
                if not selection.path_is_selected(row_path):
                    self.ui.treeview.set_cursor(row_path, column, False)
                print "button_pressed", row_path, (row_path[0], )
                iter = self.ui.store.get_iter((row_path[0], ))
                udn, = self.ui.store.get(iter, UDN_COLUMN)
                iter = self.ui.store.get_iter(row_path)
                upnp_class, url = self.ui.store.get(iter, UPNP_CLASS_COLUMN, SERVICE_COLUMN)
                print udn, upnp_class, url
                if(not upnp_class.startswith('object.container') and
                   not upnp_class == 'root'):
                    self.create_item_context(has_delete=self.ui.device_has_action(udn, 'ContentDirectory', 'DestroyObject'))
                    self.context.popup(None, None, None, event.button, event.time)
                    return 1
            except TypeError:
                pass
            return 1

    def create_item_context(self, has_delete=False):
        """ create context menu for right click in treeview item"""

        def action(menu, text):
            selection = self.ui.treeview.get_selection()
            model, selected_rows = selection.get_selected_rows()
            if text == 'item.delete':
                for row_path in selected_rows:
                    self.ui.destroy_object(row_path)
                return
            if(len(selected_rows) > 0 and
               text == ' item.play'):
                row_path = selected_rows.pop(0)
                iter = self.ui.store.get_iter(row_path)
                url, = self.ui.store.get(iter, SERVICE_COLUMN)
                app = eog.eog_application_get_instance()
                app.open_uri_list((url, ))
            for row_path in selected_rows:
                iter = self.ui.store.get_iter(row_path)
                url, = self.ui.store.get(iter, SERVICE_COLUMN)
                app = eog.eog_application_get_instance()
                app.open_uri_list((url, ))

        if not hasattr(self, 'context_no_delete'):
            self.context_no_delete = gtk.Menu()
            play_menu = gtk.MenuItem("Play")
            play_menu.connect("activate", action, 'item.play')
            self.context_no_delete.append(play_menu)
            self.context_no_delete.show_all()

        if not hasattr(self, 'context_with_delete'):
            self.context_with_delete = gtk.Menu()
            play_menu = gtk.MenuItem("Display")
            play_menu.connect("activate", action, 'item.play')
            self.context_with_delete.append(play_menu)
            self.context_with_delete.append(gtk.SeparatorMenuItem())
            menu = gtk.MenuItem("Delete")
            menu.connect("activate", action, 'item.delete')
            self.context_with_delete.append(menu)
            self.context_with_delete.show_all()

        if has_delete:
            self.context = self.context_with_delete
        else:
            self.context = self.context_no_delete

    def activate (self, window):
        self.eog_object = window
        print "activate", window

        self.ui = TreeWidget()
        self.ui.cb_item_right_click = self.button_pressed
        self.ui.window.show_all()
        selection = self.ui.treeview.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)

        sidebar = self.eog_object.get_sidebar()
        sidebar.add_page("Coherence DLNA/UPnP Client", self.ui.window)
        sidebar.show_all()

        def load_and_play(url):
            app = eog.eog_application_get_instance()
            app.open_uri_list((url, ))

        self.ui.cb_item_dbl_click = load_and_play

    def deactivate (self, window):
        #totem_object.remove_sidebar_page ("upnp-coherence")
        print "deactivate", window
