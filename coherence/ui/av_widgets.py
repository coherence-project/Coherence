# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

""" simple and hopefully reusable widgets to ease
    the creation of UPnP UI applications

    icons taken from the Tango Desktop Project
"""

from os.path import join as path_join
import socket

import pygtk
pygtk.require("2.0")
import gtk

import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
import dbus.service

from coherence.upnp.core.utils import get_host_address


# dbus defines
BUS_NAME = 'org.Coherence'
OBJECT_PATH = '/org/Coherence'

# gtk store defines
NAME_COLUMN = 0
ID_COLUMN = 1
UPNP_CLASS_COLUMN = 2
CHILD_COUNT_COLUMN = 3
UDN_COLUMN = 4
SERVICE_COLUMN = 5
ICON_COLUMN = 6

from pkg_resources import resource_filename

class TreeWidget(object):

    def __init__(self,cb_item_dbl_click=None,
                      cb_resource_chooser=None):

        self.cb_item_dbl_click = cb_item_dbl_click
        self.cb_item_right_click = None
        self.cb_resource_chooser = cb_resource_chooser

        self.hostname = socket.gethostbyname(socket.gethostname())
        if self.hostname.startswith('127.'):
            """ use interface detection via routing table as last resort """
            self.hostname = get_host_address()

        self.build_ui()
        self.init_controlpoint()

    def build_ui(self):
        self.window = gtk.ScrolledWindow()
        self.window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        icon = resource_filename(__name__, path_join('icons','network-server.png'))
        self.device_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, path_join('icons','folder.png'))
        self.folder_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, path_join('icons','audio-x-generic.png'))
        self.audio_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, path_join('icons','video-x-generic.png'))
        self.video_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, path_join('icons','image-x-generic.png'))
        self.image_icon = gtk.gdk.pixbuf_new_from_file(icon)

        self.store = gtk.TreeStore(str,  # 0: name or title
                                   str,  # 1: id, '0' for the device
                                   str,  # 2: upnp_class, 'root' for the device
                                   int,  # 3: child count, -1 if not available
                                   str,  # 4: device udn, '' for an item
                                   str,  # 5: service path, '' for a non container item
                                   gtk.gdk.Pixbuf)

        self.treeview = gtk.TreeView(self.store)
        self.column = gtk.TreeViewColumn('MediaServers')
        self.treeview.append_column(self.column)

        # create a CellRenderers to render the data
        icon_cell = gtk.CellRendererPixbuf()
        text_cell = gtk.CellRendererText()

        self.column.pack_start(icon_cell, False)
        self.column.pack_start(text_cell, True)

        self.column.set_attributes(text_cell, text=0)
        self.column.add_attribute(icon_cell, "pixbuf",6)
        #self.column.set_cell_data_func(self.cellpb, get_icon)

        #self.treeview.insert_column_with_attributes(-1, 'MediaServers', cell, text=0)
        self.treeview.connect("row-activated", self.browse)
        self.treeview.connect("button_press_event", self.button_action)

        self.window.add(self.treeview)

    def button_action(self, widget, event):
        #print "button_action", widget, event, event.button
        if self.cb_item_right_click != None:
            return self.cb_item_right_click(widget, event)
        return 0

    def handle_error(self,error):
        print error

    def handle_devices_reply(self,devices):
        for device in devices:
            if device['device_type'].split(':')[3] == 'MediaServer':
                self.media_server_found(device)

    def init_controlpoint(self):
        self.bus = dbus.SessionBus()
        self.coherence = self.bus.get_object(BUS_NAME,OBJECT_PATH)

        self.coherence.get_devices(dbus_interface=BUS_NAME,
                                   reply_handler=self.handle_devices_reply,
                                   error_handler=self.handle_error)

        self.coherence.connect_to_signal('UPnP_ControlPoint_MediaServer_detected', self.media_server_found, dbus_interface=BUS_NAME)
        self.coherence.connect_to_signal('UPnP_ControlPoint_MediaServer_removed', self.media_server_removed, dbus_interface=BUS_NAME)
        self.devices = {}

    def device_has_action(self,udn,service,action):
        try:
            self.devices[udn][service]['actions'].index(action)
            return True
        except:
            return False

    def state_variable_change( self, udn, service, variable, value):
        #print "state_variable_change", udn, service, variable, 'changed to', value
        if variable == 'ContainerUpdateIDs':
            changes = value.split(',')
            while len(changes) > 1:
                container = changes.pop(0).strip()
                update_id = changes.pop(0).strip()

                def match_func(model, iter, data):
                    column, key = data # data is a tuple containing column number, key
                    value = model.get_value(iter, column)
                    return value == key

                def search(model, iter, func, data):
                    #print "search", model, iter, data
                    while iter:
                        if func(model, iter, data):
                            return iter
                        result = search(model, model.iter_children(iter), func, data)
                        if result: return result
                        iter = model.iter_next(iter)
                    return None

                row_count = 0
                for row in self.store:
                    if udn == row[UDN_COLUMN]:
                        iter = self.store.get_iter(row_count)
                        match_iter = search(self.store, self.store.iter_children(iter),
                                        match_func, (ID_COLUMN, container))
                        if match_iter:
                            print "heureka, we have a change in ", container, ", container needs a reload"
                            child = self.store.iter_children(match_iter)
                            while child:
                                self.store.remove(child)
                                child = self.store.iter_children(match_iter)
                            self.browse(self.treeview,self.store.get_path(match_iter),None,
                                        starting_index=0,requested_count=0,force=True)

                        break
                    row_count += 1

    def media_server_found(self,device,udn=None):
        #print "media_server_found", device['friendly_name']
        item = self.store.append(None)
        self.store.set_value(item, NAME_COLUMN, device['friendly_name'])
        self.store.set_value(item, ID_COLUMN, '0')
        self.store.set_value(item, UPNP_CLASS_COLUMN, 'root')
        self.store.set_value(item, CHILD_COUNT_COLUMN, -1)
        self.store.set_value(item, UDN_COLUMN, str(device['udn']))
        self.store.set_value(item, ICON_COLUMN, self.device_icon)
        self.devices[str(device['udn'])] =  {'ContentDirectory':{}}
        for service in device['services']:
            service_type = service.split('/')[-1]
            if service_type == 'ContentDirectory':
                self.store.set_value(item, SERVICE_COLUMN, service)
                self.devices[str(device['udn'])]['ContentDirectory'] = {}

                def reply(r,udn):
                    self.devices[udn]['ContentDirectory']['actions'] = r

                def reply_subscribe(udn, service, r):
                    for k,v in r.iteritems():
                        self.state_variable_change(udn,service,k,v)

                s = self.bus.get_object(BUS_NAME+'.service',service)
                s.connect_to_signal('StateVariableChanged', self.state_variable_change, dbus_interface=BUS_NAME+'.service')
                s.get_available_actions(reply_handler=lambda x : reply(x,str(device['udn'])),error_handler=self.handle_error)
                s.subscribe(reply_handler=reply_subscribe,error_handler=self.handle_error)


    def media_server_removed(self,udn):
        #print "media_server_removed", udn
        row_count = 0
        for row in self.store:
            if udn == row[UDN_COLUMN]:
                self.store.remove(self.store.get_iter(row_count))
                del self.devices[str(udn)]
            row_count += 1
        """
        iter = self.store.get_iter_first()
        while iter != None:
            row_udn, = self.store.get(iter,UDN_COLUMN)
            next_iter = self.store.iter_next(iter)
            if udn == row_udn:
                self.store.remove(iter)
                del self.devices[udn]
            iter = next_iter
        """

    def browse(self,view,row_path,column,starting_index=0,requested_count=0,force=False):
        #print "browse", view, row_path, column,starting_index,requested_count,force
        iter = self.store.get_iter(row_path)
        children = self.store.iter_children(iter)
        if children != None and force == False:
            if view.row_expanded(row_path):
                view.collapse_row(row_path)
            else:
                view.expand_row(row_path, False)
            return
        title,object_id, upnp_class = self.store.get(iter,NAME_COLUMN,ID_COLUMN,UPNP_CLASS_COLUMN)
        if(not upnp_class.startswith('object.container') and
           not upnp_class == 'root'):
            url, = self.store.get(iter,SERVICE_COLUMN)
            if url == '':
                return
            print "request to play:", title,object_id,url
            if self.cb_item_dbl_click != None:
                self.cb_item_dbl_click(url)
            return

        def reply(r):
            #print "browse_reply - %s of %s returned" % (r['NumberReturned'],r['TotalMatches'])
            from coherence.upnp.core import DIDLLite

            didl = DIDLLite.DIDLElement.fromString(r['Result'])
            for item in didl.getItems():
                #print item.title, item.id, item.upnp_class
                if item.upnp_class.startswith('object.container'):
                    icon = self.folder_icon
                    service, = self.store.get(iter,SERVICE_COLUMN)
                    child_count = item.childCount
                    try:
                        title = "%s (%d)" % (item.title,item.childCount)
                    except TypeError:
                        title = "%s (n/a)" % item.title
                        child_count = -1
                else:
                    icon=None
                    service = ''

                    if callable(self.cb_resource_chooser):
                        service = self.cb_resource_chooser(item.res)
                    else:
                        res = item.res.get_matching(['*:%s:*:*' % self.hostname], protocol_type='internal')
                        if len(res) == 0:
                            res = item.res.get_matching(['*:*:*:*'], protocol_type='http-get')
                        if len(res) > 0:
                            res = res[0]
                            remote_protocol,remote_network,remote_content_format,_ = res.protocolInfo.split(':')
                            service = res.data

                    child_count = -1
                    title = item.title
                    if item.upnp_class.startswith('object.item.audioItem'):
                        icon = self.audio_icon
                    elif item.upnp_class.startswith('object.item.videoItem'):
                        icon = self.video_icon
                    elif item.upnp_class.startswith('object.item.imageItem'):
                        icon = self.image_icon

                self.store.append(iter, (title,item.id,item.upnp_class,child_count,'',service,icon))

            if int(r['TotalMatches']) > 0:
                view.expand_row(row_path, False)

            if(requested_count != int(r['NumberReturned']) and
               int(r['NumberReturned']) < (int(r['TotalMatches'])-starting_index)):
                print "seems we have been returned only a part of the result"
                print "requested %d, starting at %d" % (requested_count,starting_index)
                print "got %d out of %d" % (int(r['NumberReturned']), int(r['TotalMatches']))
                print "requesting more starting now at %d" % (starting_index+int(r['NumberReturned']))

                self.browse(view,row_path,column,
                            starting_index=starting_index+int(r['NumberReturned']),
                            force=True)

        service, = self.store.get(iter,SERVICE_COLUMN)
        if service == '':
            return
        s = self.bus.get_object(BUS_NAME+'.service',service)
        s.action('browse',
                 {'object_id':object_id,'process_result':'no',
                  'starting_index':str(starting_index),'requested_count':str(requested_count)},
                 reply_handler=reply,error_handler=self.handle_error)

    def destroy_object(self, row_path):
        print "destroy_object", row_path
        iter = self.store.get_iter(row_path)
        object_id, = self.store.get(iter,ID_COLUMN)
        parent_iter = self.store.iter_parent(iter)
        service, = self.store.get(parent_iter,SERVICE_COLUMN)
        if service == '':
            return

        def reply(r):
            print "reply", r

        s = self.bus.get_object(BUS_NAME+'.service',service)
        s.action('destroy_object',
                 {'object_id':object_id},
                 reply_handler=reply,error_handler=self.handle_error)


if __name__ == '__main__':

    ui=TreeWidget()

    window = gtk.Window()
    window.connect("delete_event", gtk.main_quit)
    window.set_default_size(350, 550)

    window.add(ui.window)

    window.show_all()


    gtk.gdk.threads_init()
    gtk.main()