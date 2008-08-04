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

from miro import app

class ItemListManager(object):
    """Manages item lists from a high level.

    The main thing this class does is keep track of what items are selected.
    This is a little tricky because we usually have several item list and
    items can be selected in any of them.
    """

    def __init__(self):
        self.item_lists = []
        self.callback_ids = {}
        self.current_item_list = None
        self.default_item_list = None

    def manage_item_list(self, item_list):
        """Start managing an item list.  This should be called for each item
        list that's being displayed.
        """
        self.item_lists.append(item_list)
        id = item_list.connect('selection-changed', self.on_selection_changed)
        self.callback_ids[item_list] = id

    def reset(self):
        """Reset the item list.  This should be called when item lists being
        displayed change (e.g. a new tab is selected).
        """
        for item_list in self.item_lists:
            item_list.disconnect(self.callback_ids[item_list])
        self.item_lists = []
        self.callback_ids = {}
        self.current_item_list = None

    def get_selection(self):
        """Get the currently selected items.  Returns a list of ItemInfos."""
        item_list = self.current_item_list
        if item_list is None:
            return []
        return [item_list.model[i][0] for i in item_list.get_selection()]

    def on_selection_changed(self, item_list):
        if (item_list is not self.current_item_list and
                item_list.num_rows_selected() == 0):
            # This is the result of us calling unselect_all() below
            return

        if item_list is not self.current_item_list:
            self.current_item_list = item_list
            for other_list in self.item_lists:
                if other_list is not item_list:
                    other_list.unselect_all()

        items = self.get_selection()
        app.menu_manager.handle_item_list_selection(items)

    def calc_videos_to_play(self):
        if self.current_item_list is None:
            if self.default_item_list is not None:
                return self.default_item_list.get_watchable_videos()
            else:
                return None
        selection = self.get_selection()
        # If one video is selected, play that video, then the rest in the
        # channel.  If more than one is selected, just play the selection.
        if len(selection) == 1:
            id = selection[0].id
            return self.current_item_list.get_watchable_videos(start_id=id)
        else:
            return selection
