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

"""``miro.tabs`` -- Holds the TabOrder DDBObject.
"""

from miro import database
from miro import guide
from miro import feed
from miro import folder
from miro import eventloop
from miro import playlist
from miro.util import checkU

import logging

class TabOrder(database.DDBObject):
    """TabOrder objects keep track of the order of the tabs.  Miro
    creates 2 of these, one to track channels/channel folders and another to
    track playlists/playlist folders.
    """

    def setup_new(self, type):
        """Construct a TabOrder.  type should be either ``channel`` or
        ``playlist``.
        """
        checkU(type)
        self.type = type
        self.tab_ids = []
        self._setup_views()
        decorated = [(t.get_title().lower(), t) for t in self.id_to_tab.values()]
        decorated.sort()
        for sortkey, tab in decorated:
            self.tab_ids.append(tab.id)

    def setup_restored(self):
        if not isinstance(self.tab_ids, list):
            logging.warning("tab_ids was not a list.  setting it to [].")
            self.tab_ids = []
            return
        for mem in self.tab_ids:
            if not isinstance(mem, int):
                self.tab_ids = []
                logging.warning("tab_ids wasn't a list of ints.  setting it to [].")
                return

    def restore_tab_list(self):
        """Restores the tablist.
        """
        self._setup_views()
        self._check_for_non_existent_ids()
        self._remove_out_of_order_children()
        self._add_untracked_ids()

    def _get_tab_views(self):
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
        return tab_views

    def _setup_views(self):
        """Sets up all the tab-related views.
        """
        tab_views = self._get_tab_views()

        self.id_to_tab = {}
        for view in tab_views:
            for obj in view:
                self.id_to_tab[obj.id] = obj
        self.trackers = [view.make_tracker() for view in tab_views]
        for tracker in self.trackers:
            tracker.connect("added", self._on_add_tab)
            tracker.connect("removed", self._on_remove_tab)

    @classmethod
    def view_for_type(cls, type):
        """View based on tab type.
        """
        return cls.make_view('type=?', (type,))

    @classmethod
    def site_order(cls):
        """View of sites based on order.
        """
        return cls.view_for_type(u'site').get_singleton()

    @classmethod
    def video_feed_order(cls):
        """View of feeds based on order.
        """
        return cls.view_for_type(u'channel').get_singleton()

    @classmethod
    def audio_feed_order(cls):
        """View of audio feeds based on order.
        """
        return cls.view_for_type(u'audio-channel').get_singleton()

    @classmethod
    def playlist_order(cls):
        """View of playlists based on order.
        """
        return cls.view_for_type(u'playlist').get_singleton()

    def _check_for_non_existent_ids(self):
        changed = False
        for i in reversed(xrange(len(self.tab_ids))):
            tab_id = self.tab_ids[i]
            if not tab_id in self.id_to_tab:
                del self.tab_ids[i]
                logging.warn("Throwing away non-existent TabOrder id: %s", tab_id)
                changed = True
        if changed:
            self.signal_change()

    def _add_untracked_ids(self):
        untracked_ids = set(self.id_to_tab.keys()) - set(self.tab_ids)
        if not untracked_ids:
            return
        tab_views = self._get_tab_views()
        # dict of folder_id -> list of children ids
        folders = {}
        # any non-folder item that isn't in a folder
        extras = []
        for view in tab_views:
            for obj in view:
                if obj.id not in untracked_ids:
                    continue
                if isinstance(obj, folder.FolderBase):
                    folders.setdefault(obj.id, [])
                    continue
                if obj.get_folder() is None:
                    extras.append(obj.id)
                else:
                    folders.setdefault(obj.get_folder().id, []).append(obj.id)
        for folder_id, children in folders.items():
            if folder_id in untracked_ids:
                # folder isn't tracked, add everything to the bottom
                self.tab_ids.append(folder_id)
                self.tab_ids.extend(children)
            else:
                # folder is tracked, insert the children after the folder
                pos = self.tab_ids.index(folder_id)
                self.tab_ids[pos+1:pos+1] = children

        self.tab_ids.extend(extras)
        self.signal_change()

    def _remove_out_of_order_children(self):
        """Remove ids for objects that have parents, but aren't ordered
        correctly relative to them.  (they will get added back in in
        _add_untracked_ids())
        """

        current_folder_id = None

        out_of_order_children = []

        for pos, obj in enumerate(self.get_all_tabs()):
            if obj.get_folder() is None:
                if isinstance(obj, folder.FolderBase):
                    current_folder_id = obj.id
                else:
                    current_folder_id = None
            else:
                if (current_folder_id is None or
                        obj.get_folder().id != current_folder_id):
                    out_of_order_children.append(pos)
        for pos in reversed(out_of_order_children):
            del self.tab_ids[pos]

    def get_all_tabs(self):
        """Get all the tabs in this tab ordering (in order), regardless if
        they are visible in the tab list or not.
        """
        return [self.id_to_tab[tab_id] for tab_id in self.tab_ids]

    def _on_add_tab(self, tracker, obj):
        if obj.id not in self.id_to_tab:
            self.id_to_tab[obj.id] = obj
            self.tab_ids.append(obj.id)
            self.signal_change()

    def _on_remove_tab(self, tracker, obj):
        if obj.id in self.id_to_tab:
            del self.id_to_tab[obj.id]
            self.tab_ids.remove(obj.id)
            self.signal_change()

    def reorder(self, newOrder):
        """Saves the new tab order.
        """
        self.tab_ids = newOrder
        self.signal_change()

    def move_tabs_after(self, anchor_id, tab_ids):
        """Move a sequence of tabs so that they are after another tab."""
        anchor_pos = self.tab_ids.index(anchor_id)
        move_set = set(tab_ids)
        before = [tab_id for tab_id in self.tab_ids[:anchor_pos]
                  if tab_id not in move_set]
        after = [tab_id for tab_id in self.tab_ids[anchor_pos+1:]
                 if tab_id not in move_set]
        self.reorder(before + [anchor_id] + list(tab_ids) + after)
