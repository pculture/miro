import os
import unittest
from tempfile import mkstemp, gettempdir
from datetime import datetime
from time import sleep

from miro import config
from miro import feedparser
from miro import prefs
from miro import dialogs
from miro import database
from miro import storedatabase
from miro import feedparserutil
from miro.plat import resources
from miro.item import Item
from miro.feed import validate_feed_url, normalize_feed_url, Feed

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
        self.assertEqual(validate_feed_url(u"http://foo.bar.com/"), True)
        self.assertEqual(validate_feed_url(u"https://foo.bar.com/"), True)
                         
        self.assertEqual(validate_feed_url(u"feed://foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"http://foo.bar.com"), False)
        self.assertEqual(validate_feed_url(u"http:foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"https:foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"feed:foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"http:/foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"https:/foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"feed:/foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"http:///foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"https:///foo.bar.com/"), False)
        self.assertEqual(validate_feed_url(u"feed:///foo.bar.com/"), False)

        self.assertEqual(validate_feed_url(u"foo.bar.com"), False)
        self.assertEqual(validate_feed_url(u"crap:foo.bar.com"), False)
        self.assertEqual(validate_feed_url(u"crap:/foo.bar.com"), False)
        self.assertEqual(validate_feed_url(u"crap://foo.bar.com"), False)
        self.assertEqual(validate_feed_url(u"crap:///foo.bar.com"), False)

        # FIXME - add tests for all the other kinds of urls that validate_feed_url
        # handles.

class FeedURLNormalizationTest(MiroTestCase):
    def test(self):
        self.assertEqual(normalize_feed_url(u"http://foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"https://foo.bar.com"), u"https://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"feed://foo.bar.com"), u"http://foo.bar.com/")

        self.assertEqual(normalize_feed_url(u"http:foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"https:foo.bar.com"), u"https://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"feed:foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"http:/foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"https:/foo.bar.com"), u"https://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"feed:/foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"http:///foo.bar.com"), u"http://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"https:///foo.bar.com"), u"https://foo.bar.com/")
        self.assertEqual(normalize_feed_url(u"feed:///foo.bar.com"), u"http://foo.bar.com/")

        self.assertEqual(normalize_feed_url(u"foo.bar.com"), u"http://foo.bar.com/")

        # FIXME - add tests for all the other kinds of feeds that normalize_feed_url
        # handles.

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
        config.set(prefs.MAX_OLD_ITEMS_DEFAULT, 20)

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
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 0)
        self.parseNewFeed(6)
        self.checkGuids(3, 4, 5, 6, 7, 8)

    def testOverflowWithReplacement(self):
        # Keep item with guid-2 in the feed.
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 0)
        self.counter = 1
        self.parseNewFeed(5)
        self.checkGuids(2, 3, 4, 5, 6)

    def testOverflowWithMaxOldItems(self):
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 1000) # don't bother
        self.assertEqual(self.items.len(), 2)
        self.parseNewFeed()
        self.assertEquals(self.items.len(), 4)
        self.parseNewFeed()
        self.feed.setMaxOldItems(4)
        self.feed.clean_old_items()
        while self.feed.actualFeed.updating:
            self.processThreads()
            self.processIdles()
            sleep(0.1)
        self.assertEquals(self.items.len(), 6)            
        self.feed.setMaxOldItems(2)
        self.feed.clean_old_items()
        while self.feed.actualFeed.updating:
            self.processThreads()
            self.processIdles()
            sleep(0.1)
        self.assertEquals(self.items.len(), 4)
        self.checkGuids(3, 4, 5, 6)

    def testOverflowWithGlobalMaxOldItems(self):
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 1000) # don't bother
        self.assertEqual(self.items.len(), 2)
        self.parseNewFeed()
        self.assertEquals(self.items.len(), 4)
        self.parseNewFeed()
        config.set(prefs.MAX_OLD_ITEMS_DEFAULT, 4)
        self.feed.clean_old_items()
        while self.feed.actualFeed.updating:
            self.processThreads()
            self.processIdles()
            sleep(0.1)
        self.assertEquals(self.items.len(), 6)
        config.set(prefs.MAX_OLD_ITEMS_DEFAULT, 2)
        self.feed.clean_old_items()
        while self.feed.actualFeed.updating:
            self.processThreads()
            self.processIdles()
            sleep(0.1)
        self.assertEquals(self.items.len(), 4)
        self.checkGuids(3, 4, 5, 6)

class FeedParserAttributesTestCase(FeedTestCase):
    """Test that we save/restore attributes from feedparser correctly.

    We don't store feedparser dicts in the database.  This test case is
    checking if the values we to the database are the same as the original
    ones from feedparser.
    """

    def setUp(self):
        FeedTestCase.setUp(self)
        self.write_feed()
        self.parsed_feed = feedparser.parse(self.filename)
        self.makeFeed()
        self.save_then_restore_db()

    def tearDown(self):
        self.runPendingIdles()
        self.everything.liveStorage.close()
        self.everything.liveStorage = None
        os.remove(self.tempdb)
        database.resetDefaultDatabase()
        FeedTestCase.tearDown(self)

    def save_then_restore_db(self):
        self.tempdb = os.path.join(gettempdir(), 'democracy-temp-db')
        db = database.defaultDatabase
        db.liveStorage = storedatabase.LiveStorage(self.tempdb, restore=False)
        db.liveStorage.saveDatabase()
        db.liveStorage.close()
        db.liveStorage = storedatabase.LiveStorage(self.tempdb)
        for obj in database.defaultDatabase:
            if isinstance(obj, Feed):
                self.feed = obj
            if isinstance(obj, Item):
                self.item = obj

    def write_feed(self):
        self.writefile("""<?xml version="1.0"?>
<rss version="2.0">
    <channel>
        <title>Downhill Battle Pics</title>
        <link>http://downhillbattle.org/</link>
        <description>Downhill Battle is a non-profit organization working to support participatory culture and build a fairer music industry.</description>
        <pubDate>Wed, 16 Mar 2005 12:03:42 EST</pubDate>

        <item>
            <title>Bumper Sticker</title>
            <link>http://downhillbattle.org/item</link>
            <comments>http://downhillbattle.org/item/comments</comments>
            <creativeCommons:license>http://www.creativecommons.org/licenses/by-nd/1.0</creativeCommons:license>
            <guid>guid-1234</guid>
            <enclosure url="http://downhillbattle.org/key/gallery/movie.mpg"
                length="1234"
                type="video/mpeg"
                />
            <description>I'm a musician and I support filesharing.</description>
            <pubDate>Fri, 18 Mar 2005 12:03:42 EST</pubDate>
            <media:thumbnail url="%(thumburl)s" />
            <dtv:paymentlink url="http://www.example.com/payment.html" />
        </item>

    </channel>
</rss>
""" % {'thumburl': resources.url("testdata/democracy-now-unicode-bug.xml")})


    def test_attributes(self):
        entry = self.parsed_feed.entries[0]
        self.assertEquals(self.item.getRSSID(), entry.id)
        self.assertEquals(self.item.getThumbnailURL(), entry.thumbnail['url'])
        self.assertEquals(self.item.get_title(), entry.title)
        self.assertEquals(self.item.get_raw_description(), entry.description)
        self.assertEquals(self.item.get_link(), entry.link)
        self.assertEquals(self.item.get_payment_link(), entry.payment_url)
        self.assertEquals(self.item.get_license(), entry.license)
        self.assertEquals(self.item.get_comments_link(), entry.comments)

        enclosure = entry.enclosures[0]
        self.assertEquals(self.item.getURL(), enclosure.url)
        self.assertEquals(self.item.get_size(), int(enclosure.length))
        self.assertEquals(self.item.get_format(), '.mpeg')
        self.assertEquals(self.item.getFirstVideoEnclosureType(),
                enclosure.type)

    def test_remove_rssid(self):
        self.item.removeRSSID()
        self.save_then_restore_db()
        self.assertEquals(self.item.getRSSID(), None)

    def test_change_title(self):
        entry = self.parsed_feed.entries[0]
        self.item.setTitle(u"new title")
        self.save_then_restore_db()
        self.assertEquals(self.item.get_title(), "new title")
        self.assert_(not self.item.has_original_title())

        self.item.revert_title()
        self.save_then_restore_db()
        self.assertEquals(self.item.get_title(), entry.title)
        self.assert_(self.item.has_original_title())

    def test_feedparser_output(self):
        # test a couple entries from the feedparser_output attribute
        feedparser_output = self.item.feedparser_output
        self.assertEquals(feedparser_output['title'], 'Bumper Sticker')
        self.assertEquals(feedparser_output['id'], 'guid-1234')
        self.assertEquals(feedparser_output['summary'],
            "I'm a musician and I support filesharing.")
        self.assertEquals(feedparser_output['enclosures'],
                [{'href': u'http://downhillbattle.org/key/gallery/movie.mpg',
                    'type': u'video/mpeg', 'filesize': u'1234'}])

if __name__ == "__main__":
    unittest.main()
