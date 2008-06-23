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

"""Manages the tab lists from a high level perspective."""

from miro import app
from miro.frontends.widgets import displays
from miro.frontends.widgets import feedview
from miro.frontends.widgets import tablist
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset

class TabListManager(object):
    def __init__(self):
        self.static_tab_list = tablist.StaticTabList()
        self.feed_list = tablist.FeedList()
        self.playlist_list = tablist.PlaylistList()
        self.widget_to_tablist = {}
        self.select_guide()
        for tab_list in self.all_tab_lists():
            self.widget_to_tablist[tab_list.view] = tab_list
            tab_list.view.connect('selection-changed',
                    self.on_selection_changed)

    def handle_startup_selection(self):
        app.display_manager.select_display_for_tabs(self.selected_tab_list,
                self.selected_tabs)

    def all_tab_lists(self):
        return (self.static_tab_list, self.feed_list, self.playlist_list)

    def select_guide(self):
        view = self.static_tab_list.view
        iter = view.model.first_iter()
        view.select(iter)
        self.selected_tab_list = self.static_tab_list
        self.selected_tabs = [view.model[iter][0]]

    def handle_tablist_change(self, new_tablist):
        self.selected_tab_list = new_tablist
        for tab_list in self.all_tab_lists():
            if tab_list is not new_tablist:
                tab_list.view.unselect_all()

    def update_selected_tabs(self):
        table_view = self.selected_tab_list.view
        self.selected_tabs = [table_view.model[i][0] for i in
                table_view.get_selection()]

    def on_selection_changed(self, table_view):
        if (table_view is not self.selected_tab_list.view and
                table_view.num_rows_selected() == 0):
            # This is the result of us calling unselect_all() in
            # handle_tablist_change
            return

        tab_list = self.widget_to_tablist[table_view]
        if tab_list.in_drag_and_drop_reorder:
            return
        if tab_list is not self.selected_tab_list:
            self.handle_tablist_change(tab_list)
        if table_view.num_rows_selected() > 0:
            self.update_selected_tabs()
        else:
            self.handle_no_tabs_selected()
        app.display_manager.select_display_for_tabs(self.selected_tab_list,
                self.selected_tabs)

    def handle_no_tabs_selected(self):
        for tab in self.selected_tabs:
            try:
                iter = self.selected_tab_list.iter_map[tab.id]
            except KeyError: # Tab got deleted
                continue
            self.selected_tab_list.view.select(iter)
            self.selected_tabs = [tab]
            return
        # all the tabs were deleted
        self.select_guide()

    def get_selection(self):
        return self.selected_tab_list.type, self.selected_tabs
