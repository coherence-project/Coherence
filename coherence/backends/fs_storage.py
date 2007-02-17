# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

import os
import time
import re
from datetime import datetime

import mimetypes
mimetypes.init()

from twisted.python.filepath import FilePath
from twisted.python import failure

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource
from coherence.upnp.core.soap_service import errorCode

from coherence.extern.inotify import INotify
from coherence.extern.inotify import IN_CREATE, IN_DELETE, IN_MOVED_FROM, IN_MOVED_TO, IN_ISDIR
from coherence.extern.inotify import IN_CHANGED

from coherence.extern.logger import Logger, LOG_WARNING
log = Logger('FSStore')

class FSItem:

    def __init__(self, id, parent, path, mimetype, urlbase, UPnPClass,update=False):
        self.id = id
        self.parent = parent
        if parent:
            parent.add_child(self,update=update)
        if mimetype == 'root':
            self.location = path
        else:
            self.location = FilePath(path)
        self.mimetype = mimetype
        if urlbase[-1] != '/':
            urlbase += '/'
        self.url = urlbase + str(self.id)

        
        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(id, parent_id, self.get_name())
        self.child_count = 0
        self.children = []

        if mimetype in ['directory','root']:
            self.update_id = 0
        else:
            self.item.res = Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
            self.item.res.size = self.location.getsize()
            self.item.res = [ self.item.res ]
            self.item.date = datetime.fromtimestamp(self.location.getmtime())
            # FIXME: getmtime is deprecated in Twisted 2.6
            
    def __del__(self):
        #print "FSItem __del__", self.id, self.get_name()
        pass

    def remove(self):
        #print "FSItem remove", self.id, self.get_name(), self.parent
        if self.parent:
            self.parent.remove_child(self)
        del self.item
        
    def add_child(self, child, update=False):
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update == True:
            self.update_id += 1

            
    def remove_child(self, child):
        #print "remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name())
        if child in self.children:
            self.child_count -= 1
            if isinstance(self.item, Container):
                self.item.childCount -= 1
            self.children.remove(child)
            self.update_id += 1
            
    def get_children(self,start=0,request_count=0):
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]
        
    def get_id(self):
        return self.id
        
    def get_location(self):
        return self.location
        
    def get_update_id(self):
        if hasattr(self, 'update_id'):
            return self.update_id
        else:
            return None
        
    def get_path(self):
        if isinstance( self.location,FilePath):
            return self.location.path
        else:
            self.location

    def get_name(self):
        if isinstance( self.location,FilePath):
            return self.location.basename()
        else:
            self.location

    def get_parent(self):
        return self.parent

    def get_item(self):
        return self.item
        
    def get_xml(self):
        return self.item.toString()
        
    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + self.location.basename()

class FSStore:

    implements = ['MediaServer']
    
    wmc_mapping = {'4':1000}

    def __init__(self, server, **kwargs):
        self.next_id = 1000
        self.name = kwargs.get('name','my media')
        self.content = kwargs.get('content','tests/content')
        if not isinstance( self.content, list):
            self.content = [self.content]
        self.urlbase = kwargs.get('urlbase','')
        ignore_patterns = kwargs.get('ignore_patterns',[])

        if self.urlbase[len(self.urlbase)-1] != '/':
            self.urlbase += '/'
        self.server = server
        self.store = {}
        
        self.inotify = INotify()
        
        ignore_file_pattern = re.compile('|'.join(['^\..*'] + list(ignore_patterns)))
        parent = None
        if len(self.content)>1:
            UPnPClass = classChooser('root')
            id = self.getnextID()
            parent = self.store[id] = FSItem( id, parent, 'media', 'root', self.urlbase, UPnPClass, update=False)
                            
        for path in self.content:
            if ignore_file_pattern.match(path):
                continue
            self.walk(path, parent, ignore_file_pattern)

        self.update_id = 0
        
    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def len(self):
        return len(self.store)
        
    def get_by_id(self,id):
        id = int(id)
        if id == 0:
            id = 1000
        try:
            return self.store[id]
        except:
            return None
        
    def get_id_by_name(self, parent, name):
        try:
            parent = self.store[int(parent)]
            for child in parent.children:
                if name == child.get_name():
                    return child.id
        except:
            pass
            
        return None
            
    def walk(self, path, parent=None, ignore_file_pattern=''):
        containers = []
        parent = self.append(path,parent)
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
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = FSItem( id, parent, path, mimetype, self.urlbase, UPnPClass, update=update)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
            value = (parent.get_id(),parent.get_update_id())
            if self.server:
                self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        if mimetype == 'directory':
            mask = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO | IN_CHANGED
            self.inotify.watch(path, mask=mask, auto_add=False, callbacks=(self.notify,id))
            return self.store[id]
            
        return None
        
    def remove(self, id):
        #print 'FSSTore remove id', id
        try:
            item = self.store[int(id)]
            parent = item.get_parent()
            item.remove()
            del self.store[int(id)]
            if hasattr(self, 'update_id'):
                self.update_id += 1
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        except:
            pass


    def notify(self, iwp, filename, mask, parameter=None):
        #print "Event %s on %s %s - id %d" % (
        #    ', '.join(self.inotify.flag_to_human(mask)), iwp.path, filename, parameter)
            
        path = iwp.path
        if filename:
            path = os.path.join(path, filename)

        if mask & IN_CHANGED:
            # FIXME react maybe on access right changes, loss of read rights?
            print '%s was changed, parent %d (%s)' % (path, parameter, iwp.path)
        
        if(mask & IN_DELETE or mask & IN_MOVED_FROM):
            #print '%s was deleted, parent %d (%s)' % (path, parameter, iwp.path)
            id = self.get_id_by_name(parameter,filename)
            self.remove(id)
        if(mask & IN_CREATE or mask & IN_MOVED_TO):
            #if mask & IN_ISDIR:
            #    print 'directory %s was created, parent %d (%s)' % (path, parameter, iwp.path)
            #else:
            #    print 'file %s was created, parent %d (%s)' % (path, parameter, iwp.path)
            self.append( path, self.get_by_id(parameter))

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret
        
    def upnp_init(self):
        self.current_connection_id = None
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo', 'http-get:*:audio/mpeg:*',default=True)


if __name__ == '__main__':
    p = '/data/images'
    p = 'tests/content'
    #p = '/home/dev/beeCT/beeMedia/python-upnp'
    #p = '/home/dev/beeCT/beeMedia/python-upnp/xml-service-descriptions'

    f = FSStore('my media',p, 'http://localhost/xyz',(),None)

    print f.len()
    print f.get_by_id(1000).child_count, f.get_by_id(1000).get_xml()
    #print f.get_by_id(1001).child_count, f.get_by_id(1001).get_xml()
    #print f.get_by_id(1002).child_count, f.get_by_id(1002).get_xml()
    print f.store[1000].get_children(0,0)
    print f.upnp_Search(ContainerID ='4',
                        Filter ='dc:title,upnp:artist',
                        RequestedCount = '1000',
                        StartingIndex = '0',
                        SearchCriteria = '(upnp:class = "object.container.album.musicAlbum")',
                        SortCriteria = '+dc:title')

