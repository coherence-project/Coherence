# -*- coding: utf-8 -*-

from twisted.trial.unittest import TestCase

from coherence.transcoder import TranscoderManager, get_transcoder_name

from coherence.transcoder import (PCMTranscoder, WAVTranscoder, MP3Transcoder,
        MP4Transcoder, MP2TSTranscoder, ThumbTranscoder, GStreamerTranscoder,
        ExternalProcessPipeline)

known_transcoders = [PCMTranscoder, WAVTranscoder, MP3Transcoder, MP4Transcoder,
        MP2TSTranscoder, ThumbTranscoder]

class TranscoderTestMixin(object):
    def setUp(self):
        self.manager = TranscoderManager()

    def tearDown(self):
        # as it is a singleton ensuring that we always get a clean
        # and fresh one is tricky and hacks the internals
        TranscoderManager._instance = None
        del self.manager

class TestTranscoderManagerSingletony(TranscoderTestMixin, TestCase):

    def test_is_really_singleton(self):
        #FIXME: singleton tests should be outsourced some when
        old_id = id(self.manager)
        new_manager = TranscoderManager()
        self.assertEquals(old_id, id(new_manager))

class TestTranscoderAutoloading(TranscoderTestMixin, TestCase):

    class CoherenceStump(object):
        def __init__(self, **kwargs):
            self.config = kwargs

    failing_config = {'name': 'failing', 'pipeline': 'wrong',
                     'type': 'process', 'target': 'yay'}

    gst_config = {'name': 'supertest', 'pipeline': 'pp%spppl',
                     'type': 'gstreamer', 'target': 'yay'}


    process_config = {'name': 'megaprocess', 'pipeline': 'uiui%suiui',
                     'type': 'process', 'target': 'yay'}

    bad_name_config = {'name': u'so bäd', 'pipeline': 'fake %s',
                        'type': 'process', 'target': 'norway'}

    def setUp(self):
        self.manager = None

    def test_is_loading_all_known_transcoders(self):
        self.manager = TranscoderManager()
        self._check_for_transcoders(known_transcoders)

    def _check_for_transcoders(self, transcoders):
        for klass in transcoders:
            loaded_transcoder = self.manager.transcoders[get_transcoder_name(klass)]
            self.assertEquals(loaded_transcoder, klass)

    def test_is_loading_no_config(self):
        coherence = self.CoherenceStump()
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)

    def test_is_loading_one_gst_from_config(self):
        coherence = self.CoherenceStump(transcoder=self.gst_config)
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)
        my_pipe = self.manager.select('supertest', 'http://my_uri')
        self.assertTrue(isinstance(my_pipe, GStreamerTranscoder))
        self._check_transcoder_attrs(my_pipe,
                pipeline='pp%spppl', uri="http://my_uri")


    def _check_transcoder_attrs(self, transcoder, pipeline=None, uri=None):
        # bahh... relying on implementation details of the basetranscoder here
        self.assertEquals(transcoder.pipeline_description, pipeline)
        self.assertEquals(transcoder.uri, uri)

    def test_is_loading_one_process_from_config(self):
        coherence = self.CoherenceStump(transcoder=self.process_config)
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)
        transcoder = self.manager.select('megaprocess', 'http://another/uri')
        self.assertTrue(isinstance(transcoder, ExternalProcessPipeline))

        self._check_transcoder_attrs(transcoder, 'uiui%suiui',
                'http://another/uri')

    def test_placeholdercheck_in_config(self):
        # this pipeline does not contain the '%s' placeholder and because
        # of that should not be created

        coherence = self.CoherenceStump(transcoder=self.failing_config)
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)
        self.assertRaises(KeyError, self.manager.select, 'failing',
                'http://another/uri')

    def test_badname_in_config(self):
        # this pipeline does not contain the '%s' placeholder and because
        # of that should not be created

        coherence = self.CoherenceStump(transcoder=self.bad_name_config)
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)
        self.assertRaises(KeyError, self.manager.select, u'so bäd',
                'http://another/uri')



    def test_is_loading_multiple_from_config(self):
        coherence = self.CoherenceStump(transcoder=[self.gst_config,
                self.process_config])
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)

        # check the megaprocess
        transcoder = self.manager.select('megaprocess', 'http://another/uri')
        self.assertTrue(isinstance(transcoder, ExternalProcessPipeline))

        self._check_transcoder_attrs(transcoder, 'uiui%suiui',
                'http://another/uri')

        # check the gstreamer transcoder
        transcoder = self.manager.select('supertest', 'http://another/uri2')
        self.assertTrue(isinstance(transcoder, GStreamerTranscoder))

        self._check_transcoder_attrs(transcoder, 'pp%spppl',
                'http://another/uri2')

    def test_loaded_gst_always_new_instance(self):
        coherence = self.CoherenceStump(transcoder=self.gst_config)
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)
        transcoder_a = self.manager.select('supertest', 'http://my_uri')
        self.assertTrue(isinstance(transcoder_a, GStreamerTranscoder))
        self._check_transcoder_attrs(transcoder_a,
                pipeline='pp%spppl', uri="http://my_uri")

        transcoder_b = self.manager.select('supertest', 'http://another/uri')
        self.assertTrue(isinstance(transcoder_b, GStreamerTranscoder))
        self._check_transcoder_attrs(transcoder_b,
                pipeline='pp%spppl', uri="http://another/uri")


        self.assertNotEquals(transcoder_a, transcoder_b)
        self.assertNotEquals(id(transcoder_a), id(transcoder_b))



