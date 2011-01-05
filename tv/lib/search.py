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

"""search.py -- Indexed searching of items.

To make incremental search fast, we index the n-grams for each item.
"""

import collections
import logging
import os
import re

from miro import app
from miro import fileutil
from miro import ngrams
from miro import prefs
from miro.plat.utils import filename_to_unicode

QUOTEKILLER = re.compile(r'(?<!\\)"')
SLASHKILLER = re.compile(r'\\.')
WORDMATCHER = re.compile("\w+")
NGRAM_MAX = 5
SEARCHOBJECTS = {}

def _get_boolean_search(search_string):
    if not SEARCHOBJECTS.has_key(search_string):
        SEARCHOBJECTS[search_string] = BooleanSearch(search_string)
    return SEARCHOBJECTS[search_string]

class BooleanSearch:
    def __init__ (self, search_string):
        self.string = search_string
        self.positive_terms = []
        self.negative_terms = []
        self.parse_string()

    def parse_string(self):
        inquote = False
        i = 0
        while i < len (self.string) and self.string[i] == ' ':
            i += 1
        laststart = i
        while (i < len(self.string)):
            i = laststart
            while (i < len(self.string)):
                if self.string[i] == '"':
                    inquote = not inquote
                if not inquote and self.string[i] == ' ':
                    break
                if self.string[i] == '\\':
                    i += 1
                i += 1
            if inquote:
                self.process(self.string[laststart:])
            else:
                self.process(self.string[laststart:i])
            while i < len (self.string) and self.string[i] == ' ':
                i += 1
            laststart = i

    def process(self, substring):
        if substring[0] == '-':
            substring = substring[1:]
            term_list = self.negative_terms
        else:
            term_list = self.positive_terms
        substring = QUOTEKILLER.sub("", substring)
        substring = SLASHKILLER.sub(lambda x: x.group(0)[1], substring)
        #print substring
        term_list.append(substring.lower())

    def as_string(self):
        return self.string

def _calc_search_text(item_info):
    match_against = [ item_info.name, item_info.description ]
    match_against.append(item_info.artist)
    match_against.append(item_info.album)
    match_against.append(item_info.genre)
    if item_info.feed_name is not None:
        match_against.append(item_info.feed_name)
    if item_info.download_info and item_info.download_info.torrent:
        match_against.append(u'torrent')
    if item_info.video_path:
        filename = os.path.basename(item_info.video_path)
        match_against.append(filename_to_unicode(filename))
    return (' '.join(match_against)).lower()

def calc_ngrams(item_info):
    """Get the N-grams that we want to index for a ItemInfo object"""
    words = WORDMATCHER.findall(_calc_search_text(item_info))
    return ngrams.breakup_list(words, 1, NGRAM_MAX)

class ItemSearcher(object):
    """Index Item objects so that they can be searched quickly """

    def __init__(self):
        # map N-grams -> set of item ids
        self._ngram_map = collections.defaultdict(set)
        # map item id -> set of N-grams
        self._ngrams_for_item = {}
        self._initialized = False

    def initialize(self):
        """Initialize search data.

        This method might take a few seconds, it's safe to wait a while to
        invoke this.  If search() is called in the meantime, then we will
        initialize then.
        """
        if self._initialized:
            return
        logging.info("Loading item search data")
        for item_info in app.item_info_cache.all_infos():
            self._add_item(item_info)
        app.item_info_cache.connect("added", self.on_info_added)
        app.item_info_cache.connect("changed", self.on_info_changed)
        app.item_info_cache.connect("removed", self.on_info_removed)
        self._initialized = True

    def _add_item(self, item_info):
        for ngram in item_info.search_ngrams:
            self._ngram_map[ngram].add(item_info.id)
        self._ngrams_for_item[item_info.id] = set(item_info.search_ngrams)

    def _remove_item(self, item_info):
        for ngram in self._ngrams_for_item.pop(item_info.id):
            self._ngram_map[ngram].discard(item_info.id)

    def on_info_added(self, obj, item_info):
        self._add_item(item_info)

    def on_info_changed(self, obj, item_info):
        self._remove_item(item_info)
        self._add_item(item_info)

    def on_info_removed(self, obj, item_info):
        self._remove_item(item_info)

    def _ngrams_for_term(self, term):
        """Given a term, return a list of N-grams that we should search for.

        If the term is shorter than NGRAM_MAX, this is just the term itself.
        If it's longer, we split it up into a bunch of N-grams to search for.
        """
        if len(term) <= NGRAM_MAX:
            return [term]
        else:
            # Note that we only need to use the longest N-grams, since shorter
            # N-grams will just be substrings of those.
            return ngrams.breakup_word(term, NGRAM_MAX, NGRAM_MAX)

    def _term_search(self, term):
        grams = self._ngrams_for_term(term)
        rv = self._ngram_map[grams[0]]
        for gram in grams[1:]:
            rv.intersection_update(self._ngram_map[gram])
        return rv

    def search(self, search_text):
        """Search through the index items.

        :param search_text: search_text to search with

        :returns: set of ids that match the search
        """
        self.initialize()
        parsed_search = _get_boolean_search(search_text)

        if parsed_search.positive_terms:
            matching_ids = self._term_search(parsed_search.positive_terms[0])
            for term in parsed_search.positive_terms[1:]:
                matching_ids.intersection_update(self._term_search(term))
        else:
            matching_ids = set(self._ngrams_for_item.keys())

        for term in parsed_search.negative_terms:
            matching_ids.difference_update(self._term_search(term))
        return matching_ids

    def item_matches(self, item_id, search_text):
        """Test if a single item matches a search

        :param item_id: object id of the item to test
        :param search_text: search_text to search with

        :returns: True if the item matches the search string
        """
        self.initialize()
        parsed_search = _get_boolean_search(search_text)
        item_ngrams = self._ngrams_for_item[item_id]

        for term in parsed_search.positive_terms:
            if not set(self._ngrams_for_term(term)).issubset(item_ngrams):
                return False
        for term in parsed_search.negative_terms:
            if set(self._ngrams_for_term(term)).issubset(item_ngrams):
                return False
        return True
