import os

from miro.test.framework import MiroTestCase, EventLoopTest

from miro import app
from miro import prefs
from miro import videoconversion

class ConverterManagerTest(MiroTestCase):
    def build_config_file(self, filename, data):
        fn = os.path.join(self.tempdir, filename)
        fp = open(fn, "w")
        fp.write(data)
        fp.close()

    def test_empty(self):
        cm = videoconversion.ConverterManager()
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

        cm = videoconversion.ConverterManager()
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
            "only_on: %(platform)s\n" % {"platform": app.config.get(prefs.APP_PLATFORM)}
            )
        cm = videoconversion.ConverterManager()
        cm.load_converters(os.path.join(self.tempdir, "*.conv"))
        
        self.assertEqual(len(cm.get_converters()), 1)
        converter = cm.lookup_converter("target1")
        self.assertEqual(converter.platforms, app.config.get(prefs.APP_PLATFORM))
