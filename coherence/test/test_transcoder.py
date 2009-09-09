
from twisted.trial.unittest import TestCase

from coherence.transcoder import TranscoderManager

from coherence.transcoder import (PCMTranscoder, WAVTranscoder, MP3Transcoder,
        MP4Transcoder, MP2TSTranscoder, ThumbTranscoder, GStreamerTranscoder)

known_transcoders = [PCMTranscoder, WAVTranscoder, MP3Transcoder, MP4Transcoder,
        MP2TSTranscoder, ThumbTranscoder]

# move this into the implementation to allow easier overwriting
def getuniquename(transcoder_class):
    return getattr(transcoder_class, 'id')

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

    def setUp(self):
        self.manager = None

    def test_is_loading_all_known_transcoders(self):
        self.manager = TranscoderManager()
        self._check_for_transcoders(known_transcoders)

    def _check_for_transcoders(self, transcoders):
        for klass in transcoders:
            loaded_transcoder = self.manager.transcoders[getuniquename(klass)]
            self.assertEquals(loaded_transcoder, klass)

    def test_is_loading_no_config(self):
        coherence = self.CoherenceStump()
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)

    def test_is_loading_one_gst_from_config(self):
        my_config = {'id': 'supertest', 'pipeline': 'pppppl',
                     'type': 'gstreamer',
                     'mimetype': 'yay', 'target': 'xbox360'}
        coherence = self.CoherenceStump(transcoder=my_config)
        self.manager = TranscoderManager(coherence)
        self._check_for_transcoders(known_transcoders)
        my_pipe = self.manager.select('supertest', 'http://my_uri')
        self.assertTrue(isinstance(my_pipe, GStreamerTranscoder))

        # bahh... relying on implementation details of the basetranscoder/gsttranscoder here.

        self.assertEquals(my_pipe.pipeline_description, 'pppppl')
        self.assertEquals(my_pipe.source, 'http://my_uri')
