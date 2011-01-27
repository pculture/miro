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

"""search.py -- Manages video searches.
"""

import logging

from miro import search
from miro import signals
from miro import messages
from miro import searchengines
from miro.plat.frontends.widgets.threads import call_on_ui_thread

class SearchManager(signals.SignalEmitter):
    """Keeps track of search terms.

    :attribute engine: Last used search engine
    :attribute text: Last search text

    :signal search-started: (search_manager)
    :signal search-complete: (search_manager, result_count)
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('search-started')
        self.create_signal('search-complete')
        self.engine = searchengines.get_last_engine().name
        self.text = ''
        self.searching = False

    def set_search_info(self, engine, text):
        if not searchengines.get_engine_for_name(engine):
            logging.warn('Manager asked to set engine to non-existent %s',
                         engine)
            self.perform_search(searchengines.get_last_engine().name, '')
            return
        self.engine = engine
        self.text = text
        searchengines.set_last_engine(self.engine)

    def perform_search(self, engine=None, text=None):
        if engine is not None and text is not None:
            self.set_search_info(engine, text)
            searchengines.set_last_engine(self.engine)
        if self.text == "LET'S TEST MIRO'S FRONTEND CRASH REPORTER TODAY":
            raise searchengines.IntentionalCrash("intentional error here")
        messages.Search(self.engine, self.text).send_to_backend()
        self.searching = True
        self.emit('search-started')

    def save_search(self):
        m = messages.NewFeedSearchEngine(
            searchengines.get_engine_for_name(self.engine), self.text)
        m.send_to_backend()

    def handle_search_complete(self, message):
        if message.engine == self.engine and message.query == self.text:
            # make sure that the search complete is the current one
            self.searching = False
            self.emit('search-complete', message.result_count)

class InlineSearchMemory(object):
    """Remembers inline searches the user has performed """

    def __init__(self):
        self._memory = {}

    def set_search(self, typ, id_, text):
        self._memory[(typ, id_)] = text

    def get_search(self, typ, id_):
        return self._memory.get((typ, id_), '')

    def forget_search(self, typ, id_):
        # We should call this when channels/playlists get deleted to
        # free up the memory, but it's so small that it's not worth
        # worrying about.
        try:
            del self._memory[(typ, id_)]
        except KeyError:
            pass

class SearchFilter(signals.SignalEmitter):
    """SearchFilter filter out non-matching items from item lists

    SearchFilter receives incomming ItemList and ItemsChanged messages,
    calculates which items match the search, then outputs "initial-list" and
    "items-changed" messages based on the results
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'initial-list', 'items-changed')
        self.searcher = search.ItemSearcher()
        self.query = ''
        self.all_items = {} # maps id to item info
        self.matching_ids = set()
        self._pending_adds = []
        self._pending_changes = []
        self._pending_removals = []

    def handle_item_list(self, message):
        if not self.query:
            # special case, just send out the list and calculate the index
            # later
            self.emit("initial-list", message.items)
            self._pending_adds.extend(message.items)
            self._schedule_indexing()
            return
        self._ensure_index_ready()
        self._add_items(message.items)
        matches = self.searcher.search(self.query)
        self.emit("initial-list",
                [i for i in message.items if i.id in matches])
        self.matching_ids = matches

    def handle_items_changed(self, message):
        if not self.query:
            # special case, just send out the list and calculate the index
            # later
            self.emit('items-changed', message.added, message.changed,
                    message.removed)
            self._pending_adds.extend(message.added)
            self._pending_changes.extend(message.changed)
            self._pending_removals.extend(message.removed)
            self._schedule_indexing()
            return
        self._ensure_index_ready()

        self._add_items(message.added)
        self._update_items(message.changed)
        self._remove_ids(message.removed)

        matches = self.searcher.search(self.query)
        old_matches = self.matching_ids

        added = [i for i in message.added if i.id in matches]
        removed = old_matches.intersection(message.removed)
        changed = []
        for info in message.changed:
            if info.id in matches:
                if info.id in old_matches:
                    changed.append(info)
                else:
                    added.append(info)
            elif info.id in old_matches:
                removed.add(info.id)
        self.emit('items-changed', added, changed, removed)
        self.matching_ids = matches

    def set_search(self, query):
        self._ensure_index_ready()
        self.query = query
        matches = self.searcher.search(self.query)
        added = matches - self.matching_ids
        removed = self.matching_ids - matches
        added = [self.all_items[id_] for id_ in added]
        self.emit('items-changed', added, [], removed)

        self.matching_ids = matches

    def _add_items(self, items):
        for item in items:
            self.all_items[item.id] = item
            self.searcher.add_item(item)

    def _update_items(self, items):
        for item in items:
            self.all_items[item.id] = item
            self.searcher.update_item(item)

    def _remove_ids(self, id_list):
        for id_ in id_list:
            del self.all_items[id_]
            self.searcher.remove_item(id_)

    def _ensure_index_ready(self):
        if (self._pending_adds or self._pending_changes
                or self._pending_removals):
            self._add_items(self._pending_adds)
            self._update_items(self._pending_changes)
            self._remove_ids(self._pending_removals)
            self._pending_adds = []
            self._pending_changes = []
            self._pending_removals = []
            self.matching_ids = self.searcher.search(self.query)

    def _schedule_indexing(self):
        call_on_ui_thread(self._do_index_pass)

    def _do_index_pass(self):
        # find a chunk of items, process them, then schedule another call
        CHUNK_SIZE = 250
        if self._pending_adds:
            processor = self._add_items
            pending_list = self._pending_adds
        elif self._pending_changes:
            processor = self._update_items
            pending_list = self._pending_changes
        elif self._pending_removals:
            processor = self._remove_ids
            pending_list = self._pending_removals
        else:
            self.matching_ids = self.searcher.search(self.query)
            return # all done
        # process the last CHUNK_SIZE elements of the list, then remove them
        processor(pending_list[-CHUNK_SIZE:])
        pending_list[-CHUNK_SIZE:] = []
        self._schedule_indexing()
