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

from miro import indexes
from miro import playlist
from miro import sorts
from miro import util
from miro import views
from miro.database import DDBObject
from miro.databasehelper import makeSimpleGetSet

class FolderBase(DDBObject):
    """Base class for ChannelFolder and Playlist folder classes."""

    def setup_new(self, title):
        self.title = title
        self.expanded = True

    get_title, setTitle = makeSimpleGetSet('title')

    def getExpanded(self):
        self.confirmDBThread()
        return self.expanded

    def setExpanded(self, newExpanded):
        self.confirmDBThread()
        self.expanded = newExpanded
        self.signal_change()
        for child in self.getChildrenView():
            child.signal_change(needsSave=False)

    def remove(self, moveItemsTo=None):
        children = [child for child in self.getChildrenView()]
        for child in children:
            child.remove(moveItemsTo)
        DDBObject.remove(self)

    # getFolder and setFolder are here so that channels/playlists and folders
    # have a consistent API.  They don't do much since we don't allow nested
    # folders.
    def getFolder(self):
        return None

    def setFolder(self, newFolder):
        if newFolder is not None:
            raise TypeError("Nested folders not allowed")

    def getChildrenView(self):
        """Return the children of this folder."""
        raise NotImplementedError()

class ChannelFolder(FolderBase):
    def setup_new(self, title, section=u'video'):
        self.section = section
        FolderBase.setup_new(self, title)
        self.setup_common()

    def setup_restored(self):
        self.setup_common()

    def setup_common(self):
        self.itemSort = sorts.ItemSort()
        self.itemSortDownloading = sorts.ItemSort()
        self.itemSortWatchable = sorts.ItemSortUnwatchedFirst()

    def getChildrenView(self):
        return views.feeds.filterWithIndex(indexes.byFolder, self)

    def hasDownloadedItems(self):
        for feed in self.getChildrenView():
            if feed.hasDownloadedItems():
                return True
        return False

    def hasDownloadingItems(self):
        for feed in self.getChildrenView():
            if feed.hasDownloadingItems():
                return True
        return False

    # Returns string with number of unwatched videos in feed
    def numUnwatched(self):
        unwatched = 0
        for child in self.getChildrenView():
            unwatched += child.numUnwatched()
        return unwatched

    # Returns string with number of available videos in feed
    def numAvailable(self):
        available = 0
        for child in self.getChildrenView():
            available += child.numAvailable()
        return available

    def markAsViewed(self):
        for child in self.getChildrenView():
            child.markAsViewed()
    
class PlaylistFolder(FolderBase, playlist.PlaylistMixin):
    def setup_new(self, title):
        self.item_ids = []
        FolderBase.setup_new(self, title)
        self.setup_common()

    def setup_restored(self):
        self.setup_common()

    def setup_common(self):
        self.setupTrackedItemView()

    def checkItemIDRemoved(self, id):
        index = indexes.playlistsByItemAndFolderID
        value = (id, self.getID())
        view = views.playlists.filterWithIndex(index, value)
        if view.len() == 0 and id in self.trackedItems:
            self.removeID(id)

    def checkItemIDAdded(self, id):
        if id not in self.trackedItems:
            self.trackedItems.appendID(id)

    def getChildrenView(self):
        return views.playlists.filterWithIndex(indexes.byFolder, self)
