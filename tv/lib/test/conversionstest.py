import os

from miro.test.framework import MiroTestCase

from miro import app
from miro import prefs
from miro import conversions
from miro.plat import resources

DATA = resources.path("testdata/conversions")

class ConverterManagerTest(MiroTestCase):
    def build_config_file(self, filename, data):
        fn = os.path.join(self.tempdir, filename)
        fp = open(fn, "w")
        fp.write(data)
        fp.close()

    def test_empty(self):
        cm = conversions.ConverterManager()
        cm.load_converters(os.path.join(self.tempdir, "*.conv"))
        self.assertEquals(len(cm.get_converters()), 0)
        self.assertRaises(KeyError, cm.lookup_converter, "abc")

    def test_parsing(self):
        self.build_config_file(
            "foo.conv",
            "[DEFAULT]\n"
            "name: Foo\n"
            "executable: ffmpeg\n"
            "\n"
            "[Target1]\n"
            "extension: mp4\n"
            "parameters: -i {input}\n"
            )

        cm = conversions.ConverterManager()
        cm.load_converters(os.path.join(self.tempdir, "*.conv"))

        self.assertEqual(len(cm.get_converters()), 1)
        converter = cm.lookup_converter("target1")
        # this comes from the section name
        self.assertEqual(converter.name, "Target1")
        # this comes from the default
        self.assertEqual(converter.executable, "ffmpeg")
        # this comes from the section
        self.assertEqual(converter.extension, "mp4")
        # this is a special case
        self.assertEqual(converter.platforms, None)

    def test_only_on(self):
        self.build_config_file(
            "foo2.conv",
            "[DEFAULT]\n"
            "name: Foo\n"
            "executable: ffmpeg\n"
            "\n"
            "[Target1]\n"
            "extension: mp4\n"
            "parameters: -i {input}\n"
            "only_on: %(platform)s\n" % {
                "platform": app.config.get(prefs.APP_PLATFORM)}
            )
        cm = conversions.ConverterManager()
        cm.load_converters(os.path.join(self.tempdir, "*.conv"))
        
        self.assertEqual(len(cm.get_converters()), 1)
        converter = cm.lookup_converter("target1")
        self.assertEqual(
            converter.platforms, app.config.get(prefs.APP_PLATFORM))

class MockFFMpegConversionTask(conversions.FFMpegConversionTask):
    def __init__(self):
        # not calling superclass init because it does a bunch of
        # stuff we don't want to deal with mocking.

        # instead, initialize the bits we're testing
        self.error = None
        self.progress = 0
        self.duration = None
        
    def _log_progress(self, line):
        pass

    def _notify_progress(self):
        pass

class FFMpegConversionTaskTest(MiroTestCase):
    def test_ffmpeg_mp4_to_mp3(self):
        f = open(os.path.join(DATA, "ffmpeg.mp4.mp3.txt"), "r")
        try:
            lines = conversions.line_reader(f)
            mock = MockFFMpegConversionTask()
            mock.process_output(lines)

            # no errors and progress equals 1.0
            self.assertEquals(mock.error, None)
            self.assertEquals(mock.progress, 1.0)
            self.assertEquals(mock.duration, 368)
        finally:
            f.close()

    def test_unknown_encoder(self):
        f = open(os.path.join(DATA, "ffmpeg.unknown_encoder.txt"), "r")
        try:
            lines = conversions.line_reader(f)
            mock = MockFFMpegConversionTask()
            mock.process_output(lines)

            # this kicks up an 'Unknown encoder' error.  make sure
            # it's captured and progress is 0.
            self.assertEquals(mock.error, "Unknown encoder 'libx264'")
            self.assertEquals(mock.progress, 0)
        finally:
            f.close()

    def test_error_while_decoding_stream(self):
        f = open(os.path.join(DATA, "ffmpeg.error_while_decoding_stream.txt"), "r")
        try:
            lines = conversions.line_reader(f)
            mock = MockFFMpegConversionTask()
            mock.process_output(lines)

            # no errors and progress equals 1.0
            self.assertEquals(mock.error, None)
            self.assertEquals(mock.progress, 1.0)
            self.assertEquals(mock.duration, 33)
        finally:
            f.close()


class MockFFMpeg2TheoraConversionTask(conversions.FFMpeg2TheoraConversionTask):
    def __init__(self):
        # not calling superclass init because it does a bunch of
        # stuff we don't want to deal with mocking.

        # instead, initialize the bits we're testing
        self.error = None
        self.progress = 0
        self.duration = None
        
    def _log_progress(self, line):
        pass

    def _notify_progress(self):
        pass

class FFMpeg2TheoraConversionTaskTest(MiroTestCase):
    def test_ffmpeg2theora_mp4_to_oggtheora(self):
        f = open(os.path.join(DATA, "ffmpeg2theora.mp4.oggtheora.txt"), "r")
        try:
            lines = conversions.line_reader(f)
            mock = MockFFMpeg2TheoraConversionTask()
            mock.process_output(lines)

            # no errors and progress equals 1.0
            self.assertEquals(mock.error, None)
            self.assertEquals(mock.progress, 1.0)
            self.assertEquals(mock.duration, 368)
        finally:
            f.close()
        
