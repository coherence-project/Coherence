
from twisted.trial.unittest import TestCase

from coherence.transcoder import TranscoderManager

from coherence.transcoder import (PCMTranscoder, WAVTranscoder, MP3Transcoder,
        MP4Transcoder, MP2TSTranscoder, ThumbTranscoder)

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

    def setUp(self):
        self.manager = None

    def test_is_loading_all_known_transcoders(self):
        self.manager = TranscoderManager()
        for klass in known_transcoders:
            self.assertEquals(self.manager.transcoders[getuniquename(klass)], klass)
