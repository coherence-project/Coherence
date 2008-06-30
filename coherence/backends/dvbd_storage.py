# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>


from datetime import datetime
import urllib

from twisted.internet import reactor, defer
from twisted.python import failure, util
from twisted.python.filepath import FilePath

from coherence.upnp.core import DIDLLite

import dbus

import dbus.service

import coherence.extern.louie as louie

from coherence.backend import BackendItem, BackendStore

ROOT_CONTAINER_ID = 0

RECORDINGS_CONTAINER_ID = 100

BUS_NAME = 'org.gnome.DVB'
OBJECT_PATH = '/org/gnome/DVB/RecordingsStore'

class Container(BackendItem):

    logCategory = 'dvbd_store'

    def __init__(self, id, parent_id, name, store=None, children_callback=None, container_class=DIDLLite.Container):
        self.id = id
        self.parent_id = parent_id
        self.name = name
        self.mimetype = 'directory'
        self.item = container_class(id, parent_id,self.name)
        self.item.childCount = 0
        self.update_id = 0
        if children_callback != None:
            self.children = children_callback
        else:
            self.children = util.OrderedDict()

        if store!=None:
            self.get_url = lambda: store.urlbase + str(self.id)

    def add_child(self, child):
        id = child.id
        if isinstance(child.id, basestring):
            _,id = child.id.split('.')
        self.children[id] = child
        if self.item.childCount != None:
            self.item.childCount += 1

    def get_children(self,start=0,end=0):
        self.info("container.get_children %r %r", start, end)

        if callable(self.children):
            return self.children(start,end-start)
        else:
            children = self.children.values()
        if end == 0:
            return children[start:]
        else:
            return children[start:end]

    def get_child_count(self):
        if self.item.childCount != None:
            return self.item.childCount

        if callable(self.children):
            return len(self.children())
        else:
            return len(self.children)

    def get_item(self):
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id

class Recording(BackendItem):

    logCategory = 'dvbd_store'

    def __init__(self,store,
                 id,parent_id,
                 file,title,
                 date,duration,
                 mimetype):

        self.store = store
        self.id = 'recording.%s' % id
        self.parent_id = parent_id
        self.real_id = id

        self.location = FilePath(unicode(file))
        self.title = unicode(title)
        self.mimetype = str(mimetype)
        self.date = datetime.fromtimestamp(int(date))
        self.duration = int(duration)
        self.size = self.location.getsize()
        self.bitrate = 0
        self.url = self.store.urlbase + str(self.id)

    def get_children(self, start=0, end=0):
        return []

    def get_child_count(self):
        return 0

    def get_item(self, parent_id=None):

        self.debug("Recording get_item %r @ %r" %(self.id,self.parent_id))

        # create item
        item = DIDLLite.VideoBroadcast(self.id,self.parent_id)
        item.date = self.date
        item.title = self.title

        # add http resource
        res = DIDLLite.Resource(self.url, 'http-get:*:%s:*' % self.mimetype)
        if self.size > 0:
            res.size = self.size
        if self.duration > 0:
            res.duration = str(self.duration)
        if self.bitrate > 0:
            res.bitrate = str(bitrate)
        item.res.append(res)

        # add internal resource
        res = DIDLLite.Resource('file://'+ urllib.quote(self.get_path()), 'internal:%s:%s:*' % (self.store.server.coherence.hostname,self.mimetype))
        if self.size > 0:
            res.size = self.size
        if self.duration > 0:
            res.duration = str(self.duration)
        if self.bitrate > 0:
            res.bitrate = str(bitrate)
        item.res.append(res)

        return item

    def get_id(self):
        return self.id

    def get_name(self):
        return self.title

    def get_url(self):
        return self.url

    def get_path(self):
        return self.location.path


class DVBDStore(BackendStore):

    """ this is a backend to the DVB Daemon
        http://www.k-d-w.org/node/42

    """

    implements = ['MediaServer']
    logCategory = 'dvbd_store'

    def __init__(self, server, **kwargs):

        if server.coherence.config.get('use_dbus','no') != 'yes':
            raise Exception, 'this backend needs use_dbus enabled in the configuration'

        self.config = kwargs
        self.name = kwargs.get('name','TV')

        self.urlbase = kwargs.get('urlbase','')
        if self.urlbase[len(self.urlbase)-1] != '/':
            self.urlbase += '/'

        self.server = server
        self.update_id = 0

        if kwargs.get('enable_destroy','no') == 'yes':
            self.upnp_DestroyObject = self.hidden_upnp_DestroyObject

        self.bus = dbus.SessionBus()
        dvb_daemon = self.bus.get_object(BUS_NAME,OBJECT_PATH)
        self.store_interface = dbus.Interface(dvb_daemon, 'org.gnome.DVB.RecordingsStore')

        dvb_daemon.connect_to_signal('changed', self.recording_changed, dbus_interface=BUS_NAME)

        self.containers = {}
        self.containers[ROOT_CONTAINER_ID] = \
                    Container(ROOT_CONTAINER_ID,-1,self.name,store=self)

        def query_finished(r):
            louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

        def query_failed(r):
            error = ''
            louie.send('Coherence.UPnP.Backend.init_failed', None, backend=self, msg=error)

        d = self.get_recordings()
        d.addCallback(query_finished)
        d.addErrback(lambda x: louie.send('Coherence.UPnP.Backend.init_failed', None, backend=self, msg='Connection to DVB Daemon failed!'))


    def __repr__(self):
        return "DVBDStore"

    def get_by_id(self,id):
        self.info("looking for id %r", id)
        if isinstance(id, basestring):
            id = id.split('@',1)
            id = id[0]

        item = None
        try:
            id = int(id)
            item = self.containers[id]
        except (ValueError,KeyError):
            try:
                type,id = id.split('.')
                if type == 'recording':
                    return self.containers[RECORDINGS_CONTAINER_ID].children[id]
            except (ValueError,KeyError):
                return None
        return item

    def recording_changed(self, id, mode):
        self.containers[RECORDINGS_CONTAINER_ID].update_id += 1
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                if hasattr(self.server,'content_directory_server'):
                    self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
                value = (RECORDINGS_CONTAINER_ID,self.containers[RECORDINGS_CONTAINER_ID].update_id)
                if self.server:
                    if hasattr(self.server,'content_directory_server'):
                        self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)

    def get_recording_details(self,id):

        def get_title(id):
            d = defer.Deferred()
            self.store_interface.GetName(id,
                                         reply_handler=lambda x: d.callback(x),
                                         error_handler=lambda x: d.errback(x))
            return d

        def get_path(id):
            d = defer.Deferred()
            self.store_interface.GetLocation(id,
                                         reply_handler=lambda x: d.callback(x),
                                         error_handler=lambda x: d.errback(x))
            return d

        def get_date(id):
            d = defer.Deferred()
            self.store_interface.GetStartTimestamp(id,
                                         reply_handler=lambda x: d.callback(x),
                                         error_handler=lambda x: d.errback(x))
            return d

        def get_duration(id):
            d = defer.Deferred()
            self.store_interface.GetLength(id,
                                         reply_handler=lambda x: d.callback(x),
                                         error_handler=lambda x: d.errback(x))
            return d

        def process_details(r, id):
            return {'id':id,'name':r[0][1],'path':r[1][1],'date':r[2][1],'duration':r[3][1]}

        def handle_error(error):
            return error

        dl = defer.DeferredList((get_title(id),get_path(id),get_date(id),get_duration(id)))
        dl.addCallback(process_details,id)
        dl.addErrback(handle_error)
        return dl

    def get_recordings(self):
        def handle_error(error):
            return error

        def process_query_result(ids):
            #print "process_query_result", ids
            if len(ids) == 0:
                return
            l = []
            for id in ids:
                l.append(self.get_recording_details(id))

            dl = defer.DeferredList(l)
            return dl

        def process_details(results):
            #print 'process_details', results
            for result,recording in results:
                #print result, recording['name']
                if result == True:
                    print "add", recording['id'], recording['name'], recording['path'], recording['date'], recording['duration']
                    video_item = Recording(self,
                                           recording['id'],
                                           RECORDINGS_CONTAINER_ID,
                                           recording['path'],
                                           recording['name'],
                                           recording['date'],
                                           recording['duration'],
                                           'video/mpegts')
                    self.containers[RECORDINGS_CONTAINER_ID].add_child(video_item)

        self.containers[RECORDINGS_CONTAINER_ID] = \
                    Container(RECORDINGS_CONTAINER_ID,ROOT_CONTAINER_ID,'Recordings',store=self)
        self.containers[ROOT_CONTAINER_ID].add_child(self.containers[RECORDINGS_CONTAINER_ID])

        d = defer.Deferred()
        d.addCallback(process_query_result)
        d.addCallback(process_details)
        d.addErrback(handle_error)
        d.addErrback(handle_error)
        self.store_interface.GetRecordings(reply_handler=lambda x: d.callback(x),
                                           error_handler=lambda x: d.errback(x))
        return d


    def upnp_init(self):
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                            ['http-get:*:video/mpegts:*',
                             'internal:%s:video/mpegts:*' % self.server.coherence.hostname,])

    def hidden_upnp_DestroyObject(self, *args, **kwargs):
        ObjectID = kwargs['ObjectID']

        item = self.get_by_id(ObjectID)
        if item == None:
            return failure.Failure(errorCode(701))

        def handle_success(deleted):
            print 'deleted', deleted, kwargs['ObjectID']
            if deleted == False:
                return failure.Failure(errorCode(715))
            return {}

        def handle_error(error):
            return failure.Failure(errorCode(701))

        d = defer.Deferred()
        self.store_interface.Delete(int(item.real_id),
                                    reply_handler=lambda x: d.callback(x),
                                    error_handler=lambda x: d.errback(x))
        return d
