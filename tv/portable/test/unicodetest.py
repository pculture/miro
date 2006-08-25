import unittest
from tempfile import mkstemp
from time import sleep

import feed
import database
import feedparser

from test.framework import DemocracyTestCase

class UnicodeFeedTestCase(DemocracyTestCase):
    def setUp(self):
        database.DDBObject.dd = database.DynamicDatabase()
        self.everything = database.DDBObject.dd

    def testValidUTF8Feed(self):
        [handle, self.filename] = mkstemp(".xml")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0"?>
<rss version="2.0">
   <channel>
      <title>Chinese Numbers ○一二三四五六七八九</title>
      <description>Chinese Numbers ○一二三四五六七八九</description>
      <language>zh-zh</language>
      <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>
      <generator>Weblog Editor 2.0</generator>
      <managingEditor>editor@example.com</managingEditor>
      <webMaster>webmaster@example.com</webMaster>
      <item>

         <title>○一二三四五六七八九</title>
         <link>http://participatoryculture.org/boguslink</link>
         <description>○一二三四五六七八九</description>
         <enclosure url="file://crap" length="0" type="video/mpeg"/>
         <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>
      </item>
   </channel>
</rss>""")
        handle.close()

        myFeed = feed.Feed("file://"+self.filename)
        
        # a hack to get the feed to update without eventloop
        myFeed.feedparser_callback(feedparser.parse(myFeed.initialHTML))
        
        # The title should be "Chinese numbers " followed by the
        # Chinese characters for 0-9
        self.assertEqual(len(myFeed.getTitle()), 26)

        # The description is the same, but surrounded by a <span>
        self.assertEqual(len(myFeed.getDescription()), 39)
        
        items = self.everything.filter(lambda x:x.__class__.__name__ == 'Item')
        self.assertEqual(items.len(),1)
        item = items[0]
        self.assertEqual(len(item.getTitle()), 10)

        # Again, description is the same as title, but surrounded by a <span>
        self.assertEqual(len(item.getDescription()), 23)
        
