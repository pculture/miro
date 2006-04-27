"""Sanity checks for the databases."""

import item
import feed
import util
import guide

class DatabaseInsaneError(Exception):
    pass

def checkBrokenFeeds(objectList, fixIfPossible):
    """Check that no items reference a Feed that isn't around anymore."""

    feedsInItems = set()
    topLevelFeeds = set()

    for obj in objectList:
        if isinstance(obj, item.Item):
            feedsInItems.add(obj.feed)
        elif isinstance(obj, feed.Feed):
            topLevelFeeds.add(obj)

    if not feedsInItems.issubset(topLevelFeeds):
        phantoms = feedsInItems.difference(topLevelFeeds)
        msg = "Phantom feed(s) referenced in items: %s" % phantoms
        if fixIfPossible:
            util.failed("While checking database", details=msg)
            for f in phantoms:
                objectList.append(f)
        else:
            raise DatabaseInsaneError(msg)

def checkSingleChannelGuide(objectList, fixIfPossible):
    guideCount = 0
    for i in reversed(xrange(len(objectList))):
        if isinstance(objectList[i], guide.ChannelGuide):
            guideCount += 1
            if guideCount > 1:
                msg = "Extra chanel Guide"
                if fixIfPossible:
                    util.failed("While checking database", details=msg)
                    del objectList[i]
                else:
                    raise DatabaseInsaneError(msg)

def checkSanity(objectList, fixIfPossible=True):
    """Do all sanity checks on a list of objects.

    If fixIfPossible is True, the sanity checks will try to fix errors.  If
    this happens objectList will be modified.

    If fixIfPossible is False, or if it's not possible to fix the errors
    checkSanity will raise a DatabaseInsaneError.

    Returns a reference to objectList (mostly for the unit tests)
    """

    checkBrokenFeeds(objectList, fixIfPossible)
    checkSingleChannelGuide(objectList, fixIfPossible)
    return objectList
