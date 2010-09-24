# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""Manages the tab lists from a high level perspective."""

from miro import app
from miro import config
from miro import prefs

from miro.frontends.widgets import tablist
from miro.plat.frontends.widgets import widgetset

class TabListManager(object):
    def __init__(self):
        self.static_tab_list = tablist.StaticTabList()
        self.library_tab_list = tablist.LibraryTabList()
        self.devices_list = tablist.DevicesList()
        self.site_list = tablist.SiteList()
        self.feed_list = tablist.FeedList()
        self.audio_feed_list = tablist.AudioFeedList()
        self.playlist_list = tablist.PlaylistList()
        self.widget_to_tablist = {}
        for tab_list in self.all_tab_lists():
            self.widget_to_tablist[tab_list.view] = tab_list
        self.__table_view = None

    def populate_tab_list(self):
        self.static_tab_list.build_tabs()
        self.library_tab_list.build_tabs()
        self.select_startup_default()
        for tab_list in self.all_tab_lists():
            tab_list.view.connect('selection-changed',
                    self.on_selection_changed)

    def _select_from_tab_list(self, tab_list, iter):
        view = tab_list.view
        previous_selection = view.get_selection()
        for previously_selected in previous_selection:
            if (view.model[previously_selected][0] == view.model[iter][0]):
                return # The tab is already selected
        view.select(iter)
        for previously_selected in previous_selection:
            # We unselect *after* having made the new selection because if we
            # unselect first and the selection is empty, the on_selection_changed
            # callback forces the guide to be selected.
            view.unselect(previously_selected)
        self.selected_tab_list = tab_list
        self.selected_tabs = [view.model[iter][0]]
        self.handle_new_selection()

    def handle_startup_selection(self):
        self.handle_new_selection()

    def handle_new_selection(self):
        app.display_manager.select_display_for_tabs(self.selected_tab_list,
                self.selected_tabs)

    def which_tablist_has_id(self, feed_id):
        """
        Find out whether the video feed list or the audio feed list has this id
        """
        for tablist in self.feed_list, self.audio_feed_list:
            if tablist.has_info(feed_id):
                return tablist
        raise ValueError("Unknown feed id.  %s" % feed_id)

    def all_tab_lists(self):
        return (
            self.static_tab_list, self.library_tab_list, self.devices_list,
            self.site_list, self.feed_list, self.audio_feed_list,
            self.playlist_list)

    def select_guide(self):
        self.select_static_tab(0)

    def select_search(self):
        self.select_static_tab(1)


    def select_startup_default(self):
        if config.get(prefs.OPEN_CHANNEL_ON_STARTUP) is not None:
            # try regular feeds first, followed by audio feeds
            for tab_list in self.feed_list, self.audio_feed_list:
                info = tab_list.find_feed_with_url(
                    config.get(prefs.OPEN_CHANNEL_ON_STARTUP))
                if info is not None:
                    self._select_from_tab_list(
                        tab_list,
                        tab_list.iter_map[info.id])
                    return

        if config.get(prefs.OPEN_FOLDER_ON_STARTUP) is not None:
            for tab_list in self.feed_list, self.audio_feed_list:
                for iter in tab_list.iter_map.values():
                    info = tab_list.view.model[iter][0]
                    if info.is_folder and info.name == config.get(
                        prefs.OPEN_FOLDER_ON_STARTUP):
                        self._select_from_tab_list(tab_list, iter)
                        return
        # if we get here, the fallback default is the Guide
        self.select_guide()

    def select_static_tab(self, index):
        iter = self.static_tab_list.view.model.nth_iter(index)
        self._select_from_tab_list(self.static_tab_list, iter)

    def handle_tablist_change(self, new_tablist):
        self.selected_tab_list = new_tablist
        for tab_list in self.all_tab_lists():
            if tab_list is not new_tablist:
                tab_list.view.unselect_all()

    def update_selected_tabs(self):
        table_view = self.selected_tab_list.view
        self.__table_view = table_view
        self.selected_tabs = [table_view.model[i][0] for i in
                table_view.get_selection()]

    def on_selection_changed(self, table_view):
        if (table_view is not self.selected_tab_list.view and
                table_view.num_rows_selected() == 0):
            # This is the result of us calling unselect_all() in
            # handle_tablist_change
            return

        tab_list = self.widget_to_tablist[table_view]
        if tab_list.doing_change:
            return
        if tab_list is not self.selected_tab_list:
            self.handle_tablist_change(tab_list)
        if table_view.num_rows_selected() > 0:
            self.update_selected_tabs()
        else:
            self.handle_no_tabs_selected()
        self.handle_new_selection()

    def recalc_selection(self):
        self.on_selection_changed(self.selected_tab_list.view)

    def handle_no_tabs_selected(self):
        model = self.selected_tab_list.view.model
        iter = model.first_iter()
        if iter is None:
            # We deleted all the feeds/playlists, select the guide instead
            self.select_guide()
        else:
            self.selected_tab_list.view.select(iter)
            self.selected_tabs = [model[iter][0]]

    def get_selection(self):
        if self.__table_view is not None:
            return self.selected_tab_list.type, self.selected_tabs
        else:
            return None, []

    def get_selection_and_children(self):
        """This returns the selection and, in the case of parent rows, returns
        all children, too.  This is particularly useful for getting selections
        that include children of folders.

        This returns a list generated from a set--so there are no repeated
        elements.
        """
        table_view = self.__table_view
        if table_view is not None:
            selected_tabs = set()
            for mem in table_view.get_selection():
                row = table_view.model[mem]
                # sort children before parents
                selected_tabs.add((1, row[0]))
                for children in row.iterchildren():
                    selected_tabs.add((0, children[0]))
            return self.selected_tab_list.type, [obj for index, obj in
                                                 sorted(selected_tabs)]
        else:
            return None, []
