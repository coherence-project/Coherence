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
gobject.threads_init()

import os.path
import urllib

from twisted.web import resource, server
from twisted.internet import protocol

from coherence import log

import struct

def get_transcoder_name(transcoder):
    return transcoder.name

class InternalTranscoder(object):
    """ just a class to inherit from and
        which we can look for upon creating our
        list of available transcoders
    """

class FakeTransformer(gst.Element, log.Loggable):
    logCategory = 'faker_datasink'

    _sinkpadtemplate = gst.PadTemplate ("sinkpadtemplate",
                                        gst.PAD_SINK,
                                        gst.PAD_ALWAYS,
                                        gst.caps_new_any())

    _srcpadtemplate = gst.PadTemplate ("srcpadtemplate",
                                        gst.PAD_SRC,
                                        gst.PAD_ALWAYS,
                                        gst.caps_new_any())

    def __init__(self, destination=None, request=None):
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

    def __init__(self, destination=None, request=None):
        gst.Element.__init__(self)
        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        self.add_pad(self.sinkpad)

        self.sinkpad.set_chain_function(self.chainfunc)
        self.sinkpad.set_event_function(self.eventfunc)
        self.destination = destination
        self.request = request

        if self.destination is not None:
            self.destination = open(self.destination, 'wb')
        self.buffer = ''
        self.data_size = 0
        self.got_new_segment = False
        self.closed = False

    def chainfunc(self, pad, buffer):
        if self.closed:
            return gst.FLOW_OK
        if self.destination is not None:
            self.destination.write(buffer.data)
        elif self.request is not None:
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
            if not self.got_new_segment:
                self.got_new_segment = True
            else:
                self.closed = True
        elif event.type == gst.EVENT_EOS:
            if self.destination is not None:
                self.destination.close()
            elif self.request is not None:
                if len(self.buffer) > 0:
                    self.request.write(self.buffer)
                self.request.finish()
        return True


gobject.type_register(DataSink)

class GStreamerPipeline(resource.Resource, log.Loggable):
    logCategory = 'gstreamer'
    addSlash = True

    def __init__(self, pipeline, content_type):
        self.pipeline_description = pipeline
        self.contentType = content_type
        self.requests = []
        # if stream has a streamheader (something that has to be prepended
        # before any data), then it will be a tuple of GstBuffers
        self.streamheader = None
        self.parse_pipeline()
        resource.Resource.__init__(self)

    def parse_pipeline(self):
        self.pipeline = gst.parse_launch(self.pipeline_description)
        self.appsink = gst.element_factory_make("appsink", "sink")
        self.appsink.set_property('emit-signals', True)
        self.pipeline.add(self.appsink)
        enc = self.pipeline.get_by_name("enc")
        enc.link(self.appsink)
        self.appsink.connect("new-preroll", self.new_preroll)
        self.appsink.connect("new-buffer", self.new_buffer)
        self.appsink.connect("eos", self.eos)

    def start(self, request=None):
        self.info("GStreamerPipeline start %r %r", request,
                self.pipeline_description)
        self.requests.append(request)
        self.pipeline.set_state(gst.STATE_PLAYING)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished, request)

    def new_preroll(self, appsink):
        self.debug("new preroll")
        buffer = appsink.emit('pull-preroll')
        if not self.streamheader:
            # check caps for streamheader buffer
            caps = buffer.get_caps()
            s = caps[0]
            if s.has_key("streamheader"):
                self.streamheader = s["streamheader"]
                self.debug("setting streamheader")
                for r in self.requests:
                    self.debug("writing streamheader")
                    for h in self.streamheader:
                        r.write(h.data)
        for r in self.requests:
            self.debug("writing preroll")
            r.write(buffer.data)

    def new_buffer(self, appsink):
        buffer = appsink.emit('pull-buffer')
        if not self.streamheader:
            # check caps for streamheader buffers
            caps = buffer.get_caps()
            s = caps[0]
            if s.has_key("streamheader"):
                self.streamheader = s["streamheader"]
                self.debug("setting streamheader")
                for r in self.requests:
                    self.debug("writing streamheader")
                    for h in self.streamheader:
                        r.write(h.data)
        for r in self.requests:
            r.write(buffer.data)

    def eos(self, appsink):
        self.info("eos")
        for r in self.requests:
            r.finish()
        self.cleanup()

    def getChild(self, name, request):
        self.info('getChild %s, %s' % (name, request))
        return self

    def render_GET(self, request):
        self.info('render GET %r' % (request))
        request.setResponseCode(200)
        if hasattr(self, 'contentType'):
            request.setHeader('Content-Type', self.contentType)
        request.write('')

        headers = request.getAllHeaders()
        if('connection' in headers and
           headers['connection'] == 'close'):
            pass
        if self.requests:
            if self.streamheader:
                self.debug("writing streamheader")
                for h in self.streamheader:
                    request.write(h.data)
            self.requests.append(request)
        else:
            self.parse_pipeline()
            self.start(request)
        return server.NOT_DONE_YET

    def render_HEAD(self, request):
        self.info('render HEAD %r' % (request))
        request.setResponseCode(200)
        request.setHeader('Content-Type', self.contentType)
        request.write('')

    def requestFinished(self, result, request):
        self.info("requestFinished %r" % result)
        """ we need to find a way to destroy the pipeline here
        """
        #from twisted.internet import reactor
        #reactor.callLater(0, self.pipeline.set_state, gst.STATE_NULL)
        self.requests.remove(request)
        if not self.requests:
            self.cleanup()

    def on_message(self, bus, message):
        t = message.type
        print "on_message", t
        if t == gst.MESSAGE_ERROR:
            #err, debug = message.parse_error()
            #print "Error: %s" % err, debug
            self.cleanup()
        elif t == gst.MESSAGE_EOS:
            self.cleanup()

    def cleanup(self):
        self.info("pipeline cleanup")
        self.pipeline.set_state(gst.STATE_NULL)
        self.requests = []
        self.streamheader = None


class BaseTranscoder(resource.Resource, log.Loggable):
    logCategory = 'transcoder'
    addSlash = True

    def __init__(self, uri, destination=None):
        self.info('uri %s %r' % (uri, type(uri)))
        if uri[:7] not in ['file://', 'http://']:
            uri = 'file://' + urllib.quote(uri)   #FIXME
        self.uri = uri
        self.destination = destination
        resource.Resource.__init__(self)

    def getChild(self, name, request):
        self.info('getChild %s, %s' % (name, request))
        return self

    def render_GET(self, request):
        self.info('render GET %r' % (request))
        request.setResponseCode(200)
        if hasattr(self, 'contentType'):
            request.setHeader('Content-Type', self.contentType)
        request.write('')

        headers = request.getAllHeaders()
        if('connection' in headers and
           headers['connection'] == 'close'):
            pass

        self.start(request)
        return server.NOT_DONE_YET

    def render_HEAD(self, request):
        self.info('render HEAD %r' % (request))
        request.setResponseCode(200)
        request.setHeader('Content-Type', self.contentType)
        request.write('')

    def requestFinished(self, result):
        self.info("requestFinished %r" % result)
        """ we need to find a way to destroy the pipeline here
        """
        #from twisted.internet import reactor
        #reactor.callLater(0, self.pipeline.set_state, gst.STATE_NULL)
        gobject.idle_add(self.cleanup)

    def on_message(self, bus, message):
        t = message.type
        print "on_message", t
        if t == gst.MESSAGE_ERROR:
            #err, debug = message.parse_error()
            #print "Error: %s" % err, debug
            self.cleanup()
        elif t == gst.MESSAGE_EOS:
            self.cleanup()

    def cleanup(self):
        self.pipeline.set_state(gst.STATE_NULL)


class PCMTranscoder(BaseTranscoder, InternalTranscoder):
    contentType = 'audio/L16;rate=44100;channels=2'
    name = 'lpcm'

    def start(self, request=None):
        self.info("PCMTranscoder start %r %r", request, self.uri)
        self.pipeline = gst.parse_launch(
            "%s ! decodebin ! audioconvert name=conv" % self.uri)

        conv = self.pipeline.get_by_name('conv')
        caps = gst.Caps("audio/x-raw-int,rate=44100,endianness=4321,channels=2,width=16,depth=16,signed=true")
        #FIXME: UGLY. 'filter' is a python builtin!
        filter = gst.element_factory_make("capsfilter", "filter")
        filter.set_property("caps", caps)
        self.pipeline.add(filter)
        conv.link(filter)

        sink = DataSink(destination=self.destination, request=request)
        self.pipeline.add(sink)
        filter.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished)


class WAVTranscoder(BaseTranscoder, InternalTranscoder):

    contentType = 'audio/x-wav'
    name = 'wav'

    def start(self, request=None):
        self.info("start %r", request)
        self.pipeline = gst.parse_launch(
            "%s ! decodebin ! audioconvert ! wavenc name=enc" % self.uri)
        enc = self.pipeline.get_by_name('enc')
        sink = DataSink(destination=self.destination, request=request)
        self.pipeline.add(sink)
        enc.link(sink)
        #bus = self.pipeline.get_bus()
        #bus.connect('message', self.on_message)
        self.pipeline.set_state(gst.STATE_PLAYING)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished)


class MP3Transcoder(BaseTranscoder, InternalTranscoder):

    contentType = 'audio/mpeg'
    name = 'mp3'

    def start(self, request=None):
        self.info("start %r", request)
        self.pipeline = gst.parse_launch(
            "%s ! decodebin ! audioconvert ! lame name=enc" % self.uri)
        enc = self.pipeline.get_by_name('enc')
        sink = DataSink(destination=self.destination, request=request)
        self.pipeline.add(sink)
        enc.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished)


class MP4Transcoder(BaseTranscoder, InternalTranscoder):
    """ Only works if H264 inside Quicktime/MP4 container is input
        Source has to be a valid uri
    """
    contentType = 'video/mp4'
    name = 'mp4'

    def start(self, request=None):
        self.info("start %r", request)
        self.pipeline = gst.parse_launch(
            "%s ! qtdemux name=d ! queue ! h264parse ! mp4mux name=mux d. ! queue ! mux." % self.uri)
        mux = self.pipeline.get_by_name('mux')
        sink = DataSink(destination=self.destination, request=request)
        self.pipeline.add(sink)
        mux.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished)


class MP2TSTranscoder(BaseTranscoder, InternalTranscoder):

    contentType = 'video/mpeg'
    name = 'mpegts'

    def start(self, request=None):
        self.info("start %r", request)
        ### FIXME mpeg2enc
        self.pipeline = gst.parse_launch(
            "mpegtsmux name=mux %s ! decodebin2 name=d ! queue ! ffmpegcolorspace ! mpeg2enc ! queue ! mux. d. ! queue ! audioconvert ! twolame ! queue ! mux."  % self.uri)
        enc = self.pipeline.get_by_name('mux')
        sink = DataSink(destination=self.destination, request=request)
        self.pipeline.add(sink)
        enc.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished)


class ThumbTranscoder(BaseTranscoder, InternalTranscoder):
    """ should create a valid thumbnail according to the DLNA spec
        neither width nor height must exceed 160px
    """
    contentType = 'image/jpeg'
    name = 'thumb'

    def start(self, request=None):
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
        try:
            type = request.args['type'][0]
        except:
            type = 'jpeg'
        if type == 'png':
            self.pipeline = gst.parse_launch(
                "%s ! decodebin2 ! videoscale ! video/x-raw-yuv,width=160,height=160 ! pngenc name=enc" % self.uri)
            self.contentType = 'image/png'
        else:
            self.pipeline = gst.parse_launch(
                "%s ! decodebin2 ! videoscale ! video/x-raw-yuv,width=160,height=160 ! jpegenc name=enc" % self.uri)
            self.contentType = 'image/jpeg'
        enc = self.pipeline.get_by_name('enc')
        sink = DataSink(destination=self.destination, request=request)
        self.pipeline.add(sink)
        enc.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished)


class GStreamerTranscoder(BaseTranscoder):
    """ a generic Transcode based on GStreamer

        the pipeline which will be parsed upon
        calling the start method, as to be set as
        the attribute pipeline_description to the
        instantiated class

        same for the attribute contentType
    """

    def start(self, request=None):
        self.info("start %r", request)
        self.pipeline = gst.parse_launch(self.pipeline_description % self.uri)
        enc = self.pipeline.get_by_name('mux')
        sink = DataSink(destination=self.destination, request=request)
        self.pipeline.add(sink)
        enc.link(sink)
        self.pipeline.set_state(gst.STATE_PLAYING)

        d = request.notifyFinish()
        d.addBoth(self.requestFinished)


class ExternalProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, caller):
        self.caller = caller

    def connectionMade(self):
        print "pp connection made"

    def outReceived(self, data):
        #print "outReceived with %d bytes!" % len(data)
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


class ExternalProcessProducer(object):
    logCategory = 'externalprocess'

    def __init__(self, pipeline, request):
        self.pipeline = pipeline
        self.request = request
        self.process = None
        self.written = 0
        self.data = ''
        self.ended = False
        request.registerProducer(self, 0)

    def write_data(self, data):
        if data:
            #print "write %d bytes of data" % len(data)
            self.written += len(data)
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        if self.request and self.ended:
            print "closing"
            self.request.unregisterProducer()
            self.request.finish()
            self.request = None

    def resumeProducing(self):
        #print "resumeProducing", self.request
        if not self.request:
            return
        if self.process is None:
            argv = self.pipeline.split()
            executable = argv[0]
            argv[0] = os.path.basename(argv[0])
            from twisted.internet import reactor
            self.process = reactor.spawnProcess(ExternalProcessProtocol(self),
                    executable, argv, {})

    def pauseProducing(self):
        pass

    def stopProducing(self):
        print "stopProducing", self.request
        self.request.unregisterProducer()
        self.process.loseConnection()
        self.request.finish()
        self.request = None


class ExternalProcessPipeline(resource.Resource, log.Loggable):
    logCategory = 'externalprocess'
    addSlash = False

    def __init__(self, uri):
        self.uri = uri

    def getChildWithDefault(self, path, request):
        return self

    def render(self, request):
        print "ExternalProcessPipeline render"
        try:
            if self.contentType:
                request.setHeader('Content-Type', self.contentType)
        except AttributeError:
            pass

        ExternalProcessProducer(self.pipeline_description % self.uri, request)
        return server.NOT_DONE_YET

def transcoder_class_wrapper(klass, content_type, pipeline):
    def create_object(uri):
        transcoder = klass(uri)
        transcoder.contentType = content_type
        transcoder.pipeline_description = pipeline
        return transcoder
    return create_object



class TranscoderManager(log.Loggable):

    """ singleton class which holds information
        about all available transcoders

        they are put into a transcoders dict with
        their id as the key

        we collect all internal transcoders by searching
        for all subclasses of InternalTranscoder, the class
        will be the value

        transcoders defined in the config are parsed and
        stored as a dict in the transcoders dict

        in the config a transcoder description has to look like this:

        *** preliminary, will be extended and might even change without further notice ***

        <transcoder>
          <pipeline>%s ...</pipeline> <!-- we need a %s here to insert the source uri
                                           (or can we have all the times pipelines we can prepend
                                            with a '%s !')
                                           and an element named mux where we can attach
                                           our sink -->
          <type>gstreamer</type>      <!-- could be gstreamer or process -->
          <name>mpegts</name>
          <target>video/mpeg</target>
          <fourth_field>              <!-- value for the 4th field of the protocolInfo phalanx,
                                           default is '*' -->
        </transcoder>

    """

    logCategory = 'transcoder_manager'
    _instance_ = None  # Singleton

    def __new__(cls, *args, **kwargs):
        """ creates the singleton """
        if cls._instance_ is None:
            obj = super(TranscoderManager, cls).__new__(cls, *args, **kwargs)
            cls._instance_ = obj
        return cls._instance_

    def __init__(self, coherence=None):
        """ initializes the class

            it should be called at least once
            with the main coherence class passed as an argument,
            so we have access to the config
        """
        self.transcoders = {}
        for transcoder in InternalTranscoder.__subclasses__():
            self.transcoders[get_transcoder_name(transcoder)] = transcoder

        if coherence is not None:
            self.coherence = coherence
            try:
                transcoders_from_config = self.coherence.config['transcoder']
                if isinstance(transcoders_from_config, dict):
                    transcoders_from_config = [transcoders_from_config]
            except KeyError:
                transcoders_from_config = []

            for transcoder in transcoders_from_config:
                # FIXME: is anyone checking if all keys are given ?
                pipeline = transcoder['pipeline']
                if not '%s' in pipeline:
                    self.warning("Can't create transcoder %r:"
                            " missing placehoder '%%s' in 'pipeline'",
                            transcoder)
                    continue

                try:
                    transcoder_name = transcoder['name'].decode('ascii')
                except UnicodeEncodeError:
                    self.warning("Can't create transcoder %r:"
                            " the 'name' contains non-ascii letters",
                            transcoder)
                    continue


                transcoder_type = transcoder['type'].lower()

                if transcoder_type == 'gstreamer':
                    wrapped = transcoder_class_wrapper(GStreamerTranscoder,
                            transcoder['target'], transcoder['pipeline'])
                elif transcoder_type == 'process':
                    wrapped = transcoder_class_wrapper(ExternalProcessPipeline,
                            transcoder['target'], transcoder['pipeline'])
                else:
                    self.warning("unknown transcoder type %r", transcoder_type)
                    continue

                self.transcoders[transcoder_name] = wrapped

        #FIXME reduce that to info later
        self.warning("available transcoders %r" % self.transcoders)


    def select(self, name, uri, backend=None):
        # FIXME:why do we specify the name when trying to get it?

        if backend is not None:
            """ try to find a transcoder provided by the backend
                and return that here,
                if there isn't one continue with the ones
                provided by the config or the internal ones
            """
            pass

        transcoder = self.transcoders[name](uri)
        return transcoder

if __name__ == '__main__':
    t = Transcoder(None)
