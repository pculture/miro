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

    :attribute key: string specifying the name of the column for an ItemView
    that this sort should be used for.  Subclasses must set this.

    :attribute columns: list of columns to pass to set_order_by().  These
    should specify an ascending search.  Subclasses must set this.

    :attribute collations: list of collations for each column.  By default
    this is None, which specifies the default collations
    """
    collations = None

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
            query.set_order_by(self.columns, self.collations)
        else:
            query.set_order_by(self.reverse_columns(), self.collations)

class TitleSort(ItemSort):
    key = 'name'
    columns = ['title']
    collations = ['name']

class DateSort(ItemSort):
    key = 'date'
    columns = ['release_date']

class ArtistSort(ItemSort):
    key = 'artist'
    columns = ['artist', 'album', 'track']
    collations = ['name', 'name', None]

class AlbumSort(ItemSort):
    key = 'album'
    columns = ['album', 'track']
    collations = ['name', None]

class FeedNameSort(ItemSort):
    key = 'feed-name'
    columns = ['parent_title', 'feed_id', 'parent_id']

class StateCircleSort(ItemSort):
    # Weird sort, this one is for when the user clicks on the header above the
    # status bumps.  It's almost the same as StatusSort, but there isn't a
    # bump for expiring.
    key = 'state'
    def add_to_query(self, query):
        sql = ("CASE "
               # downloading
               "WHEN remote_downloader.state IN ('downloading', 'paused') OR "
               "pending_manual_download THEN 1 "
               # unwatched
               "WHEN item.filename IS NOT NULL AND was_downloaded AND "
               "watched_time IS NULL THEN 2 "
               # new
               "WHEN new THEN 3 "
               # other
               "ELSE 4 "
               "END")
        if not self.ascending:
            sql += ' DESC'
        columns = ['remote_downloader.state', 'pending_manual_download',
                   'filename', 'was_downloaded', 'watched_time', 'new']
        query.set_complex_order_by(columns, sql)

class StatusSort(ItemSort):
    key = 'status'
    def add_to_query(self, query):
        sort1 = ("CASE "
                 # new
                 "WHEN new THEN 0 "
                 # downloading
                 "WHEN remote_downloader.state IN ('downloading', 'paused') OR "
                 "pending_manual_download THEN 2 "
                 # unwatched
                 "WHEN item.filename IS NOT NULL AND was_downloaded AND "
                 "watched_time IS NULL THEN 3 "
                 # expiring
                 "WHEN item.filename IS NOT NULL AND was_downloaded AND "
                 "NOT keep AND watched_time IS NOT NULL THEN 4 "
                 # other
                 "ELSE 1 "
                 "END")
        sort2 = ("CASE "
                 # for expiring items, our secondary sort is the watched time,
                 # this makes items that expire sooner appear on top.
                 "WHEN item.filename IS NOT NULL AND was_downloaded AND "
                 "NOT keep AND watched_time IS NOT NULL THEN watched_time "
                 # for other items we don't care.  Just use id.
                 "ELSE item.id "
                 "END")

        if self.ascending:
            sql = "%s, %s" % (sort1, sort2)
        else:
            sql = "%s DESC, %s DESC" % (sort1, sort2)
        columns = ['remote_downloader.state', 'pending_manual_download',
                   'filename', 'was_downloaded', 'watched_time', 'new',
                   'keep',
                  ]
        query.set_complex_order_by(columns, sql)

class LengthSort(ItemSort):
    key = 'length'
    columns = ['duration']

class DateAddedSort(ItemSort):
    key = 'date-added'
    columns = ['creation_time']

class SizeSort(ItemSort):
    # FIXME: need to implement this.
    key = 'size'
    columns = ['id']

class DescriptionSort(ItemSort):
    key = 'description'

    def add_to_query(self, query):
        sql = ("CASE "
               # downloading
               "WHEN description IS NOT NULL "
               "THEN description "
               "ELSE entry_description "
               "END collate name")
        if not self.ascending:
            sql += ' DESC'
        columns = ['description', 'entry_description' ]
        query.set_complex_order_by(columns, sql)

class FileTypeSort(ItemSort):
    key = 'file-type'
    columns = ['file_type']

class RatingSort(ItemSort):
    # TODO: should this also include auto rating?
    key = 'rating'
    columns = ['rating']

class GenreSort(ItemSort):
    key = 'genre'
    columns = ['genre']

class ShowSort(ItemSort):
    key = 'show'
    columns = ['show']

class TrackSort(ItemSort):
    key = 'track'
    columns = ['track']

class YearSort(ItemSort):
    key = 'year'
    columns = ['year']

class VideoKindSort(ItemSort):
    key = 'kind'
    columns = ['kind']

class MultiRowAlbum(ItemSort):
    # FIXME need to implement this
    key = 'multi-row-album'
    columns = ['id']

    def switch_mode(self, mode):
        pass

class DRMSort(ItemSort):
    key  = 'drm'
    columns = ['-has_drm']

class RateSort(ItemSort):
    key  = 'rate'
    columns = ['remote_downloader.rate']

class ETASort(ItemSort):
    key  = 'eta'
    columns = ['remote_downloader.eta']

class TorrentDetailsSort(ItemSort):
    # FIXME: need to implement this
    key  = 'torrent-details'
    columns = ['id']

class PlaylistSort(ItemSort):
    key  = 'playlist'
    columns = ['playlist_item_map.position']

SORT_KEY_MAP = dict((sort.key, sort) for sort in util.all_subclasses(ItemSort))
