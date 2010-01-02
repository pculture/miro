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

    def run_dialog(self, dialog):
        self.calls += 1
        if not isinstance(dialog, dialogs.ChoiceDialog):
            raise AssertionError("Only expected ChoiceDialogs")
        if not dialog.title.startswith("Channel is not compatible"):
            raise AssertionError("Only expected scrape dialogs")
        dialog.choice = dialogs.BUTTON_YES
        dialog.callback(dialog)

class FeedURLValidationTest(MiroTestCase):
    def test_positive(self):
        for i, o in [(u"http://foo.bar.com/", True),
                     (u"https://foo.bar.com/", True)
                     ]:
            self.assertEqual(validate_feed_url(i), o)

    def test_negative(self):
        for i, o in [(u"feed://foo.bar.com/", False),
                     (u"http://foo.bar.com", False),
                     (u"http:foo.bar.com/", False),
                     (u"https:foo.bar.com/", False),
                     (u"feed:foo.bar.com/", False),
                     (u"http:/foo.bar.com/", False),
                     (u"https:/foo.bar.com/", False),
                     (u"feed:/foo.bar.com/", False),
                     (u"http:///foo.bar.com/", False),
                     (u"https:///foo.bar.com/", False),
                     (u"feed:///foo.bar.com/", False),
                     (u"foo.bar.com", False),
                     (u"crap:foo.bar.com", False),
                     (u"crap:/foo.bar.com", False),
                     (u"crap://foo.bar.com", False),
                     (u"crap:///foo.bar.com", False),
                     ]:
            self.assertEqual(validate_feed_url(i), o)

        # FIXME - add tests for all the other kinds of urls that
        # validate_feed_url handles.

class FeedURLNormalizationTest(MiroTestCase):
    def test_easy(self):
        for i, o in [(u"http://foo.bar.com", u"http://foo.bar.com/"),
                     (u"https://foo.bar.com", u"https://foo.bar.com/"),
                     (u"feed://foo.bar.com", u"http://foo.bar.com/")
                     ]:
            self.assertEqual(normalize_feed_url(i), o)

    def test_garbage(self):
        for i, o in [(u"http:foo.bar.com", u"http://foo.bar.com/"),
                     (u"https:foo.bar.com", u"https://foo.bar.com/"),
                     (u"feed:foo.bar.com", u"http://foo.bar.com/"),
                     (u"http:/foo.bar.com", u"http://foo.bar.com/"),
                     (u"https:/foo.bar.com", u"https://foo.bar.com/"),
                     (u"feed:/foo.bar.com", u"http://foo.bar.com/"),
                     (u"http:///foo.bar.com", u"http://foo.bar.com/"),
                     (u"https:///foo.bar.com", u"https://foo.bar.com/"),
                     (u"feed:///foo.bar.com", u"http://foo.bar.com/"),
                     (u"foo.bar.com", u"http://foo.bar.com/"),
                     (u"http://foo.bar.com:80", u"http://foo.bar.com:80/"),
                     ]:
            self.assertEquals(normalize_feed_url(i), o)

        # FIXME - add tests for all the other kinds of feeds that
        # normalize_feed_url handles.

class FeedTestCase(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.filename = self.make_temp_path()

    def write_file(self, content):
        self.url = u'file://%s' % self.filename
        handle = file(self.filename,"wb")
        # RSS 2.0 example feed
        # http://cyber.law.harvard.edu/blogs/gems/tech/rss2sample.xml
        handle.write(content)
        handle.close()

    def update_feed(self, feed):
        feed.update()
        self.processThreads()
        self.processIdles()

    def make_feed(self):
        feed = Feed(self.url)
        self.update_feed(feed)
        return feed

class SimpleFeedTestCase(FeedTestCase):
    def setUp(self):
        FeedTestCase.setUp(self)
        # Based on 
        # http://cyber.law.harvard.edu/blogs/gems/tech/rss2sample.xml

        # this rss feed has no enclosures.
        self.write_file("""<?xml version="1.0"?>
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

    def test_run(self):
        dialogs.delegate = AcceptScrapeTestDelegate()
        my_feed = self.make_feed()

        # the feed has no enclosures, but we now insert enclosures into it.
        # thus it should not cause a dialog to pop up and ask the user if they
        # want to scrape.
        self.assertEqual(dialogs.delegate.calls, 0)
        # the Feed, plus the 1 item that is a video
        items = list(Item.make_view())
        self.assertEqual(len(items), 1)

        # make sure that re-updating doesn't re-create the items
        my_feed.update()
        items = list(Item.make_view())
        self.assertEqual(len(items), 1)
        my_feed.remove()

class MultiFeedExpireTest(FeedTestCase):
    def write_files(self, subfeed_count, feed_item_count):
        all_urls = []
        self.filenames = []

        content = self.make_feed_content(feed_item_count)
        for i in xrange(subfeed_count):
            filename = self.make_temp_path()
            open(filename, 'wb').write(content)
            all_urls.append(u"file://%s" % filename)
            self.filenames.append(filename)

        self.url = u'dtv:multi:' + ','.join(all_urls) + "," + 'testquery'

    def rewrite_files(self, feed_item_count):
        content = self.make_feed_content(feed_item_count)
        for filename in self.filenames:
            open(filename, 'wb').write(content)

    def make_feed_content(self, entry_count):
        # make a feed with a new item and parse it
        items = []
        counter = 0

        items.append("""<?xml version="1.0"?>
<rss version="2.0">
   <channel>
      <title>Downhill Battle Pics</title>
      <link>http://downhillbattle.org/</link>
      <description>Downhill Battle is a non-profit organization working to support participatory culture and build a fairer music industry.</description>
      <pubDate>Wed, 16 Mar 2005 12:03:42 EST</pubDate>
""")

        for x in range(entry_count):
            counter += 1
            items.append("""\
<item>
 <title>Bumper Sticker</title>
 <guid>guid-%s</guid>
 <enclosure url="http://downhillbattle.org/key/gallery/%s.mpg" />
 <description>I'm a musician and I support filesharing.</description>
</item>
""" % (counter, counter))

        items.append("""
   </channel>
</rss>""")
        return "".join(items)

    def test_multi_feed_expire(self):
        # test what happens when a RSSMultiFeed has feeds that
        # reference the same item, and they are truncated at the same
        # time (#11756)

        self.write_files(5, 10) # 5 feeds containing 10 identical items
        self.feed = self.make_feed()
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 4)
        config.set(prefs.MAX_OLD_ITEMS_DEFAULT, 5)
        self.rewrite_files(1) # now only 5 items in each feed
        self.update_feed(self.feed)

class EnclosureFeedTestCase(FeedTestCase):
    def setUp(self):
        FeedTestCase.setUp(self)
        self.write_file("""<?xml version="1.0"?>
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

    def test_run(self):
        my_feed = self.make_feed()
        items = list(Item.make_view())
        self.assertEqual(len(items), 4)
        # make sure that re-updating doesn't re-create the items
        my_feed.update()
        items = list(Item.make_view())
        self.assertEqual(len(items), 4)
        my_feed.remove()

class OldItemExpireTest(FeedTestCase):
    # Test that old items expire when the feed gets too big
    def setUp(self):
        FeedTestCase.setUp(self)
        self.counter = 0
        self.write_new_feed()
        self.feed = self.make_feed()
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 4)
        config.set(prefs.MAX_OLD_ITEMS_DEFAULT, 20)

    def write_new_feed(self, entryCount=2):
        # make a feed with a new item and parse it
        items = []

        items.append("""<?xml version="1.0"?>
<rss version="2.0">
   <channel>
      <title>Downhill Battle Pics</title>
      <link>http://downhillbattle.org/</link>
      <description>Downhill Battle is a non-profit organization working to support participatory culture and build a fairer music industry.</description>
      <pubDate>Wed, 16 Mar 2005 12:03:42 EST</pubDate>
""")

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

        items.append("""
   </channel>
</rss>""")
        self.write_file("\n".join(items))

    def check_guids(self, *ids):
        actual = set()
        for i in Item.make_view():
            actual.add(i.get_rss_id())
        correct = set(['guid-%d' % i for i in ids])
        self.assertEquals(actual, correct)

    def parse_new_feed(self, entryCount=2):
        self.write_new_feed(entryCount)
        self.update_feed(self.feed)

    def test_simple_overflow(self):
        self.assertEqual(Item.make_view().count(), 2)
        self.parse_new_feed()
        self.assertEqual(Item.make_view().count(), 4)
        self.parse_new_feed()
        self.assertEqual(Item.make_view().count(), 4)
        self.check_guids(3, 4, 5, 6)

    def test_overflow_with_downloads(self):
        items = list(Item.make_view())
        items[0]._downloader = FakeDownloader()
        items[1]._downloader = FakeDownloader()
        self.assertEqual(len(items), 2)
        self.parse_new_feed()
        self.parse_new_feed()
        self.check_guids(1, 2, 5, 6)

    def test_overflow_still_in_feed(self):
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 0)
        self.parse_new_feed(6)
        self.check_guids(3, 4, 5, 6, 7, 8)

    def test_overflow_with_replacement(self):
        # Keep item with guid-2 in the feed.
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 0)
        self.counter = 1
        self.parse_new_feed(5)
        self.check_guids(2, 3, 4, 5, 6)

    def test_overflow_with_max_old_items(self):
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 1000) # don't bother
        self.assertEqual(Item.make_view().count(), 2)
        self.parse_new_feed()
        self.assertEquals(Item.make_view().count(), 4)
        self.parse_new_feed()
        self.feed.setMaxOldItems(4)
        self.feed.actualFeed.clean_old_items()
        while self.feed.actualFeed.updating:
            self.processThreads()
            self.processIdles()
            sleep(0.1)
        self.assertEquals(Item.make_view().count(), 6)            
        self.feed.setMaxOldItems(2)
        self.feed.actualFeed.clean_old_items()
        while self.feed.actualFeed.updating:
            self.processThreads()
            self.processIdles()
            sleep(0.1)
        self.assertEquals(Item.make_view().count(), 4)
        self.check_guids(3, 4, 5, 6)

    def test_overflow_with_global_max_old_items(self):
        config.set(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS, 1000) # don't bother
        self.assertEqual(Item.make_view().count(), 2)
        self.parse_new_feed()
        self.assertEquals(Item.make_view().count(), 4)
        self.parse_new_feed()
        config.set(prefs.MAX_OLD_ITEMS_DEFAULT, 4)
        self.feed.actualFeed.clean_old_items()
        while self.feed.actualFeed.updating:
            self.processThreads()
            self.processIdles()
            sleep(0.1)
        self.assertEquals(Item.make_view().count(), 6)
        config.set(prefs.MAX_OLD_ITEMS_DEFAULT, 2)
        self.feed.actualFeed.clean_old_items()
        while self.feed.actualFeed.updating:
            self.processThreads()
            self.processIdles()
            sleep(0.1)
        self.assertEquals(Item.make_view().count(), 4)
        self.check_guids(3, 4, 5, 6)

class FeedParserAttributesTestCase(FeedTestCase):
    """Test that we save/restore attributes from feedparser correctly.

    We don't store feedparser dicts in the database.  This test case is
    checking if the values we to the database are the same as the original
    ones from feedparser.
    """
    def setUp(self):
        FeedTestCase.setUp(self)
        self.tempdb = os.path.join(gettempdir(), 'democracy-temp-db')
        if os.path.exists(self.tempdb):
            os.remove(self.tempdb)
        self.reload_database(self.tempdb)
        self.write_feed()
        self.parsed_feed = feedparser.parse(self.filename)
        self.make_feed()
        self.save_then_restore_db()

    def tearDown(self):
        self.runPendingIdles()
        os.remove(self.tempdb)
        FeedTestCase.tearDown(self)

    def save_then_restore_db(self):
        self.reload_database(self.tempdb)
        self.feed = Feed.make_view().get_singleton()
        self.item = Item.make_view().get_singleton()

    def write_feed(self):
        self.write_file("""<?xml version="1.0"?>
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
        self.assertEquals(self.item.get_rss_id(), entry.id)
        self.assertEquals(self.item.get_thumbnail_url(), entry.thumbnail['url'])
        self.assertEquals(self.item.get_title(), entry.title)
        self.assertEquals(self.item.get_raw_description(), entry.description)
        self.assertEquals(self.item.get_link(), entry.link)
        self.assertEquals(self.item.get_payment_link(), entry.payment_url)
        self.assertEquals(self.item.get_license(), entry.license)
        self.assertEquals(self.item.get_comments_link(), entry.comments)

        enclosure = entry.enclosures[0]
        self.assertEquals(self.item.get_url(), enclosure.url)
        self.assertEquals(self.item.get_size(), int(enclosure.length))
        self.assertEquals(self.item.get_format(), '.mpeg')

    def test_remove_rssid(self):
        self.item.remove_rss_id()
        self.save_then_restore_db()
        self.assertEquals(self.item.get_rss_id(), None)

    def test_change_title(self):
        entry = self.parsed_feed.entries[0]
        self.item.set_title(u"new title")
        self.save_then_restore_db()
        self.assertEquals(self.item.get_title(), "new title")
        self.assert_(not self.item.has_original_title())

        self.item.revert_title()
        self.save_then_restore_db()
        self.assertEquals(self.item.get_title(), entry.title)
        self.assert_(self.item.has_original_title())

if __name__ == "__main__":
    unittest.main()
