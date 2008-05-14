import unittest
from tempfile import mkstemp
from time import sleep
import time
import types

from miro import feed
from miro import item
from miro import database
from miro import feedparser
from miro import app
from miro import dialogs
import framework
import os
from miro import gtcache
import gettext
from miro import signals
from miro.plat import resources
from miro.frontends.html import template
from miro import util
from miro.frontends.html.template_compiler import TemplateError
from miro.frontends.html import template_compiler

from miro.test.framework import MiroTestCase

class UnicodeFeedTestCase(framework.EventLoopTest):
    def setUp(self):
        super(UnicodeFeedTestCase, self).setUp()
        signals.system.connect('new-dialog', self.onNewDialog)
        self.choice = None
        self.numDialogs = 0

    def onNewDialog(self, obj, dialog):
        self.assertNotEqual(self.choice, None)
        self.numDialogs += 1
        # print "rundialog called from %s" % dialog.title
        dialog.choice = self.choice
        # a bit of a hack to avoid using eventloop
        dialog.callback(dialog)

    def isProperFeedParserDict(self, parsed, name="top"):
        if isinstance(parsed, types.DictionaryType):
            for (key, value) in parsed.items():
                self.isProperFeedParserDict(value, key)
        elif (isinstance(parsed, types.ListType) or
              isinstance(parsed, types.TupleType)):
            for value in parsed:
                self.isProperFeedParserDict(value, name)
        elif isinstance(parsed, types.StringType):
            self.assert_(name in ["base","type","encoding","version","href","rel"])
        elif isinstance(parsed, time.struct_time):
            self.assert_(name in ["updated_parsed"])
        elif isinstance(parsed, types.IntType):
            self.assert_(name in ["bozo"])
        else:
            self.assert_((isinstance(parsed,types.UnicodeType) or
                          isinstance(parsed,types.NoneType)))

    # Returns true iff value is a python unicode string containing
    # only ascii characters
    def isASCIIUnicode(self, value):
        return ((type(value) == types.UnicodeType) and
                (value == value.encode('ascii')))

    def testValidUTF8Feed(self):
        [handle, self.filename] = mkstemp(".xml")
        handle =file(self.filename,"wb")
        handle.write(u'<?xml version="1.0"?>\n<rss version="2.0">\n   <channel>\n <title>Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d</title>\n      <description>Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d</description>\n      <language>zh-zh</language>\n     <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>\n      <generator>Weblog Editor 2.0</generator>\n      <managingEditor>editor@example.com</managingEditor>\n      <webMaster>webmaster@example.com</webMaster>\n      <item>\n\n         <title>\u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d</title>\n     <link>http://participatoryculture.org/boguslink</link>\n         <description>\u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d</description>\n        <enclosure url="file://crap" length="0" type="video/mpeg"/>\n         <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>\n      </item>\n   </channel>\n</rss>'.encode('utf-8'))

        handle.close()

        myFeed = feed.Feed(u"file://"+self.filename)
        self.forceFeedParserCallback(myFeed)

        self.isProperFeedParserDict(myFeed.parsed)

        # We need to explicitly check that the type is unicode because
        # Python automatically converts bytes strings to unicode strings
        # using the current system character set
        self.assertEqual(type(myFeed.getTitle()), types.UnicodeType)
        self.assertEqual(u"Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d",myFeed.getTitle())

        # The description is the same, but surrounded by a <span>
        self.assertEqual(type(myFeed.getDescription()), types.UnicodeType)
        self.assertEqual(u"<span>Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d</span>",myFeed.getDescription())

        items = database.defaultDatabase.filter(lambda x:x.__class__ == item.Item)
        self.assertEqual(items.len(),1)
        i = items[0]
        self.assertEqual(type(i.getTitle()), types.UnicodeType)
        self.assertEqual(u"\u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d",i.getTitle())

        self.assertEqual(type(i.getDescription()), types.UnicodeType)
        self.assertEqual(u"<span>\u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d</span>",i.getDescription())

    def forceFeedParserCallback(self, myFeed):
        # a hack to get the feed to update without eventloop
        myFeed.feedparser_callback(feedparser.parse(myFeed.initialHTML))

    # This is a latin1 feed that claims to be UTF-8
    def testInvalidLatin1Feed(self):
        [handle, self.filename] = mkstemp(".xml")
        handle = file(self.filename,"wb")
        handle.write('<?xml version="1.0"?>\n<rss version="2.0">\n   <channel>\n      <title>H\xe4ppy Birthday</title>\n      <description>H\xe4ppy Birthday</description>\n <language>zh-zh</language>\n      <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>\n      <generator>Weblog Editor 2.0</generator>\n      <managingEditor>editor@example.com</managingEditor>\n      <webMaster>webmaster@example.com</webMaster>\n      <item>\n         <title>H\xe4ppy Birthday</title>\n         <link>http://participatoryculture.org/boguslink</link>\n         <description>H\xe4ppy Birthday</description>\n         <enclosure url="file://crap" length="0" type="video/mpeg"/>\n         <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>\n      </item>\n   </channel>\n</rss>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)

        myFeed.update()
        self.processThreads()
        self.processIdles()
        self.assertEqual(len(myFeed.items), 1)
        myItem = myFeed.items[0]
        self.assertEqual(len(myItem.getTitle()), 14)
        self.assertEqual(myItem.getTitle(), u"H\xe4ppy Birthday")

    # This is latin1 HTML that claims to be Latin 1
    def testLatin1HTML(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write('<?xml version="1.0" encoding="iso-8859-1"?>\n<html>\n   <head>\n       <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />\n  <title>H\xe4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/hbml.mov">H\xe4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs, 1)
        myFeed.update()
        self.assertEqual(len(myFeed.items), 1)
        myItem = myFeed.items[0]
        self.assertEqual(len(myItem.getTitle()), 14)
        self.assertEqual(myItem.getTitle(), u"H\xe4ppy Birthday")

    # This is latin1 HTML that claims to be UTF-8
    def testInvalidLatin1HTML(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write('<?xml version="1.0" encoding="utf-8"?>\n<html>\n   <head>\n       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n      <title>H\xe4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/hbml.mov">H\xe4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs,1)
        myFeed.update()
        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        self.assertEqual(len(myItem.getTitle()),14)
        self.assertEqual(myItem.getTitle(), u"H\xe4ppy Birthday")

    # This is utf-8 HTML that claims to be utf-8
    def testUTF8HTML(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write('<?xml version="1.0" encoding="utf-8"?>\n<html>\n   <head>\n       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n      <title>H\xc3\xa4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/hbml.mov">H\xc3\xa4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs,1)
        myFeed.update()
        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        self.assertEqual(len(myItem.getTitle()),14)
        self.assertEqual(myItem.getTitle(), u"H\xe4ppy Birthday")

    def testUTF8HTMLLinks(self):
        [handle, self.filename] = mkstemp(".html")
        handle =file(self.filename,"wb")
        handle.write('<?xml version="1.0" encoding="utf-8"?>\n<html>\n   <head>\n       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n      <title>H\xc3\xa4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/H\xc3\xa4ppy.mov">H\xc3\xa4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs,1)
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
        handle.write('<?xml version="1.0" encoding="iso-8859-1"?>\n<html>\n   <head>\n <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />\n   <title>H\xe4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/H\xe4ppy.mov">H\xe4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs,1)
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
        handle.write('<?xml version="1.0" encoding="iso-8859-1"?>\n<html>\n   <head>\n       <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />\n      <title>H\xc3\xa4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/H\xc3\xa4ppy.mov">H\xc3\xa4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs,1)
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
        handle.write('<?xml version="1.0" encoding="utf-8"?>\n<html>\n   <head>\n <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n      <title>H\xc3\xa4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/hbml.mov"><img src="http://www.wccatv.com/files/video/H\xc3\xa4ppy.png"/>H\xc3\xa4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs,1)
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
        handle.write('<?xml version="1.0" encoding="iso-8859-1"?>\n<html>\n   <head>\n  <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />\n    <title>H\xe4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/hbml.mov"><img src="http://www.wccatv.com/files/video/H\xe4ppy.png"/>H\xe4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs,1)
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
        handle.write('<?xml version="1.0" encoding="iso-8859-1"?>\n<html>\n   <head>\n       <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />\n <title>H\xc3\xa4ppy Birthday</title>\n   </head>\n   <body>\n   <a href="http://www.wccatv.com/files/video/hbml.mov"><img src="http://www.wccatv.com/files/video/H\xc3\xa4ppy.png"/>H\xc3\xa4ppy Birthday</a>\n   </body>\n</html>')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        myFeed = feed.Feed(u"file://"+self.filename)
        
        self.assertEqual(self.numDialogs,1)
        myFeed.update()

        self.assertEqual(len(myFeed.items),1)
        myItem = myFeed.items[0]
        myURL = myItem.getURL()
        self.assertEqual(str(myURL),myURL)

        thumb = myItem.getThumbnailURL()
        if thumb is not None:
            self.assertEqual(str(thumb),thumb)

    def testDemocracyNowBug(self):
        url = resources.url("testdata/democracy-now-unicode-bug.xml")
        myFeed = feed.Feed(url)
        self.forceFeedParserCallback(myFeed)
        for item in myFeed.items:
            u'booya' in item.getTitle().lower()

    def testGetText(self):
        # FIXME this only works on GTK platforms. See #3831
        oldLang = None
        try:
            oldLang = os.environ["LANGUAGE"]
        except:
            pass
        os.environ["LANGUAGE"] = "fr"
        gtcache._gtcache = {}

        gettext.bindtextdomain("miro",resources.path("../../locale"))
        gettext.textdomain("miro")
        gettext.bind_textdomain_codeset("miro","UTF-8")
        self.assertEqual(gtcache.gettext("Settings"),u'R\xe9glages')
        if oldLang is None:
            del os.environ["LANGUAGE"]
        else:
            os.environ["LANGUAGE"] = oldLang

    def testTemplates(self):
        # This tests that templates output valid UTF-8
        
        # FIXME this only works on GTK platforms. See #3831
        oldLang = None
        try:
            oldLang = os.environ["LANGUAGE"]
        except:
            pass
        os.environ["LANGUAGE"] = "fr"
        gtcache._gtcache = {}

        gettext.bindtextdomain("miro",resources.path("../../locale"))
        gettext.textdomain("miro")
        gettext.bind_textdomain_codeset("miro","UTF-8")

        out = template.fillStaticTemplate("unittest/simpleunicode", "gtk-x11", "noCookie")
        self.assert_(type(out)==types.UnicodeType)
        # We shouldn't find utf-8 versions of this text
        self.assert_(out.find(u'<h1>H\xc3\xa4ppy Birthday</h1>') == -1)
        self.assert_(out.find(u'<p>R\xc3\xa9glages</p>') == -1)

        # We should find the unicode string
        self.assert_(out.find(u"<h1>H\xe4ppy Birthday</h1>") != -1)
        self.assert_(out.find(u"<p>R\xe9glages</p>") != -1)
        if oldLang is None:
            del os.environ["LANGUAGE"]
        else:
            os.environ["LANGUAGE"] = oldLang

class TemplateCompilerTest(framework.MiroTestCase):
    def testNonUnicode(self):
        # genRepeatText
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genRepeatText("out","123","    ","boo"))
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genRepeatText("out","123","    ","Chinese Numbers \x25cb\x4e00\x4e8c\x4e09\x56db\x4e94\x516d\x4e03\x516b\x4e5d"))
        self.assertEqual(u"    out.write(u'Chinese Numbers \\u25cb\\u4e00\\u4e8c\\u4e09\\u56db\\u4e94\\u516d\\u4e03\\u516b\\u4e5d')\n",
                         template_compiler.genRepeatText("out","123","    ",u"Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d"))


        # genRepeatTranslate
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genRepeatTranslate("out","123","    ",("boo",{})))
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genRepeatTranslate("out","123","    ",("Chinese Numbers \x25cb\x4e00\x4e8c\x4e09\x56db\x4e94\x516d\x4e03\x516b\x4e5d",{})))


        # genRepeatTextHide
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genRepeatTextHide("out","123","    ",(False,"boo")))
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genRepeatTextHide("out","123","    ",(False, "Chinese Numbers \x25cb\x4e00\x4e8c\x4e09\x56db\x4e94\x516d\x4e03\x516b\x4e5d")))
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genRepeatTextHide("out","123","    ",(True,"boo")))
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genRepeatTextHide("out","123","    ",(True, "Chinese Numbers \x25cb\x4e00\x4e8c\x4e09\x56db\x4e94\x516d\x4e03\x516b\x4e5d")))

        self.assertEqual(u"    if not (True):\n        out.write(u'Chinese Numbers \\u25cb\\u4e00\\u4e8c\\u4e09\\u56db\\u4e94\\u516d\\u4e03\\u516b\\u4e5d')\n",
                         template_compiler.genRepeatTextHide("out","123","    ",(True, u"Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d")))

        # genHideSection
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genHideSection("out","123","    ",(False,[(lambda a,b,c,d: "boo","ignored")])))
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda : template_compiler.genHideSection("out","123","    ",(False,[(lambda a,b,c,d: "Chinese Numbers \x25cb\x4e00\x4e8c\x4e09\x56db\x4e94\x516d\x4e03\x516b\x4e5d","ignored")])))
        self.assertEqual(u'    if not (False):\nChinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d',
                          template_compiler.genHideSection("out","123","    ",(False,[(lambda a,b,c,d: u"Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d","ignored")])))

        # genQuoteAndFillAttr
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda:template_compiler.genQuoteAndFillAttr("out","123","    ","boo"))
        self.assertRaises(util.DemocracyUnicodeError,
                          lambda:template_compiler.genQuoteAndFillAttr("out","123","    ","Chinese Numbers \x25cb\x4e00\x4e8c\x4e09\x56db\x4e94\x516d\x4e03\x516b\x4e5d"))
        self.assertEqual(u"    out.write(quoteAndFillAttr(u'Chinese Numbers \\u25cb\\u4e00\\u4e8c\\u4e09\\u56db\\u4e94\\u516d\\u4e03\\u516b\\u4e5d',locals()))\n",
                         template_compiler.genQuoteAndFillAttr("out","123","    ",u"Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d"))

