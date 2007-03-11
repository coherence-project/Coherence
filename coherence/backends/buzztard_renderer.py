# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred
from twisted.python import failure

from twisted.internet import reactor, protocol
from twisted.protocols.basic import LineReceiver

from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core import DIDLLite

import string

import louie

from coherence.extern.logger import Logger
log = Logger('BuzztardPlayer')

class BzClient(LineReceiver):
    
    def __init__( self):
        self.expecting_content = False

    def connectionMade(self):
        print "connected to Buzztard"
        self.factory.clientReady(self)

    def lineReceived(self, line):
        print "received:", line
        
class BzFactory(protocol.ClientFactory):          

    protocol = BzClient
    
    def __init__(self,backend):
        self.backend = backend

    def clientConnectionFailed(self, connector, reason):
        print 'connection failed:', reason.getErrorMessage()

    def clientConnectionLost(self, connector, reason):
        print 'connection lost:', reason.getErrorMessage()

    def startFactory(self):
        self.messageQueue = []
        self.clientInstance = None

    def clientReady(self, instance):
        print "clientReady"
        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self.backend)
        self.clientInstance = instance
        for msg in self.messageQueue:
            self.sendMessage(msg)

    def sendMessage(self, msg):
        if self.clientInstance is not None:
            self.clientInstance.sendLine(msg)
        else:
            self.messageQueue.append(msg)

class BuzztardPlayer:

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
        
        self.buzztard = BzFactory(self)
        reactor.connectTCP( self.host, self.port, self.buzztard)

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def poll_player( self):
        pass

    def query_position( self):
        pass

    def load( self, uri, metadata):
        pass

    def start( self, uri):
        self.load( uri)
        self.play()

    def stop(self):
        self.buzztard.sendMessage('stop')

    def play( self):
        self.buzztard.sendMessage('play')

    def pause( self):
        self.buzztard.sendMessage('pause')

    def seek(self, location):
        """
        @param location:    simple number = time to seek to, in seconds
                            +nL = relative seek forward n seconds
                            -nL = relative seek backwards n seconds
        """

    def mute(self):
        pass
    
    def unmute(self):
        pass
    
    def get_mute(self):
        return False
        
    def get_volume(self):
        return 50
        
    def set_volume(self, volume):
        pass
        
    def upnp_init(self):
        self.current_connection_id = None
        self.server.connection_manager_server.set_variable(0, 'SinkProtocolInfo',
                            ['internal:%s:audio/mpeg:*' % self.host],
                            default=True)
        self.server.av_transport_server.set_variable(0, 'TransportState', 'NO_MEDIA_PRESENT', default=True)
        self.server.av_transport_server.set_variable(0, 'TransportStatus', 'OK', default=True)
        self.server.av_transport_server.set_variable(0, 'CurrentPlayMode', 'NORMAL', default=True)
        self.server.av_transport_server.set_variable(0, 'CurrentTransportActions', '', default=True)
        self.server.rendering_control_server.set_variable(0, 'Volume', self.get_volume())
        self.server.rendering_control_server.set_variable(0, 'Mute', self.get_mute())
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
        else:
            elt = DIDLLite.DIDLElement.fromString(CurrentURIMetaData)
            if elt.numItems() == 1:
                item = elt.getItems()[0]
                for res in item.res:
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
        
def main():

    f = BuzztardPlayer(None)

    def call_player():
        f.get_volume()
        f.get_mute()
        f.poll_player()
    
    reactor.callLater(2,call_player)
    
if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
