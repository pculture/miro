import logging
import os
import unittest
from miro import feedparser
from miro.plat import resources

from miro.test.framework import MiroTestCase

FEEDPARSERTESTS = resources.path("testdata/feedparsertests")

class FeedParserDictTest(MiroTestCase):
    def test_equality(self):
        # feedparserdicts are equal if for all keys k, either
        # the two feedparserdicts have the same value, or 
        # one of the feedparserdicts doesn't have the key.
        a = feedparser.FeedParserDict()
        a["href"] = "hello"
        b = feedparser.FeedParserDict()
        b["url"] = "hello"
        c = feedparser.FeedParserDict()
        c["href"] = "hi"
        d = feedparser.FeedParserDict()
        d["href"] = "hi"
        d["what"] = "hello"
        self.assertEqual(a.equal(a), True)
        self.assertEqual(b.equal(b), True)
        self.assertEqual(c.equal(c), True)
        self.assertEqual(d.equal(d), True)
        self.assertEqual(a.equal(b), True)
        self.assertEqual(b.equal(a), True)

    def test_inequality(self):
        # feedparserdicts are inequal if for some key k, the
        # two feedparserdicts have different values.
        a = feedparser.FeedParserDict()
        a["href"] = "hello"
        b = feedparser.FeedParserDict()
        b["url"] = "hello"
        c = feedparser.FeedParserDict()
        c["href"] = "hi"
        d = feedparser.FeedParserDict()
        d["href"] = "hi"
        d["what"] = "hello"
        self.assertEqual(a.equal(c), False)
        self.assertEqual(c.equal(a), False)
        self.assertEqual(b.equal(c), False)
        self.assertEqual(c.equal(b), False)
        self.assertEqual(a.equal(d), False)
        self.assertEqual(d.equal(a), False)

class FeedParserTest(MiroTestCase):
    def test_ooze(self):
        feedparser.parse(os.path.join(FEEDPARSERTESTS, "ooze.rss"))

    def test_usvideo(self):
        # test for bug 10653
        d = feedparser.parse(os.path.join(FEEDPARSERTESTS, "usvideo.xml"))

        # this should kick up a KeyError and NOT a TypeError
        self.assertRaises(KeyError, lambda: d['url'])

# FIXME - could use way more feedparser tests

if __name__ == "__main__":
    unittest.main()
