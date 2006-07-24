"""Sanity checks for the databases."""

import item
import feed
import util
import guide

class DatabaseInsaneError(Exception):
    pass

class SanityTest(object):
    """Base class for the sanity test objects."""

    def checkObject(self, object):
        """checkObject will be called for each object in the object list.
        If there is an error return a string describing it.  If not return
        None (or just let the function hit the bottom).
        """
        raise NotImplementedError()

    def finished(self):
        """Called when we reach the end of the object list, SanityTest
        subclasses may implement additional checking here."""
        return

    def fixIfPossible(self, objectList):
        """Subclasses may implement this method if it's possible to fix broken
        databases.  The default implementation just raises a
        DatabaseInsaneError.
        """
        raise DatabaseInsaneError()

class PhontomFeedTest(SanityTest):
    """Check that no items reference a Feed that isn't around anymore."""
    def __init__(self):
        self.feedsInItems = set()
        self.topLevelFeeds = set()

    def checkObject(self, obj):
        if isinstance(obj, item.Item):
            self.feedsInItems.add(obj.feed_id)
        elif isinstance(obj, feed.Feed):
            self.topLevelFeeds.add(obj.id)

    def finished(self):
        if not self.feedsInItems.issubset(self.topLevelFeeds):
            phantoms = self.feedsInItems.difference(self.topLevelFeeds)
            phantomsString = ', '.join([str(p) for p in phantoms])
            return "Phantom feed(s) referenced in items: %s" % phantomsString

    def fixIfPossible(self, objectList):
        for i in reversed(xrange(len(objectList))):
            if (isinstance(objectList[i], item.Item) and 
                    objectList[i].feed_id not in self.topLevelFeeds):
                del objectList[i]

class SingletonTest(SanityTest):
    """Check that singleton DB objects are really singletons.

    This is a baseclass for the channle guide test, manual feed test, etc.
    """

    def __init__(self):
        self.count = 0

    def checkObject(self, obj):
        if self.objectIsSingleton(obj):
            self.count += 1
            if self.count > 1:
                return "Extra %s in database" % self.singletonName
    
    def finished(self):
        if self.count == 0:
            # For all our singletons (currently at least), we don't need to
            # create them here.  It'll happen when democracy is restarted.
            # return "No %s in database" % self.singletonName
            pass

    def fixIfPossible(self, objectList):
        if self.count == 0:
            # For all our singletons (currently at least), we don't need to
            # create them here.  It'll happen when democracy is restarted.
            return
        else:
            seenObject = False
            for i in reversed(xrange(len(objectList))):
                if self.objectIsSingleton(objectList[i]):
                    if seenObject:
                        del objectList[i]
                    else:
                        seenObject = True

class ChannelGuideSingletonTest(SingletonTest):
    singletonName = "Channel Guide"
    def objectIsSingleton(self, obj):
        return isinstance(obj, guide.ChannelGuide)

class ManualFeedSingletonTest(SingletonTest):
    singletonName = "Manual Feed"
    def objectIsSingleton(self, obj):
        return (isinstance(obj, feed.Feed) and 
                isinstance(obj.actualFeed, feed.ManualFeedImpl))

def checkSanity(objectList, fixIfPossible=True, quiet=False, reallyQuiet=False):
    """Do all sanity checks on a list of objects.

    If fixIfPossible is True, the sanity checks will try to fix errors.  If
    this happens objectList will be modified.

    If fixIfPossible is False, or if it's not possible to fix the errors
    checkSanity will raise a DatabaseInsaneError.

    If quiet is True, we print to the log instead of poping up an error dialog
    on fixable problems.  We set this when we are converting old databases,
    since sanity errors are somewhat expected.

    If reallyQuiet is True, won't even print out a warning on fixable
    problems.

    Returns True if the database passed all sanity tests, false otherwise.
    """

    tests = set([
        PhontomFeedTest(),
        ChannelGuideSingletonTest(),
        ManualFeedSingletonTest(),
    ])

    errors = []
    failedTests = set()
    for obj in objectList:
        for test in tests:
            rv = test.checkObject(obj)
            if rv is not None:
                errors.append(rv)
                failedTests.add(test)
        tests = tests.difference(failedTests)
    for test in tests:
        rv = test.finished()
        if rv is not None:
            errors.append(rv)
            failedTests.add(test)

    if errors:
        errorMsg = "The database failed the following sanity tests:\n"
        errorMsg += "\n".join(errors)
        if fixIfPossible:
            if not quiet:
                util.failed(when="While checking database", details=errorMsg)
            elif not reallyQuiet:
                print "WARNING: Database sanity error"
                print errorMsg
            for test in failedTests:
                test.fixIfPossible(objectList)
                # fixIfPossible will throw a DatabaseInsaneError if it fails,
                # which we let get raised to our caller
        else:
            raise DatabaseInsaneError(errorMsg)
    return (errors == [])
