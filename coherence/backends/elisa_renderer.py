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
                print "player", player
                louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)
                
                def got_infos(infos):
                    print infos

                dfr = self.player.callRemote("get_status_informations")
                dfr.addCallback(got_infos)
                
            def got_error(error):
                print "connection to Elisa failed!"

            d.addCallback(lambda object: object.callRemote("get_player"))
            d.addCallback(result)
            d.addErrback(got_error)

    
        self.playing = False
        self.duration = None
        self.view = []
        self.tags = {}
        self.server = device

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def poll_gst_bus( self):
        # FIXME: isn't there any better way to do this?
        #print 'poll_gst_bus'
        while True:
            # FIXME: maybe a counter, so we don't stay to long in here?
            message = self.bus.poll(gst.MESSAGE_ERROR|gst.MESSAGE_EOS| \
                                        gst.MESSAGE_TAG|gst.MESSAGE_STATE_CHANGED,
                                    timeout=1)
            if message == None:
                return
            self.on_message(self.bus, message)
            
    def on_message(self, bus, message):
        #print "on_message", message
        #print "from", message.src.get_name()
        t = message.type
        #print t
        if t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Gstreamer error: %s" % err, debug
            if self.playing == True:
                self.seek('-0')
            #self.player.set_state(gst.STATE_READY)
        elif t == gst.MESSAGE_TAG:
            for key in message.parse_tag().keys():
                self.tags[key] = message.structure[key]
            #print self.tags
        elif t == gst.MESSAGE_STATE_CHANGED:
            if message.src == self.player:
                old, new, pending = message.parse_state_changed()
                #print "player (%s) state_change:" %(message.src.get_path_string()), old, new, pending
                if new == gst.STATE_PLAYING:
                    self.playing = True
                    self.update_LC.start( 1, False)
                    self.update()
                elif old == gst.STATE_PLAYING:
                    self.playing = False
                    self.update_LC.stop()
                    self.update()
                #elif new == gst.STATE_READY:
                #    self.update()

        elif t == gst.MESSAGE_EOS:
            print "reached file end"
            self.seek('-0')
            self.update()
        
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
        print "load -->", uri
        _,state,_ = self.player.get_state()
        if( state == gst.STATE_PLAYING or state == gst.STATE_PAUSED):
            self.stop()
        else:
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'STOPPED')
        self.player.set_property('uri', uri)
        self.duration = None
        self.tags = {}
        #self.player.set_state(gst.STATE_PAUSED)
        self.player.set_state(gst.STATE_READY)
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentTrackURI', uri)
        #self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'TRANSITIONING')
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'AVTransportURIMetaData', 'NOT_IMPLEMENTED')
        #self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentTransportActions','Play,Stop,Pause,Seek,Next,Previous')
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentTransportActions','Play,Stop,Pause')
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'NumberOfTracks',1)
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'CurrentTracks',1)
        self.update()
        print "load <--"
        if state == gst.STATE_PLAYING:
            self.play()

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
        if self.player.get_property('uri') == None:
            return
        print 'Stopping:', self.player.get_property('uri')
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'STOPPED')
        self.seek('-0')
        
    def play( self):   
        print "play -->"
        print 'Playing:', self.player.get_property('uri')
        self.player.set_state(gst.STATE_PLAYING)
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'PLAYING')
        print "play <--"

    def pause( self):
        print 'Pausing:', self.player.get_property('uri')
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'PAUSED_PLAYBACK')
        self.player.set_state(gst.STATE_PAUSED)
        
    def seek(self, location):
        """
        @param location:    simple number = time to seek to, in seconds
                            +nL = relative seek forward n seconds
                            -nL = relative seek backwards n seconds
        """
        
        _,state,_ = self.player.get_state()
        if state != gst.STATE_PAUSED:
            self.player.set_state(gst.STATE_PAUSED)
        l = long(location)*1000000000
        p = self.query_position()
        
        #print p['raw']['position'], l

        if location[0] == '+':
            l =  long(p[u'raw'][u'position']) + (long(location[1:])*1000000000)
            l = min( l, long(p[u'raw'][u'duration']))
        if location[0] == '-':
            if location == '-0':
                l = 0L
            else:
                l = long(p[u'raw'][u'position']) - (long(location[1:])*1000000000)
                l = max( l, 0L)


        print "seeking to %r" % l
        """
        self.player.seek( 1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
            gst.SEEK_TYPE_SET, l,
            gst.SEEK_TYPE_NONE, 0)

        """
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_KEY_UNIT,
            gst.SEEK_TYPE_SET, l,
            gst.SEEK_TYPE_NONE, 0)

        res = self.player.send_event(event)
        if res:
            pass
            #print "setting new stream time to 0"
            #self.player.set_new_stream_time(0L)
        else:
            print "seek to %r failed" % location

        if location == '-0':
            self.player.set_state(gst.STATE_READY)
        else:
            self.player.set_state(state)
            if state == gst.STATE_PAUSED:
                self.update()

    def mute(self):
        self.player.callRemote("mute")
        rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
        self.server.rendering_control_server.set_variable(rcs_id, 'Mute', 'True')
        
    def unmute(self):
        self.player.callRemote("un_mute")
        rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
        self.server.rendering_control_server.set_variable(rcs_id, 'Mute', 'False')
        
    def get_mute(self):
        def got_infos(result):
            print "get_mute", result
            return result
            
        dfr=self.player.callRemote("get_mute")
        dfr.addCallback(got_infos)
        print "get_mute", dfr
        return dfr
        
    def get_volume(self):
        """ playbin volume is a double from 0.0 - 10.0
        """
        def got_infos(result):
            print "get_volume", result
            return result
            
        dfr=self.player.callRemote("get_volume")
        dfr.addCallback(got_infos)
        print "get_volume", dfr
        return dfr
        
    def set_volume(self, volume):
        volume = int(volume)
        if volume < 0:
            volume=0
        if volume > 100:
            volume=100
        self.player.callRemote("set_volume",volume)
        rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
        self.server.rendering_control_server.set_variable(rcs_id, 'Volume', volume)
        
    def upnp_init(self):
        self.current_connection_id = None
        self.server.connection_manager_server.set_variable(0, 'SinkProtocolInfo', 'http-get:*:audio/mpeg:*', default=True)
        self.server.av_transport_server.set_variable(0, 'TransportState', 'NO_MEDIA_PRESENT', default=True)
        self.server.av_transport_server.set_variable(0, 'TransportStatus', 'OK', default=True)
        self.server.av_transport_server.set_variable(0, 'CurrentPlayMode', 'NORMAL', default=True)
        self.server.av_transport_server.set_variable(0, 'CurrentTransportActions', '', default=True)
        self.server.rendering_control_server.set_variable(0, 'Volume', self.get_volume())
        self.server.rendering_control_server.set_variable(0, 'Mute', self.get_mute())

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
    
    reactor.callLater(2,call_player)
    
if __name__ == '__main__':

    from twisted.internet import reactor

    reactor.callWhenRunning(main)
    reactor.run()
