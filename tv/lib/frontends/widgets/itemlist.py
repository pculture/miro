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

import sys
import time
import logging

from miro import app
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
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
    def sort_key(self, info):
        return info.release_date

class NameSort(ItemSort):
    KEY = 'name'
    def sort_key(self, info):
        return info.name_sort_key

class LengthSort(ItemSort):
    KEY = 'length'
    def sort_key(self, info):
        return info.duration

class SizeSort(ItemSort):
    KEY = 'size'
    def sort_key(self, info):
        return info.size

class DescriptionSort(ItemSort):
    KEY = 'description'
    def sort_key(self, info):
        return info.description

class FeedNameSort(ItemSort):
    KEY = 'feed-name'
    def sort_key(self, info):
        if info.feed_name:
            return info.feed_name.lower()
        return info.feed_name

class StatusCircleSort(ItemSort):
    KEY = 'state'
    # Weird sort, this one is for when the user clicks on the header above the
    # status bumps.  It's almost the same as StatusSort, but there isn't a
    # bump for expiring.
    def sort_key(self, info):
        if info.state == 'downloading':
            return 1 # downloading
        elif info.downloaded and not info.video_watched:
            return 2 # unwatched
        elif not info.item_viewed and not info.expiration_date:
            return 0 # new
        else:
            return 3 # other

class StatusSort(ItemSort):
    KEY = 'status'
    def sort_key(self, info):
        if info.state == 'downloading':
            return (2, ) # downloading
        elif info.downloaded and not info.video_watched:
            return (3, ) # unwatched
        elif info.expiration_date:
            # the tuple here creates a subsort on expiration_date
            return (4, info.expiration_date) # expiring
        elif not info.item_viewed:
            return (0, ) # new
        else:
            return (1, ) # other

class ETASort(ItemSort):
    KEY = 'eta'
    def sort_key(self, info):
        if info.state == 'downloading':
            eta = info.download_info.eta
            if eta > 0:
                return eta
        elif not self.reverse:
            return sys.maxint
        else:
            return -sys.maxint

class DownloadRateSort(ItemSort):
    KEY = 'rate'
    def sort_key(self, info):
        if info.state == 'downloading':
            return info.download_info.rate
        elif not self.reverse:
            return sys.maxint
        else:
            return -1

class ArtistSort(ItemSort):
    KEY = 'artist'
    def sort_key(self, info):
        return (info.artist_sort_key,
                info.album_sort_key,
                info.track)

class AlbumSort(ItemSort):
    KEY = 'album'
    def sort_key(self, info):
        return (info.album_sort_key,
                info.track,
                info.artist_sort_key)

class TrackSort(ItemSort):
    KEY = 'track'
    def sort_key(self, info):
        return (info.track,
                info.artist_sort_key,
                info.album_sort_key)

class YearSort(ItemSort):
    KEY = 'year'
    def sort_key(self, info):
        return info.year

class GenreSort(ItemSort):
    KEY = 'genre'
    def sort_key(self, info):
        return info.genre

class RatingSort(ItemSort):
    KEY = 'rating'
    def sort_key(self, info):
        return info.rating

class DRMSort(ItemSort):
    KEY = 'drm'
    def sort_key(self, info):
        return info.has_drm

class FileTypeSort(ItemSort):
    KEY = 'file-type'
    def sort_key(self, info):
        return info.file_type

class TorrentDetailsSort(ItemSort):
    KEY = 'torrent-details'
    def sort_key(self, info):
        return 0 # FIXME

class DateAddedSort(ItemSort):
    KEY = 'date-added'
    def sort_key(self, info):
        return info.date_added

DEFAULT_SORT = ArtistSort(False)

SORT_KEY_MAP = {
    DateSort.KEY:           DateSort,
    NameSort.KEY:           NameSort,
    LengthSort.KEY:         LengthSort,
    SizeSort.KEY:           SizeSort,
    DescriptionSort.KEY:    DescriptionSort,
    FeedNameSort.KEY:       FeedNameSort,
    StatusCircleSort.KEY:   StatusCircleSort,
    StatusSort.KEY:         StatusSort,
    ETASort.KEY:            ETASort,
    DownloadRateSort.KEY:   DownloadRateSort,
    ArtistSort.KEY:         ArtistSort,
    AlbumSort.KEY:          AlbumSort,
    TrackSort.KEY:          TrackSort,
    YearSort.KEY:           YearSort,
    GenreSort.KEY:          GenreSort,
    RatingSort.KEY:         RatingSort,
    DRMSort.KEY:            DRMSort,
    FileTypeSort.KEY:       FileTypeSort,
    TorrentDetailsSort.KEY: TorrentDetailsSort,
    DateAddedSort.KEY:      DateAddedSort,
}

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
        self._sorter = DEFAULT_SORT
        self.model = widgetset.InfoListModel(self._sorter.sort_key,
                self._sorter.reverse)
        self.new_only = False
        self.unwatched_only = False
        self.downloaded_only = False
        self.non_feed_only = False
        self.resort_on_update = False
        self._hidden_items = {}
        self._filter = WidgetStateStore.get_view_all_filter()
        # maps ids -> items that should be in this list, but are filtered out
        # for some reason

    def set_sort(self, sorter):
        self._sorter = sorter
        self.model.change_sort(sorter.sort_key, sorter.reverse)

    def resort(self):
        self.set_sort(self._sorter)

    def get_sort(self):
        return self._sorter

    def get_count(self):
        """Get the number of items in this list that are displayed."""
        return len(self.model)

    def get_hidden_count(self):
        """Get the number of items in this list that are hidden."""
        return len(self._hidden_items)

    def get_item(self, id):
        return self.model.get_info(id)

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
                    not app.playback_manager.is_playing_item(item_info) and
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
        """Update the throbber count for an item.

        raises a KeyError if item_id is not in the model.
        """
        try:
            counter = self.model.get_attr(item_id, 'throbber-value')
        except KeyError:
            counter = 0
        self.model.set_attr(item_id, 'throbber-value', counter + 1)

    def finish_throbber(self, item_id):
        self.model.unset_attr(item_id, 'throbber-value')

    def start_keep_animation(self, item_id):
        self.model.set_attr(item_id, 'keep-animation-start', time.time())
        self.model.set_attr(item_id, 'keep-animation-alpha', 1.0)

    def update_keep_animation(self, item_id, fade_delay, fade_length):
        start_time = self.model.get_attr(item_id, 'keep-animation-start')
        elapsed = time.time() - start_time
        if elapsed < fade_delay:
            # waiting to start the fade
            return False
        elif elapsed < fade_delay + fade_length:
            # doing the fade
            alpha = 1.0 - (float(elapsed - fade_delay) / fade_length)
            self.model.set_attr(item_id, 'keep-animation-alpha', alpha)
            return False
        else:
            # done with the fade
            self.model.unset_attr(item_id, 'keep-animation-start')
            self.model.unset_attr(item_id, 'keep-animation-alpha')
            return True

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

    def toggle_filter(self, filter_):
        self._filter = WidgetStateStore.toggle_filter(self._filter, filter_)
        self.unwatched_only = WidgetStateStore.has_unwatched_filter(
                self._filter)
        self.downloaded_only = WidgetStateStore.has_downloaded_filter(
                self._filter)
        self.non_feed_only = WidgetStateStore.has_non_feed_filter(
                self._filter)
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

class ConvertingItemList(ItemList):
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
