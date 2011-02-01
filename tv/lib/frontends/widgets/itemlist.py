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

"""itemlist.py -- Handles TableModel objects that store items.

itemlist, itemlistcontroller and itemlistwidgets work together using the MVC
pattern.  itemlist handles the Model, itemlistwidgets handles the View and
itemlistcontroller handles the Controller.

ItemList manages a TableModel that stores ItemInfo objects.  It handles
filtering out items from the list (for example in the Downloading items list).
They also handle temporarily filtering out items based the user's search
terms.
"""

import re
import sys
import unicodedata
import logging

from miro import search
from miro import signals
from miro import util
from miro.frontends.widgets import imagepool
from miro.plat.utils import filename_to_unicode
from miro.plat.frontends.widgets import timer
from miro.plat.frontends.widgets import widgetset


class ItemSort(object):
    """Class that sorts items in an item list."""

    def __init__(self, ascending):
        self.reverse = not ascending

    def is_ascending(self):
        return not self.reverse

    def sort_key(self, item):
        """Return a value that can be used to sort item.

        Must be implemented by subclasses.
        """
        raise NotImplementedError()

class DateSort(ItemSort):
    KEY = 'date'
    def sort_key(self, item):
        return item.release_date

class NameSort(ItemSort):
    KEY = 'name'
    def sort_key(self, item):
        return util.name_sort_key(item.name)

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
        if item.feed_name:
            return item.feed_name.lower()
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
            return (2, ) # downloading
        elif item.downloaded and not item.video_watched:
            return (3, ) # unwatched
        elif item.expiration_date:
            # the tuple here creates a subsort on expiration_date
            return (4, item.expiration_date) # expiring
        elif not item.item_viewed:
            return (0, ) # new
        else:
            return (1, ) # other

class ETASort(ItemSort):
    KEY = 'eta'
    def sort_key(self, item):
        if item.state == 'downloading':
            eta = item.download_info.eta
            if eta > 0:
                return eta
        elif not self.reverse:
            return sys.maxint
        else:
            return -sys.maxint

class DownloadRateSort(ItemSort):
    KEY = 'rate'
    def sort_key(self, item):
        if item.state == 'downloading':
            return item.download_info.rate
        elif not self.reverse:
            return sys.maxint
        else:
            return -1

class ProgressSort(ItemSort):
    KEY = 'progress'
    def sort_key(self, item):
        if item.state in ('downloading', 'paused'):
            return float(item.download_info.downloaded_size) / item.size
        elif not self.reverse:
            return sys.maxint
        else:
            return -1

class ArtistSort(ItemSort):
    KEY = 'artist'
    def sort_key(self, item):
        return [util.name_sort_key(item.artist),
                util.name_sort_key(item.album),
                int(item.track)]

class AlbumSort(ItemSort):
    KEY = 'album'
    def sort_key(self, item):
        return [util.name_sort_key(item.album),
                int(item.track),
                util.name_sort_key(item.artist)]

class TrackSort(ItemSort):
    KEY = 'track'
    def sort_key(self, item):
        return [int(item.track),
                util.name_sort_key(item.artist),
                util.name_sort_key(item.album)]

class YearSort(ItemSort):
    KEY = 'year'
    def sort_key(self, item):
        return int(item.year)

class GenreSort(ItemSort):
    KEY = 'genre'
    def sort_key(self, item):
        return item.genre

class RatingSort(ItemSort):
    KEY = 'rating'
    def sort_key(self, item):
        return item.rating

DEFAULT_SORT = ArtistSort(False)

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
    ArtistSort.KEY:       ArtistSort,
    AlbumSort.KEY:        AlbumSort,
    TrackSort.KEY:        TrackSort,
    YearSort.KEY:         YearSort,
    GenreSort.KEY:        GenreSort,
    RatingSort.KEY:       RatingSort,
}

class ItemListGroup(object):
    """Manages a set of ItemLists.

    ItemListGroup keep track of one or more ItemLists.  When items are
    added/changed/removed they take care of making sure each child list
    updates itself.

    ItemLists maintain an item sorting and a search filter that are shared by
    each child list.
    """

    def __init__(self, item_lists, sorter=None):
        """Construct in ItemLists.

        item_lists is a list of ItemList objects that should be grouped
        together.
        """
        self.item_lists = item_lists
        self.set_sort(sorter)
        self._throbber_timeouts = {}

    def _throbber_timeout(self, id):
        for item_list in self.item_lists:
            item_list.update_throbber(id)
        self._schedule_throbber_timeout(id)

    def _schedule_throbber_timeout(self, id):
        timeout = timer.add(0.4, self._throbber_timeout, id)
        self._throbber_timeouts[id] = timeout

    def _setup_info(self, info):
        """Initialize a newly received ItemInfo."""
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
        for item_info in item_list:
            self._setup_info(item_info)
        for sublist in self.item_lists:
            sublist.add_items(item_list)

    def update_items(self, changed_items):
        """Update items.

        Note: This method will sort changed_items
        """
        for item_info in changed_items:
            self._setup_info(item_info)
        for sublist in self.item_lists:
            sublist.update_items(changed_items)

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

class ItemList(object):
    """
    Attributes:

    model -- TableModel for this item list.  It contains these columns:
        * ItemInfo (object)
        * show_details flag (boolean)
        * counter used to change the progress throbber (integer)

    new_only -- Are we only displaying the new items?
    unwatched_only -- Are we only displaying the unwatched items?
    downloaded_only -- Are we only displaying the downloaded items?
    non_feed_only -- Are we only displaying file items?
    resort_on_update -- Should we re-sort the list when items change?
    """

    def __init__(self):
        self.model = widgetset.InfoListModel(None)
        self._sorter = None
        self.new_only = False
        self.unwatched_only = False
        self.downloaded_only = False
        self.non_feed_only = False
        self.resort_on_update = False
        self._hidden_items = {}
        # maps ids -> items that should be in this list, but are filtered out
        # for some reason

    def set_sort(self, sorter):
        self._sorter = sorter
        if sorter is not None:
            self.model.change_sort(sorter.sort_key, sorter.reverse)
        else:
            self.model.change_sort(None)

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
        rv = self.model.info_list()
        if start_id is not None:
            for idx in xrange(len(rv)):
                if rv[idx].id == start_id:
                    break
            return rv[idx:]
        return rv

    def iter_items(self, start_id=None):
        """Iterate through ItemInfo objects in this list"""
        info_list = self.model.info_list()
        if start_id is not None:
            for start_id_index in xrange(len(info_list)):
                if info_list[start_id_index].id == start_id:
                    break
        else:
            start_id_index = 0
        for i in xrange(start_id_index, len(info_list)):
            yield info_list[i]

    def __iter__(self):
        return self.iter_items()

    def filter(self, item_info):
        """Can be overrided by subclasses to filter out items from the list.
        """
        return True

    def _should_show_item(self, item_info):
        if not self.filter(item_info):
            return False
        return (not (self.new_only and item_info.item_viewed) and
                not (self.unwatched_only and
                        (item_info.video_path is None or
                            item_info.video_watched)) and
                not (self.downloaded_only and
                    item_info.video_path is None) and
                not (self.non_feed_only and (not item_info.is_external and
                    item_info.feed_url != 'dtv:searchDownloads')))

    def set_show_details(self, item_id, value):
        """Change the show details value for an item"""
        try:
            self.model.set_attr(item_id, 'show-details', value)
        except KeyError:
            pass

    def update_throbber(self, item_id):
        try:
            counter = self.model.get_attr(item_id, 'throbber-value', 0)
        except KeyError:
            return
        counter = self.model.set_attr(item_id, 'throbber-value', counter + 1)

    def _insert_items(self, to_add):
        if len(to_add) == 0:
            return
        self.model.add_infos(to_add)

    def add_items(self, item_list):
        to_add = []
        for item in item_list:
            if self._should_show_item(item):
                to_add.append(item)
            else:
                self._hidden_items[item.id] = item
        self._insert_items(to_add)

    def update_items(self, changed_items):
        to_add = []
        to_remove = []
        to_update = []
        for info in changed_items:
            should_show = self._should_show_item(info)
            if info.id in self._hidden_items:
                # Item not already displayed
                if should_show:
                    to_add.append(info)
                    del self._hidden_items[info.id]
                else:
                    self._hidden_items[info.id] = info
            else:
                # Item already displayed
                if not should_show:
                    to_remove.append(info.id)
                    self._hidden_items[info.id] = info
                else:
                    to_update.append(info)
        self._insert_items(to_add)
        self.model.update_infos(to_update, resort=self.resort_on_update)
        self.model.remove_ids(to_remove)

    def remove_items(self, id_list):
        ids_in_model = []
        for id_ in id_list:
            if id_ in self._hidden_items:
                del self._hidden_items[id_]
            else:
                ids_in_model.append(id_)
        self.model.remove_ids(ids_in_model)

    def remove_all(self):
        """Remove items from the list."""
        self.model.remove_all()
        self._hidden_items = {}

    def set_new_only(self, new_only):
        """Set if only new items are to be displayed (default False)."""
        self.new_only = new_only
        self._recalculate_hidden_items()

    def view_all(self):
        self.unwatched_only = False
        self.downloaded_only = False
        self.non_feed_only = False
        self._recalculate_hidden_items()

    def toggle_unwatched_only(self):
        self.unwatched_only = not self.unwatched_only
        self._recalculate_hidden_items()

    def toggle_non_feed(self):
        self.non_feed_only = not self.non_feed_only
        self._recalculate_hidden_items()

    def set_filters(self, unwatched, non_feed, downloaded):
        self.unwatched_only = unwatched
        self.non_feed_only = non_feed
        self.downloaded_only = downloaded
        self._recalculate_hidden_items()

    def _recalculate_hidden_items(self):
        info_list_at_start = self.model.info_list()

        newly_matching = []
        for item in self._hidden_items.values():
            if self._should_show_item(item):
                newly_matching.append(item)
                del self._hidden_items[item.id]
        self._insert_items(newly_matching)

        newly_unmatching_ids = []
        for item in info_list_at_start:
            if not self._should_show_item(item):
                newly_unmatching_ids.append(item.id)
                self._hidden_items[item.id] = item
        self.model.remove_ids(newly_unmatching_ids)

    def move_items(self, insert_before, item_ids):
        """Move a group of items inside the list.

        The items for item_ids will be positioned before insert_before.
        insert_before should be an iterator, or None to position the items at
        the end of the list.
        """
        if insert_before is not None:
            insert_before_id = insert_before.id
        else:
            insert_before_id = None
        self.model.move_before(insert_before_id, list(item_ids))

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

class ConversionsItemList(ItemList):
    """ItemList that displays items being converted."""
    def filter(self, item_info):
        return item_info.converting

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
