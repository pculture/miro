from miro import filetypes
from miro.test.framework import MiroTestCase

class FiletypesTestCase(MiroTestCase):
    def test_is_maybe_rss_url(self):
        # these should all be false
        self.assertEqual(filetypes.is_maybe_rss_url("http://example.com/"), False)
        self.assertEqual(filetypes.is_maybe_rss_url("mailto:foo@example.com"), False)

        # these should all be true
        self.assertEqual(filetypes.is_maybe_rss_url("http://feeds.feedburner.com/galacticast-flv"), True)
        self.assertEqual(filetypes.is_maybe_rss_url("http://example.com/101-tips-from-dean/feed.rss"), True)
        self.assertEqual(filetypes.is_maybe_rss_url("http://example.com/rss/DeanRocksVideoPodcast"), True)
        self.assertEqual(filetypes.is_maybe_rss_url("http://example.com/rss2.php"), True)
