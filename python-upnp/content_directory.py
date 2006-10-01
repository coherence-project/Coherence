# Elisa - Home multimedia server
# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# All rights reserved.
# 
# This software is available under three license agreements.
# 
# There are various plugins and extra modules for Elisa licensed
# under the MIT license. For instance our upnp module uses this license.
# 
# The core of Elisa is licensed under GPL version 2.
# See "LICENSE.GPL" in the root of this distribution including a special 
# exception to use Elisa with Fluendo's plugins.
# 
# The GPL part is also available under a commerical licensing
# agreement.
# 
# The second license is the Elisa Commercial License Agreement.
# This license agreement is available to licensees holding valid
# Elisa Commercial Agreement licenses.
# See "LICENSE.Elisa" in the root of this distribution.

import re

def get_media_type(protocolInfo):
    match = re.match(".*\:.*\:(.*)/(.*)\:.*", protocolInfo)
    media_type = ''
    format = ''
    if match:
        media_type, format = match.groups()
    return media_type, format


class Object:

    def __init__(self, id, name, child_count, parent):

        self.id = id
        self.name = name
        #if child_count:
            # reset child_count since it will be updated later on when Item instances
            # will be added to the Folder
            # TODO: handle this in non-recursive browsing scenario
            #child_count = 0
        self.child_count = child_count
        if parent:
            parent.add_child(self)
            self.parentID = parent.get_id()
            
    def get_id(self):
        return self.id

    def as_dict(self):
        r = {'id': self.id, 'name': self.name, }
        return r

   
class Folder(Object):

    def __init__(self, id, name, child_count, search_class, parent):
        Object.__init__(self, id, name, child_count, parent)
        self.children = []
        self.search_class = search_class
        
    def add_child(self, child):
        self.children.append(child)
        self.child_count += 1
        
    def get_folder_with_id(self, folder_id):
        folders = [ child for child in self.children
                   if isinstance(child, Folder) and \
                   str(child.get_id()) == str(folder_id) ]
        if folders:
            folder = folders[0]
        else:
            folder = None
            for child in self.children:
                if isinstance(child, Folder):
                    folder = child.get_folder_with_id(folder_id)
                    if folder:
                        break
                
        return folder

    def get_search_class(self):
        return self.search_class

    def as_dict(self):
        r = Object.as_dict(self)
        r['children'] = []
        for child in self.children:
            r['children'].append(child.as_dict())
        return r

class Item(Object):

    def __init__(self, id, name, parentID, urls):
        Object.__init__(self, id, name, 0, parentID)
        self.urls = {}
        for url, protocolInfo in urls.iteritems():
            self.urls[url] = get_media_type(protocolInfo)

    def get_url(self, preferred_formats):
        for preferred_format in preferred_formats:
            for url, (media_type, format) in self.urls.iteritems():
                if preferred_format == format:
                    return url
        return ''

    def get_urls(self):
        return self.urls

    def get_media_type(self):
        infos = self.urls.values()
        media_type = ''
        if infos:
            media_type = infos[0][0]
        return media_type
            
    def as_dict(self):
        r = Object.as_dict(self)
        r.update({'urls': self.urls})
        return r

def _sort_list(a_list):
    r = []
    o = []
    a_list.sort()
    for i in a_list:
        try:
            i = int(i)
        except:
            o.append(i)
        else:
            r.append(i)
    r.sort()
    r = [str(i) for i in r]
    o.sort()
    return r + o

def _get_parent(root, folder, folders):
    parent_id = folder['parentID']
    parent = root.get_folder_with_id(parent_id)
    if not parent:
        if parent_id == '0':
            parent = root
        else:
            try:
                parent_parent_id = folders[parent_id]['parentID']
                parent_parent = root.get_folder_with_id(parent_parent_id)
                parent = Folder(parent_id,
                                folders[parent_id]['title'],
                                folder['childCount'], folder['search_class'],
                                parent_parent)
            except KeyError:
                print 'Parent not found for folder %s in %s' % (parent_id,
                                                                folders.keys())
    return parent


def buildHierarchy(hashed_items, container_id, build_parents=True):
    items = {}
    folders = {}
    for item_id, item in hashed_items.iteritems():
        if not item.has_key('urls') or not item['urls']:
            # folder
            folders[item_id] = item
        else:
            items[item_id] = item

    keys = _sort_list(folders.keys())

    root = Folder(container_id, "root", 0, [], None)

    for folder_id in keys:
	folder = folders[folder_id]

        if build_parents:
            parent = _get_parent(root,folder, folders)
        else:
            parent = root

	Folder(folder_id, folder['title'], folder['childCount'],
               folder['search_class'], parent)
        
    for item_id, item in items.iteritems():
        folder_id = item['parentID']
        folder = root.get_folder_with_id(folder_id)
        if not folder:
            folder = root
        Item(item_id, item['title'], folder, item['urls'])

    return root
