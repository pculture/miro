import unittest
from miro import feedparser
from miro.plat import resources

from miro.test.framework import MiroTestCase

class FeedParserDictTest(MiroTestCase):
    def test(self):
        a = feedparser.FeedParserDict ()
        a["href"] = "hello"
        b = feedparser.FeedParserDict ()
        b["url"] = "hello"
        c = feedparser.FeedParserDict ()
        c["href"] = "hi"
        d = feedparser.FeedParserDict ()
        d["href"] = "hi"
        d["what"] = "hello"
        self.assertEqual(a.equal(a), True)
        self.assertEqual(b.equal(b), True)
        self.assertEqual(c.equal(c), True)
        self.assertEqual(d.equal(d), True)
        self.assertEqual(a.equal(b), True)
        self.assertEqual(b.equal(a), True)
        self.assertEqual(a.equal(c), False)
        self.assertEqual(c.equal(a), False)
        self.assertEqual(b.equal(c), False)
        self.assertEqual(c.equal(b), False)
        self.assertEqual(a.equal(d), False)
        self.assertEqual(d.equal(a), False)

class FeedParserTest (MiroTestCase):
    def test_ooze(self):
        feedparser.parse(resources.path("testdata/ooze.rss"))

if __name__ == "__main__":
    unittest.main()
