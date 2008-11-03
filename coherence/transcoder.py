# -*- coding: utf-8 -*-

# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2008, Frank Scholz <coherence@beebits.net>

import pygst
pygst.require('0.10')
import gst
import gobject
gobject.threads_init ()

class DataSink(gst.Element):

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
        #print "eventfunc", event
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

            print "finished", self.data_size
        return True

gobject.type_register(DataSink)

from twisted.web import resource, server

from coherence import log


class PCMTranscoder(resource.Resource, log.Loggable):
    logCategory = 'transcoder'
    addSlash = True

    def __init__(self,source,destination=None):
        self.source = source
        self.destination = destination
        resource.Resource.__init__(self)

    def getChild(self, name, request):
        self.info('getChild %s, %s' % (name, request))
        return self

    def render_GET(self,request):
        self.info('render GET %r' % (request))
        request.setResponseCode(200)
        request.setHeader('Content-Type', 'audio/L16;rate=44100;channels=2')
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
        request.setHeader('Content-Type', 'audio/L16;rate=44100;channels=2')
        request.write('')

    def start(self,request=None):
        print "start", request
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
            print "requestFinished", result
            """ we need to find a way to destroy the pipeline here
            """
            #from twisted.internet import reactor
            #reactor.callLater(0, self.pipeline.set_state, gst.STATE_NULL)
            #reactor.callLater(0, self.pipeline.get_state)
            return

        d = request.notifyFinish()
        d.addBoth(requestFinished)

    def __on_new_decoded_pad(self, element, pad, last):
        caps = pad.get_caps()
        name = caps[0].get_name()
        if 'audio' in name:
            if not self.__audioconvert_pad.is_linked(): # Only link once
                pad.link(self.__audioconvert_pad)