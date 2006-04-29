import unittest
import subscription

class TestSubscription (unittest.TestCase):
    
    SAMPLE_RSS_SUBSCRIPTION_URL  = "http://www.telemusicvision.com/videos/rss.php?i=1"
    SAMPLE_ATOM_SUBSCRIPTION_URL = "http://www.telemusicvision.com/videos/atom.php?i=1"
    
    def testInvalidSubscription(self):
        urls = subscription.parseFile("this-file-does-not-exist.xml")
        self.assert_(urls is None)
        urls = subscription.parseFile("subscription-invalid-content-1.xml")
        self.assert_(urls is None)
        urls = subscription.parseFile("subscription-invalid-content-2.xml")
        self.assert_(urls is None)
    
    def testAtomLinkConstruct(self):
        urls = subscription.parseFile("subscription-atom-link-construct-in-rss.xml")
        self.assert_(len(urls) == 1)
        self.assert_(urls[0] == self.SAMPLE_RSS_SUBSCRIPTION_URL)
        urls = subscription.parseFile("subscription-atom-link-construct-in-atom.xml")
        self.assert_(len(urls) == 1)
        self.assert_(urls[0] == self.SAMPLE_ATOM_SUBSCRIPTION_URL)
        
    def testReflexiveAutoDiscovery(self):
        subscription.reflexiveAutoDiscoveryOpener = open
        urls = subscription.parseFile("subscription-reflexive-auto-discovery-in-rss.xml")
        self.assert_(len(urls) == 1)
        self.assert_(urls[0] == self.SAMPLE_RSS_SUBSCRIPTION_URL)
        urls = subscription.parseFile("subscription-reflexive-auto-discovery-in-atom.xml")
        self.assert_(len(urls) == 1)
        self.assert_(urls[0] == self.SAMPLE_ATOM_SUBSCRIPTION_URL)
    
    def testOPMLSubscription(self):
        pass


if __name__ == "__main__":
    unittest.main()