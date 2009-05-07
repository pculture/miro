# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

# Since we have a sort named "item" we name the item module "itemmod"
import item as itemmod

# These functions should be STL style sort functions that returns true
# for x<y and false otherwise.

# For now, these functions expect x and y to be pairs. The first item
# in the pair is the unmapped version of the object, the second is the
# mapped version. In practice, you'll only want to use the second item.

# FIXME - do we need this module anymore?

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
                    return x.get_title() < y.get_title()
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
            xParent = x.get_parent()
            yParent = y.get_parent()
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

        if self.sortDirection == 'descending':
            x, y = y, x
        
        if self.sortBy == 'date':
            return x[1].get_release_date_obj() < y[1].get_release_date_obj()
        elif self.sortBy == 'size':
            return x[1].get_size() < y[1].get_size()
        elif self.sortBy == 'name':
            return x[1].get_title().lower() < y[1].get_title().lower()
        elif self.sortBy == 'duration':
            return x[1].get_duration_value() < y[1].get_duration_value()

        return False

    def getSortButtonState(self, by):
        if self.sortBy == by:
            if self.sortDirection == 'ascending':
                return 'ascending'
            else:
                return 'descending'
        return ''

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
        rv = item.get_state() == 'newly-downloaded'
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
itemSortSeedingTorrents = ItemSort()
itemSortUploads = ItemSort()
itemSortPendingDownloads = ItemSort()
itemSortPausedDownloads = ItemSort()

def guideTabs(x, y):
    xguide = x[1].obj
    yguide = y[1].obj
    if xguide.get_default() and not yguide.get_default():
        return True
    if not xguide.get_default() and yguide.get_default():
        return False
    return xguide.get_title() < yguide.get_title()

def staticTabs(x, y):
    return x[1].obj.order < y[1].obj.order
