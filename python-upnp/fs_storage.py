# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import os
import time
import re

from twisted.python.filepath import FilePath

from DIDLLite import Container, Item, DIDLElement

class FSItem:

    def __init__(self, id, parent, location, item):
        self.id = id
        self.parent = parent
        if parent:
            parent.add_child(self)
        self.location = location
        self.item = item
        self.child_count = 0
        self.children = []
        
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
        
    def get_parent(self):
        return self.item

    def get_item(self):
        return self.item
        
    def get_xml(self):
        return self.item.toString()
        
    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + self.location.basename()

class FSStore:

    def __init__(self, name, path, ignore_patterns):
        self.nextID = 0
        self.name = name
        self.path = path
        self.store = {}
        
        ignore_file_pattern = re.compile('|'.join(['^\..*'] + list(ignore_patterns)))
        if ignore_file_pattern.match(self.path):
            return
        self.walk(self.path, ignore_file_pattern)

    def len(self):
        return len(self.store)
        
    def get_by_id(self,id):
        try:
            return self.store[id]
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
        id = self.getnextID()
        #print "append", path, "with", id, 'at parent', parent
        if parent == None:
            parent_id = 0
        else:
            parent_id = parent.get_id()
        f = FilePath(path)
        if f.isdir():
            self.store[id] = FSItem( id, parent, f, Container(id,parent_id,f.basename()))
            return self.store[id]
        elif f.isfile():
            self.store[id] = FSItem( id, parent, f, Item(id,parent_id,f.basename()))
            return None
        
    def getnextID(self):
        ret = self.nextID
        self.nextID += 1
        return ret
        
    def browse(self, *args, **kwargs):
        ObjectID = int(kwargs['ObjectID'])
        BrowseFlag = kwargs['BrowseFlag']
        Filter = kwargs['Filter']
        StartingIndex = int(kwargs['StartingIndex'])
        RequestedCount = int(kwargs['RequestedCount'])
        SortCriteria = kwargs['SortCriteria']

        didl = DIDLElement()

        if ObjectID not in self.store:
            raise errorCode(701)

        if BrowseFlag == 'BrowseDirectChildren':
            childs = self.store[ObjectID].get_children(StartingIndex, StartingIndex + RequestedCount)
            for i in childs:
                didl.addItem(i.item)
            total = self.store[ObjectID].child_count
        else:
            didl.addItem(self.store[ObjectID])
            total = 1

        r = { 'Result': didl.toString(), 'TotalMatches': total,
            'NumberReturned': didl.numItems(), 'UpdateID': 0}
        return r


if __name__ == '__main__':
    p = '/data/images'
    #p = '/home/dev/beeCT/beeMedia/python-upnp'
    #p = '/home/dev/beeCT/beeMedia/python-upnp/xml-service-descriptions'

    f = FSStore('my media',p,())

    print f.len()
    print f.get_by_id(0).child_count, f.get_by_id(0).get_xml()
    print f.get_by_id(1).child_count, f.get_by_id(1).get_xml()
    print f.store[0].get_children(0,0)
    