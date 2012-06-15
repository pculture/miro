# Miro - an RSS based video player application
# Copyright (C) 2012
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

"""itemsort.py -- Define sorts for item lists.

This module defines the ItemSort base class and subclasses that define
concrete ways of sorting item lists.
"""

from miro import util

class ItemSort(object):
    """Class that sorts items in an item list.

    :attribute columns: list of columns to pass to set_order_by().  These
    should specify an ascending search.  Subclasses must set this.

    :attribute key: string specifying the name of the column for an ItemView
    that this sort should be used for.  Subclasses must set this.
    """

    def __init__(self, ascending=True):
        self.ascending = ascending

    def is_ascending(self):
        return self.ascending

    def reverse_columns(self):
        """Generate columns for a reverse search

        By default, we just negate every column in self.columns.  Subclasses
        can override this if they want different behavior.
        """
        def reverse_term(term):
            if term[0] == '-':
                return term[1:]
            else:
                return '-' + term
        return [reverse_term(t) for t in self.columns]

    def add_to_query(self, query):
        if self.ascending:
            query.set_order_by(*self.columns)
        else:
            query.set_order_by(*self.reverse_columns())

class TitleSort(ItemSort):
    key = 'name'
    columns = ['title']

class DateSort(ItemSort):
    key = 'date'
    columns = ['release_date']

class ArtistSort(ItemSort):
    key = 'artist'
    # FIXME: should sort using the result of name_sort_key rather than the raw
    # values
    columns = ['artist', 'album', 'track']

class AlbumSort(ItemSort):
    key = 'album'
    # FIXME: should sort using the result of name_sort_key rather than the raw
    # values
    columns = ['album', 'track']

class FeedNameSort(ItemSort):
    # FIXME: need to implement this
    key = 'feed-name'
    columns = ['id']

SORT_KEY_MAP = dict((sort.key, sort) for sort in util.all_subclasses(ItemSort))
