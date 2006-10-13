# Since we have a sort named "item" we name the item module "itemmod"
import item as itemmod

# These functions should be STL style sort functions that returns true
# for x<y and false otherwise.

# For now, these functions expect x and y to be pairs. The first item
# in the pair is the unmapped version of the object, the second is the
# mapped version. In practice, you'll only want to use the second item.

def item(x,y):
    x = x[1]
    y = y[1]
    if x.parent_id == y.parent_id:
        if y.releaseDateObj != x.releaseDateObj:
            return x.releaseDateObj < y.releaseDateObj
        else:
            # If we're going to sort file items and non-file items
            # differently, then one must precede the other or it won't be
            # a valid sort.
            if x.__class__ is itemmod.FileItem:
                if y.__class__ is itemmod.FileItem:
                    return x.getTitle() < y.getTitle()
                else:
                    return False
            else:
                if y.__class__ is not itemmod.FileItem:
                    if y.linkNumber == x.linkNumber:
                        return y.id < x.id
                    else:
                        return y.linkNumber < x.linkNumber
                else:
                    return True
    else:
        if x.parent_id == y.id:
            # y is x's parent
            return False
        elif y.parent_id == x.id:
            # x is y's parent
            return True
        else:
            # x and y are not children of the same item, so sort by the parent (which might be the self)
            xParent = x.getParent()
            yParent = y.getParent()
            return item((xParent, xParent), (yParent, yParent))

unwatchedMemory = {}
unwatchedMemoryFor = None
def switchUnwatchedFirstChannel(newChannel):
    """The itemsUnwatchedFirst() sort normally remembers which items were
    unwatched.  This way if an item becomes watched while the user is viewing
    a channel, it doesn't jump around in the view.  This method takes care of
    resetting the memory when the user switches channels.  Call it before
    using the itemsUnwatchedFirst() sort.  newChannel should be the
    channel/channel folder object that's being displayed.  Or None if the new
    videos tab is being displayed.
    """
    global unwatchedMemoryFor, unwatchedMemory
    if newChannel != unwatchedMemoryFor:
        unwatchedMemory.clear()
        unwatchedMemoryFor = newChannel

def _getUnwatchedWithMemory(item):
    try:
        return unwatchedMemory[item.getID()]
    except KeyError:
        rv = item.getState() == 'newly-downloaded'
        unwatchedMemory[item.getID()] = rv
        return rv

def itemsUnwatchedFirst(x,y):
    uwx = _getUnwatchedWithMemory(x[1])
    uwy = _getUnwatchedWithMemory(y[1])
    if uwx != uwy:
        return uwx
    else:
        return item(x,y)

# The sort function used to order tabs in the tab list: just use the
# sort keys provided when mapToTab created the Tabs. These can be
# lists, which are tested left-to-right in the way you'd
# expect. Generally, the way this is used is that static tabs are
# assigned a numeric priority, and get a single-element list with that
# number as their sort key; feeds get a list with '100' in the first
# position, and a value that determines the order of the feeds in the
# second position. This way all of the feeds are together, and the
# static tabs can be positioned around them.
def tabs(x, y):
    return x[1].sortKey < y[1].sortKey

def searchEngines(x, y):
    try:
        return x[1].sortOrder < y[1].sortOrder
    except:
        pass
    if x[1].title == y[1].title:
        return x[1].name < y[1].name
    else:
        return x[1].title < y[1].title
