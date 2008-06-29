# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2007, Frank Scholz <coherence@beebits.net>

from urlparse import urlsplit

from twisted.internet import reactor, protocol
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred
from twisted.python import failure
from twisted.protocols.basic import LineReceiver

from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core import DIDLLite
from coherence.upnp.core.DIDLLite import classChooser, Container, Resource, DIDLElement

import coherence.extern.louie as louie

from coherence.extern.simple_plugin import Plugin

from coherence import log

class BzClient(LineReceiver, log.Loggable):
    logCategory = 'buzztard_client'

    def connectionMade(self):
        self.info("connected to Buzztard")
        self.factory.clientReady(self)

    def lineReceived(self, line):
        self.debug( "received:", line)

        if line == 'flush':
            louie.send('Buzztard.Response.flush', None)
        elif line.find('event') == 0:
            louie.send('Buzztard.Response.event', None, line)
        elif line.find('volume') == 0:
            louie.send('Buzztard.Response.volume', None, line)
        elif line.find('mute') == 0:
            louie.send('Buzztard.Response.mute', None, line)
        elif line.find('repeat') == 0:
            louie.send('Buzztard.Response.repeat', None, line)
        elif line.find('playlist') == 0:
            louie.send('Buzztard.Response.browse', None, line)

class BzFactory(protocol.ClientFactory, log.Loggable):
    logCategory = 'buzztard_factory'
    protocol = BzClient

    def __init__(self,backend):
        self.backend = backend

    def clientConnectionFailed(self, connector, reason):
        self.error('connection failed:', reason.getErrorMessage())

    def clientConnectionLost(self, connector, reason):
        self.error('connection lost:', reason.getErrorMessage())

    def startFactory(self):
        self.messageQueue = []
        self.clientInstance = None

    def clientReady(self, instance):
        self.info("clientReady")
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self.backend)
        self.clientInstance = instance
        for msg in self.messageQueue:
            self.sendMessage(msg)

    def sendMessage(self, msg):
        if self.clientInstance is not None:
            self.clientInstance.sendLine(msg)
        else:
            self.messageQueue.append(msg)

    def rebrowse(self):
        self.backend.clear()
        self.browse()

    def browse(self):
        self.sendMessage('browse')


class BzConnection(log.Loggable):
    """ a singleton class
    """
    logCategory = 'buzztard_connection'

    def __new__(cls, *args, **kwargs):
        self.debug("BzConnection __new__")
        obj = getattr(cls,'_instance_',None)
        if obj is not None:
            louie.send('Coherence.UPnP.Backend.init_completed', None, backend=kwargs['backend'])
            return obj
        else:
            obj = super(BzConnection, cls).__new__(cls, *args, **kwargs)
            cls._instance_ = obj
            obj.connection = BzFactory(kwargs['backend'])
            reactor.connectTCP( kwargs['host'], kwargs['port'], obj.connection)
            return obj

    def __init__(self,backend=None,host='localhost',port=7654):
        self.debug("BzConnection __init__")

class BuzztardItem(log.Loggable):
    logCategory = 'buzztard_item'

    def __init__(self, id, name, parent, mimetype, urlbase, host, update=False):
        self.id = id
        self.name = name
        self.mimetype = mimetype

        self.parent = parent
        if parent:
            parent.add_child(self,update=update)

        if parent == None:
            parent_id = -1
        else:
            parent_id = parent.get_id()

        UPnPClass = classChooser(mimetype, sub='music') # FIXME: this is stupid
        self.item = UPnPClass(id, parent_id, self.name)
        self.child_count = 0
        self.children = []

        if( len(urlbase) and urlbase[-1] != '/'):
            urlbase += '/'

        #self.url = urlbase + str(self.id)
        self.url = self.name

        if self.mimetype == 'directory':
            self.update_id = 0
        else:
            res = Resource(self.url, 'internal:%s:%s:*' % (host,self.mimetype))
            res.size = None
            self.item.res.append(res)
            self.item.artist = self.parent.name


    def __del__(self):
        self.debug("BuzztardItem __del__", self.id, self.name)
        pass

    def remove(self,store):
        self.debug("BuzztardItem remove", self.id, self.name, self.parent)
        while len(self.children) > 0:
            child = self.children.pop()
            self.remove_child(child)
            del store[int(child.id)]

        if self.parent:
            self.parent.remove_child(self)

        del store[int(self.id)]
        del self.item
        del self

    def add_child(self, child, update=False):
        self.children.append(child)
        self.child_count += 1
        if isinstance(self.item, Container):
            self.item.childCount += 1
        if update == True:
            self.update_id += 1

    def remove_child(self, child):
        self.debug("remove_from %d (%s) child %d (%s)" % (self.id, self.get_name(), child.id, child.get_name()))
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

    def get_child_count(self):
        return self.child_count

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
        if self.parent == None:
            parent = 'root'
        else:
            parent = str(self.parent.get_id())
        return 'id: ' + str(self.id) +'/' + self.name + '/' + parent + ' ' + str(self.child_count) + ' @ ' + self.url

class BuzztardStore(log.Loggable,Plugin):
    logCategory = 'buzztard_store'
    implements = ['MediaServer']

    def __init__(self, server, **kwargs):
        self.next_id = 1000
        self.config = kwargs
        self.name = kwargs.get('name','Buzztard')

        self.urlbase = kwargs.get('urlbase','')
        if( len(self.urlbase)>0 and
            self.urlbase[len(self.urlbase)-1] != '/'):
            self.urlbase += '/'

        self.host = kwargs.get('host','127.0.0.1')
        self.port = int(kwargs.get('port',7654))

        self.server = server
        self.update_id = 0
        self.store = {}
        self.parent = None

        louie.connect( self.add_content, 'Buzztard.Response.browse', louie.Any)
        louie.connect( self.clear, 'Buzztard.Response.flush', louie.Any)

        self.buzztard = BzConnection(backend=self,host=self.host,port=self.port)


    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def add_content(self,line):
        data = line.split('|')[1:]
        parent = self.append(data[0], 'directory', self.parent)
        i = 0
        for label in data[1:]:
            self.append(':'.join((label,str(i))), 'audio/mpeg', parent)
            i += 1

    def append( self, name, mimetype, parent):

        id = self.getnextID()
        update = False
        if hasattr(self, 'update_id'):
            update = True

        self.store[id] = BuzztardItem( id, name, parent, mimetype,
                                        self.urlbase,self.host,update=update)
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

    def remove(self, id):
        item = self.store[int(id)]
        parent = item.get_parent()
        item.remove(self.store)
        try:
            del self.store[int(id)]
        except:
            pass
        if hasattr(self, 'update_id'):
            self.update_id += 1
            if self.server:
                self.server.content_directory_server.set_variable(0, 'SystemUpdateID', self.update_id)
            value = (parent.get_id(),parent.get_update_id())
            if self.server:
                self.server.content_directory_server.set_variable(0, 'ContainerUpdateIDs', value)


    def clear(self):
        for item in self.get_by_id(1000).get_children():
            self.remove(item.get_id())
        self.buzztard.connection.browse()

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

    def getnextID(self):
        ret = self.next_id
        self.next_id += 1
        return ret

    def upnp_init(self):
        self.current_connection_id = None
        self.parent = self.append('Buzztard', 'directory', None)

        source_protocols = ""
        if self.server:
            self.server.connection_manager_server.set_variable(0, 'SourceProtocolInfo',
                                                                    source_protocols,
                                                                    default=True)

        self.buzztard.connection.browse()


class BuzztardPlayer(log.Loggable):
    logCategory = 'buzztard_player'
    implements = ['MediaRenderer']
    vendor_value_defaults = {'RenderingControl': {'A_ARG_TYPE_Channel':'Master'}}
    vendor_range_defaults = {'RenderingControl': {'Volume': {'maximum':100}}}

    def __init__(self, device, **kwargs):
        self.name = kwargs.get('name','Buzztard MediaRenderer')
        self.host = kwargs.get('host','127.0.0.1')
        self.port = int(kwargs.get('port',7654))
        self.player = None

        self.playing = False
        self.state = None
        self.duration = None
        self.view = []
        self.tags = {}
        self.server = device

        self.poll_LC = LoopingCall( self.poll_player)

        louie.connect( self.event, 'Buzztard.Response.event', louie.Any)
        louie.connect( self.get_volume, 'Buzztard.Response.volume', louie.Any)
        louie.connect( self.get_mute, 'Buzztard.Response.mute', louie.Any)
        louie.connect( self.get_repeat, 'Buzztard.Response.repeat', louie.Any)
        self.buzztard = BzConnection(backend=self,host=self.host,port=self.port)

    def event(self,line):
        infos = line.split('|')[1:]
        self.debug(infos)
        if infos[0] == 'playing':
            transport_state = 'PLAYING'
        if infos[0] == 'stopped':
            transport_state = 'STOPPED'
        if infos[0] == 'paused':
            transport_state = 'PAUSED_PLAYBACK'
        if self.server != None:
            connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
        if self.state != transport_state:
            self.state = transport_state
            if self.server != None:
                self.server.av_transport_server.set_variable(connection_id,
                                             'TransportState', transport_state)

        label = infos[1]
        position = infos[2].split('.')[0]
        duration = infos[3].split('.')[0]
        if self.server != None:
            self.server.av_transport_server.set_variable(connection_id, 'CurrentTrack', 0)
            self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackDuration', duration)
            self.server.av_transport_server.set_variable(connection_id, 'CurrentMediaDuration', duration)
            self.server.av_transport_server.set_variable(connection_id, 'RelativeTimePosition', position)
            self.server.av_transport_server.set_variable(connection_id, 'AbsoluteTimePosition', position)

        try:
            self.server.rendering_control_server.set_variable(connection_id, 'Volume', int(infos[4]))
        except:
            pass

        try:
            if infos[5] in ['on','1','true','True','yes','Yes']:
                mute = True
            else:
                mute = False
            self.server.rendering_control_server.set_variable(connection_id, 'Mute', mute)
        except:
            pass

        try:
            if infos[6] in ['on','1','true','True','yes','Yes']:
                self.server.av_transport_server.set_variable(connection_id, 'CurrentPlayMode', 'REPEAT_ALL')
            else:
                self.server.av_transport_server.set_variable(connection_id, 'CurrentPlayMode', 'NORMAL')
        except:
            pass

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def poll_player( self):
        self.buzztard.connection.sendMessage('status')

    def load( self, uri, metadata):
        self.debug("load", uri, metadata)
        self.duration = None
        self.metadata = metadata
        connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
        self.server.av_transport_server.set_variable(connection_id, 'CurrentTransportActions','Play,Stop')
        self.server.av_transport_server.set_variable(connection_id, 'NumberOfTracks',1)
        self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackURI',uri)
        self.server.av_transport_server.set_variable(connection_id, 'AVTransportURI',uri)
        self.server.av_transport_server.set_variable(connection_id, 'AVTransportURIMetaData',metadata)
        self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackURI',uri)
        self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackMetaData',metadata)

    def start( self, uri):
        self.load( uri)
        self.play()

    def stop(self):
        self.buzztard.connection.sendMessage('stop')

    def play( self):
        connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
        label_id = self.server.av_transport_server.get_variable('CurrentTrackURI',connection_id).value
        id = '0'
        if ':' in label_id:
            label,id = label_id.split(':')
        self.buzztard.connection.sendMessage('play|%s' % id)

    def pause( self):
        self.buzztard.connection.sendMessage('pause')

    def seek(self, location):
        """
        @param location:    simple number = time to seek to, in seconds
                            +nL = relative seek forward n seconds
                            -nL = relative seek backwards n seconds
        """

    def mute(self):
        self.buzztard.connection.sendMessage('set|mute|on')

    def unmute(self):
         self.buzztard.connection.sendMessage('set|mute|off')

    def get_mute(self,line):
        infos = line.split('|')[1:]
        if infos[0] in ['on','1','true','True','yes','Yes']:
            mute = True
        else:
            mute = False
        self.server.rendering_control_server.set_variable(0, 'Mute', mute)

    def get_repeat(self,line):
        infos = line.split('|')[1:]
        if infos[0] in ['on','1','true','True','yes','Yes']:
            self.server.av_transport_server.set_variable(0, 'CurrentPlayMode', 'REPEAT_ALL')
        else:
            self.server.av_transport_server.set_variable(0, 'CurrentPlayMode', 'NORMAL')

    def set_repeat(self, playmode):
        if playmode in ['REPEAT_ONE','REPEAT_ALL']:
            self.buzztard.connection.sendMessage('set|repeat|on')
        else:
            self.buzztard.connection.sendMessage('set|repeat|off')

    def get_volume(self,line):
        infos = line.split('|')[1:]
        self.server.rendering_control_server.set_variable(0, 'Volume', int(infos[0]))

    def set_volume(self, volume):
        volume = int(volume)
        if volume < 0:
            volume=0
        if volume > 100:
            volume=100
        self.buzztard.connection.sendMessage('set|volume|%d'% volume)

    def upnp_init(self):
        self.current_connection_id = None
        self.server.connection_manager_server.set_variable(0, 'SinkProtocolInfo',
                            ['internal:%s:audio/mpeg:*' % self.host],
                            default=True)
        self.server.av_transport_server.set_variable(0, 'TransportState', 'NO_MEDIA_PRESENT', default=True)
        self.server.av_transport_server.set_variable(0, 'TransportStatus', 'OK', default=True)
        self.server.av_transport_server.set_variable(0, 'CurrentPlayMode', 'NORMAL', default=True)
        self.server.av_transport_server.set_variable(0, 'CurrentTransportActions', '', default=True)
        self.buzztard.connection.sendMessage('get|volume')
        self.buzztard.connection.sendMessage('get|mute')
        self.buzztard.connection.sendMessage('get|repeat')

        self.poll_LC.start( 1.0, True)

    def upnp_Play(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        Speed = int(kwargs['Speed'])
        self.play()
        return {}

    def upnp_Pause(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        self.pause()
        return {}

    def upnp_Stop(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        self.stop()
        return {}

    def upnp_SetAVTransportURI(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        CurrentURI = kwargs['CurrentURI']
        CurrentURIMetaData = kwargs['CurrentURIMetaData']
        local_protocol_info=self.server.connection_manager_server.get_variable('SinkProtocolInfo').value.split(',')
        if len(CurrentURIMetaData)==0:
            self.load(CurrentURI,CurrentURIMetaData)
            return {}
        else:
            elt = DIDLLite.DIDLElement.fromString(CurrentURIMetaData)
            print elt.numItems()
            if elt.numItems() == 1:
                item = elt.getItems()[0]
                for res in item.res:
                    print res.protocolInfo,local_protocol_info
                    if res.protocolInfo in local_protocol_info:
                        self.load(CurrentURI,CurrentURIMetaData)
                        return {}
        return failure.Failure(errorCode(714))

    def upnp_SetMute(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        Channel = kwargs['Channel']
        DesiredMute = kwargs['DesiredMute']
        if DesiredMute in ['TRUE', 'True', 'true', '1','Yes','yes']:
            self.mute()
        else:
            self.unmute()
        return {}

    def upnp_SetVolume(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        Channel = kwargs['Channel']
        DesiredVolume = int(kwargs['DesiredVolume'])
        self.set_volume(DesiredVolume)
        return {}

def test_init_complete(backend):

    print "Houston, we have a touchdown!"
    backend.buzztard.sendMessage('browse')

def main():

    louie.connect( test_init_complete, 'Coherence.UPnP.Backend.init_completed', louie.Any)

    f = BuzztardStore(None)

    f.parent = f.append('Buzztard', 'directory', None)
    print f.parent
    print f.store
    f.add_content('playlist|test label|start|stop')
    print f.store
    f.clear()
    print f.store
    f.add_content('playlist|after flush label|flush-start|flush-stop')
    print f.store

    #def got_upnp_result(result):
    #    print "upnp", result

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
