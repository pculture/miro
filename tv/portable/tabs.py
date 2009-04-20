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
from miro import guide
from miro import feed
from miro import folder
from miro import eventloop
from miro import playlist
from miro.util import checkU
from miro.databasehelper import TrackedIDList

import logging

class TabOrder(database.DDBObject):
    """TabOrder objects keep track of the order of the tabs.  Miro
    creates 2 of these, one to track channels/channel folders and another to
    track playlists/playlist folders.
    """

    def setup_new(self, type):
        """Construct a TabOrder.  type should be either "channel", or
        "playlist".
        """
        checkU(type)
        self.type = type
        self.tab_ids = []
        self.setup_views()
        decorated = [(t.get_title().lower(), t) for t in self.id_to_tab.values()]
        decorated.sort()
        for sortkey, tab in decorated:
            self.tab_ids.append(tab.id)

    def restore_tab_list(self):
        self.setup_views()
        self.check_for_non_existent_ids()

    def setup_views(self):
        if self.type == u'site':
            tab_views = (guide.ChannelGuide.site_view(),)
        elif self.type == u'channel':
            tab_views = (feed.Feed.visible_video_view(),
                    folder.ChannelFolder.video_view())
        elif self.type == u'audio-channel':
            tab_views = (feed.Feed.visible_audio_view(),
                    folder.ChannelFolder.audio_view())
        elif self.type == u'playlist':
            tab_views = (playlist.SavedPlaylist.make_view(),
                    folder.PlaylistFolder.make_view())
        else:
            raise ValueError("Bad type for TabOrder")

        self.id_to_tab = {}
        for view in tab_views:
            for obj in view:
                self.id_to_tab[obj.id] = obj
        self.trackers = [view.make_tracker() for view in tab_views]
        for tracker in self.trackers:
            tracker.connect("added", self.on_add_tab)
            tracker.connect("removed", self.on_remove_tab)

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

    def check_for_non_existent_ids(self):
        changed = False
        for i in reversed(xrange(len(self.tab_ids))):
            id = self.tab_ids[i]
            if not id in self.id_to_tab:
                del self.tab_ids[i]
                logging.warn("Throwing away non-existent TabOrder id: %s", id)
                changed = True
        if changed:
            self.signal_change()

    def get_all_tabs(self):
        """Get all the tabs in this tab ordering (in order), regardless if
        they are visible in the tab list or not.
        """
        return [self.id_to_tab[id] for id in self.tab_ids]

    def on_add_tab(self, tracker, obj):
        if obj.id not in self.id_to_tab:
            self.id_to_tab[obj.id] = obj
            self.tab_ids.append(obj.id)
            self.signal_change()

    def on_remove_tab(self, tracker, obj):
        if obj.id in self.id_to_tab:
            del self.id_to_tab[obj.id]
            self.tab_ids.remove(obj.id)
            self.signal_change()

    def reorder(self, newOrder):
        self.tab_ids = newOrder
        self.signal_change()
