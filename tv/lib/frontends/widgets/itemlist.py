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

ItemList manages a TableModel that stores ItemInfo objects.  It uses an
ItemFilter object to filter out items from the list.
"""

import itertools
import sys

from miro import app
from miro import util
from miro.frontends.widgets import itemfilter
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

    def items_will_change(self, added, changed, removed):
        """Called when the item list will change.

        Subclasses can override this if they need to update things based on
        changes to the item list.
        """

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

class MultiRowAlbumSort(ItemSort):
    """Sorter for the album view column.  It operates the same as AlbumSort
    """
    KEY = 'multi-row-album'

    def __init__(self, ascending):
        ItemSort.__init__(self, ascending)
        self.switch_mode('standard')

    def switch_mode(self, new_mode):
        """Switch which mode we use to sort.

        MultiRowAlbumRenderer displays different data depending on what mode
        it's in.  Therefore, this sorter needs to sort differently depending
        on that mode.

        The modes available are the same as MultiRowAlbumRenderer's modes
        (standard, feed, and video).  The mode should be set the same on each
        """
        if new_mode not in ('standard', 'feed', 'video'):
            raise ValueError("unknown mode: %s" % new_mode)
        self.sort_key = getattr(self, 'sort_key_%s' % new_mode)

    # we don't define sort_key() directly instead, we define a version of it
    # for each mode we can be in, and set the sort_key attribute in
    # switch_mode()

    def sort_key_standard(self, info):
        return (info.album_sort_key,
                info.artist_sort_key,
                info.track)

    def sort_key_feed(self, info):
        # sort watched folders to the bottom
        if info.feed_url.startswith('dtv:directoryfeed:'):
            watched_folder_key = 1
        else:
            watched_folder_key = 0
        # We want watched folders to always be at the bottom, even if we
        # reverse the search.
        if self.reverse:
            watched_folder_key = -watched_folder_key
        return (watched_folder_key,
                info.feed_name.lower(),
                info.release_date)

    def sort_key_video(self, info):
        if info.show:
            show_name = info.show
        elif info.parent_sort_key:
            show_name = info.parent_sort_key
        elif info.feed_name:
            show_name = info.feed_name
        else:
            show_name = ''
        return (show_name,
                info.release_date)

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

class ShowSort(ItemSort):
    KEY = 'show'
    def sort_key(self, info):
        return info.show

class KindSort(ItemSort):
    KEY = 'kind'
    def sort_key(self, info):
        return info.kind

class PlaylistSort(ItemSort):
    """Sort that orders items by their order in the playlist.
    """
    KEY = 'playlist'

    def __init__(self, initial_items=None):
        ItemSort.__init__(self, True)
        self.reset_current_position()
        self.positions = {}
        # ascending works weirdly for playlist.  We always sort items in
        # their playlist order.  When the user asks to reverse the sort, we
        # reverse the actual order of items.  So self.reverse is always false,
        # and self.order_is_reversed tracks our internal notion if we've
        # reversed the order or not.
        self.order_is_reversed = False
        self.reverse = False
        if initial_items:
            for item in initial_items:
                self.positions[item.id] = self.current_postion.next()

    def reset_current_position(self):
        self.current_postion = itertools.count()

    def set_ascending(self, ascending):
        self.reverse = not ascending

    def add_items(self, item_list):
        if not self.order_is_reversed:
            self.add_items_at_end(item_list)
        else:
            self.add_items_at_start(item_list)

    def add_items_at_end(self, item_list):
        for item in item_list:
            if item.id not in self.positions:
                self.positions[item.id] = self.current_postion.next()

    def add_items_at_start(self, item_list):
        new_items = [i for i in item_list if i.id not in self.positions]
        new_count = len(new_items)
        # move current positions forward
        for key, pos in self.positions.iteritems():
            self.positions[key] = pos + new_count
        # add new positions
        for pos, item in enumerate(new_items):
            self.positions[item.id] = pos
        # fix current_postion
        self.current_postion = itertools.count(len(self.positions))

    def forget_items(self, id_list):
        for id in id_list:
            del self.positions[id]
        new_items = self.positions.items()
        new_items.sort(key=lambda row: row[1])
        self.reset_current_position()
        self.positions = {}
        for id, old_position in new_items:
            self.positions[id] = self.current_postion.next()

    def should_reverse_order(self, ascending):
        """Should we reverse the playlist order?
        
        This method is called after the user clicks on a sort header.  If the
        sort header direction is different then our internal notion of if we
        are reversed or not, then we return true.
        """
        return ascending == self.order_is_reversed

    def reverse_order(self):
        """Reverse the order of our playlist

        :returns: the new order as a list of ids
        """
        last_position = len(self.positions) - 1
        new_order = [None] * len(self.positions)
        for id_ in self.positions:
            index = last_position - self.positions[id_]
            self.positions[id_] = index
            new_order[index] = id_
        self.order_is_reversed = not self.order_is_reversed
        return new_order

    def set_new_order(self, id_order):
        self.reset_current_position()
        self.positions = dict((id, self.current_postion.next())
            for id in id_order)

    def move_ids_before(self, before_id, id_list):
        """Move ids around in the position list

        The ids in id_list will be placed before before_id.  If before_id is
        None, then they will be placed at the end of the list.

        :returns: new sort order as a list of ids
        """

        # calculate order of ids not in id_list
        moving = set(id_list)
        new_order = [id_ for id_ in self.positions if id_ not in moving]
        new_order.sort(key=lambda id_: self.positions[id_])
        # insert id_list into new_order
        if before_id is not None:
            insert_pos = new_order.index(before_id)
            new_order[insert_pos:insert_pos] = id_list
        else:
            new_order.extend(id_list)
        self.set_new_order(new_order)
        return new_order

    def sort_key(self, item):
        try:
            return self.positions[item.id]
        except KeyError:
            # Something wrong happened and the item is not in our internal
            # list.  Let's add it to the end to prevent endless crash reports.
            self.add_items([item])
            app.widgetapp.handle_soft_failure("getting playlist sort key",
                    'Key Error: %s' % item.id, with_exception=True)
            return self.positions[item.id]

    def items_will_change(self, added, changed, removed):
        self.add_items(added)

    def items_removed_from_source(self, removed):
        self.forget_items(removed)

DEFAULT_SORT = ArtistSort(False)

SORT_KEY_MAP = dict((sort.KEY, sort) for sort in util.all_subclasses(ItemSort))

def album_grouping(info):
    """Grouping function that groups infos by albums."""
    return (info.album_sort_key, info.artist_sort_key)

def feed_grouping(info):
    """Grouping function that groups infos by their feed."""
    return info.feed_id

def video_grouping(info):
    """Grouping function that groups infos for the videos tab.

    For this group, we try to figure out what "show" the item is in.  If the
    user has set a show we use that, otherwise we use the podcast.

    """
    if info.show:
        return info.show
    elif info.parent_sort_key:
        return info.parent_sort_key
    elif info.feed_name:
        return info.feed_name
    else:
        return None

class ItemList(object):
    """
    Attributes:

    model -- TableModel for this item list.  It contains these columns:
        * ItemInfo (object)
        * show_details flag (boolean)
        * counter used to change the progress throbber (integer)

    filter_set -- ItemFilterSet for this item list
    resort_on_update -- Should we re-sort the list when items change?
    """

    def __init__(self):
        self._sorter = DEFAULT_SORT
        self.model = widgetset.InfoListModel(self._sorter.sort_key,
                self._sorter.reverse)
        self.filter_set = itemfilter.ItemFilterSet()
        self.resort_on_update = False
        # maps ids -> items that are this list, but are filtered by our
        # ItemFilters
        self._hidden_items = {}

    def set_sort(self, sorter):
        self._sorter = sorter
        self.model.change_sort(sorter.sort_key, sorter.reverse)

    def set_resort_on_update(self, resort):
        self.resort_on_update = resort

    def resort(self):
        self.set_sort(self._sorter)

    def set_grouping(self, grouping):
        self.model.set_grouping(grouping)

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

    def get_iter(self, id_):
        """Get a TableView iter object for an id."""
        return self.model.iter_for_id(id_)

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

    def _insert_items(self, to_add):
        if len(to_add) == 0:
            return
        self.model.add_infos(to_add)

    def add_items(self, item_list):
        to_add = []
        for item in item_list:
            if self.filter_set.filter(item):
                to_add.append(item)
            else:
                self._hidden_items[item.id] = item
        self._insert_items(to_add)

    def update_items(self, changed_items):
        to_add = []
        to_remove = []
        to_update = []
        for info in changed_items:
            should_show = self.filter_set.filter(info)
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

    def select_filter(self, key):
        self.filter_set.select(key)

    def set_filters(self, filter_keys):
        self.filter_set.set_filters(filter_keys)

    def get_filters(self):
        return self.filter_set.active_filters

    def recalculate_hidden_items(self):
        info_list_at_start = self.model.info_list()

        newly_matching = []
        for item in self._hidden_items.values():
            if self.filter_set.filter(item):
                newly_matching.append(item)
                del self._hidden_items[item.id]
        self._insert_items(newly_matching)

        newly_unmatching_ids = []
        for item in info_list_at_start:
            if not self.filter_set.filter(item):
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
