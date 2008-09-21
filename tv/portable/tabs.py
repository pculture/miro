# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

from miro import database
from miro import views
from miro import eventloop
from miro import feed
from miro import folder
from miro import guide
from miro import playlist
from miro.util import checkU
from miro.databasehelper import TrackedIDList

import logging

class Tab:
    idCounter = 0

    def __init__(self, tabTemplateBase, contentsTemplate, templateState, obj):
        self.tabTemplateBase = tabTemplateBase
        self.contentsTemplate = contentsTemplate
        self.templateState = templateState
        self.display = None
        self.id = "tab%d" % Tab.idCounter
        Tab.idCounter += 1
        self.selected = False
        self.active = False
        self.obj = obj

        if obj.__class__ == guide.ChannelGuide:
            if obj.getDefault():
                self.type = 'guide'
            else:
                self.type = 'site'
        elif obj.__class__ in (feed.Feed, folder.ChannelFolder): 
            self.type = 'feed'
        elif obj.__class__ in (playlist.SavedPlaylist, folder.PlaylistFolder):
            self.type = 'playlist'
        else:
            raise TypeError("Bad tab object type: %s" % type(obj))

    def setSelected(self, newValue):
        self.obj.confirmDBThread()
        self.selected = newValue
        self.obj.signalChange(needsSave=False)

    def getSelected(self):
        self.obj.confirmDBThread()
        return self.selected

    def getState(self):
        """Returns "normal" "selected" or "selected-inactive"
        """
        if not self.selected:
            return 'normal'
        elif not self.active:
            return 'selected-inactive'
        else:
            return 'selected'

    def redraw(self):
        """Force a redraw by sending a change notification on the underlying
        DB object.
        """
        self.obj.signalChange()

    def isFeed(self):
        """True if this Tab represents a Feed."""
        return isinstance(self.obj, feed.Feed)

    def isChannelFolder(self):
        """True if this Tab represents a Channel Folder."""
        return isinstance(self.obj, folder.ChannelFolder)

    def isGuide(self):
        """True if this Tab represents a Channel Guide."""
        return isinstance(self.obj, guide.ChannelGuide) and self.obj.getDefault()

    def isSite(self):
        """True is this Tab represents a Web Site"""
        return isinstance(self.obj, guide.ChannelGuide) and not self.obj.getDefault()

    def isPlaylist(self):
        """True if this Tab represents a Playlist."""
        return isinstance(self.obj, playlist.SavedPlaylist)

    def isPlaylistFolder(self):
        """True if this Tab represents a Playlist Folder."""
        return isinstance(self.obj, folder.PlaylistFolder)

    def feedURL(self):
        """If this Tab represents a Feed or a Guide, the URL. Otherwise None."""
        if self.isFeed() or self.isGuide() or self.isSite():
            return self.obj.getURL()
        else:
            return None

    def objID(self):
        """If this Tab represents a Feed, the feed's ID. Otherwise None."""
        if isinstance (self.obj, database.DDBObject):
            return self.obj.getID()
        else:
            return None

    def getID(self):
        """Gets an id that can be used to lookup this tab from views.allTabs.

        NOTE: Tabs are mapped database objects, they don't have actual
        DDBObject ids.
        """
        return self.obj.getID()

    def signalChange(self, needsSave=True):
        """Call signalChange on the object that is mapped to this tab (the
        Feed, Playlist, etc.)
        """
        self.obj.signalChange(needsSave=needsSave)

    def idExists(self):
        """Returns True if the object that maps to this tab still exists in
        the DB.
        """

        return self.obj.idExists()

class TabOrder(database.DDBObject):
    """TabOrder objects keep track of the order of the tabs.  Miro
    creates 2 of these, one to track channels/channel folders and another to
    track playlists/playlist folders.

    TabOrder objects emit the 'tab-added' signal when a new tab is added.
    """
    def __init__(self, type):
        """Construct a TabOrder.  type should be either "channel", or
        "playlist".
        """
        checkU(type)
        self.type = type
        self.tab_ids = []
        database.DDBObject.__init__(self)
        self._init_restore()
        decorated = [(t.obj.get_title().lower(), t) for t in self.tabView]
        decorated.sort()
        for sortkey, tab in decorated:
            self.trackedTabs.appendID(tab.getID())

    def onRestore(self):
        database.DDBObject.onRestore(self)
        self._init_restore()
        eventloop.addIdle(self.checkForNonExistentIds, 
                "checking for non-existent TabOrder ids")

    def _init_restore(self):
        self.create_signal('tab-added')
        if self.type == u'site':
            self.tabView = views.siteTabs
        elif self.type == u'channel':
            self.tabView = views.feedTabs
        elif self.type == u'playlist':
            self.tabView = views.playlistTabs
        else:
            raise ValueError("Bad type for TabOrder")
        self.trackedTabs = TrackedIDList(self.tabView, self.tab_ids)
        self.tabView.addAddCallback(self.onAddTab)
        self.tabView.addRemoveCallback(self.onRemoveTab)

    def checkForNonExistentIds(self):
        changed = False
        for id in self.tab_ids[:]:
            if not self.tabView.idExists(id):
                self.trackedTabs.removeID(id)
                logging.warn("Throwing away non-existent TabOrder id: %s", id)
                changed = True
        if changed:
            self.signalChange()

    def getView(self):
        """Get a database view for this tab ordering."""
        return self.trackedTabs.view

    def getAllTabs(self):
        """Get all the tabs in this tab ordering (in order), regardless if
        they are visible in the tab list or not.
        """
        return [self.tabView.getObjectByID(id) for id in self.tab_ids \
                if self.tabView.idExists(id) ]

    def onAddTab(self, obj, id):
        if id not in self.trackedTabs:
            self.trackedTabs.appendID(id, sendSignalChange=False)
            obj.signalChange(needsSave=False)
            self.signalChange()
            self.emit('tab-added', obj)

    def onRemoveTab(self, obj, id):
        if id in self.trackedTabs:
            self.trackedTabs.removeID(id)
        self.signalChange()

    def moveTabs(self, anchorItem, toMove, sendSignalChange=True):
        if anchorItem is not None:
            self.trackedTabs.moveIDList(toMove, anchorItem.getID())
        else:
            self.trackedTabs.moveIDList(toMove, None)
        if sendSignalChange:
            self.signalChange()

    def reorder(self, newOrder):
        self.trackedTabs.reorder(newOrder)
