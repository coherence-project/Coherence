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
        self.host = kwargs.get('host','localhost')
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
            print result
            if self.server != None:
                connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
            if result == 'STOPPED':
                transport_state = 'STOPPED'
            if result == 'PLAYING':
                transport_state = 'PLAYING'
            if result == 'PAUSED':                
                transport_state = 'PAUSED_PLAYBACK'

            if self.state != transport_state:
                self.state = transport_state                             
                if self.server != None:
                    self.server.av_transport_server.set_variable(connection_id,
                                                 'TransportState', transport_state) 
                                                        
        dfr = self.player.callRemote("get_readable_state")
        dfr.addCallback(got_result)
        

    def query_position( self):
        #print "query_position"
        try:
            position, format = self.player.query_position(gst.FORMAT_TIME)
        except:
            print "CLOCK_TIME_NONE", gst.CLOCK_TIME_NONE
            position = gst.CLOCK_TIME_NONE
            position = 0
        #print position

        if self.duration == None:
            try:
                self.duration, format = self.player.query_duration(gst.FORMAT_TIME)
            except:
                self.duration = gst.CLOCK_TIME_NONE
                self.duration = 0
        #print self.duration
            
        r = {}
        if self.duration == 0:
            self.duration = None
            return r
        r[u'raw'] = {u'position':unicode(str(position)), u'remaining':unicode(str(self.duration - position)), u'duration':unicode(str(self.duration))}
            
        position_human = u'%d:%02d' % (divmod( position/1000000000, 60))
        duration_human = u'%d:%02d' % (divmod( self.duration/1000000000, 60))
        remaining_human = u'%d:%02d' % (divmod( (self.duration-position)/1000000000, 60))
        
        r[u'human'] = {u'position':position_human, u'remaining':remaining_human, u'duration':duration_human}
        r[u'percent'] = {u'position':position*100/self.duration, u'remaining':100-(position*100/self.duration)}

        #print r
        return r



    def update( self):
        #print "update"
        _, current,_ = self.player.get_state()
        if( current != gst.STATE_PLAYING and current != gst.STATE_PAUSED and current != gst.STATE_READY):
            print "I'm out"
            return
        if current == gst.STATE_PLAYING:
            state = 'playing'
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'PLAYING')
        elif current == gst.STATE_PAUSED:
            state = 'paused'
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'PAUSED_PLAYBACK')
        else:
            state = 'idle'
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'STOPPED')

        position = self.query_position()
        #print position

        for view in self.view:
            view.status( self.status( position))

        if position.has_key(u'raw'):
            print "%s %d/%d/%d - %d%%/%d%% - %s/%s/%s" % (state,
                            string.atol(position[u'raw'][u'position'])/1000000000,
                            string.atol(position[u'raw'][u'remaining'])/1000000000,
                            string.atol(position[u'raw'][u'duration'])/1000000000,
                            position[u'percent'][u'position'],
                            position[u'percent'][u'remaining'],
                            position[u'human'][u'position'],
                            position[u'human'][u'remaining'],
                            position[u'human'][u'duration'])
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentTrack', 0)
            duration = string.atol(position[u'raw'][u'duration'])
            m,s = divmod( duration/1000000000, 60)
            h,m = divmod(m,60)
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentTrackDuration', '%02d:%02d:%02d' % (h,m,s))
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentMediaDuration', '%02d:%02d:%02d' % (h,m,s))
            position = string.atol(position[u'raw'][u'position'])
            m,s = divmod( position/1000000000, 60)
            h,m = divmod(m,60)
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'RelativeTimePosition', '%02d:%02d:%02d' % (h,m,s))
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'AbsoluteTimePosition', '%02d:%02d:%02d' % (h,m,s))
        
    def load( self, uri):
        def got_result(result):
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentTransportActions','Play,Stop,Pause')
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'NumberOfTracks',1)
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentTracks',1)

        dfr = self.player.callRemote("set_uri", uri)
        dfr.addCallback(got_result)

    def status( self, position):
        uri = self.player.get_property('uri')
        if uri == None:
            return {u'state':u'idle',u'uri':u''}
        else:
            r = {u'uri':unicode(uri),
                 u'position':position}
            if self.tags != {}:
                try:
                    r[u'artist'] = unicode(self.tags['artist'])
                except:
                    pass
                try:
                    r[u'title'] = unicode(self.tags['title'])
                except:
                    pass
                try:
                    r[u'album'] = unicode(self.tags['album'])
                except:
                    pass
                    
            if self.player.get_state()[1] == gst.STATE_PLAYING:
                r[u'state'] = u'playing'
            elif self.player.get_state()[1] == gst.STATE_PAUSED:
                r[u'state'] = u'paused'
            else:
                r[u'state'] = u'idle'

            return r
        
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
        self.server.connection_manager_server.set_variable(0, 'SinkProtocolInfo', 'http-get:*:audio/mpeg:*', default=True)
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
        elt = DIDLLite.DIDLElement.fromString(CurrentURIMetaData)
        if elt.numItems() == 1:
            item = elt.getItems()[0]
            for res in item.res:
                if res.protocolInfo in local_protocol_info:
                    self.load(CurrentURI)
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
