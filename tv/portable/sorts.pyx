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
            # The sort here is > because we want newer items to show
            # up earlier in the list.
            return x.releaseDateObj > y.releaseDateObj
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
            # x and y are not children of the same item, so sort by the parent (which might be the self for one of them.)
            xParent = x.getParent()
            yParent = y.getParent()
            return item((xParent, xParent), (yParent, yParent))

def downloadersByEndTime (x, y):
    xtime = x[1].status.get("endTime", 0)
    ytime = y[1].status.get("endTime", 0)
    return xtime < ytime

class ItemSort:
    """Object that sorts item lists.  There is one of these for every section
    that contains a list of items (i.e. there are several for most templates).

    Member attributes:
        sortBy -- Possible values: 'date', 'size', 'name'
        sortDirection -- Possible values: 'ascending', 'descending'
    """

    existingSorts = {}

    def __init__(self):
        self.sortBy = 'date'
        self.sortDirection = 'descending'

    def setSortBy(self, by):
        if self.sortBy == by:
            if self.sortDirection == 'ascending':
                self.sortDirection = 'descending'
            else:
                self.sortDirection = 'ascending'
        else:
            self.sortBy = by
            self.sortDirection = 'descending'

    def sort(self, x, y):
        """Pass this to view.sort()"""

        if self.sortBy == 'date':
            result = itemByDate(x, y)
        elif self.sortBy == 'size':
            result = itemBySize(x, y)
        elif self.sortBy == 'name':
            result = itemByName(x, y)
        elif self.sortBy == 'duration':
            result = itemByDuration(x, y)
        if self.sortDirection == 'descending':
            result = not result
        return result

    def getSortButtonState(self, by):
        if self.sortBy == by:
            if self.sortDirection == 'ascending':
                return 'ascending'
            else:
                return 'descending'
        return ''

def itemByDate(x, y):
    return x[1].releaseDateObj < y[1].releaseDateObj

def itemByName(x, y):
    return x[1].getTitle() < y[1].getTitle()

def itemBySize(x, y):
    return x[1].getSize() < y[1].getSize()

def itemByDuration(x, y):
    return x[1].duration < y[1].duration

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

class ItemSortUnwatchedFirst(ItemSort):
    def sort(self, x, y):
        uwx = _getUnwatchedWithMemory(x[1])
        uwy = _getUnwatchedWithMemory(y[1])
        if uwx != uwy:
            return uwx
        else:
            return ItemSort.sort(self, x, y)

# Create sort objects for each item list in the static tabs.  We need to
# remember the sort criteria and direction for each one separately.

itemSortNew = ItemSortUnwatchedFirst()
itemSortLibrary = ItemSort()
itemSortSearch = ItemSort()
itemSortDownloads = ItemSort()
itemSortUploads = ItemSort()
itemSortPendingDownloads = ItemSort()
itemSortPausedDownloads = ItemSort()

def guideTabs(x, y):
    xguide = x[1].obj
    yguide = y[1].obj
    if xguide.getDefault() and not yguide.getDefault():
        return True
    return xguide.getURL() < yguide.getURL()

def staticTabs(x, y):
    return x[1].obj.order < y[1].obj.order

def searchEngines(x, y):
    try:
        return x[1].sortOrder < y[1].sortOrder
    except:
        pass
    if x[1].title == y[1].title:
        return x[1].name < y[1].name
    else:
        return x[1].title < y[1].title
