import unittest
import feedparser

from test.framework import DemocracyTestCase

class FeedURLValidationTest(DemocracyTestCase):
    def test(self):
        a = feedparser.FeedParserDict ()
        a["href"] = "hello"
        b = feedparser.FeedParserDict ()
        b["url"] = "hello"
        c = feedparser.FeedParserDict ()
        c["href"] = "hi"
        self.assertEqual(a.equal(a), True)
        self.assertEqual(b.equal(b), True)
        self.assertEqual(c.equal(c), True)
        self.assertEqual(a.equal(b), True)
        self.assertEqual(a.equal(c), False)
        self.assertEqual(b.equal(c), False)
            
if __name__ == "__main__":
    unittest.main()
