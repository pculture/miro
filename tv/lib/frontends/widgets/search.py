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

"""search.py -- Manages video searches.
"""

import logging

from miro import signals
from miro import messages
from miro import searchengines

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
