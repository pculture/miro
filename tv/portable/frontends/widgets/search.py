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

"""search.py -- Manages video searches.
"""

from miro import messages
from miro import searchengines

class SearchManager(object):
    """Keeps track of search terms.

    Attributes:

      engine -- Last used search engine
      text -- Last search text
    """

    def __init__(self):
        self.engine = 'all'
        self.text = ''

    def set_search_info(self, engine, text):
        self.engine = engine
        self.text = text

    def perform_search(self, engine, text):
        self.set_search_info(engine, text)
        messages.Search(engine, text).send_to_backend()

    def save_search(self):
        m = messages.NewChannelSearchEngine(self._lookup_engine(), self.text)
        m.send_to_backend()

    def _lookup_engine(self):
        for engine in searchengines.get_search_engines():
            if engine.name == self.engine:
                return engine
        raise LookupError("Couldn't find search engine %r" % name)
