# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

""" transcoder classes to be used in combination with
    a Coherence MediaServer

    using GStreamer pipelines for the actually work
    and feeding the output into a http response
"""

import pygst
pygst.require('0.10')
import gst
import gobject
gobject.threads_init ()

import urllib

from twisted.web import resource, server

from coherence import log

import struct

class FakeTransformer(gst.Element, log.Loggable):
    logCategory = 'faker_datasink'

    _sinkpadtemplate = gst.PadTemplate ("sinkpadtemplate",
                                        gst.PAD_SINK,
                                        gst.PAD_ALWAYS,
                                        gst.caps_new_any())

    _srcpadtemplate =  gst.PadTemplate ("srcpadtemplate",
                                        gst.PAD_SRC,
                                        gst.PAD_ALWAYS,
                                        gst.caps_new_any())

    def __init__(self,destination=None,request=None):
        gst.Element.__init__(self)
        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        self.srcpad = gst.Pad(self._srcpadtemplate, "src")
        self.add_pad(self.sinkpad)
        self.add_pad(self.srcpad)

        self.sinkpad.set_chain_function(self.chainfunc)

        self.buffer = ''
        self.buffer_size = 0
        self.proxy = False
        self.got_new_segment = False
        self.closed = False

    def get_fake_header(self):
        return struct.pack(">L4s", 32, 'ftyp') + \
            "mp42\x00\x00\x00\x00mp42mp41isomiso2"

    def chainfunc(self, pad, buffer):
        if self.proxy:
            # we are in proxy mode already
            self.srcpad.push(buffer)
            return gst.FLOW_OK

        self.buffer = self.buffer + buffer.data
        if not self.buffer_size:
            try:
                self.buffer_size, a_type = struct.unpack(">L4s", self.buffer[:8])
            except:
                return gst.FLOW_OK

        if len(self.buffer) < self.buffer_size:
            # we need to buffer more
            return gst.FLOW_OK

        buffer = self.buffer[self.buffer_size:]
        fake_header = self.get_fake_header()
        n_buf = gst.Buffer(fake_header + buffer)
        self.proxy = True
        self.srcpad.push(n_buf)

        return gst.FLOW_OK

gobject.type_register(FakeTransformer)

class DataSink(gst.Element, log.Loggable):

    logCategory = 'transcoder_datasink'

    _sinkpadtemplate = gst.PadTemplate ("sinkpadtemplate",
                                        gst.PAD_SINK,
                                        gst.PAD_ALWAYS,
                                        gst.caps_new_any())

    def __init__(self,destination=None,request=None):
        gst.Element.__init__(self)
        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        self.add_pad(self.sinkpad)

        self.sinkpad.set_chain_function(self.chainfunc)
        self.sinkpad.set_event_function(self.eventfunc)
        self.destination = destination
        self.request = request

        if self.destination != None:
            self.destination = open(self.destination, 'wb')
        self.buffer = ''
        self.data_size = 0
        self.got_new_segment = False
        self.closed = False

    def chainfunc(self, pad, buffer):
        if self.closed == True:
            return gst.FLOW_OK
        if self.destination != None:
            self.destination.write(buffer.data)
        elif self.request != None:
            self.buffer += buffer.data
            if len(self.buffer) > 200000:
                self.request.write(self.buffer)
                self.buffer = ''
        else:
            self.buffer += buffer.data

        self.data_size += buffer.size
        return gst.FLOW_OK

    def eventfunc(self, pad, event):
        if event.type == gst.EVENT_NEWSEGMENT:
            if self.got_new_segment == False:
                self.got_new_segment = True
            else:
                self.closed = True
        elif event.type == gst.EVENT_EOS:
            if self.destination != None:
                self.destination.close()
            elif self.request != None:
                if len(self.buffer) > 0:
                    self.request.write(self.buffer)
                self.request.finish()
        return True


gobject.type_register(DataSink)

class BaseTranscoder(resource.Resource, log.Loggable):
    logCategory = 'transcoder'
    addSlash = True

    def __init__(self,uri,destination=None):
        if uri[:7] not in ['file://','http://']:
            uri = 'file://' + urllib.quote(uri)   #FIXME
        self.source = uri
        self.destination = destination
        resource.Resource.__init__(self)

    def getChild(self, name, request):
        self.info('getChild %s, %s' % (name, request))
        return self

    def render_GET(self,request):
        self.info('render GET %r' % (request))
        request.setResponseCode(200)
        if hasattr(self,'contentType'):
            request.setHeader('Content-Type', self.contentType)
        request.write('')

        headers = request.getAllHeaders()
        if('connection' in headers and
           headers['connection'] == 'close'):
            return

        self.start(request)
        return server.NOT_DONE_YET

    def render_HEAD(self,request):
        self.info('render HEAD %r' % (request))
        request.setResponseCode(200)
        request.setHeader('Content-Type', self.contentType)
        request.write('')

    def cleanup(self):
        self.pipeline.set_state(gst.STATE_NULL)


class PCMTranscoder(BaseTranscoder):
    contentType = 'audio/L16;rate=44100;channels=2'

    def start(self,request=None):
        self.info("start %r" % request)
        src = gst.element_factory_make('filesrc')
        src.set_property('location', self.source)
        sink = DataSink(destination=self.destination,request=request)

        decodebin = gst.element_factory_make('decodebin')
        decodebin.connect('new-decoded-pad', self.__on_new_decoded_pad)
        audioconvert = gst.element_factory_make('audioconvert')

        self.__audioconvert_pad = audioconvert.get_pad('sink')

        caps = gst.Caps("audio/x-raw-int,rate=44100,endianness=4321,channels=2,width=16,depth=16,signed=true")
        filter = gst.element_factory_make("capsfilter", "filter")
        filter.set_property("caps", caps)

        self.pipeline = gst.Pipeline()
        self.pipeline.add(src, decodebin, audioconvert, filter, sink)

        src.link(decodebin)
        audioconvert.link(filter)
        filter.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        def requestFinished(result):
            self.info("requestFinished %r" % result)
            """ we need to find a way to destroy the pipeline here
            """
            #from twisted.internet import reactor
            #reactor.callLater(0, self.pipeline.set_state, gst.STATE_NULL)
            #reactor.callLater(0, self.pipeline.get_state)
            gobject.idle_add(self.cleanup)
            return

        d = request.notifyFinish()
        d.addBoth(requestFinished)

    def __on_new_decoded_pad(self, element, pad, last):
        caps = pad.get_caps()
        name = caps[0].get_name()
        if 'audio' in name:
            if not self.__audioconvert_pad.is_linked(): # Only link once
                pad.link(self.__audioconvert_pad)


class WAVTranscoder(BaseTranscoder):

    contentType = 'audio/x-wav'

    def start(self,request=None):
        self.info("start %r", request)
        self.pipeline = gst.parse_launch(
            "%s ! decodebin ! audioconvert ! wavenc name=enc" % self.source)
        enc = self.pipeline.get_by_name('enc')
        sink = DataSink(destination=self.destination,request=request)
        self.pipeline.add(sink)
        enc.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        def requestFinished(result):
            self.info("requestFinished %r" % result)
            gobject.idle_add(self.cleanup)
            return

        d = request.notifyFinish()
        d.addBoth(requestFinished)


class MP4Transcoder(BaseTranscoder):
    """ Only works if H264 inside Quicktime/MP4 container is input
        Source has to be a valid uri
    """
    contentType = 'video/mp4'

    def start(self,request=None):
        self.info("start %r", request)
        self.pipeline = gst.parse_launch(
            "%s ! qtdemux name=d ! queue ! h264parse ! mp4mux name=mux d. ! queue ! mux." % self.source)
        mux = self.pipeline.get_by_name('mux')
        sink = DataSink(destination=self.destination,request=request)
        self.pipeline.add(sink)
        mux.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        def requestFinished(result):
            self.info("requestFinished %r" % result)
            """ we need to find a way to destroy the pipeline here
            """
            #from twisted.internet import reactor
            #reactor.callLater(0, self.pipeline.set_state, gst.STATE_NULL)
            #reactor.callLater(0, self.pipeline.get_state)
            gobject.idle_add(self.cleanup)
            return

        d = request.notifyFinish()
        d.addBoth(requestFinished)


class JPEGThumbTranscoder(BaseTranscoder):
    """ should create a valid thumbnail according to the DLNA spec
        neither width nor height must exceed 160px
    """
    contentType = 'image/jpeg'

    def start(self,request=None):
        self.info("start %r", request)
        """ what we actually want here is a pipeline that calls
            us when it knows about the size of the original image,
            and allows us now to adjust the caps-filter with the
            calculated values for width and height

            new_width = 160
            new_height = 160
            if original_width > 160:
                new_heigth = int(float(original_height) * (160.0/float(original_width)))
                if new_height > 160:
                    new_width = int(float(new_width) * (160.0/float(new_height)))
            elif original_height > 160:
                new_width = int(float(original_width) * (160.0/float(original_height)))
        """
        self.pipeline = gst.parse_launch(
            "%s ! jpegdec ! videoscale ! video/x-raw-yuv,width=160,height=160 ! jpegenc name=enc" % self.source)
        enc = self.pipeline.get_by_name('enc')
        sink = DataSink(destination=self.destination,request=request)
        self.pipeline.add(sink)
        enc.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        def requestFinished(result):
            self.info("requestFinished %r" % result)
            """ we need to find a way to destroy the pipeline here
            """
            gobject.idle_add(self.cleanup)
            return

        d = request.notifyFinish()
        d.addBoth(requestFinished)
