# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

""" simple and hopefully reusable widgets to ease
    the creation of UPnP UI applications

    icons taken from the Tango Desktop Project
"""

import os.path
import urllib

import traceback


import pygtk
pygtk.require("2.0")
import gtk
import gobject

import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
import dbus.service

import mimetypes
mimetypes.init()


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
DIDL_COLUMN = 7
TOOLTIP_ICON_COLUMN = 8

from pkg_resources import resource_filename

class ControlPoint(object):

    _instance_ = None  # Singleton

    def __new__(cls, *args, **kwargs):
        obj = getattr(cls, '_instance_', None)
        if obj is not None:
            return obj
        else:
            obj = super(ControlPoint, cls).__new__(cls, *args, **kwargs)
            cls._instance_ = obj
            obj._connect(*args, **kwargs)
            return obj

    def __init__(self):
        pass

    def _connect(self):
        self.bus = dbus.SessionBus()
        self.coherence = self.bus.get_object(BUS_NAME,OBJECT_PATH)


class DeviceExportWidget(object):

    def __init__(self,name='Nautilus',standalone=True,root=None):
        self.root=root
        self.uuid = None
        self.name = name
        self.standalone=standalone

        icon = resource_filename(__name__, os.path.join('icons','emblem-new.png'))
        self.new_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, os.path.join('icons','emblem-shared.png'))
        self.shared_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, os.path.join('icons','emblem-unreadable.png'))
        self.unshared_icon = gtk.gdk.pixbuf_new_from_file(icon)

        self.filestore = gtk.ListStore(str,gtk.gdk.Pixbuf)

        self.coherence = ControlPoint().coherence

    def build_ui(self,root=None):
        if root != None:
            self.root = root
        self.window = gtk.VBox(homogeneous=False, spacing=0)

        self.fileview = gtk.TreeView(self.filestore)
        column = gtk.TreeViewColumn('Folders to share')
        self.fileview.append_column(column)
        icon_cell = gtk.CellRendererPixbuf()
        text_cell = gtk.CellRendererText()

        column.pack_start(icon_cell, False)
        column.pack_start(text_cell, True)

        column.set_attributes(text_cell, text=0)
        column.add_attribute(icon_cell, "pixbuf",1)

        self.window.pack_start(self.fileview,expand=True,fill=True)

        buttonbox = gtk.HBox(homogeneous=False, spacing=0)
        button = gtk.Button(stock=gtk.STOCK_ADD)
        button.set_sensitive(False)
        button.connect("clicked", self.new_files)
        buttonbox.pack_start(button, expand=False,fill=False, padding=2)
        button = gtk.Button(stock=gtk.STOCK_REMOVE)
        #button.set_sensitive(False)
        button.connect("clicked", self.remove_files)
        buttonbox.pack_start(button, expand=False,fill=False, padding=2)
        button = gtk.Button(stock=gtk.STOCK_CANCEL)
        button.connect("clicked", self.share_cancel)
        buttonbox.pack_start(button, expand=False,fill=False, padding=2)
        button = gtk.Button(stock=gtk.STOCK_APPLY)
        button.connect("clicked", self.share_files)
        buttonbox.pack_start(button, expand=False,fill=False, padding=2)

        self.window.pack_end(buttonbox,expand=False,fill=False)
        return self.window

    def share_cancel(self,button):
        for row in self.filestore:
            print row
            if row[1] == self.new_icon:
                del row
                continue
            if row[1] == self.unshared_icon:
                row[1] = self.shared_icon

        if self.standalone:
            gtk.main_quit()
        else:
            self.root.hide()

    def share_files(self,button):
        print "share_files with", self.uuid
        folders = []
        for row in self.filestore:
            if row[1] == self.unshared_icon:
                del row
                continue
            folders.append(row[0])

        if self.uuid == None:
            if len(folders) > 0:
                self.uuid = self.coherence.add_plugin('FSStore', {'name': self.name,
                                                              'version':'1',
                                                              'create_root': 'yes',
                                                              'import_folder': '/tmp/UPnP Imports',
                                                              'content':','.join(folders)},
                                            dbus_interface=BUS_NAME)
                #self.coherence.pin('Nautilus::MediaServer::%d'%os.getpid(),self.uuid)
        else:
            result = self.coherence.call_plugin(self.uuid,'update_config',{'content':','.join(folders)})
            if result != self.uuid:
                print "something failed", result
        for row in self.filestore:
            row[1] = self.shared_icon
        self.root.hide()

    def add_files(self,files):
        print "add_files", files
        for filename in files:
            for row in self.filestore:
                if os.path.abspath(filename) == row[0]:
                    break
            else:
                self.add_file(filename)

    def add_file(self,filename):
        self.filestore.append([os.path.abspath(filename),self.new_icon])

    def new_files(self,button):
        print "new_files"

    def remove_files(self,button):
        print "remove_files"
        selection = self.fileview.get_selection()
        print selection
        model, selected_rows = selection.get_selected_rows()
        for row_path in selected_rows:
            #model.remove(model.get_iter(row_path))
            row = model[row_path]
            row[1] = self.unshared_icon


class DeviceImportWidget(object):

    def __init__(self,standalone=True,root=None):
        self.standalone=standalone
        self.root=root
        self.build_ui()
        self.init_controlpoint()

    def build_ui(self):
        self.window = gtk.VBox(homogeneous=False, spacing=0)
        self.combobox = gtk.ComboBox()
        self.store = gtk.ListStore(str,  # 0: friendly name
                                   str,  # 1: device udn
                                   gtk.gdk.Pixbuf)

        icon = resource_filename(__name__, os.path.join('icons','network-server.png'))
        self.device_icon = gtk.gdk.pixbuf_new_from_file(icon)

        # create a CellRenderers to render the data
        icon_cell = gtk.CellRendererPixbuf()
        text_cell = gtk.CellRendererText()

        self.combobox.pack_start(icon_cell, False)
        self.combobox.pack_start(text_cell, True)

        self.combobox.set_attributes(text_cell, text=0)
        self.combobox.add_attribute(icon_cell, "pixbuf",2)

        self.combobox.set_model(self.store)


        item = self.store.append(None)
        self.store.set_value(item, 0, 'Select a MediaServer...')
        self.store.set_value(item, 1, '')
        self.store.set_value(item, 2, None)
        self.combobox.set_active(0)

        self.window.pack_start(self.combobox,expand=False,fill=False)

        self.filestore = gtk.ListStore(str)

        self.fileview = gtk.TreeView(self.filestore)
        column = gtk.TreeViewColumn('Files')
        self.fileview.append_column(column)
        text_cell = gtk.CellRendererText()

        column.pack_start(text_cell, True)
        column.set_attributes(text_cell, text=0)

        self.window.pack_start(self.fileview,expand=True,fill=True)

        buttonbox = gtk.HBox(homogeneous=False, spacing=0)
        button = gtk.Button(stock=gtk.STOCK_ADD)
        button.set_sensitive(False)
        button.connect("clicked", self.new_files)
        buttonbox.pack_start(button, expand=False,fill=False, padding=2)
        button = gtk.Button(stock=gtk.STOCK_REMOVE)
        button.set_sensitive(False)
        button.connect("clicked", self.remove_files)
        buttonbox.pack_start(button, expand=False,fill=False, padding=2)
        button = gtk.Button(stock=gtk.STOCK_CANCEL)
        if self.standalone:
            button.connect("clicked", gtk.main_quit)
        else:
            button.connect("clicked", lambda x: self.root.destroy())
        buttonbox.pack_start(button, expand=False,fill=False, padding=2)
        button = gtk.Button(stock=gtk.STOCK_APPLY)
        button.connect("clicked", self.import_files)
        buttonbox.pack_start(button, expand=False,fill=False, padding=2)

        self.window.pack_end(buttonbox,expand=False,fill=False)

    def add_file(self,filename):
        self.filestore.append([os.path.abspath(filename)])

    def new_files(self,button):
        print "new_files"

    def remove_files(self,button):
        print "remove_files"

    def import_files(self,button):
        print "import_files"
        active = self.combobox.get_active()
        if active <= 0:
            print "no MediaServer selected"
            return None
        friendlyname, uuid,_ = self.store[active]

        try:
            row = self.filestore[0]
            print 'import to', friendlyname,os.path.basename(row[0])

            def success(r):
                print 'success',r
                self.filestore.remove(self.filestore.get_iter(0))
                self.import_files(None)

            def reply(r):
                print 'reply',r['Result'], r['ObjectID']
                from coherence.upnp.core import DIDLLite

                didl = DIDLLite.DIDLElement.fromString(r['Result'])
                item = didl.getItems()[0]
                res = item.res.get_matching(['*:*:*:*'], protocol_type='http-get')
                if len(res) > 0:
                    print 'importURI',res[0].importUri
                    self.coherence.put_resource(res[0].importUri,row[0],
                                                reply_handler=success,
                                                error_handler=self.handle_error)

            mimetype,_ = mimetypes.guess_type(row[0], strict=False)
            if mimetype.startswith('image/'):
                upnp_class = 'object.item.imageItem'
            elif mimetype.startswith('video/'):
                upnp_class = 'object.item.videoItem'
            elif mimetype.startswith('audio/'):
                upnp_class = 'object.item.audioItem'
            else:
                upnp_class = 'object.item'

            self.coherence.create_object(uuid,'DLNA.ORG_AnyContainer',
                                            {'parentID':'DLNA.ORG_AnyContainer','upnp_class':upnp_class,'title':os.path.basename(row[0])},
                                            reply_handler=reply,
                                            error_handler=self.handle_error)

        except IndexError:
            pass


    def handle_error(self,error):
        print error

    def handle_devices_reply(self,devices):
        for device in devices:
            if device['device_type'].split(':')[3] == 'MediaServer':
                self.media_server_found(device)

    def init_controlpoint(self):
        cp = ControlPoint()
        self.bus = cp.bus
        self.coherence = cp.coherence

        self.coherence.get_devices(dbus_interface=BUS_NAME,
                                   reply_handler=self.handle_devices_reply,
                                   error_handler=self.handle_error)

        self.coherence.connect_to_signal('UPnP_ControlPoint_MediaServer_detected', self.media_server_found, dbus_interface=BUS_NAME)
        self.coherence.connect_to_signal('UPnP_ControlPoint_MediaServer_removed', self.media_server_removed, dbus_interface=BUS_NAME)
        self.devices = {}

    def media_server_found(self,device,udn=None):
        for service in device['services']:
            service_type = service.split('/')[-1]
            if service_type == 'ContentDirectory':

                def got_icons(r,udn,item):
                    print 'got_icons', r
                    for icon in r:
                        ###FIXME, we shouldn't just use the first icon
                        icon_loader = gtk.gdk.PixbufLoader()
                        icon_loader.write(urllib.urlopen(str(icon['url'])).read())
                        icon_loader.close()
                        icon = icon_loader.get_pixbuf()
                        icon = icon.scale_simple(16,16,gtk.gdk.INTERP_BILINEAR)
                        self.store.set_value(item, 2, icon)
                        break

                def reply(r,udn):
                    if 'CreateObject' in r:
                        self.devices[udn] =  {'ContentDirectory':{}}
                        self.devices[udn]['ContentDirectory']['actions'] = r

                        item = self.store.append(None)
                        self.store.set_value(item, 0, str(device['friendly_name']))
                        self.store.set_value(item, 1, str(device['udn']))
                        self.store.set_value(item, 2, self.device_icon)

                        d = self.bus.get_object(BUS_NAME+'.device',device['path'])
                        d.get_device_icons(reply_handler=lambda x : got_icons(x,str(device['udn']),item),error_handler=self.handle_error)

                s = self.bus.get_object(BUS_NAME+'.service',service)
                s.get_available_actions(reply_handler=lambda x : reply(x,str(device['udn'])),error_handler=self.handle_error)

    def media_server_removed(self,udn):
        row_count = 0
        for row in self.store:
            if udn == row[1]:
                self.store.remove(self.store.get_iter(row_count))
                del self.devices[str(udn)]
                break
            row_count += 1


class TreeWidget(object):

    def __init__(self,cb_item_dbl_click=None,
                      cb_resource_chooser=None):

        self.cb_item_dbl_click = cb_item_dbl_click
        self.cb_item_right_click = None
        self.cb_resource_chooser = cb_resource_chooser

        self.build_ui()
        self.init_controlpoint()

    def build_ui(self):
        self.window = gtk.ScrolledWindow()
        self.window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        icon = resource_filename(__name__, os.path.join('icons','network-server.png'))
        self.device_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, os.path.join('icons','folder.png'))
        self.folder_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, os.path.join('icons','audio-x-generic.png'))
        self.audio_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, os.path.join('icons','video-x-generic.png'))
        self.video_icon = gtk.gdk.pixbuf_new_from_file(icon)
        icon = resource_filename(__name__, os.path.join('icons','image-x-generic.png'))
        self.image_icon = gtk.gdk.pixbuf_new_from_file(icon)

        self.store = gtk.TreeStore(str,  # 0: name or title
                                   str,  # 1: id, '0' for the device
                                   str,  # 2: upnp_class, 'root' for the device
                                   int,  # 3: child count, -1 if not available
                                   str,  # 4: device udn, '' for an item
                                   str,  # 5: service path, '' for a non container item
                                   gtk.gdk.Pixbuf,
                                   str,  # 7: DIDLLite fragment, '' for a non upnp item
                                   gtk.gdk.Pixbuf
                                )

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
        self.treeview.connect("row-expanded", self.row_expanded)
        self.treeview.connect("button_press_event", self.button_action)

        self.treeview.set_property("has-tooltip", True)
        self.treeview.connect("query-tooltip", self.show_tooltip)

        self.tooltip_path = None

        self.we_are_scrolling = None

        def end_scrolling():
            self.we_are_scrolling = None

        def start_scrolling(w,e):
            if self.we_are_scrolling != None:
                gobject.source_remove(self.we_are_scrolling)
            self.we_are_scrolling = gobject.timeout_add(800, end_scrolling)

        self.treeview.connect('scroll-event', start_scrolling)

        self.window.add(self.treeview)

    def show_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if self.we_are_scrolling != None:
            return False
        ret = False
        try:
            path = self.treeview.get_dest_row_at_pos(x, y)
            iter = self.store.get_iter(path[0])
            title,object_id,upnp_class,item = self.store.get(iter,NAME_COLUMN,ID_COLUMN,UPNP_CLASS_COLUMN,DIDL_COLUMN)
            from coherence.upnp.core import DIDLLite
            if upnp_class == 'object.item.videoItem':
                self.tooltip_path = object_id
                item = DIDLLite.DIDLElement.fromString(item).getItems()[0]
                tooltip_icon, = self.store.get(iter,TOOLTIP_ICON_COLUMN)
                if tooltip_icon != None:
                    tooltip.set_icon(tooltip_icon)
                else:
                    tooltip.set_icon(self.video_icon)
                    for res in item.res:
                        protocol,network,content_format,additional_info = res.protocolInfo.split(':')
                        if(content_format == 'image/jpeg' and
                           'DLNA.ORG_PN=JPEG_TN' in additional_info.split(';')):
                            icon_loader = gtk.gdk.PixbufLoader()
                            icon_loader.write(urllib.urlopen(str(res.data)).read())
                            icon_loader.close()
                            icon = icon_loader.get_pixbuf()
                            tooltip.set_icon(icon)
                            self.store.set_value(iter, TOOLTIP_ICON_COLUMN, icon)
                            #print "got poster", icon
                            break
                title = title.replace('&','&amp;')
                try:
                    director = item.director.replace('&','&amp;')
                except AttributeError:
                    director = ""
                try:
                    description = item.description.replace('&','&amp;')
                except AttributeError:
                    description = ""
                tooltip.set_markup("<b>%s</b>\n"
                                   "<b>Director:</b> %s\n"
                                   "<b>Description:</b> %s" % (title,
                                                                director,
                                                                description))
                ret = True

        except TypeError:
            #print traceback.format_exc()
            pass
        except Exception:
            #print traceback.format_exc()
            #print "something wrong"
            pass
        return ret

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
        cp = ControlPoint()
        self.bus = cp.bus
        self.coherence = cp.coherence

        self.hostname = self.coherence.hostname(dbus_interface=BUS_NAME)

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
                            path = self.store.get_path(match_iter)
                            expanded = self.treeview.row_expanded(path)
                            child = self.store.iter_children(match_iter)
                            while child:
                                self.store.remove(child)
                                child = self.store.iter_children(match_iter)
                            self.browse(self.treeview,path,None,
                                        starting_index=0,requested_count=0,force=True,expand=expanded)

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
        self.store.set_value(item, DIDL_COLUMN, '')
        self.store.set_value(item, TOOLTIP_ICON_COLUMN, None)

        self.store.append(item, ('...loading...','','placeholder',-1,'','',None,'',None))

        self.devices[str(device['udn'])] =  {'ContentDirectory':{}}
        for service in device['services']:
            service_type = service.split('/')[-1]
            if service_type == 'ContentDirectory':
                self.store.set_value(item, SERVICE_COLUMN, service)
                self.devices[str(device['udn'])]['ContentDirectory'] = {}

                def reply(r,udn):
                    self.devices[udn]['ContentDirectory']['actions'] = r

                def got_icons(r,udn,item):
                    #print 'got_icons', r
                    for icon in r:
                        ###FIXME, we shouldn't just use the first icon
                        icon_loader = gtk.gdk.PixbufLoader()
                        icon_loader.write(urllib.urlopen(str(icon['url'])).read())
                        icon_loader.close()
                        icon = icon_loader.get_pixbuf()
                        icon = icon.scale_simple(16,16,gtk.gdk.INTERP_BILINEAR)
                        self.store.set_value(item, ICON_COLUMN, icon)
                        break


                def reply_subscribe(udn, service, r):
                    for k,v in r.iteritems():
                        self.state_variable_change(udn,service,k,v)

                s = self.bus.get_object(BUS_NAME+'.service',service)
                s.connect_to_signal('StateVariableChanged', self.state_variable_change, dbus_interface=BUS_NAME+'.service')
                s.get_available_actions(reply_handler=lambda x : reply(x,str(device['udn'])),error_handler=self.handle_error)
                s.subscribe(reply_handler=reply_subscribe,error_handler=self.handle_error)

                d = self.bus.get_object(BUS_NAME+'.device',device['path'])
                d.get_device_icons(reply_handler=lambda x : got_icons(x,str(device['udn']),item),error_handler=self.handle_error)


    def media_server_removed(self,udn):
        #print "media_server_removed", udn
        row_count = 0
        for row in self.store:
            if udn == row[UDN_COLUMN]:
                self.store.remove(self.store.get_iter(row_count))
                del self.devices[str(udn)]
                break
            row_count += 1

    def row_expanded(self,view,iter,row_path):
        #print "row_expanded", view,iter,row_path
        child = self.store.iter_children(iter)
        if child:
            upnp_class, = self.store.get(child,UPNP_CLASS_COLUMN)
            if upnp_class == 'placeholder':
                self.browse(view,row_path,None)

    def browse(self,view,row_path,column,starting_index=0,requested_count=0,force=False,expand=False):
        #print "browse", view,row_path,column,starting_index,requested_count,force
        iter = self.store.get_iter(row_path)
        child = self.store.iter_children(iter)
        if child:
            upnp_class, = self.store.get(child,UPNP_CLASS_COLUMN)
            if upnp_class != 'placeholder':
                if force == False:
                    if view.row_expanded(row_path):
                        view.collapse_row(row_path)
                    else:
                        view.expand_row(row_path, False)
                    return

        title,object_id,upnp_class = self.store.get(iter,NAME_COLUMN,ID_COLUMN,UPNP_CLASS_COLUMN)
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

            child = self.store.iter_children(iter)
            if child:
                upnp_class, = self.store.get(child,UPNP_CLASS_COLUMN)
                if upnp_class == 'placeholder':
                    self.store.remove(child)

            title, = self.store.get(iter,NAME_COLUMN)
            try:
                title = title[:title.rindex('(')]
                self.store.set_value(iter,NAME_COLUMN, "%s(%d)" % (title,int(r['TotalMatches'])))
            except ValueError:
                pass
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

                stored_didl = DIDLLite.DIDLElement()
                stored_didl.addItem(item)
                new_iter = self.store.append(iter, (title,item.id,item.upnp_class,child_count,'',service,icon,stored_didl.toString(),None))
                if item.upnp_class.startswith('object.container'):
                    self.store.append(new_iter, ('...loading...','','placeholder',-1,'','',None,'',None))


            if((int(r['TotalMatches']) > 0 and force==False) or
                expand==True):
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
        #print "destroy_object", row_path
        iter = self.store.get_iter(row_path)
        object_id, = self.store.get(iter,ID_COLUMN)
        parent_iter = self.store.iter_parent(iter)
        service, = self.store.get(parent_iter,SERVICE_COLUMN)
        if service == '':
            return

        def reply(r):
            #print "destroy_object reply", r
            pass

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