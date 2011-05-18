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

"""itemtrack.py -- Create and track ItemList objects

itemtrack's job is to create ItemLists and keep them updated.  It handles the
following things:
    - Sending TrackItems/StopTrackingItems messages
    - Filtering out items from the messages that don't match the search
    - Managing the life of an ItemList
"""

import weakref
import itertools
import logging

from miro import app
from miro import datastructures
from miro import messages
from miro import signals
from miro import search
from miro.frontends.widgets import itemlist
from miro.plat.frontends.widgets.threads import call_on_ui_thread

class ItemListTracker(signals.SignalEmitter):
    """ItemListTracker -- Track ItemLists

    ItemListTracker manages tracking the items for a given type/id.  When the
    first object connects to the initial-list method, ItemListTracker will
    send out the TrackItems message to the backend.  When all objects
    disconnect from the initial-list and items-changed method, then the
    StopTrackingItems message will be sent.

    ItemListTracker handles filtering out items that don't match a search via
    the ``set_search()`` method.

    Attributes:
        item_list -- ItemList object containing our items
    
    Signals:
        items-will-change (tracker) -- We are about to modify item_list
        initial-list (tracker, items) -- The initial item list was received
        items-changed (tracker, added, changed, removed) -- The item list
            changed
        items-removed-from-source (tracker, removed) - Items were permanently
            removed from the item list (as opposed to just filtered out by
            the filter). The passed items include all removed items, 
            irrespective of whether they currently are filtered out by the
            filter or not
    """



    # maps (type, id) -> ItemListTracker objects
    _live_trackers = weakref.WeakValueDictionary()

    @classmethod
    def create(cls, type_, id_):
        """Get a ItemListTracker 

        This method will return an existing ItemListTracker if one already
        exists for (type_, id_).  If not, it will create a new one.
        """
        key = (type_, id_)
        if key in cls._live_trackers:
            return cls._live_trackers[(type_, id_)]
        else:
            # need to do a little bit of fancy footwork here because
            # _live_trackers is a WeakValueDictionary.
            if type_ == 'playlist':
                tracker = PlaylistItemListTracker(type_, id_)
            else:
                tracker = ItemListTracker(type_, id_)
            retval = cls._live_trackers[key] = tracker
            return retval

    def __init__(self, type_, id_):
        """Create a new ItemListTracker

        Don't construct ItemListTracker's directly!  Instead use the
        create() factory method.
        """
        # FIXME: there's probably a better way of doing a factory method to
        # create ItemListTrackers.  I think a private constructor would be
        # ideal, but that's not really possible in python.
        signals.SignalEmitter.__init__(self, 'items-will-change',
                'initial-list', 'items-changed', 'items-removed-from-source')
        self.type = type_
        self.item_list = itemlist.ItemList()
        self.id = id_
        self.is_tracking = False
        self.search_filter = SearchFilter()
        self.saw_initial_list = False

    def connect(self, name, func, *extra_args):
        if not self.is_tracking:
            self._start_tracking()
        return signals.SignalEmitter.connect(self, name, func, *extra_args)

    def disconnect(self, callback_handle):
        signals.SignalEmitter.disconnect(self, callback_handle)
        if self.is_tracking and self._all_handlers_disconnected():
            self._stop_tracking()

    def disconnect_all(self):
        signals.Signals.disconnect_all(self)
        self._stop_tracking()

    def _all_handlers_disconnected(self):
        for callback_dict in self.signal_callbacks.values():
            if len(callback_dict) > 0:
                return False
        return True

    def _start_tracking(self):
        if self.is_tracking:
            return
        logging.debug("ItemListTracker -- tracking: %s, %s", self.type,
                self.id)
        self._send_track_items_message()
        app.info_updater.item_list_callbacks.add(self.type, self.id,
                self.on_item_list)
        app.info_updater.item_changed_callbacks.add(self.type, self.id,
                self.on_items_changed)
        self.is_tracking = True

    def _send_track_items_message(self):
        messages.TrackItems(self.type, self.id).send_to_backend()

    def _stop_tracking(self):
        if not self.is_tracking:
            return
        logging.debug("ItemListTracker -- stopping tracking: %s, %s",
                self.type, self.id)
        messages.StopTrackingItems(self.type, self.id).send_to_backend()
        app.info_updater.item_list_callbacks.remove(self.type, self.id,
                self.on_item_list)
        app.info_updater.item_changed_callbacks.remove(self.type, self.id,
                self.on_items_changed)
        self.is_tracking = False

    def on_item_list(self, message):
        self.add_initial_items(message.items)

    def is_filtering(self):
        """Check if we are filtering out any items."""
        return self.search_filter.is_filtering()

    def add_initial_items(self, items):
        self.saw_initial_list = True
        items = self.search_filter.filter_initial_list(items)
        self.emit('items-will-change', items, [], [])
        # call remove all to handle the race described in #16089.  We may get
        # multiple ItemList messages, in which case we want the last one to be
        # the one that sticks.
        self.item_list.remove_all()
        self.item_list.add_items(items)
        self.emit("initial-list", items)

    def on_items_changed(self, message):
        if not self.saw_initial_list:
            # another hack for #16089, if things get backed up in the wrong
            # way, we could get an ItemsChanged message for our old list,
            # before the ItemList message for our new one.
            return
        added, changed, removed = self.search_filter.filter_changes(
                message.added, message.changed, message.removed)
        self.emit('items-will-change', added, changed, removed)
        self.item_list.add_items(added)
        self.item_list.update_items(changed)
        self.item_list.remove_items(removed)
        #Note that the code in PlaybackPlaylist expects this signal order
        self.emit("items-removed-from-source", message.removed)
        self.emit("items-changed", added, changed, removed)

    def set_search(self, query):
        added, removed = self.search_filter.set_search(query)
        self.emit("items-will-change", added, [], removed)
        self.item_list.add_items(added)
        self.item_list.remove_items(removed)
        self.emit("items-changed", added, [], removed)

class PlaylistItemListTracker(ItemListTracker):
    """ItemListTracker for playlists.

    This class adds a playlist_sort attribute, that contains a
    itemlist.PlaylistSort object that is kept up to date.
    """
    def __init__(self, type_, id_):
        ItemListTracker.__init__(self, type_, id_)
        self.playlist_sort = itemlist.PlaylistSort()

    def do_items_will_change(self, added, changed, removed):
        self.playlist_sort.items_will_change(added, changed, removed)

    def do_items_removed_from_source(self, removed):
        self.playlist_sort.items_removed_from_source(removed)

class ManualItemListTracker(ItemListTracker):
    id_counter = itertools.count()

    @classmethod
    def create(cls, info_list):
        """Create a new ManualItemListTracker

        This method can safely by used, unlike regular ItemListTrackers
        """
        # overide the code to share ItemListTrackers, since it doesn't really
        # make sense for ManualItemListTracker.  Note: this could just be an
        # __init__ method, but I wanted to match the API of ItemListTracker
        # (BDK).
        my_unique_id = ('item-list-tracker-%d' %
                ManualItemListTracker.id_counter.next())
        self = ManualItemListTracker('manual', my_unique_id)
        self.info_list = info_list
        self.add_initial_items(info_list)
        return self

    def _send_track_items_message(self):
        messages.TrackItemsManually(self.id, self.info_list).send_to_backend()

class SearchFilter(object):
    """SearchFilter filter out non-matching items from item lists
    """
    def __init__(self):
        self.searcher = search.ItemSearcher()
        self.query = ''
        self.all_items = {} # maps id to item info
        self.matching_ids = set()
        self._pending_changes = datastructures.Fifo()
        self._index_pass_scheduled = False

    def is_filtering(self):
        return len(self.all_items) > len(self.matching_ids)

    def filter_initial_list(self, items):
        """Filter a list of incoming items.

        :param items: list of ItemInfos

        :returns: list of items that match our search
        """
        if not self.query:
            # special case, just send out the list and calculate the index
            # later
            self._pending_changes.enqueue((items, [], []))
            self._schedule_indexing()
            return items
        self._ensure_index_ready()
        self._add_items(items)
        self.matching_ids = self.searcher.search(self.query)
        return [i for i in items if i.id in self.matching_ids]

    def filter_changes(self, added, changed, removed):
        """Filter a list of incoming changes

        :param added: list of added ItemInfos
        :param changed: list of changed ItemInfos
        :param removed: list of removed ItemInfos ids

        :returns: (added, changed, removed), updated based on our search
        """
        if not self.query:
            # special case, just send out the list and calculate the index
            # later
            self._pending_changes.enqueue((added, changed, removed))
            self._schedule_indexing()
            return added, changed, removed
        self._ensure_index_ready()

        self._add_items(added)
        self._update_items(changed)
        self._remove_ids(removed)

        matches = self.searcher.search(self.query)
        old_matches = self.matching_ids

        added_filtered = [i for i in added if i.id in matches]
        remove_filtered = old_matches.intersection(removed)
        changed_filtered = []
        for info in changed:
            if info.id in matches:
                if info.id in old_matches:
                    changed_filtered.append(info)
                else:
                    added_filtered.append(info)
            elif info.id in old_matches:
                remove_filtered.add(info.id)
        self.matching_ids = matches
        return added_filtered, changed_filtered, remove_filtered

    def set_search(self, query):
        """Change the current search.

        :param query: new search to filter on

        :returns: (added, removed) based on the new search
        """
        self._ensure_index_ready()
        self.query = query
        matches = self.searcher.search(self.query)
        added = matches - self.matching_ids
        removed = self.matching_ids - matches
        self.matching_ids = matches
        added_infos = [self.all_items[id_] for id_ in added]
        return added_infos, removed

    def _add_items(self, items):
        for item in items:
            self.all_items[item.id] = item
            self.searcher.add_item(item)

    def _update_items(self, items):
        for item in items:
            self.all_items[item.id] = item
            try:
                self.searcher.update_item(item)
            except KeyError:
                # This happens when the item is not in the index
                # As a precaution, try out best to recover, log the error,
                # then just add the item.  (see #17152 for details).
                app.widgetapp.handle_soft_failure("Item Track update",
                        "Tried to update item not in index: %s" % item.id,
                        with_exception=True)
                self.searcher.add_item(item)

    def _remove_ids(self, id_list):
        for id_ in id_list:
            del self.all_items[id_]
            try:
                self.searcher.remove_item(id_)
            except KeyError:
                # This happens when the item is not in the index.  As a
                # precaution, try to recover.  log the error, then keep going.
                app.widgetapp.handle_soft_failure("Item Track update",
                        "Tried to update item not in index: %s" % id_,
                        with_exception=True)

    def _ensure_index_ready(self):
        if len(self._pending_changes) > 0:
            while len(self._pending_changes) > 0:
                (added, changed, removed) = self._pending_changes.dequeue()
                self._add_items(added)
                self._update_items(changed)
                self._remove_ids(removed)
            self.matching_ids = self.searcher.search(self.query)

    def _schedule_indexing(self):
        if not self._index_pass_scheduled:
            call_on_ui_thread(self._do_index_pass)
            self._index_pass_scheduled = True

    def _do_index_pass(self):
        self._index_pass_scheduled = False
        # find a chunk of items, process them, then schedule another call
        if len(self._pending_changes) == 0:
            return
        (added, changed, removed) = self._pending_changes.dequeue()
        self._add_items(added)
        self._update_items(changed)
        self._remove_ids(removed)
        if len(self._pending_changes) > 0:
            self._schedule_indexing()
        else:
            self.matching_ids = self.searcher.search(self.query)
