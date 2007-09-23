# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.python import failure

from coherence.upnp.core.soap_service import errorCode
from coherence.upnp.core import DIDLLite

import string
import os, platform

import pygst
pygst.require('0.10')
import gst

import louie

from coherence.extern.simple_plugin import Plugin

from coherence import log

class Player(log.Loggable):
    logCategory = 'gstreamer_player'

    def __init__(self, default_mimetype='audio/mpeg'):
        self.player = None
        self.source = None
        self.sink = None
        self.bus = None
        self.poll_LC = None

        self.views = []

        self.playing = False
        self.duration = None

        self.mimetype = default_mimetype
        self.create_pipeline(self.mimetype)
        self.create_poll()

    def add_view(self,view):
        self.views.append(view)

    def remove_view(self,view):
        self.views.remove(view)

    def update(self):
        for v in self.views:
            v()

    def create_pipeline(self, mimetype):
        if platform.uname()[1].startswith('Nokia'):
            self.bus = None
            self.player = None
            self.source = None
            self.sink = None

            if mimetype == 'application/ogg':
                self.player = gst.parse_launch('gnomevfssrc name=source ! oggdemux ! ivorbisdec ! audioconvert ! dsppcmsink name=sink')
                self.player.set_name('oggplayer')
                self.set_volume = self.set_volume_dsp_pcm_sink
                self.get_volume = self.get_volume_dsp_pcm_sink
            else:
                self.player = gst.parse_launch('gnomevfssrc name=source ! id3lib ! dspmp3sink name=sink')
                self.player.set_name('mp3player')
                self.set_volume = self.set_volume_dsp_mp3_sink
                self.get_volume = self.get_volume_dsp_mp3_sink
            self.source = self.player.get_by_name('source')
            self.sink = self.player.get_by_name('sink')
            self.player_uri = 'location'
        else:
            self.player = gst.element_factory_make('playbin', 'player')
            self.player_uri = 'uri'
            self.source = self.sink = self.player
            self.set_volume = self.set_volume_playbin
            self.get_volume = self.get_volume_playbin

        self.bus = self.player.get_bus()
        self.player_clean = True

    def create_poll(self):
        self.poll_LC = LoopingCall( self.poll_gst_bus)
        self.poll_LC.start( 0.3)
        self.update_LC = LoopingCall( self.update)

    def get_volume_playbin(self):
        """ playbin volume is a double from 0.0 - 10.0
        """
        volume = self.sink.get_property('volume')
        return int(volume*10)

    def set_volume_playbin(self, volume):
        volume = int(volume)
        if volume < 0:
            volume=0
        if volume > 100:
            volume=100
        self.sink.set_property('volume', float(volume)/10)

    def get_volume_dsp_mp3_sink(self):
        """ dspmp3sink volume is a n in from 0 to 65535
        """
        volume = self.sink.get_property('volume')
        return int(volume*100/65535)

    def set_volume_dsp_mp3_sink(self, volume):
        volume = int(volume)
        if volume < 0:
            volume=0
        if volume > 100:
            volume=100
        self.sink.set_property('volume',  volume*65535/100)

    def get_volume_dsp_pcm_sink(self):
        """ dspmp3sink volume is a n in from 0 to 65535
        """
        volume = self.sink.get_property('volume')
        return int(volume*100/65535)

    def set_volume_dsp_pcm_sink(self, volume):
        volume = int(volume)
        if volume < 0:
            volume=0
        if volume > 100:
            volume=100
        self.sink.set_property('volume',  volume*65535/100)

    def mute(self):
        if hasattr(self,'stored_volume'):
            self.stored_volume = self.sink.get_property('volume')
            self.sink.set_property('volume', 0)
        else:
            self.sink.set_property('mute', True)

    def unmute(self):
        if hasattr(self,'stored_volume'):
            self.sink.set_property('volume', self.stored_volume)
        else:
            self.sink.set_property('mute', False)

    def get_mute(self):
        if hasattr(self,'stored_volume'):
            muted = self.sink.get_property('volume') == 0
        else:
            try:
                muted = self.sink.get_property('mute')
            except TypeError:
                if not hasattr(self,'stored_volume'):
                    self.stored_volume = self.sink.get_property('volume')
                muted = self.stored_volume == 0
            except:
                muted = False
                print "can't get mute state"
        return muted

    def get_state(self):
        return self.player.get_state()

    def get_uri(self):
        return self.source.get_property(self.player_uri)

    def poll_gst_bus( self):
        # FIXME: isn't there any better way to do this?
        #print 'poll_gst_bus'
        if self.bus == None:
            return
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
                    try:
                        self.update_LC.stop()
                    except:
                        pass
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
            #print "CLOCK_TIME_NONE", gst.CLOCK_TIME_NONE
            position = gst.CLOCK_TIME_NONE
            position = 0
        #print position

        if self.duration == None:
            try:
                self.duration, format = self.player.query_duration(gst.FORMAT_TIME)
            except:
                self.duration = gst.CLOCK_TIME_NONE
                self.duration = 0
                #import traceback
                #print traceback.print_exc()

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

        self.debug(r)
        return r

    def load( self, uri, mimetype):
        print "load -->", uri, mimetype
        _,state,_ = self.player.get_state()
        if( state == gst.STATE_PLAYING or state == gst.STATE_PAUSED):
            self.stop()

        print "player -->", self.player.get_name()
        if self.player.get_name() != 'player':
            self.create_pipeline(mimetype)

        self.source.set_property(self.player_uri, uri)
        self.player_clean = True
        self.duration = None
        self.mimetype = mimetype
        self.tags = {}
        #self.player.set_state(gst.STATE_PAUSED)
        self.player.set_state(gst.STATE_READY)
        self.update()
        print "load <--"
        if state == gst.STATE_PLAYING:
            self.play()

    def play( self):
        uri = self.get_uri()
        mimetype = self.mimetype
        print "play -->", uri, mimetype

        if self.player.get_name() != 'player':
            if self.player_clean == False:
                print "rebuild pipeline"
                self.player.set_state(gst.STATE_NULL)

                self.create_pipeline(mimetype)

                self.source.set_property(self.player_uri, uri)
                self.player.set_state(gst.STATE_READY)
        else:
            self.player_clean = True
        self.player.set_state(gst.STATE_PLAYING)
        print "play <--"

    def pause(self):
        self.player.set_state(gst.STATE_PAUSED)

    def stop(self):
        self.seek('-0')

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
        elif location != '-0':
            print "seek to %r failed" % location

        if location == '-0':

            try:
                self.update_LC.stop()
            except:
                pass
            if self.player.get_name != 'player':
                self.player.set_state(gst.STATE_NULL)
                self.player_clean = False
            else:
                self.player.set_state(gst.STATE_NULL)
                #self.player.set_state(gst.STATE_READY)
            #self.playing = False
            self.update()
        else:
            self.player.set_state(state)
            if state == gst.STATE_PAUSED:
                self.update()


class GStreamerPlayer(log.Loggable,Plugin):

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

    logCategory = 'gstreamer_player'
    implements = ['MediaRenderer']
    vendor_value_defaults = {'RenderingControl': {'A_ARG_TYPE_Channel':'Master'}}
    vendor_range_defaults = {'RenderingControl': {'Volume': {'maximum':100}}}

    def __init__(self, device, **kwargs):
        self.name = kwargs.get('name','GStreamer Audio Player')

        self.player = Player()
        self.player.add_view(self.update)

        self.metadata = None
        self.duration = None

        self.view = []
        self.tags = {}
        self.server = device

        louie.send('Coherence.UPnP.Backend.init_completed', None, backend=self)

    def __repr__(self):
        return str(self.__class__).split('.')[-1]

    def update( self):
        _, current,_ = self.player.get_state()
        print "update", current
        """
        if current == gst.STATE_NULL:
            return
        if current not in (gst.STATE_PLAYING, gst.STATE_PAUSED,
                           gst.STATE_READY):
            print "I'm out"
            return
        """
        if current == gst.STATE_PLAYING:
            state = 'playing'
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'PLAYING')
        elif current == gst.STATE_PAUSED:
            state = 'paused'
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'PAUSED_PLAYBACK')
        else:
            state = 'idle'
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'STOPPED')

        print "update", state
        position = self.player.query_position()
        #print position

        for view in self.view:
            view.status( self.status( position))

        if position.has_key(u'raw'):

            if(self.duration == None and
               position[u'raw'].has_key(u'duration')):
                self.duration = int(position[u'raw'][u'duration'])
                if self.metadata != None and len(self.metadata)>0:
                    # FIXME: duration breaks client parsing MetaData?
                    elt = DIDLLite.DIDLElement.fromString(self.metadata)
                    for item in elt:
                        for res in item.findall('res'):
                            m,s = divmod( self.duration/1000000000, 60)
                            h,m = divmod(m,60)
                            res.attrib['duration'] = "%d:%02d:%02d" % (h,m,s)

                    self.metadata = elt.toString()
                    #print self.metadata
                    if self.server != None:
                        connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
                        self.server.av_transport_server.set_variable(connection_id,
                                                    'AVTransportURIMetaData',self.metadata)
                        self.server.av_transport_server.set_variable(connection_id,
                                                    'CurrentTrackMetaData',self.metadata)


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

    def load( self, uri,metadata, mimetype=None):
        print "loading:", uri, mimetype
        _,state,_ = self.player.get_state()
        connection_id = self.server.connection_manager_server.lookup_avt_id(self.current_connection_id)
        if( state == gst.STATE_PLAYING or state == gst.STATE_PAUSED):
            self.stop()
        else:
            self.server.av_transport_server.set_variable(connection_id, 'TransportState', 'STOPPED')

        if mimetype is None:
            _,ext =  os.path.splitext(uri)
            if ext == '.ogg':
                mimetype = 'application/ogg'
            else:
                mimetype = 'audio/mpeg'
        self.player.load( uri, mimetype)

        self.metadata = metadata
        self.mimetype = mimetype
        self.tags = {}

        self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackURI',uri)
        self.server.av_transport_server.set_variable(connection_id, 'AVTransportURI',uri)
        self.server.av_transport_server.set_variable(connection_id, 'AVTransportURIMetaData',metadata)
        self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackURI',uri)
        self.server.av_transport_server.set_variable(connection_id, 'CurrentTrackMetaData',metadata)

        #self.server.av_transport_server.set_variable(connection_id, 'TransportState', 'TRANSITIONING')
        #self.server.av_transport_server.set_variable(connection_id, 'CurrentTransportActions','Play,Stop,Pause,Seek,Next,Previous')
        self.server.av_transport_server.set_variable(connection_id, 'CurrentTransportActions','Play,Stop,Pause')
        self.server.av_transport_server.set_variable(connection_id, 'NumberOfTracks',1)
        self.server.av_transport_server.set_variable(connection_id, 'CurrentTracks',1)
        self.update()
        if state == gst.STATE_PLAYING:
            print "was playing..."
            self.play()

    def status( self, position):
        uri = self.player.get_uri()
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
        print 'Stopping:', self.player.get_uri()
        if self.player.get_uri() == None:
            return
        if self.player.get_state()[1] in [gst.STATE_PLAYING,gst.STATE_PAUSED]:
            self.player.stop()
            self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'STOPPED')

    def play( self):
        print "Playing:", self.player.get_uri()
        if self.player.get_uri() == None:
            return
        self.player.play()
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'PLAYING')


    def pause( self):
        print 'Pausing:', self.player.get_uri()
        self.player.pause()
        self.server.av_transport_server.set_variable(self.server.connection_manager_server.lookup_avt_id(self.current_connection_id), 'TransportState', 'PAUSED_PLAYBACK')

    def seek(self, location):
        self.player.seek(location)

    def mute(self):
        self.player.mute()
        rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
        self.server.rendering_control_server.set_variable(rcs_id, 'Mute', 'True')

    def unmute(self):
        self.player.unmute()
        rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
        self.server.rendering_control_server.set_variable(rcs_id, 'Mute', 'False')

    def get_mute(self):
        return self.player.get_mute()

    def get_volume(self):
        return self.player.get_volume()

    def set_volume(self, volume):
        self.player.set_volume(volume)
        rcs_id = self.server.connection_manager_server.lookup_rcs_id(self.current_connection_id)
        self.server.rendering_control_server.set_variable(rcs_id, 'Volume', volume)



    def upnp_init(self):
        self.current_connection_id = None
        self.server.connection_manager_server.set_variable(0, 'SinkProtocolInfo',
                            ['internal:%s:audio/mpeg:*' % self.server.coherence.hostname,
                             'http-get:*:audio/mpeg:*',
                             'internal:%s:audio/mp4:*' % self.server.coherence.hostname,
                             'http-get:*:audio/mp4:*',
                             'internal:%s:application/ogg:*' % self.server.coherence.hostname,
                             'http-get:*:application/ogg:*',
                             'internal:%s:video/x-msvideo:*' % self.server.coherence.hostname,
                             'http-get:*:video/x-msvideo:*',
                             'internal:%s:video/quicktime:*' % self.server.coherence.hostname,
                             'http-get:*:video/quicktime:*'],
                            default=True)
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
        #print InstanceID, CurrentURI, CurrentURIMetaData
        if len(CurrentURIMetaData)==0:
            self.load(CurrentURI,CurrentURIMetaData)
            return {}
        else:
            local_protocol_infos=self.server.connection_manager_server.get_variable('SinkProtocolInfo').value.split(',')
            #print local_protocol_infos
            elt = DIDLLite.DIDLElement.fromString(CurrentURIMetaData)
            if elt.numItems() == 1:
                item = elt.getItems()[0]
                for res in item.res:
                    #print res.protocolInfo, res.data
                    # FIXME:we can't rely on the sequence!
                    #       if we accept internal:,
                    #       we need to check _first_ if there
                    #       are any matching ones,
                    #       and if not try something else
                    for protocol_info in local_protocol_infos:
                        remote_protocol,remote_network,remote_content_format,_ = res.protocolInfo.split(':')
                        print remote_protocol,remote_network,remote_content_format
                        local_protocol,local_network,local_content_format,_ = protocol_info.split(':')
                        print local_protocol,local_network,local_content_format
                        if((remote_protocol == local_protocol or
                            remote_protocol == '*' or
                            local_protocol == '*') and
                           (remote_network == local_network or
                            remote_network == '*' or
                            local_network == '*') and
                           (remote_content_format == local_content_format or
                            remote_content_format == '*' or
                            local_content_format == '*')):
                            self.load(res.data,CurrentURIMetaData,mimetype=remote_content_format)
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


if __name__ == '__main__':

    import sys

    p = Player(None)
    if len(sys.argv) > 1:
        reactor.callWhenRunning( p.start, sys.argv[1])

    reactor.run()
