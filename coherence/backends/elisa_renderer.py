# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.defer import Deferred
from twisted.python import failure

from twisted.spread import pb

from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core import DIDLLite

import string

import pygst
pygst.require('0.10')
import gst

import louie

from coherence.extern.logger import Logger
log = Logger('ElisaPlayer')

class ElisaPlayer:

    """ a backend to the Elisa player
    
    """

    implements = ['MediaRenderer']
    vendor_value_defaults = {'RenderingControl': {'A_ARG_TYPE_Channel':'Master'}}
    vendor_range_defaults = {'RenderingControl': {'Volume': {'maximum':100}}}

    def __init__(self, device, **kwargs):
        self.name = kwargs.get('name','Elisa MediaRenderer')
        self.host = kwargs.get('host','127.0.0.1')
        self.player = None
        
        if self.host == 'internal':
            try:
                from elisa.core import common
                self.player = common.get_application().get_player()
                louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)
            except:
                log.warning("this works only from within Elisa")
                raise ImportError
        else:
            factory = pb.PBClientFactory()
            reactor.connectTCP(self.host, 8789, factory)
            d = factory.getRootObject()
            
            def result(player):
                self.player = player
                louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)
                
            def got_error(error):
                log.warning("connection to Elisa failed!")

            d.addCallback(lambda object: object.callRemote("get_player"))
            d.addCallback(result)
            d.addErrback(got_error)

    
        self.playing = False
        self.state = None
        self.duration = None
        self.view = []
        self.tags = {}
        self.server = device
        self.poll_LC = LoopingCall( self.poll_player)

        
    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def poll_player( self):
        def got_result(result):
            if self.server != None:
                connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
            if result == 'STOPPED':
                transport_state = 'STOPPED'
            if result == 'PLAYING':
                transport_state = 'PLAYING'
            if result == 'PAUSED':                
                transport_state = 'PAUSED_PLAYBACK'
                
            if transport_state == 'PLAYING':
                self.query_position()

            if self.state != transport_state:
                self.state = transport_state                             
                if self.server != None:
                    self.server.av_transport_server.set_variable(connection_id,
                                                 'TransportState', transport_state) 
                                                        
        dfr = self.player.callRemote("get_readable_state")
        dfr.addCallback(got_result)
        

    def query_position( self):
        def got_result(result):
            print result
            position, duration = result
            if self.server != None:
                connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
                self.server.av_transport_server.set_variable(connection_id, 'CurrentTrack', 0)
                if position is not None:
                    m,s = divmod( position/1000000000, 60)
                    h,m = divmod(m,60)
                    self.server.av_transport_server.set_variable(connection_id, 'RelativeTimePosition', '%02d:%02d:%02d' % (h,m,s))
                    self.server.av_transport_server.set_variable(connection_id, 'AbsoluteTimePosition', '%02d:%02d:%02d' % (h,m,s))
                if duration is not None:
                    m,s = divmod( duration/1000000000, 60)
                    h,m = divmod(m,60)
                    self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackDuration', '%02d:%02d:%02d' % (h,m,s))
                    self.server.av_transport_server.set_variable(connection_id, 'CurrentMediaDuration', '%02d:%02d:%02d' % (h,m,s))

                    if self.duration is None:
                        elt = DIDLLite.DIDLElement.fromString(self.metadata)
                        for item in elt:
                            for res in item.findall('res'):
                                m,s = divmod( duration/1000000000, 60)
                                h,m = divmod(m,60)
                                res.attrib['duration'] = "%d:%02d:%02d" % (h,m,s)
                        self.metadata = elt.toString()
                        self.server.av_transport_server.set_variable(connection_id, 'AVTransportURIMetaData',self.metadata)
                        self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackMetaData',self.metadata)
                        self.duration = duration
                                    
        dfr = self.player.callRemote("get_status")
        dfr.addCallback(got_result)
        
        
        
    def load( self, uri, metadata):

        def got_result(result):
            self.duration = None
            self.metadata = metadata
            self.tags = {}
            connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
            self.server.av_transport_server.set_variable(connection_id, 'CurrentTransportActions','Play,Stop,Pause')
            self.server.av_transport_server.set_variable(connection_id, 'NumberOfTracks',1)
            self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackURI',uri)
            self.server.av_transport_server.set_variable(connection_id, 'AVTransportURI',uri)
            self.server.av_transport_server.set_variable(connection_id, 'AVTransportURIMetaData',metadata)
            self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackURI',uri)
            self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackMetaData',metadata)

        dfr = self.player.callRemote("set_uri", uri)
        dfr.addCallback(got_result)


    def start( self, uri):
        self.load( uri)
        self.play()
        
    def stop(self):
        def got_result(result):
            self.server.av_transport_server.set_variable( \
                self.server.connection_manager_server.lookup_avt_id(self.current_connection_id),\
                                 'TransportState', 'STOPPED')        
        dfr = self.player.callRemote("stop")
        dfr.addCallback(got_result)
        
    def play( self):   
        def got_result(result):
            self.server.av_transport_server.set_variable( \
                self.server.connection_manager_server.lookup_avt_id(self.current_connection_id),\
                                 'TransportState', 'PLAYING')        
        dfr = self.player.callRemote("play")
        dfr.addCallback(got_result)

    def pause( self):
        def got_result(result):
            self.server.av_transport_server.set_variable( \
                self.server.connection_manager_server.lookup_avt_id(self.current_connection_id),\
                                 'TransportState', 'PAUSED_PLAYBACK')        
        dfr = self.player.callRemote("pause")
        dfr.addCallback(got_result)


    def seek(self, location):
        """
        @param location:    simple number = time to seek to, in seconds
                            +nL = relative seek forward n seconds
                            -nL = relative seek backwards n seconds
        """
        


    def mute(self):
        def got_result(result):
            rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
            #FIXME: use result, not True
            self.server.rendering_control_server.set_variable(rcs_id, 'Mute', 'True')

        dfr=self.player.callRemote("mute")
        dfr.addCallback(got_result)
        
    def unmute(self):
        def got_result(result):
            rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
            #FIXME: use result, not False
            self.server.rendering_control_server.set_variable(rcs_id, 'Mute', 'False')

        dfr=self.player.callRemote("un_mute")
        dfr.addCallback(got_result)
        
    def get_mute(self):
        def got_infos(result):
            log.info("get_mute", result)
            return result
            
        dfr=self.player.callRemote("get_mute")
        dfr.addCallback(got_infos)
        return dfr
        
    def get_volume(self):
        """ playbin volume is a double from 0.0 - 10.0
        """
        def got_infos(result):
            log.info("get_volume", result)
            return result
            
        dfr=self.player.callRemote("get_volume")
        dfr.addCallback(got_infos)
        return dfr
        
    def set_volume(self, volume):
        volume = int(volume)
        if volume < 0:
            volume=0
        if volume > 100:
            volume=100
            
        def got_result(result):
            rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
            #FIXME: use result, not volume
            self.server.rendering_control_server.set_variable(rcs_id, 'Volume', volume)
                
        dfr=self.player.callRemote("set_volume",volume)
        dfr.addCallback(got_result)
        
    def upnp_init(self):
        self.current_connection_id = None
        self.server.connection_manager_server.set_variable(0, 'SinkProtocolInfo',
                            ['internal:%s:audio/mpeg:*' % self.host,
                             'http-get:*:audio/mpeg:*'],
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

    f = ElisaPlayer(None)

    def call_player():
        f.get_volume()
        f.get_mute()
        f.poll_player()
    
    reactor.callLater(2,call_player)
    
if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
