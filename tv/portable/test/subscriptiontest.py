import os
import unittest

from miro import subscription

from miro.test.framework import MiroTestCase

# =============================================================================
# Test data
# =============================================================================

SAMPLE_RSS_SUBSCRIPTION_URL_1  = "http://www.domain-1.com/videos/rss.xml"
SAMPLE_RSS_SUBSCRIPTION_URL_2  = "http://www.domain-2.com/videos/rss.xml"
SAMPLE_ATOM_SUBSCRIPTION_URL_1 = "http://www.domain-1.com/videos/atom.xml"
SAMPLE_ATOM_SUBSCRIPTION_URL_2 = "http://www.domain-2.com/videos/atom.xml"

# -----------------------------------------------------------------------------

INVALID_CONTENT_1 = u"""
This is not XML...
"""

# -----------------------------------------------------------------------------

INVALID_CONTENT_2 = u"""\
<?xml version="1.0" encoding="UTF-8" ?>
<this-is-bogus-xml-syntax>
    yes indeed
</this-is-bogus-xml-syntax>
"""

# -----------------------------------------------------------------------------

ATOM_LINK_CONSTRUCT_IN_RSS = u"""\
<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
    <channel>
        <title>Dummy RSS Feed</title>
        <link>http://www.getdemocracy.com</link>
        <description>A dummy RSS feed to test USM subscription</description>
        <atom:link 
            xmlns:atom="http://www.w3.org/2005/Atom"
            rel="self" 
            type="application/rss+xml" 
            title="Sample Dummy RSS Feed" 
            href="%s" />
    </channel>
</rss>
""" % SAMPLE_RSS_SUBSCRIPTION_URL_1

# -----------------------------------------------------------------------------

ATOM_LINK_CONSTRUCT_IN_ATOM = u"""\
<?xml version="1.0" encoding="UTF-8" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Dummy Atom Feed</title>
    <updated>2006-05-28T11:00:00Z</updated>
    <author><name>Luc Heinrich</name></author>
    <id>urn:uuid:D7732206-B0BF-4FAF-B2CE-FC25C6C5548F</id>
    <link 
        xmlns:atom="http://www.w3.org/2005/Atom"
        rel="self" 
        type="application/rss+xml" 
        title="Sample Dummy Atom Feed" 
        href="%s" />
</feed>
""" % SAMPLE_ATOM_SUBSCRIPTION_URL_1

# -----------------------------------------------------------------------------

REFLEXIVE_AUTO_DISCOVERY_IN_RSS = u"""\
<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
    <channel>
        <title>Dummy RSS Feed</title>
        <description>
            A dummy RSS feed to test USM Reflexive Auto Discovery
        </description>
        <link>reflexive-auto-discovery-page-rss.html</link>
    </channel>
</rss>
"""

REFLEXIVE_AUTO_DISCOVERY_PAGE_RSS_FILENAME = "reflexive-auto-discovery-page-rss.html"
REFLEXIVE_AUTO_DISCOVERY_PAGE_RSS = u"""\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" 
                          "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
        <head>
                <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
                <title>Reflexive Auto Discovery Page</title>
            <link rel="alternate" type="application/rss+xml" title="RSS" href="%s" />
        </head>
        <body>
            This place intentionally (almost) blank... :)
        </body>
</html>
""" % SAMPLE_RSS_SUBSCRIPTION_URL_1

# -----------------------------------------------------------------------------

REFLEXIVE_AUTO_DISCOVERY_IN_ATOM = u"""\
<?xml version="1.0" encoding="UTF-8" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Dummy Atom Feed</title>
    <updated>2006-05-28T11:00:00Z</updated>
    <author><name>Luc Heinrich</name></author>
    <id>urn:uuid:D7732206-B0BF-4FAF-B2CE-FC25C6C5548F</id>
    <link 
        xmlns:atom="http://www.w3.org/2005/Atom"
        rel="alternate" 
        type="application/atom+xml" 
        title="Sample Dummy AutoDiscovery Feed" 
        href="reflexive-auto-discovery-page-atom.html" />
</feed>
"""
REFLEXIVE_AUTO_DISCOVERY_PAGE_ATOM_FILENAME = "reflexive-auto-discovery-page-atom.html"
REFLEXIVE_AUTO_DISCOVERY_PAGE_ATOM = u"""\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" 
                          "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
    <head>
        <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
        <title>Reflexive Auto Discovery Page</title>
        <link rel="alternate" type="application/atom+xml" title="RSS" href="%s" />
    </head>
    <body>
        This place intentionally (almost) blank... :)
    </body>
</html>
""" % SAMPLE_ATOM_SUBSCRIPTION_URL_1

# -----------------------------------------------------------------------------

OPML_FLAT = u"""\
<?xml version="1.0" encoding="utf-8"?>
<opml version="1.0">
    <head>
        <title>Sample OPML Flat Subscription List</title>
    </head>
    <body>
        <outline text="Sample Dummy RSS Feed 1" type="rss" xmlUrl="%s" />
        <outline text="Sample Dummy Atom Feed 1" type="rss" xmlUrl="%s" />
        <outline text="Sample Dummy RSS Feed 2" type="rss" xmlUrl="%s" />
        <outline text="Sample Dummy Atom Feed 2" type="rss" xmlUrl="%s" />
    </body>
</opml>
""" % (SAMPLE_RSS_SUBSCRIPTION_URL_1, SAMPLE_ATOM_SUBSCRIPTION_URL_1, SAMPLE_RSS_SUBSCRIPTION_URL_2, SAMPLE_ATOM_SUBSCRIPTION_URL_2)

OPML_NESTED = u"""\
<?xml version="1.0" encoding="utf-8"?>
<opml version="1.0">
    <head>
        <title>Sample OPML Flat Subscription List</title>
    </head>
    <body>
        <outline text="folder 1">
            <outline text="Sample Dummy RSS Feed 1" type="rss" xmlUrl="%s" />
            <outline text="folder1-1">
                <outline text="Sample Dummy Atom Feed 1" type="rss" xmlUrl="%s" />
            </outline>
        </outline>
        <outline text="folder 2">
            <outline text="folder2-1">
                <outline text="Sample Dummy RSS Feed 2" type="rss" xmlUrl="%s" />
            </outline>
            <outline text="Sample Dummy Atom Feed 2" type="rss" xmlUrl="%s" />
        </outline>
    </body>
</opml>
""" % (SAMPLE_RSS_SUBSCRIPTION_URL_1, SAMPLE_ATOM_SUBSCRIPTION_URL_1, SAMPLE_RSS_SUBSCRIPTION_URL_2, SAMPLE_ATOM_SUBSCRIPTION_URL_2)

# =============================================================================
# Test case
# =============================================================================

class TestSubscription (MiroTestCase):
        
    subscription.reflexiveAutoDiscoveryOpener = open

    def testInvalidSubscriptions(self):
        urls = subscription.parseFile("this-file-does-not-exist.xml")
        self.assert_(urls is None)
        urls = subscription.parseContent(INVALID_CONTENT_1)
        self.assert_(urls is None)
        urls = subscription.parseContent(INVALID_CONTENT_2)
        self.assert_(urls is None)
    
    def testAtomLinkConstructInRSS(self):
        urls = subscription.parseContent(ATOM_LINK_CONSTRUCT_IN_RSS)
        self.assert_(len(urls) == 1)
        self.assert_(urls[0] == SAMPLE_RSS_SUBSCRIPTION_URL_1)

    def testAtomLinkConstructInAtom(self):
        urls = subscription.parseContent(ATOM_LINK_CONSTRUCT_IN_ATOM)
        self.assert_(len(urls) == 1)
        self.assert_(urls[0] == SAMPLE_ATOM_SUBSCRIPTION_URL_1)
        
    def testReflexiveAutoDiscoveryInRSS(self):
        pageFile = file(REFLEXIVE_AUTO_DISCOVERY_PAGE_RSS_FILENAME, "w")
        pageFile.write(REFLEXIVE_AUTO_DISCOVERY_PAGE_RSS)
        pageFile.close()
        urls = subscription.parseContent(REFLEXIVE_AUTO_DISCOVERY_IN_RSS)
        self.assert_(len(urls) == 1)
        self.assert_(urls[0] == SAMPLE_RSS_SUBSCRIPTION_URL_1)
        os.remove(REFLEXIVE_AUTO_DISCOVERY_PAGE_RSS_FILENAME)

    def testReflexiveAutoDiscoveryInAtom(self):
        pageFile = file(REFLEXIVE_AUTO_DISCOVERY_PAGE_ATOM_FILENAME, "w")
        pageFile.write(REFLEXIVE_AUTO_DISCOVERY_PAGE_ATOM)
        pageFile.close()
        urls = subscription.parseContent(REFLEXIVE_AUTO_DISCOVERY_IN_ATOM)
        self.assert_(len(urls) == 1)
        self.assert_(urls[0] == SAMPLE_ATOM_SUBSCRIPTION_URL_1)
        os.remove(REFLEXIVE_AUTO_DISCOVERY_PAGE_ATOM_FILENAME)
    
    def testFlatOPMLSubscriptions(self):
        urls = subscription.parseContent(OPML_FLAT)
        self.assert_(len(urls) == 4)
        self.assert_(urls[0] == SAMPLE_RSS_SUBSCRIPTION_URL_1)
        self.assert_(urls[1] == SAMPLE_ATOM_SUBSCRIPTION_URL_1)
        self.assert_(urls[2] == SAMPLE_RSS_SUBSCRIPTION_URL_2)
        self.assert_(urls[3] == SAMPLE_ATOM_SUBSCRIPTION_URL_2)

    def testNestedOPMLSubscriptions(self):
        urls = subscription.parseContent(OPML_NESTED)
        self.assert_(len(urls) == 4)
        self.assert_(urls[0] == SAMPLE_RSS_SUBSCRIPTION_URL_1)
        self.assert_(urls[1] == SAMPLE_ATOM_SUBSCRIPTION_URL_1)
        self.assert_(urls[2] == SAMPLE_RSS_SUBSCRIPTION_URL_2)
        self.assert_(urls[3] == SAMPLE_ATOM_SUBSCRIPTION_URL_2)

class TestFindSubscribeLinks (MiroTestCase):
    def testDifferstHost(self):
        url = 'http://youtoob.com'
        self.assertEquals(subscription.findSubscribeLinks(url), 
                ('none', []))

    def testNoLinks(self):
        url = 'http://subscribe.getdemocracy.com/'
        self.assertEquals(subscription.findSubscribeLinks(url), 
                ('feed', []))

    def testLinkInPath(self):
        url = 'http://subscribe.getdemocracy.com/http%3A//www.myblog.com/rss'
        self.assertEquals(subscription.findSubscribeLinks(url), 
                ('feed', [ ('http://www.myblog.com/rss', {}) ]))

    def testLinkInQuery(self):
        url = ('http://subscribe.getdemocracy.com/' + \
               '?url1=http%3A//www.myblog.com/rss')
        self.assertEquals(subscription.findSubscribeLinks(url), 
                ('feed', [ ('http://www.myblog.com/rss', {}) ]))

    def testMultipleLinksInQuery(self):
        url = ('http://subscribe.getdemocracy.com/' + \
               '?url1=http%3A//www.myblog.com/rss' + \
               '&url2=http%3A//www.yourblog.com/atom' + \
               '&url3=http%3A//www.herblog.com/scoobydoo')

        contenttype, links = subscription.findSubscribeLinks(url)
        self.assertEquals(contenttype, 'feed')
        # have to sort them because they could be in any order
        links.sort()
        self.assertEquals(links, [ ('http://www.herblog.com/scoobydoo', {}),
                                   ('http://www.myblog.com/rss', {}),
                                   ('http://www.yourblog.com/atom', {}) ])

    def testQueryGarbage(self):
        url = ('http://subscribe.getdemocracy.com/' + \
               '?url1=http%3A//www.myblog.com/rss' + \
               '&url2=http%3A//www.yourblog.com/atom' + \
               '&url3=http%3A//www.herblog.com/scoobydoo' + \
               '&foo=bar' + \
               '&extra=garbage')

        contenttype, links = subscription.findSubscribeLinks(url)
        self.assertEquals(contenttype, 'feed')
        # have to sort them because they could be in any order
        links.sort()
        self.assertEquals(links, [ ('http://www.herblog.com/scoobydoo', {}),
                                   ('http://www.myblog.com/rss', {}),
                                   ('http://www.yourblog.com/atom', {}) ])

    def testChannelGuideLinks(self):
        url = ('http://subscribe.getdemocracy.com/channelguide.php' + \
               '?url1=http%3A//www.mychannelguide.com/')
        self.assertEquals(subscription.findSubscribeLinks(url), 
                ('guide', [ ('http://www.mychannelguide.com/', {}) ]))

    def testDownloadLinks(self):
        url = ('http://subscribe.getdemocracy.com/download.php' + \
               '?url1=http%3A//www.myblog.com/videos/cats.ogm')
        self.assertEquals(subscription.findSubscribeLinks(url), 
                ('download', [ ('http://www.myblog.com/videos/cats.ogm', {}) ]))
