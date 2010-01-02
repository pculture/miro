from miro import filetypes
from miro.test.framework import MiroTestCase

class FiletypesTestCase(MiroTestCase):
    def test_negative(self):
        for i, o in [("http://example.com/", False),
                     ("mailto:foo@example.com", False)]:
            self.assertEqual(filetypes.is_maybe_rss_url(i), o)

    def test_positive(self):
        for i, o in [("http://feeds.feedburner.com/galacticast-flv", True),
                     ("http://example.com/101-tips-from-dean/feed.rss", True),
                     ("http://example.com/rss/DeanRocksVideoPodcast", True),
                     ("http://example.com/rss2.php", True)
                     ]:
            self.assertEqual(filetypes.is_maybe_rss_url(i), o)
