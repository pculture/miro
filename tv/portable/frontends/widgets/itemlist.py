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

"""itemlist.py -- Handles TableModel objects that store items.

itemlist, itemlistcontroller and itemlistwidgets work together using the MVC
pattern.  itemlist handles the Model, itemlistwidgets handles the View and
itemlistcontroller handles the Controller.

ItemList manages a TableModel that stores ItemInfo objects.  It handles
filtering out items from the list (for example in the Downloading items list).
They also handle temporarily filtering out items based the user's search
terms.
"""

import sys

from miro import search
from miro import util
from miro.frontends.widgets import imagepool
from miro.plat.utils import filenameToUnicode
from miro.plat.frontends.widgets import timer
from miro.plat.frontends.widgets import widgetset

def item_matches_search(item_info, search_text):
    """Check if an item matches search text."""
    if search_text == '':
        return True
    match_against = [item_info.name, item_info.description]
    if item_info.video_path is not None:
        match_against.append(filenameToUnicode(item_info.video_path))
    return search.match(search_text, match_against)

class ItemSort(object):
    """Class that sorts items in an item list."""

    def __init__(self, ascending):
        self._reverse = not ascending

    def is_ascending(self):
        return not self._reverse

    def sort_key(self, item):
        """Return a value that can be used to sort item.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()

    def compare(self, item, other):
        """Compare two items

        Returns -1 if item < other, 1 if other > item and 0 if item == other
        (same as cmp)
        """
        if self._reverse:
            return -cmp(self.sort_key(item), self.sort_key(other))
        else:
            return cmp(self.sort_key(item), self.sort_key(other))

    def sort_items(self, item_list):
        """Sort a list of items (in place)."""
        item_list.sort(key=self.sort_key, reverse=self._reverse)

    def sort_item_rows(self, rows):
        rows.sort(key=lambda row: self.sort_key(row[0]),
                reverse=self._reverse)

class DateSort(ItemSort):
    KEY = 'date'
    def sort_key(self, item):
        return item.release_date

class NameSort(ItemSort):
    KEY = 'name'
    def sort_key(self, item):
        return item.name

class LengthSort(ItemSort):
    KEY = 'length'
    def sort_key(self, item):
        return item.duration

class SizeSort(ItemSort):
    KEY = 'size'
    def sort_key(self, item):
        return item.size

class DescriptionSort(ItemSort):
    KEY = 'description'
    def sort_key(self, item):
        return item.description

class FeedNameSort(ItemSort):
    KEY = 'feed-name'
    def sort_key(self, item):
        return item.feed_name

class StatusCircleSort(ItemSort):
    KEY = 'state'
    # Weird sort, this one is for when the user clicks on the header above the
    # status bumps.  It's almost the same as StatusSort, but there isn't a
    # bump for expiring.
    def sort_key(self, item):
        if item.state == 'downloading':
            return 1 # downloading
        elif item.downloaded and not item.video_watched:
            return 2 # unwatched
        elif not item.item_viewed and not item.expiration_date:
            return 0 # new
        else:
            return 3 # other

class StatusSort(ItemSort):
    KEY = 'status'
    def sort_key(self, item):
        if item.state == 'downloading':
            return 2 # downloading
        elif item.downloaded and not item.video_watched:
            return 3 # unwatched
        elif item.expiration_date:
            return 4 # expiring
        elif not item.item_viewed:
            return 0 # new
        else:
            return 1 # other

class ETASort(ItemSort):
    KEY = 'eta'
    def sort_key(self, item):
        if item.state in ('downloading', 'paused'):
            eta = item.download_info.eta
            if eta > 0:
                return eta
        elif not self._reverse:
            return sys.maxint
        else:
            return -sys.maxint

class DownloadRateSort(ItemSort):
    KEY = 'rate'
    def sort_key(self, item):
        if item.state in ('downloading', 'paused'):
            return item.download_info.rate
        elif not self._reverse:
            return sys.maxint
        else:
            return -1

class ProgressSort(ItemSort):
    KEY = 'progress'
    def sort_key(self, item):
        if item.state in ('downloading', 'paused'):
            return float(item.download_info.downloaded_size) / item.size
        elif not self._reverse:
            return sys.maxint
        else:
            return -1

SORT_KEY_MAP = {
    DateSort.KEY:         DateSort,
    NameSort.KEY:         NameSort,
    LengthSort.KEY:       LengthSort,
    SizeSort.KEY:         SizeSort,
    DescriptionSort.KEY:  DescriptionSort,
    FeedNameSort.KEY:     FeedNameSort,
    StatusCircleSort.KEY: StatusCircleSort,
    StatusSort.KEY:       StatusSort,
    ETASort.KEY:          ETASort,
    DownloadRateSort.KEY: DownloadRateSort,
    ProgressSort.KEY:     ProgressSort,
}

class ItemListGroup(object):
    """Manages a set of ItemLists.

    ItemListGroup keep track of one or more ItemLists.  When items are
    added/changed/removed they take care of making sure each child list
    updates itself.

    ItemLists maintain an item sorting and a search filter that are shared by
    each child list.
    """

    def __init__(self, item_lists, sorter):
        """Construct in ItemLists.

        item_lists is a list of ItemList objects that should be grouped
        together.
        """
        self.item_lists = item_lists
        if sorter is None:
            self.set_sort(DateSort(False))
        else:
            self.set_sort(sorter)
        self._throbber_timeouts = {}
        self.html_stripper = util.HTMLStripper()

    def _throbber_timeout(self, id):
        for item_list in self.item_lists:
            item_list.update_throbber(id)
        self._schedule_throbber_timeout(id)

    def _schedule_throbber_timeout(self, id):
        timeout = timer.add(0.4, self._throbber_timeout, id)
        self._throbber_timeouts[id] = timeout

    def _setup_info(self, info):
        """Initialize a newly received ItemInfo."""
        info.icon = imagepool.LazySurface(info.thumbnail, (154, 105))
        info.description_text, info.description_links = \
                self.html_stripper.strip(info.description)
        download_info = info.download_info
        if (download_info is not None and
                not download_info.finished and
                download_info.state != 'paused' and
                download_info.downloaded_size > 0 and info.size == -1):
            # We are downloading an item without a content-length.  Take steps
            # to update the progress throbbers.
            if info.id not in self._throbber_timeouts:
                self._schedule_throbber_timeout(info.id)
        elif info.id in self._throbber_timeouts:
            timer.cancel(self._throbber_timeouts.pop(info.id))

    def add_items(self, item_list):
        """Add a list of new items to the item list.

        Note: This method will sort item_list
        """
        self._sorter.sort_items(item_list)
        for item_info in item_list:
            self._setup_info(item_info)
        for sublist in self.item_lists:
            sublist.add_items(item_list, already_sorted=True)

    def update_items(self, changed_items):
        """Update items.

        Note: This method will sort changed_items
        """
        self._sorter.sort_items(changed_items)
        for item_info in changed_items:
            self._setup_info(item_info)
        for sublist in self.item_lists:
            sublist.update_items(changed_items, already_sorted=True)

    def remove_items(self, removed_ids):
        """Remove items from the list."""
        for sublist in self.item_lists:
            sublist.remove_items(removed_ids)

    def set_sort(self, sorter):
        """Change the way items are sorted in the list (and filtered lists)

        sorter must be a subclass of ItemSort.
        """
        self._sorter = sorter
        for sublist in self.item_lists:
            sublist.set_sort(sorter)

    def get_sort(self):
        return self._sorter

    def set_search_text(self, search_text):
        """Update the search for each child list."""
        for sublist in self.item_lists:
            sublist.set_search_text(search_text)

class ItemList(object):
    """
    Attributes:

    model -- TableModel for this item list.  It contains these columns:
        * ItemInfo (object)
        * show_details flag (boolean)
        * counter used to change the progress throbber (integer)

    new_only -- Are we only displaying the new items?
    """

    def __init__(self):
        self.model = widgetset.TableModel('object', 'boolean', 'integer')
        self._iter_map = {}
        self._sorter = None
        self._search_text = ''
        self.new_only = False
        self.unwatched_only = False
        self.non_feed_only = False
        self._hidden_items = {}
        # maps ids -> items that should be in this list, but are filtered out
        # for some reason

    def set_sort(self, sorter):
        self._sorter = sorter
        self._resort_items()

    def get_sort(self):
        return self._sorter

    def get_count(self):
        """Get the number of items in this list that are displayed."""
        return len(self.model)

    def get_hidden_count(self):
        """Get the number of items in this list that are hidden."""
        return len(self._hidden_items)

    def get_items(self, start_id=None):
        """Get a list of ItemInfo objects in this list"""
        if start_id is None:
            return [row[0] for row in self.model]
        else:
            iter = self._iter_map[start_id]
            retval = []
            while iter is not None:
                retval.append(self.model[iter][0])
                iter = self.model.next_iter(iter)
            return retval

    def _resort_items(self):
        rows = []
        iter = self.model.first_iter()
        while iter is not None:
            rows.append(tuple(self.model[iter]))
            iter = self.model.remove(iter)
        self._sorter.sort_item_rows(rows)
        for row in rows:
            self._iter_map[row[0].id] = self.model.append(*row)

    def filter(self, item_info):
        """Can be overrided by subclasses to filter out items from the list.
        """
        return True

    def _should_show_item(self, item_info):
        if not self.filter(item_info):
            return False
        return (not (self.new_only and item_info.item_viewed) and
                not (self.unwatched_only and item_info.video_watched) and
                not (self.non_feed_only and (not item_info.is_external and item_info.feed_url != 'dtv:searchDownloads')) and
                item_matches_search(item_info, self._search_text))

    def set_show_details(self, item_id, value):
        """Change the show details value for an item"""
        iter = self._iter_map[item_id]
        self.model.update_value(iter, 1, value)

    def find_show_details_rows(self):
        """Return a list of iters for rows with in show details mode."""
        retval = []
        iter = self.model.first_iter()
        while iter is not None:
            if self.model[iter][1]:
                retval.append(iter)
            iter = self.model.next_iter(iter)
        return retval

    def update_throbber(self, item_id):
        try:
            iter = self._iter_map[item_id]
        except KeyError:
            pass
        else:
            counter = self.model[iter][2]
            self.model.update_value(iter, 2, counter + 1)

    def _insert_sorted_items(self, item_list):
        pos = self.model.first_iter()
        for item_info in item_list:
            while (pos is not None and
                    self._sorter.compare(self.model[pos][0], item_info) < 0):
                pos = self.model.next_iter(pos)
            iter = self.model.insert_before(pos, item_info, False, 0)
            self._iter_map[item_info.id] = iter

    def add_items(self, item_list, already_sorted=False):
        to_add = []
        for item in item_list:
            if self._should_show_item(item):
                to_add.append(item)
            else:
                self._hidden_items[item.id] = item
        if not already_sorted:
            self._sorter.sort_items(to_add)
        self._insert_sorted_items(to_add)

    def update_items(self, changed_items, already_sorted=False):
        to_add = []
        for info in changed_items:
            should_show = self._should_show_item(info)
            if info.id in self._iter_map:
                # Item already displayed
                if not should_show:
                    self.remove_item(info.id)
                    self._hidden_items[info.id] = info
                else:
                    self.update_item(info)
            else:
                # Item not already displayed
                if should_show:
                    to_add.append(info)
                    del self._hidden_items[info.id]
                else:
                    self._hidden_items[info.id] = info
        if not already_sorted:
            self._sorter.sort_items(to_add)
        self._insert_sorted_items(to_add)

    def remove_item(self, id):
        try:
            iter = self._iter_map.pop(id)
        except KeyError:
            pass # The item isn't in our current list, just skip it
        else:
            self.model.remove(iter)

    def update_item(self, info):
        iter = self._iter_map[info.id]
        self.model.update_value(iter, 0, info)

    def remove_items(self, id_list):
        for id in id_list:
            self.remove_item(id)

    def set_new_only(self, new_only):
        """Set if only new items are to be displayed (default False)."""
        self.new_only = new_only
        self._recalculate_hidden_items()

    def view_all(self):
        self.unwatched_only = False
        self.non_feed_only = False
        self._recalculate_hidden_items()

    def toggle_unwatched_only(self):
        self.unwatched_only = not self.unwatched_only
        self._recalculate_hidden_items()

    def toggle_non_feed(self):
        self.non_feed_only = not self.non_feed_only
        self._recalculate_hidden_items()

    def set_search_text(self, search_text):
        self._search_text = search_text
        self._recalculate_hidden_items()

    def _recalculate_hidden_items(self):
        newly_matching = self._find_newly_matching_items()
        removed = self._remove_non_matching_items()
        self._sorter.sort_items(newly_matching)
        self._insert_sorted_items(newly_matching)
        for item in removed:
            self._hidden_items[item.id] = item
        for item in newly_matching:
            del self._hidden_items[item.id]

    def move_items(self, insert_before, item_ids):
        """Move a group of items inside the list.

        The items for item_ids will be positioned before insert_before.
        insert_before should be an iterator, or None to position the items at
        the end of the list.
        """

        new_iters = _ItemReorderer().reorder(self.model, insert_before,
                item_ids)
        self._iter_map.update(new_iters)

    def _find_newly_matching_items(self):
        retval = []
        for item in self._hidden_items.values():
            if self._should_show_item(item):
                retval.append(item)
        return retval

    def _remove_non_matching_items(self):
        removed = []
        iter = self.model.first_iter()
        while iter is not None:
            item = self.model[iter][0]
            if not self._should_show_item(item):
                iter = self.model.remove(iter)
                del self._iter_map[item.id]
                removed.append(item)
            else:
                iter = self.model.next_iter(iter)
        return removed

class IndividualDownloadItemList(ItemList):
    """ItemList that only displays single downloads items.

    Used in the downloads tab."""
    def filter(self, item_info):
        return (item_info.is_external
                and not (item_info.download_info
                         and item_info.download_info.state in ('uploading', 'uploading-paused')))

class ChannelDownloadItemList(ItemList):
    """ItemList that only displays channel downloads items.

    Used in the downloads tab."""
    def filter(self, item_info):
        return (not item_info.is_external
                and not (item_info.download_info
                         and item_info.download_info.state in ('uploading', 'uploading-paused')))

class SeedingItemList(ItemList):
    """ItemList that only displays seeding items.

    Used in the downloads tab."""
    def filter(self, item_info):
        return (item_info.download_info
                and item_info.download_info.state in ('uploading', 'uploading-paused'))

class DownloadingItemList(ItemList):
    """ItemList that only displays downloading items."""
    def filter(self, item_info):
        return (item_info.download_info
                and not item_info.download_info.finished
                and not item_info.download_info.state == 'failed')

class DownloadedItemList(ItemList):
    """ItemList that only displays downloaded items."""
    def filter(self, item_info):
        return (item_info.download_info and
                item_info.download_info.finished)

class _ItemReorderer(object):
    """Handles re-ordering items inside an itemlist.

    This object is just around for utility sake.  It's only created to track
    the state during the call to ItemList.move_items()
    """

    def __init__(self):
        self.removed_rows = []

    def calc_insert_id(self, model):
        if self.insert_iter is not None:
            self.insert_id = model[self.insert_iter][0].id
        else:
            self.insert_id = None

    def reorder(self, model, insert_iter, ids):
        self.insert_iter = insert_iter
        self.calc_insert_id(model)
        self.remove_rows(model, ids)
        return self.put_rows_back(model)

    def remove_row(self, model, iter, row):
        self.removed_rows.append(row)
        if row[0].id == self.insert_id:
            self.insert_iter = model.next_iter(self.insert_iter)
            self.calc_insert_id(model)
        return model.remove(iter)

    def remove_rows(self, model, ids):
        # iterating through the entire table seems inefficient, but we have to
        # know the order of rows so we can insert them back in the right
        # order.
        iter = model.first_iter()
        while iter is not None:
            row = model[iter]
            if row[0].id in ids:
                # need to make a copy of the row data, since we're removing it
                # from the table
                iter = self.remove_row(model, iter, tuple(row))
            else:
                iter = model.next_iter(iter)

    def put_rows_back(self, model):
        if self.insert_iter is None:
            def put_back(moved_row):
                return model.append(*moved_row)
        else:
            def put_back(moved_row):
                return model.insert_before(self.insert_iter, *moved_row)
        retval = {}
        for removed_row in self.removed_rows:
            iter = put_back(removed_row)
            retval[removed_row[0].id] = iter
        return retval
