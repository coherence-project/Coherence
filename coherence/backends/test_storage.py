# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008 Frank Scholz <coherence@beebits.net>


""" A MediaServer backend to test Items

    Item information can be passed on the commandline
    or in the config as an XMl fragment

    coherence --plugin=backend:TestStore,name:Test,\
                       item:<item><location>audio.mp3</location>\
                            <mimetype>audio/mpeg</mimetype></item>,\
                       item:<item><location>audio.ogg</location>\
                            <mimetype>audio/ogg</mimetype></item>

    coherence --plugin="backend:TestStore,name:Test,\
                       item:<item><type>gstreamer</type>\
                            <pipeline>v4l2src num-buffers=1 ! video/x-raw-yuv,width=640,height=480 ! ffmpegcolorspace ! jpegenc name=enc</pipeline>\
                            <mimetype>image/jpeg></mimetype></item>"

                "video/x-raw-yuv,width=640,height=480" won't work here as it is a delimiter for the plugin string,
                so if you need things like that in the pipeline, you need to use a config file

    coherence --plugin="backend:TestStore,name:Test,\
                        item:<item><type>process</type>\
                            <command>man date</command>\
                            <mimetype>text/html</mimetype></item>"

    The XML fragment has these elements:

    'type': file - the item is some file-system object (default)
            url - an item pointing to an object off-site
            gstreamer - the item is actually a GStreamer pipeline
            process - the items content is created by an external process

    'location': the filesystem path or an url (mandatory)
    'mimetype': the mimetype of the item (mandatory)
    'extension': an optional extension to append to the
                 url created for the DIDLLite resource data
    'title': the 'title' this item should have (optional)
    'upnp_class': the DIDLLite class the item shall have,
                  object.item will be taken as default
    'fourth_field': value for the 4th field of the protocolInfo phalanx,
                    default is '*'
    'pipeline': a GStreamer pipeline that has to end with a bin named 'enc',
                some pipelines do only work properly when we have a glib mainloop
                running, so coherence needs to be started with -o glib:yes
    'command': the commandline for an external script to run, its output will
              be returned as the items content

In the config file the definition of this backend could look like this:

        <plugin active="yes">
          <backend>TestStore</backend>
          <name>Test</name>
          <item>
            <location>/tmp/audio.mp3</location>
            <mimetype>audio/mpeg</mimetype>
          </item>
          <item>
            <location>/tmp/audio.ogg</location>
            <mimetype>audio/ogg</mimetype>
          </item>
        </plugin>

"""

import os

from twisted.python.filepath import FilePath
from twisted.internet import protocol,reactor
from twisted.web import resource,server

from coherence.backend import BackendStore,BackendRssMixin
from coherence.backend import BackendItem

try:
    from coherence.transcoder import GStreamerPipeline
except ImportError:
    pass

from coherence.upnp.core import DIDLLite
from coherence.upnp.core.utils import parse_xml

from coherence import log


ROOT_CONTAINER_ID = 0

class ExternalProcessProtocol(protocol.ProcessProtocol):

    def __init__(self,caller):
        self.caller = caller

    def connectionMade(self):
        print "pp connection made"

    def outReceived(self, data):
        print "outReceived with %d bytes!" % len(data)
        self.caller.write_data(data)

    def errReceived(self, data):
        #print "errReceived! with %d bytes!" % len(data)
        print "pp (err):", data.strip()

    def inConnectionLost(self):
        #print "inConnectionLost! stdin is closed! (we probably did it)"
        pass

    def outConnectionLost(self):
        #print "outConnectionLost! The child closed their stdout!"
        pass

    def errConnectionLost(self):
        #print "errConnectionLost! The child closed their stderr."
        pass

    def processEnded(self, status_object):
        print "processEnded, status %d" % status_object.value.exitCode
        print "processEnded quitting"
        self.caller.ended = True
        self.caller.write_data('')


class ExternalProcessPipeline(resource.Resource, log.Loggable):
    logCategory = 'externalprocess'
    addSlash = True

    def __init__(self,pipeline,mimetype):
        self.uri = pipeline
        self.mimetype = mimetype

    def render(self, request):
        print "ExternalProcessPipeline render"
        if self.mimetype:
            request.setHeader('content-type', self.mimetype)

        ExternalProcessProducer(self.uri,request)
        return server.NOT_DONE_YET


class ExternalProcessProducer(object):
    logCategory = 'externalprocess'
    addSlash = True

    def __init__(self, pipeline,request):
        self.pipeline = pipeline
        self.request = request
        self.process = None
        self.written = 0
        self.data = ''
        self.ended = False
        request.registerProducer(self, 0)

    def write_data(self,data):
        if data:
            print "write %d bytes of data" % len(data)
            self.written += len(data)
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        if self.request and self.ended == True:
            print "closing"
            self.request.unregisterProducer()
            self.request.finish()
            self.request = None

    def resumeProducing(self):
        print "resumeProducing", self.request
        if not self.request:
            return
        if self.process == None:
            argv = self.pipeline.split()
            executable = argv[0]
            argv[0] = os.path.basename(argv[0])
            self.process = reactor.spawnProcess(ExternalProcessProtocol(self), executable, argv, {})

    def pauseProducing(self):
        pass

    def stopProducing(self):
        print "stopProducing",self.request
        self.request.unregisterProducer()
        self.process.loseConnection()
        self.request.finish()
        self.request = None


class Item(BackendItem):

    def __init__(self,parent,id,title,location,url):
        self.parent = parent
        self.id = id
        self.location = location
        self.url = url
        self.name = title
        self.duration = None
        self.size = None
        self.mimetype = None
        self.fourth_field = '*'
        self.description = None
        self.date = None

        self.upnp_class = DIDLLite.Item

        self.item = None

    def get_item(self):
        print "get_item %r" % self.item
        if self.item == None:
            self.item = self.upnp_class(self.id, self.parent.id, self.get_name())
            self.item.description = self.description
            self.item.date = self.date

            res = DIDLLite.Resource(self.url, 'http-get:*:%s:%s' % (self.mimetype,self.fourth_field))
            res.duration = self.duration
            res.size = self.get_size()
            self.item.res.append(res)
        return self.item

    def get_name(self):
        if self.name == None:
            if isinstance(self.location,FilePath):
                self.name = self.location.basename().decode("utf-8", "replace")
            else:
                self.name = 'item'
        return self.name

    def get_path(self):
        if isinstance( self.location,FilePath):
            return self.location.path
        else:
            return self.location

    def get_size(self):
        if isinstance( self.location,FilePath):
            try:
                return self.location.getsize()
            except OSError:
                return self.size
        else:
            return self.size


class ResourceItem(Item,BackendItem):

    def get_name(self):
        if self.name == None:
            self.name = 'item'
        return self.name

    def get_path(self):
        return self.location

    def get_size(self):
        return self.size


class Container(BackendItem):

    def __init__(self, id, store, parent_id, title):
        self.url = store.urlbase+str(id)
        self.parent_id = parent_id
        self.id = id
        self.name = title
        self.mimetype = 'directory'
        self.update_id = 0
        self.children = []

        self.item = DIDLLite.Container(self.id, self.parent_id, self.name)
        self.item.childCount = 0

        self.sorted = False

    def add_child(self, child):
        print "ADD CHILD %r" % child
        #id = child.id
        #if isinstance(child.id, basestring):
        #    _,id = child.id.split('.')
        self.children.append(child)
        self.item.childCount += 1
        self.sorted = False

    def get_children(self, start=0, end=0):
        print "GET CHILDREN"
        if self.sorted == False:
            def childs_sort(x,y):
                r = cmp(x.name,y.name)
                return r

            self.children.sort(cmp=childs_sort)
            self.sorted = True
        if end != 0:
            return self.children[start:end]
        return self.children[start:]

    def get_child_count(self):
        return len(self.children)

    def get_path(self):
        return self.url

    def get_item(self):
        return self.item

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id


class TestStore(BackendStore):

    implements = ['MediaServer']

    def __init__(self, server, *args, **kwargs):
        print "TestStore kwargs", kwargs
        BackendStore.__init__(self,server,**kwargs)
        self.name = kwargs.get('name', 'TestServer')
        self.next_id = 1000
        self.update_id = 0
        self.store = {}

        self.store[ROOT_CONTAINER_ID] = \
                        Container(ROOT_CONTAINER_ID,self,-1, self.name)

        items = kwargs.get('item', [])
        if not isinstance( items, list):
            items = [items]

        for item in items:
            if isinstance(item,basestring):
                xml = parse_xml(item)
                print xml.getroot()
                item = {}
                for child in xml.getroot():
                    item[child.tag] = child.text
            type = item.get('type','file')
            try:
                name = item.get('title',None)
                if type == 'file':
                    location = FilePath(item.get('location'))
                if type == 'url':
                    location = item.get('location')

                mimetype = item.get('mimetype')
                item_id = self.get_next_id()

                extension = item.get('extension')
                if extension == None:
                    extension = ''
                if len(extension) and extension[0] != '.':
                    extension = '.' + extension

                if extension != None:
                    item_id = str(item_id)+extension

                if type in ('file','url'):
                    new_item = Item(self.store[ROOT_CONTAINER_ID], item_id, name, location,self.urlbase + str(item_id))
                elif type == 'gstreamer':
                    pipeline = item.get('pipeline')
                    try:
                        pipeline = GStreamerPipeline(pipeline,mimetype)
                        new_item = ResourceItem(self.store[ROOT_CONTAINER_ID], item_id, name, pipeline,self.urlbase + str(item_id))
                    except NameError:
                        self.warning("Can't enable GStreamerPipeline, probably pygst not installed")
                        continue

                elif type == 'process':
                    pipeline = item.get('command')
                    pipeline = ExternalProcessPipeline(pipeline,mimetype)
                    new_item = ResourceItem(self.store[ROOT_CONTAINER_ID], item_id, name, pipeline,self.urlbase + str(item_id))

                try:
                    new_item.upnp_class = self.get_upnp_class(item.get('upnp_class','object.item'))
                except:
                    pass
                #item.description = u'some text what's the file about'
                #item.date = something
                #item.size = something
                new_item.mimetype = mimetype
                new_item.fourth_field = item.get('fourth_field','*')

                self.store[ROOT_CONTAINER_ID].add_child(new_item)
                self.store[item_id] = new_item

            except:
                import traceback
                self.warning(traceback.format_exc())

        #print self.store

        self.init_completed()

    def get_upnp_class(self,name):
        try:
            return DIDLLite.upnp_classes[name]
        except KeyError:
            self.warning("upnp_class %r not found, trying fallback", name)
            parts = name.split('.')
            parts.pop()
            while len(parts) > 1:
                try:
                    return DIDLLite.upnp_classes['.'.join(parts)]
                except KeyError:
                    parts.pop()

        self.warning("WTF - no fallback for upnp_class %r found ?!?", name)
        return None

    def get_next_id(self):
        self.next_id += 1
        return self.next_id

    def get_by_id(self, id):
        print "GET_BY_ID %r" % id
        item = self.store.get(id,None)
        if item == None:
            if int(id) == 0:
                item = self.store[ROOT_CONTAINER_ID]
            else:
                item = self.store.get(int(id),None)
        return item