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

This module defines ItemLists, which integres ItemTracker with the rest of the
widgets code.

It also defines several ItemTrackerQuery subclasses that correspond to tabs
in the interface.
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
    def __init__(self, tab_type, tab_id):
        """Create a new ItemList

        Note: outside classes shouldn't call this directly.  Instead, they
        should use the app.item_list_pool.get() method.

        :param tab_type: type of tab that this list is for
        :parab tab_id: id of the tab that this list is for
        """
        self.tab_type = tab_type
        self.tab_id = tab_id
        self.base_query = self._make_base_query(tab_type, tab_id)
        self.item_attributes = collections.defaultdict(dict)
        self.filter_set = itemfilter.ItemFilterSet()
        self.sorter = itemsort.DateSort()
        self.group_func = None
        itemtrack.ItemTracker.__init__(self, call_on_ui_thread,
                                       self._make_query())

    def _fetch_id_list(self):
        itemtrack.ItemTracker._fetch_id_list(self)
        self._reset_group_info()

    def _make_base_query(self, tab_type, tab_id):
        query = itemtrack.ItemTrackerQuery()
        if tab_type == 'feed':
            query.add_condition('feed_id', '=', tab_id)
        else:
            raise ValueError("Can't handle tab type %r" % tab_type)
        return query

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

class ItemListPool(object):
    """Pool of ItemLists that the frontend is using.

    This class keeps track of all active ItemList objects so that we can avoid
    creating 2 ItemLists for the same tab.  This helps with performance
    because we don't have to process the ItemsChanged message twice.  Also, we
    want changes to the item list to be shared.  For example, if a user is
    playing items from a given tab and they change the filters on that tab, we
    want the PlaybackPlaylist to reflect those changes.
    """
    def __init__(self):
        self.all_item_lists = set()
        self._refcounts = {}

    def get(self, tab_type, tab_id):
        """Get an ItemList to use.

        This method will first try to re-use an existing ItemList from the
        pool.  If it can't, then a new ItemList will be created.

        :returns: ItemList object.  When you are done with it, you must pass
        the ItemList to the release() method.
        """
        for obj in self.all_item_lists:
            if obj.tab_type == tab_type and obj.tab_id == tab_id:
                self._refcounts[obj] += 1
                return obj
        new_list = ItemList(tab_type, tab_id)
        self.all_item_lists.add(new_list)
        self._refcounts[new_list] = 1
        return new_list

    def release(self, item_list):
        """Release an item list.

        Call this when you're done using an ItemList.  Once this has been
        called for each time the list has been returned from get(), then that
        list will be removed from the pool and no longer get callbacks for the
        ItemsChanged message.
        """
        self._refcounts[item_list] -= 1
        if self._refcounts[item_list] <= 0:
            self.all_item_lists.remove(item_list)
            del self._refcounts[item_list]

    def on_item_changes(self, message):
        """Call on_item_changes for each ItemList in the pool."""
        for obj in self.all_item_lists:
            obj.on_item_changes(message)
