from miro import filetypes
from miro.test.framework import MiroTestCase

class FiletypesTestCase(MiroTestCase):
    def test_is_maybe_rss_url(self):
        # negative tests
        for test in ["http://example.com/",
                     "mailto:foo@example.com",
                     ]:
            self.assertEqual(filetypes.is_maybe_rss_url(test), False)

        # positive tests
        for test in ["http://feeds.feedburner.com/galacticast-flv",
                     "http://example.com/101-tips-from-dean/feed.rss",
                     "http://example.com/rss/DeanRocksVideoPodcast",
                     "http://example.com/rss2.php",
                     ]:
            self.assertEqual(filetypes.is_maybe_rss_url(test), True)

    def test_is_allowed_mimetype(self):
        # negative tests
        for test in ["text/plain",
                     "foo",
                     "",
                     None,
                     ]:
            self.assertEqual(filetypes.is_allowed_mimetype(test), False)

        # positive tests
        for test in ["video/flv",
                     "audio/mp4",
                     "application/x-bittorrent",
                     ]:
            self.assertEqual(filetypes.is_allowed_mimetype(test), True)

    def test_is_subtitle_filename(self):
        # negative tests
        for test in ["/foo/bar.mov",
                     "/foo/bar",
                     "",
                     None
                     ]:
            self.assertEqual(filetypes.is_subtitle_filename(test), False)

        # positive tests
        for test in ["/foo/bar.srt",
                     "/foo/bar.en.srt",
                     "/foo/bar.sub",
                     "/foo/bar.eng.smil",
                     "/foo/bar.cmml",
                     "/foo/bar.ssa",
                     "/foo/bar.ass",
                     ]:
            self.assertEquals(filetypes.is_subtitle_filename(test), True)
