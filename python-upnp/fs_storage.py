# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import os
import time
import re
import urlparse

import mimetypes
mimetypes.init()

from twisted.python.filepath import FilePath

from DIDLLite import classChooser, Container, Resource, DIDLElement

class FSItem:

    def __init__(self, id, parent, path, mimetype, urlbase, UPnPClass):
        self.id = id
        self.parent = parent
        if parent:
            parent.add_child(self)
        self.location = FilePath(path)
        self.mimetype = mimetype
        self.url = urlparse.urljoin(urlbase, str(self.id))

        
        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(id, parent_id, path)
        self.child_count = 0
        self.children = []

        if mimetype == 'directory':
            self.update_id = 0
        else:
            self.item.res = Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            self.item.res.size = self.location.getsize()
            self.item.res = [ self.item.res ]
        
    def add_child(self, child):
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
            
    def get_children(self,start=0,request_count=0):
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]
        
    def get_id(self):
        return self.id
        
    def get_location(self):
        return self.location
        
    def get_path(self):
        return self.location.path

    def get_parent(self):
        return self.item

    def get_item(self):
        return self.item
        
    def get_xml(self):
        return self.item.toString()
        
    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + self.location.basename()

class FSStore:

    def __init__(self, name, path, urlbase, ignore_patterns):
        self.next_id = 0
        self.name = name
        self.path = path
        self.urlbase = urlbase
        self.update_id = 0
        self.store = {}
        
        #print 'FSStore', name, path, urlbase, ignore_patterns
        ignore_file_pattern = re.compile('|'.join(['^\..*'] + list(ignore_patterns)))
        if ignore_file_pattern.match(self.path):
            return
        self.walk(self.path, ignore_file_pattern)

    def len(self):
        return len(self.store)
        
    def get_by_id(self,id):
        try:
            return self.store[int(id)]
        except:
            return None
        
    def walk(self, path, ignore_file_pattern):
        containers = []
        parent = self.append(path,None)
        if parent != None:
            containers.append(parent)
        while len(containers)>0:
            container = containers.pop()
            for child in container.location.children():
                if ignore_file_pattern.match(child.basename()) != None:
                    continue
                new_container = self.append(child.path,container)
                if new_container != None:
                    containers.append(new_container)

    def append(self, path, parent):
        mimetype,_ = mimetypes.guess_type(path)
        if mimetype == None:
            if os.path.isdir(path):
                mimetype = 'directory'
        if mimetype == None:
            return None
        
        UPnPClass = classChooser(mimetype)
        if UPnPClass == None:
            return None
        
        id = self.getnextID()
        #print "append", path, "with", id, 'at parent', parent
        self.store[id] = FSItem( id, parent, path, mimetype, self.urlbase, UPnPClass)
        if mimetype == 'directory':
            return self.store[id]
            
        return None
        
    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret
        
    def upnp_Browse(self, *args, **kwargs):
        ObjectID = int(kwargs['ObjectID'])
        BrowseFlag = kwargs['BrowseFlag']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']

        didl = DIDLElement()

        item = self.get_by_id(ObjectID)
        if item  == None:
            raise errorCode(701)
            
        if BrowseFlag == 'BrowseDirectChildren':
            childs = item.get_children(StartingIndex, StartingIndex + RequestedCount)
            for i in childs:
                didl.addItem(i.item)
            total = item.child_count
        else:
            didl.addItem(item.item)
            total = 1

        r = { 'Result': didl.toString(), 'TotalMatches': total,
            'NumberReturned': didl.numItems()}

        if hasattr(item, 'update_id'):
            r['UpdateID'] = item.update_id
        else:
            r['UpdateID'] = self.update_id

        return r


if __name__ == '__main__':
    p = '/data/images'
    p = 'content'
    #p = '/home/dev/beeCT/beeMedia/python-upnp'
    #p = '/home/dev/beeCT/beeMedia/python-upnp/xml-service-descriptions'

    f = FSStore('my media',p,())

    print f.len()
    print f.get_by_id(0).child_count, f.get_by_id(0).get_xml()
    print f.get_by_id(1).child_count, f.get_by_id(1).get_xml()
    print f.get_by_id(2).child_count, f.get_by_id(2).get_xml()
    print f.store[0].get_children(0,0)
    