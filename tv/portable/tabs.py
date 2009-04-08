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

from miro import database
from miro import views
from miro import eventloop
from miro import playlist
from miro.util import checkU
from miro.databasehelper import TrackedIDList

import logging

class TabOrder(database.DDBObject):
    """TabOrder objects keep track of the order of the tabs.  Miro
    creates 2 of these, one to track channels/channel folders and another to
    track playlists/playlist folders.

    TabOrder objects emit the 'tab-added' signal when a new tab is added.
    """

    def setup_new(self, type):
        """Construct a TabOrder.  type should be either "channel", or
        "playlist".
        """
        checkU(type)
        self.type = type
        self.tab_ids = []
        self.setup_common()
        decorated = [(t.get_title().lower(), t) for t in self.tabView]
        decorated.sort()
        for sortkey, tab in decorated:
            self.trackedTabs.appendID(tab.getID())

    def setup_restored(self):
        self.setup_common()
        eventloop.addIdle(self.checkForNonExistentIds, 
                "checking for non-existent TabOrder ids")

    def setup_common(self):
        self.create_signal('tab-added')
        if self.type == u'site':
            self.tabView = views.sites
        elif self.type == u'channel':
            self.tabView = views.videoFeedTabs
        elif self.type == u'audio-channel':
            self.tabView = views.audioFeedTabs
        elif self.type == u'playlist':
            self.tabView = views.playlistTabs
        else:
            raise ValueError("Bad type for TabOrder")
        self.trackedTabs = TrackedIDList(self.tabView, self.tab_ids)
        self.tabView.addAddCallback(self.onAddTab)
        self.tabView.addRemoveCallback(self.onRemoveTab)

    @classmethod
    def view_for_type(cls, type):
        return cls.make_view('type=?', (type,))

    @classmethod
    def site_order(cls):
        return cls.view_for_type(u'site').get_singleton()

    @classmethod
    def video_feed_order(cls):
        return cls.view_for_type(u'channel').get_singleton()

    @classmethod
    def audio_feed_order(cls):
        return cls.view_for_type(u'audio-channel').get_singleton()

    @classmethod
    def playlist_order(cls):
        return cls.view_for_type(u'playlist').get_singleton()

    def checkForNonExistentIds(self):
        changed = False
        for id in self.tab_ids[:]:
            if not self.tabView.idExists(id):
                self.trackedTabs.removeID(id)
                logging.warn("Throwing away non-existent TabOrder id: %s", id)
                changed = True
        if changed:
            self.signal_change()

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
            obj.signal_change()
            self.signal_change()
            self.emit('tab-added', obj)

    def onRemoveTab(self, obj, id):
        if id in self.trackedTabs:
            self.trackedTabs.removeID(id)
        self.signal_change()

    def moveTabs(self, anchorItem, toMove, sendSignalChange=True):
        if anchorItem is not None:
            self.trackedTabs.moveIDList(toMove, anchorItem.getID())
        else:
            self.trackedTabs.moveIDList(toMove, None)
        if sendSignalChange:
            self.signal_change()

    def reorder(self, newOrder):
        self.trackedTabs.reorder(newOrder)

    def move_tab_after(self, anchor_id, id_list):
        view = self.getView()
        view.moveCursorToID(anchor_id)
        next = view.getNext()
        while next is not None and next.getID() in id_list:
            next = view.getNext()
        self.moveTabs(next, id_list)
