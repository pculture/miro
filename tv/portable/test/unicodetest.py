import unittest
from tempfile import mkstemp
from time import sleep

import feed
import database
import feedparser
import app
import dialogs
import eventloop
import schedulertest

from test.framework import DemocracyTestCase

class UnicodeTestDelegate:
    def __init__(self):
        self.choice = None
        self.numCalls = 0
    def runDialog(self, dialog):
        self.numCalls += 1
        # print "rundialog called from %s" % dialog.title
        dialog.choice = self.choice
        # a bit of a hack to avoid using eventloop
        dialog.callback(dialog)

class UnicodeFeedTestCase(schedulertest.EventLoopTest):
    def setUp(self):
        super(UnicodeFeedTestCase, self).setUp()

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
        
        items = database.defaultDatabase.filter(lambda x:x.__class__.__name__ == 'Item')
        self.assertEqual(items.len(),1)
        item = items[0]
        self.assertEqual(len(item.getTitle()), 10)

        # Again, description is the same as title, but surrounded by a <span>
        self.assertEqual(len(item.getDescription()), 23)

    # This is a latin1 feed that claims to be UTF-8
    def testInvalidLatin1Feed(self):
        [handle, self.filename] = mkstemp(".xml")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0"?>
<rss version="2.0">
   <channel>
      <title>H�ppy Birthday</title>
      <description>H�ppy Birthday</description>
      <language>zh-zh</language>
      <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>
      <generator>Weblog Editor 2.0</generator>
      <managingEditor>editor@example.com</managingEditor>
      <webMaster>webmaster@example.com</webMaster>
      <item>
         <title>H�ppy Birthday</title>
         <link>http://participatoryculture.org/boguslink</link>
         <description>H�ppy Birthday</description>
         <enclosure url="file://crap" length="0" type="video/mpeg"/>
         <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>
      </item>
   </channel>
</rss>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)

        # Make sure the feed shows up as invalid
        self.assertEqual(dialogs.delegate.numCalls,1)

    # This is latin1 HTML that claims to be Latin 1
    def testLatin1HTML(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
      <title>H�ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">H�ppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()
        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        self.assertEqual(len(myItem.getTitle()),14)
        self.assertEqual(myItem.getTitle(), u"H�ppy Birthday")

    # This is latin1 HTML that claims to be UTF-8
    def testInvalidLatin1HTML(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="utf-8"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>H�ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">H�ppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()
        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        self.assertEqual(len(myItem.getTitle()),14)
        self.assertEqual(myItem.getTitle(), u"H�ppy Birthday")

    # This is utf-8 HTML that claims to be utf-8
    def testUTF8HTML(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="utf-8"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>Häppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">Häppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()
        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        self.assertEqual(len(myItem.getTitle()),14)
        self.assertEqual(myItem.getTitle(), u"H�ppy Birthday")

    def testUTF8HTMLLinks(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="utf-8"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>Häppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/Häppy.mov">Häppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()
        # Either the item isn't added or it's added with an ascii URL
        if len(myFeed.items) > 0:
            self.assertEqual(len(myFeed.items),1)
            myItem = myFeed.items[0]
            myURL = myItem.getURL()
            self.assertEqual(str(myURL),myURL)

    def testLatin1HTMLLinks(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
      <title>H�ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/H�ppy.mov">H�ppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()
        # Either the item isn't added or it's added with an ascii URL
        if len(myFeed.items) > 0:
            self.assertEqual(len(myFeed.items),1)
            myItem = myFeed.items[0]
            myURL = myItem.getURL()
            self.assertEqual(str(myURL),myURL)

    def testInvalidLatin1HTMLLinks(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
      <title>Häppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/Häppy.mov">Häppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()
        # Either the item isn't added or it's added with an ascii URL
        if len(myFeed.items) > 0:
            self.assertEqual(len(myFeed.items),1)
            myItem = myFeed.items[0]
            myURL = myItem.getURL()
            self.assertEqual(str(myURL),myURL)

    def testUTF8HTMLThumbs(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="utf-8"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>Häppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov"><img src="http://www.wccatv.com/files/video/Häppy.png"/>Häppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()

        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        myURL = myItem.getURL()
        self.assertEqual(str(myURL),myURL)

        thumb = myItem.getThumbnailURL()
        if thumb is not None:
            self.assertEqual(str(thumb),thumb)

    def testLatin1HTMLThumbs(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
      <title>H�ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov"><img src="http://www.wccatv.com/files/video/H�ppy.png"/>H�ppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()

        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        myURL = myItem.getURL()
        self.assertEqual(str(myURL),myURL)

        thumb = myItem.getThumbnailURL()
        if thumb is not None:
            self.assertEqual(str(thumb),thumb)

    def testInvalidLatin1HTMLThumbs(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write("""<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
      <title>Häppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov"><img src="http://www.wccatv.com/files/video/Häppy.png"/>Häppy Birthday</a>
   </body>
</html>""")
        handle.close()

        dialogs.delegate = UnicodeTestDelegate()
        dialogs.delegate.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed("file://"+self.filename)
        
        self.assertEqual(dialogs.delegate.numCalls,1)
        myFeed.update()

        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        myURL = myItem.getURL()
        self.assertEqual(str(myURL),myURL)

        thumb = myItem.getThumbnailURL()
        if thumb is not None:
            self.assertEqual(str(thumb),thumb)
