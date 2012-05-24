# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

"""itemlist.py -- Handles item data for our table views

This module uses the miro.data.itemtrack module as a base and adds
widget-specific functionality and convenience methods.
"""

import collections

from miro.data import itemtrack
from miro.frontends.widgets import itemfilter
from miro.frontends.widgets import itemsort
from miro.plat.frontends.widgets.threads import call_on_ui_thread

class ItemList(itemtrack.ItemTracker):
    """ItemList -- Track a list of items for TableView

    ItemList extends ItemTracker to provide:
        - set/get arbitrary attributes on items
        - grouping information
        - simpler interface to construct queries:
            - set_filters/select_filter changes the filters
            - set_sort changes the sort
    """
    def __init__(self, base_query):
        self.base_query = base_query
        self.item_attributes = collections.defaultdict(dict)
        self.filter_set = itemfilter.ItemFilterSet()
        self.sorter = itemsort.DateSort()
        self.group_func = None
        itemtrack.ItemTracker.__init__(self, call_on_ui_thread,
                                       self._make_query())

    def _fetch_id_list(self):
        itemtrack.ItemTracker._fetch_id_list(self)
        self._reset_group_info()

    def _make_query(self):
        query = self.base_query.copy()
        self.filter_set.add_to_query(query)
        self.sorter.add_to_query(query)
        return query

    def _update_query(self):
        self.change_query(self._make_query())

    # filters
    def select_filter(self, key):
        self.filter_set.select(key)

    def set_filters(self, filter_keys):
        self.filter_set.set_filters(filter_keys)
        self._update_query()

    def get_filters(self):
        return self.filter_set.active_filters

    # sorts
    def set_sort(self, sorter):
        self.sorter = sorter
        self._update_query()

    # attributes
    def set_attr(self, id, name, value):
        self.item_attributes[id][name] = value

    def get_attr(self, id, name):
        return self.item_attributes[id][name]

    def unset_attr(self, id, name):
        if name in self.item_attributes[id]:
            del self.item_attributes[id][name]

    # grouping
    def get_group_info(self, row):
        """Get the info about the group an info is inside.

        This method fetches the index of the info inside the group and the
        total size of the group.

        :returns: an (index, count) tuple
        :raises ValueError: if no groupping is set
        """
        if self.group_func is None:
            raise ValueError("no grouping set")
        if self.group_info[row] is None:
            self._calc_group_info(row)
        return self.group_info[row]

    def get_grouping(self):
        """Get the function set with set_grouping."""
        return self.group_func

    def set_grouping(self, func):
        """Set a grouping function for this info list.

        Grouping functions input info objects and return values that will be
        used to segment the list into groups.  Adjacent infos with the same
        grouping value are part of the same group.

        get_group_info() can be used to find the position of an info inside
        its group.
        """
        self.group_func = func
        self._reset_group_info()

    def _reset_group_info(self):
        self.group_info = [None] * len(self)

    def _calc_group_info(self, row):
        key = self.group_func(self.get_row(row))
        start = end = row
        while (start > 0 and
               self.group_func(self.get_row(start-1)) == key):
            start -= 1
        while (end < len(self) - 1 and
               self.group_func(self.get_row(end+1)) == key):
            end += 1
        total = end - start + 1
        for row in xrange(start, end+1):
            self.group_info[row] = (row-start, total)

class FeedItemList(ItemList):
    def __init__(self, feed_id):
        base_query = itemtrack.ItemTrackerQuery()
        base_query.add_condition('feed_id', '=', feed_id)
        ItemList.__init__(self, base_query)
        self.feed_id = feed_id
