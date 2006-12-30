# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.python import failure

from coherence.upnp.core.soap_service import errorCode

import string

import pygst
pygst.require('0.10')
import gst

class Player:

    """ a backend with a GStreamer based audio player
    
        needs gnomevfssrc from gst-plugins-base
        unfortunately gnomevfs has way too much dependencies

        # not working -> http://bugzilla.gnome.org/show_bug.cgi?id=384140
        # needs the neonhttpsrc plugin from gst-plugins-bad
        # tested with CVS version
        # and with this patch applied
        # --> http://bugzilla.gnome.org/show_bug.cgi?id=375264
        # not working
        
        and id3demux from gst-plugins-good CVS too

    """

    implements = ['MediaRenderer']

    def __init__(self, server):
        self.player = gst.element_factory_make("playbin", "myplayer")
        self.playing = False
        self.duration = None
        self.connection_id = None
        self.view = []
        self.tags = {}
        self.server = server

        self.bus = self.player.get_bus()
        self.poll_LC = LoopingCall( self.poll_gst_bus)
        self.poll_LC.start( 0.3)
        self.update_LC = LoopingCall( self.update)

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
        elif current == gst.STATE_PAUSED:
            state = 'paused'
        else:
            state = 'idle'

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
            self.server.av_transport_server.set_variable(0, 'CurrentTrack', 0)
            duration = string.atol(position[u'raw'][u'duration'])
            m,s = divmod( duration/1000000000, 60)
            h,m = divmod(m,60)
            self.server.av_transport_server.set_variable(0, 'CurrentTrackDuration', '%02d:%02d:%02d' % (h,m,s))
            position = string.atol(position[u'raw'][u'position'])
            m,s = divmod( position/1000000000, 60)
            h,m = divmod(m,60)
            self.server.av_transport_server.set_variable(0, 'RelativeTimePosition', '%02d:%02d:%02d' % (h,m,s))
            self.server.av_transport_server.set_variable(0, 'AbsoluteTimePosition', '%02d:%02d:%02d' % (h,m,s))
        
    def load( self, uri):
        print "load -->", uri
        _,state,_ = self.player.get_state()
        if( state == gst.STATE_PLAYING or state == gst.STATE_PAUSED):
            self.stop()
        self.player.set_property('uri', uri)
        self.duration = None
        self.tags = {}
        #self.player.set_state(gst.STATE_PAUSED)
        self.player.set_state(gst.STATE_READY)
        self.server.av_transport_server.set_variable(0, 'CurrentTrackURI', uri)
        #self.server.av_transport_server.set_variable(0, 'TransportState', 'TRANSITIONING')
        self.server.av_transport_server.set_variable(0, 'AVTransportURIMetaData', 'NOT_IMPLEMENTED')
        self.server.av_transport_server.set_variable(0, 'CurrentTransportActions',
                                                            'Play,Stop,Pause,Seek,Next,Previous')
        self.update()
        print "load <--"

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
        self.server.av_transport_server.set_variable(0, 'TransportState', 'STOPPED')
        self.seek('-0')
        
    def play( self):   
        print "play -->"
        _,state,_ = self.player.get_state()
        #if( state == gst.STATE_PLAYING or state == gst.STATE_PAUSED):
        if state == gst.STATE_PLAYING:
            print 'we are already playing, so this means probably to stop'
            self.stop()
            return
        print 'Playing:', self.player.get_property('uri')
        self.player.set_state(gst.STATE_PLAYING)
        self.server.av_transport_server.set_variable(0, 'TransportState', 'PLAYING')
        print "play <--"

    def pause( self):
        _,state,_ = self.player.get_state()
        if state == gst.STATE_PAUSED:
            print 'we are already paused, so this means probably to play again'
            self.play()
            return
        if state == gst.STATE_READY:
            return
        print 'Pausing:', self.player.get_property('uri')
        self.server.av_transport_server.set_variable(0, 'TransportState', 'PAUSED_PLAYBACK')
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
                
    def upnp_init(self):
        self.server.connection_manager_server.set_variable(0, 'SinkProtocolInfo', 'http-get:*:audio/mpeg:*')
        self.server.av_transport_server.set_variable(0, 'TransportState', 'NO_MEDIA_PRESENT')
        self.server.av_transport_server.set_variable(0, 'TransportStatus', 'OK')
        self.server.av_transport_server.set_variable(0, 'CurrentPlayMode', 'NORMAL')
        self.server.av_transport_server.set_variable(0, 'CurrentTransportActions', '')

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
        self.pause()
        return {}
        
    def upnp_SetAVTransportURI(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        CurrentURI = kwargs['CurrentURI']
        CurrentURIMetaData = kwargs['CurrentURIMetaData']
        self.start(CurrentURI)
        return {}

    def upnp_PrepareForConnection(self, *args, **kwargs):
        """ check if we really support that mimetype """
        RemoteProtocolInfo = kwargs['RemoteProtocolInfo']
        """ if we are a MR and this in not 'Input'
            then there is something strange going on
        """
        Direction = kwargs['Direction']
        """ the InstanceID of the MS ? """
        PeerConnectionID = kwargs['PeerConnectionID']
        """ ??? """
        PeerConnectionManager = kwargs['PeerConnectionManager']
        if self.server:
            self.connection_id = \
                    self.server.connection_manager_server.add_connection(RemoteProtocolInfo,
                                                                            Direction,
                                                                            PeerConnectionID,
                                                                            PeerConnectionManager)

        return {'ConnectionID': self.connection_id, 'AVTransportID': 0, 'RcsID': 0}

    def upnp_ConnectionComplete(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        """ remove this InstanceID
            and the associated InstanceIDs @ AVTransportID and RcsID
        """
        if self.server:
            self.server.connection_manager_server.remove_connection(self.connection_id)
        return {}

    def Xupnp_GetPositionInfo(self, *args, **kwargs):
        InstanceID = int(kwargs['InstanceID'])
        """ get track info for this InstanceID
        
            or send a 718 if there isn't such a InstanceID
        """
        return failure.Failure(errorCode(718))
        return {}
            
if __name__ == '__main__':

    import sys
    
    p = Player(None)
    if len(sys.argv) > 1:
        reactor.callWhenRunning( p.start, sys.argv[1])

    reactor.run()
