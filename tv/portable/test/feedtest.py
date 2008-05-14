import unittest
from tempfile import mkstemp
from time import sleep

from miro import config
from miro import prefs
from miro import dialogs
from miro import database
from miro.feed import validateFeedURL, normalizeFeedURL, Feed

from miro.test.framework import MiroTestCase, EventLoopTest

class FakeDownloader:
    pass

class AcceptScrapeTestDelegate:
    def __init__(self):
        self.calls = 0

    def runDialog(self, dialog):
        self.calls += 1
        if not isinstance(dialog, dialogs.ChoiceDialog):
            raise AssertionError("Only expected ChoiceDialogs")
        if not dialog.title.startswith("Channel is not compatible"):
            raise AssertionError("Only expected scrape dialogs")
        dialog.choice = dialogs.BUTTON_YES
        dialog.callback(dialog)

class FeedURLValidationTest(MiroTestCase):
    def test(self):
        self.assertEqual(validateFeedURL(u"http://foo.bar.com/"), True)
        self.assertEqual(validateFeedURL(u"https://foo.bar.com/"), True)
                         
        self.assertEqual(validateFeedURL(u"feed://foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"http://foo.bar.com"), False)
        self.assertEqual(validateFeedURL(u"http:foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"https:foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"feed:foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"http:/foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"https:/foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"feed:/foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"http:///foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"https:///foo.bar.com/"), False)
        self.assertEqual(validateFeedURL(u"feed:///foo.bar.com/"), False)

        self.assertEqual(validateFeedURL(u"foo.bar.com"), False)
        self.assertEqual(validateFeedURL(u"crap:foo.bar.com"), False)
        self.assertEqual(validateFeedURL(u"crap:/foo.bar.com"), False)
        self.assertEqual(validateFeedURL(u"crap://foo.bar.com"), False)
        self.assertEqual(validateFeedURL(u"crap:///foo.bar.com"), False)

class FeedURLNormalizationTest(MiroTestCase):
    def test(self):
        self.assertEqual(normalizeFeedURL(u"http://foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"https://foo.bar.com"), u"https://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"feed://foo.bar.com"), u"http://foo.bar.com/")

        self.assertEqual(normalizeFeedURL(u"http:foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"https:foo.bar.com"), u"https://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"feed:foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"http:/foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"https:/foo.bar.com"), u"https://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"feed:/foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"http:///foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"https:///foo.bar.com"), u"https://foo.bar.com/")
        self.assertEqual(normalizeFeedURL(u"feed:///foo.bar.com"), u"http://foo.bar.com/")

        self.assertEqual(normalizeFeedURL(u"foo.bar.com"), u"http://foo.bar.com/")

class FeedTestCase(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.everything = database.defaultDatabase
        [handle, self.filename] = mkstemp(".xml")

    def writefile(self, content):
        self.url = u'file://%s' % self.filename
        handle = file(self.filename,"wb")
        # RSS 2.0 example feed
        # http://cyber.law.harvard.edu/blogs/gems/tech/rss2sample.xml
        handle.write(content)
        handle.close()

    def makeFeed(self):
        feed = Feed(self.url)
        self.updateFeed(feed)
        return feed

    def updateFeed(self, feed):
        feed.update()
        self.processThreads()
        self.processIdles()

class SimpleFeedTestCase(FeedTestCase):
    def setUp(self):
        FeedTestCase.setUp(self)
        # Based on 
        # http://cyber.law.harvard.edu/blogs/gems/tech/rss2sample.xml

        # this rss feed has no enclosures.
        self.writefile("""<?xml version="1.0"?>
<rss version="2.0">
   <channel>
      <title>Liftoff News</title>
      <link>http://liftoff.msfc.nasa.gov/</link>
      <description>Liftoff to Space Exploration.</description>
      <language>en-us</language>
      <pubDate>Tue, 10 Jun 2003 04:00:00 GMT</pubDate>

      <lastBuildDate>Tue, 10 Jun 2003 09:41:01 GMT</lastBuildDate>
      <docs>http://blogs.law.harvard.edu/tech/rss</docs>
      <generator>Weblog Editor 2.0</generator>
      <managingEditor>editor@example.com</managingEditor>
      <webMaster>webmaster@example.com</webMaster>
      <item>
         <title>Star City</title>
         <link>http://liftoff.msfc.nasa.gov/news/2003/news-starcity.mov</link>
         <description>How do Americans get ready to work with Russians aboard the International Space Station? They take a crash course in culture, language and protocol at Russia's &lt;a href="http://howe.iki.rssi.ru/GCTC/gctc_e.htm"&gt;Star City&lt;/a&gt;.</description>
         <pubDate>Tue, 03 Jun 2003 09:39:21 GMT</pubDate>
         <guid>http://liftoff.msfc.nasa.gov/2003/06/03.html#item573</guid>
      </item>
      <item>
         <description>Sky watchers in Europe, Asia, and parts of Alaska and Canada will experience a &lt;a href="http://science.nasa.gov/headlines/y2003/30may_solareclipse.htm"&gt;partial eclipse of the Sun&lt;/a&gt; on Saturday, May 31st.</description>
         <pubDate>Fri, 30 May 2003 11:06:42 GMT</pubDate>
         <guid>http://liftoff.msfc.nasa.gov/2003/05/30.html#item572</guid>
      </item>
      <item>
         <title>The Engine That Does More</title>
         <link>http://liftoff.msfc.nasa.gov/news/2003/news-VASIMR.asp</link>
         <description>Before man travels to Mars, NASA hopes to design new engines that will let us fly through the Solar System more quickly.  The proposed VASIMR engine would do that.</description>
         <pubDate>Tue, 27 May 2003 08:37:32 GMT</pubDate>
         <guid>http://liftoff.msfc.nasa.gov/2003/05/27.html#item571</guid>
      </item>
      <item>
         <title>Astronauts' Dirty Laundry</title>
         <link>http://liftoff.msfc.nasa.gov/news/2003/news-laundry.asp</link>
         <description>Compared to earlier spacecraft, the International Space Station has many luxuries, but laundry facilities are not one of them.  Instead, astronauts have other options.</description>
         <pubDate>Tue, 20 May 2003 08:56:02 GMT</pubDate>
         <guid>http://liftoff.msfc.nasa.gov/2003/05/20.html#item570</guid>
      </item>
   </channel>
</rss>""")
    def testRun(self):
        dialogs.delegate = AcceptScrapeTestDelegate()
        myFeed = self.makeFeed()

        # the feed has no enclosures, but we now insert enclosures into it.
        # thus it should not cause a dialog to pop up and ask the user if they
        # want to scrape.
        self.assertEqual(dialogs.delegate.calls, 0)
        self.assertEqual(self.everything.len(), 2) 

        # the Feed, plus the 1 item that is a video
        items = self.everything.filter(lambda x:x.__class__.__name__ == 'Item')
        self.assertEqual(items.len(), 1)

        # make sure that re-updating doesn't re-create the items
        myFeed.update()
        self.assertEqual(self.everything.len(), 2)
        items = self.everything.filter(lambda x:x.__class__.__name__ == 'Item')
        self.assertEqual(items.len(), 1)
        myFeed.remove()

class EnclosureFeedTestCase(FeedTestCase):
    def setUp(self):
        FeedTestCase.setUp(self)
        self.writefile("""<?xml version="1.0"?>
<rss version="2.0">
   <channel>
      <title>Downhill Battle Pics</title>
      <link>http://downhillbattle.org/</link>
      <description>Downhill Battle is a non-profit organization working to support participatory culture and build a fairer music industry.</description>
      <pubDate>Wed, 16 Mar 2005 12:03:42 EST</pubDate>
      <item>
         <title>Bumper Sticker</title>
         <enclosure url="http://downhillbattle.org/key/gallery/chriscA.mpg" />
         <description>I'm a musician and I support filesharing.</description>

      </item>
      <item>
         <title>T-shirt</title>
         <enclosure url="http://downhillbattle.org/key/gallery/payola_tshirt.mpg" />
      </item>
      <item>
         <enclosure url="http://downhillbattle.org/key/gallery/chriscE.mpg" />
         <description>Flyer in Yucaipa, CA</description>
      </item>
      <item>
         <enclosure url="http://downhillbattle.org/key/gallery/jalabel_nov28.mpg" />
      </item>
      <item>
         <enclosure url="http://downhillbattle.org/key/gallery/jalabel_nov28.jpg" />
      </item>
      
   </channel>
</rss>""")
    def testRun(self):
        myFeed = self.makeFeed()
        self.assertEqual(self.everything.len(),5)
        items = self.everything.filter(lambda x:x.__class__.__name__ == 'Item')
        self.assertEqual(items.len(),4)
        #Make sure that re-updating doesn't re-create the items
        myFeed.update()
        self.assertEqual(self.everything.len(),5)
        items = self.everything.filter(lambda x:x.__class__.__name__ == 'Item')
        self.assertEqual(items.len(),4)
        for item in items:
            #Generate an exception if we didn't get one of the enclosures
            item.entry["enclosures"][0]
            self.assertRaises(IndexError,lambda :item.entry["enclosures"][1])
        myFeed.remove()

class OldItemExpireTest(FeedTestCase):
    # Test that old items expire when the feed gets too big
    def setUp(self):
        FeedTestCase.setUp(self)
        self.counter = 0
        self.writeNewFeed()
        self.feed = self.makeFeed()
        self.items = self.everything.filter(lambda x:x.__class__.__name__ == 'Item')
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 4)

    def writeNewFeed(self, entryCount=2):
        # make a feed with a new item and parse it
        items = []
        for x in range(entryCount):
            self.counter += 1

            items.append("""\
<item>
 <title>Bumper Sticker</title>
 <guid>guid-%s</guid>
 <enclosure url="http://downhillbattle.org/key/gallery/%s.mpg" />
 <description>I'm a musician and I support filesharing.</description>
</item>
""" % (self.counter, self.counter))

        self.writefile("""<?xml version="1.0"?>
<rss version="2.0">
   <channel>
      <title>Downhill Battle Pics</title>
      <link>http://downhillbattle.org/</link>
      <description>Downhill Battle is a non-profit organization working to support participatory culture and build a fairer music industry.</description>
      <pubDate>Wed, 16 Mar 2005 12:03:42 EST</pubDate>
      %s
   </channel>
</rss>""" % '\n'.join(items))

    def checkGuids(self, *ids):
        actual = set()
        for i in self.items:
            actual.add(i.getRSSID())
        correct = set(['guid-%d' % i for i in ids])
        self.assertEquals(actual, correct)

    def parseNewFeed(self, entryCount=2):
        self.writeNewFeed(entryCount)
        self.updateFeed(self.feed)

    def testSimpleOverflow(self):
        self.assertEqual(self.items.len(), 2)
        self.parseNewFeed()
        self.assertEqual(self.items.len(), 4)
        self.parseNewFeed()
        self.assertEqual(self.items.len(), 4)
        self.checkGuids(3, 4, 5, 6)

    def testOverflowWithDownloads(self):
        self.items[0].downloader = FakeDownloader()
        self.items[1].downloader = FakeDownloader()
        self.assertEqual(self.items.len(), 2)
        self.parseNewFeed()
        self.parseNewFeed()
        self.checkGuids(1, 2, 5, 6)

    def testOverflowStillInFeed(self):
        self.parseNewFeed(6)
        self.checkGuids(3, 4, 5, 6, 7, 8)

    def testOverflowWithReplacement(self):
        # Keep item with guid-2 in the feed.
        self.counter = 1
        self.parseNewFeed(5)
        self.checkGuids(2, 3, 4, 5, 6)

if __name__ == "__main__":
    unittest.main()
