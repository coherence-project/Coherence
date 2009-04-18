# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

# check http://www.iana.org/assignments/rtp-parameters
# for the RTP payload type identifier
#

from sets import Set

from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement

from coherence.backend import BackendStore,BackendItem

class AxisCamItem(BackendItem):
    logCategory = 'axis_cam_item'

    def __init__(self, id, obj, parent, mimetype, urlbase, UPnPClass,update=False):
        self.id = id
        if mimetype == 'directory':
            self.name = obj
            self.mimetype = mimetype
        else:
            self.name = obj.get('name')
            self.mimetype = mimetype

        self.parent = parent
        if parent:
            parent.add_child(self,update=update)

        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        self.item = UPnPClass(id, parent_id, self.name)
        if isinstance(self.item, Container):
            self.item.childCount = 0
        self.children = []

        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'

        if self.mimetype == 'directory':
            self.url = urlbase + str(self.id)
        else:
            self.url = obj.get('url')

        if self.mimetype == 'directory':
            self.update_id = 0
        else:
            res = Resource(self.url, obj.get('protocol'))
            res.size = None
            self.item.res.append(res)


    def __del__(self):
        #print "AxisCamItem __del__", self.id, self.name
        pass


    def remove(self):
        #print "AxisCamItem remove", self.id, self.name, self.parent
        if self.parent:
            self.parent.remove_child(self)
        del self.item

    def add_child(self, child, update=False):
        self.children.append(child)
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update == True:
            self.update_id += 1


    def remove_child(self, child):
        self.info("remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name()))
        if child in self.children:
            if isinstance(self.item, Container):
                self.item.childCount -= 1
            self.children.remove(child)
            self.update_id += 1

    def get_children(self,start=0,request_count=0):
        if request_count == 0:
            return self.children[start:]
        else:
            return self.children[start:request_count]

    def get_child_count(self):
        return len(self.children)

    def get_id(self):
        return self.id

    def get_update_id(self):
        if hasattr(self, 'update_id'):
            return self.update_id
        else:
            return None

    def get_path(self):
        return self.url

    def get_name(self):
        return self.name

    def get_parent(self):
        return self.parent

    def get_item(self):
        return self.item

    def get_xml(self):
        return self.item.toString()

    def __repr__(self):
        return 'id: ' + str(self.id) + ' @ ' + self.url


class AxisCamStore(BackendStore):

    logCategory = 'axis_cam_store'

    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        BackendStore.__init__(self,server,**kwargs)

        self.next_id = 1000
        self.config = kwargs
        self.name = kwargs.get('name','AxisCamStore')

        self.update_id = 0
        self.store = {}

        self.wmc_mapping = {'8': 1000}

        self.init_completed()

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def append( self, obj, parent):
        if isinstance(obj, basestring):
            mimetype = 'directory'
        else:
            protocol,network,content_type,info = obj['protocol'].split(':')
            mimetype = content_type

        UPnPClass = classChooser(mimetype)
        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = AxisCamItem( id, obj, parent, mimetype, self.urlbase,
                                        UPnPClass, update=update)
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            if parent:
                #value = '%d,%d' % (parent.get_id(),parent_get_update_id())
                value = (parent.get_id(),parent.get_update_id())
                if self.server:
                    self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

        if mimetype == 'directory':
            return self.store[id]

        return None

    def len(self):
        return len(self.store)

    def get_by_id(self,id):
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]
        id = int(id)
        if id == 0:
            id = 1000
        try:
            return self.store[id]
        except:
            return None

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def upnp_init(self):
        self.current_connection_id = None
        parent = self.append('AxisCam', None)

        source_protocols = Set()

        for k,v in self.config.items():
            if isinstance(v,dict):
                v['name'] = k
                source_protocols.add(v['protocol'])
                self.append(v, parent)

        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    source_protocols,
                                                                    default=True)

def main():

    f = AxisCamStore(None)

    def got_upnp_result(result):
        print "upnp", result

    #f.upnp_init()
    #print f.store
    #r = f.upnp_Browse(BrowseFlag='BrowseDirectChildren',
    #                    RequestedCount=0,
    #                    StartingIndex=0,
    #                    ObjectID=0,
    #                    SortCriteria='*',
    #                    Filter='')
    #got_upnp_result(r)


if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
