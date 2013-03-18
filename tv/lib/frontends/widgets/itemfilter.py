# Miro - an RSS based video player application
# Copyright (C) 2011
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

"""itemfilter.py -- Filter out items from item lists

ItemFilter is a base class for item filters.  They handle determining what
items should be filtered out of an item list.  They also handle
selecting/deselecting other ItemFilters when they are first activated (most
filters deselect all other filters, but some can be used together).

ItemFilterSet handles keeping track of what filters are available and which
are selected for a given item list.
"""

from miro import app
from miro import util
from miro.gtcache import gettext as _
from miro.gtcache import declarify

class ItemFilter(object):
    """Base class for item filters.

    To create a new item filter you must:
      - define key, which must be a unique string
      - define user_label
      - define the filter() method()
      - (optionally) override the switch_to_filter() method
    """
    key = None

    def add_to_query(self, item_tracker_query):
        """Add this filter to an ItemTrackerQuery

        subclasses must override this
        """
        # TODO: This is the new interface for ItemFilter.  We need to
        # implement this method on all subclasses.
        raise NotImplementedError()

    def switch_to_filter(self, previous_filters):
        """select/deselect filters when this one is selected

        By default, we select this filter and deselect all others.

        :param previous_filters: set of previously active filters
        :returns: set of new active filters
        """
        return set((self.key,))

    @staticmethod
    def lookup_class(key):
        """Find a ItemFilter subclass for a key."""

        for cls in util.all_subclasses(ItemFilter):
            if cls.key == key:
                return cls
        hook_results = api.hook_invoke('item_list_filters', self.type,
                self.id)
        for filter_list in hook_results:
            for filter_ in filter_list:
                if filter_.key == key:
                    return filter_
        raise KeyError(key)

    # maps keys to ItemFilter objects
    _cached_filters = {}
    @staticmethod
    def get_filter(key):
        """Factory method to create an ItemFilter subclass from its key."""
        try:
            return ItemFilter._cached_filters[key]
        except KeyError:
            filter = ItemFilter.lookup_class(key)()
            ItemFilter._cached_filters[key] = filter
            return filter

class ItemFilterSet(object):
    def __init__(self):
        """Create a new ItemFilterSet

        By default only the all filter will be available.
        """
        # set of filter keys currently active
        self.active_filters = set()
        # list of ItemFilter objects currently active
        self.active_filter_objects = []
        # select the 'all' filter
        self.select('all')

    def select(self, key):
        """Select a new filter

        This method should be used when a user selects a new filter.  We will
        apply our selection logic to determine if other filters should stay
        active, or if new ones should also select.
        """

        # get the filter we want to add
        filter_ = ItemFilter.get_filter(key)
        # let the filter figure out what other filters to select/deselect
        new_active_filters = filter_.switch_to_filter(self.active_filters)
        self.set_filters(new_active_filters)

    def set_filters(self, filter_keys):
        """Set the filters to be a specific set.

        No validation is used to check that the set is valid.

        :raises KeyError: one of the filter keys is not valid
        """
        # fetch the filters first.  This way we won't change our attributes in
        # case of a KeyError.
        filter_objs = [ItemFilter.get_filter(k) for k in filter_keys]
        self.active_filters = set(filter_keys)
        self.active_filter_objects = filter_objs

    def add_to_query(self, query):
        """Add conditions to an ItemTrackerQuery object """
        for f in self.active_filter_objects:
            f.add_to_query(query)

# define the actual filter classes we use

class ItemFilterAll(ItemFilter):
    """Filter that shows all items."""
    key = u'all'
    # this "All" is different than other "All"s in the codebase, so it
    # needs to be clarified
    user_label = declarify(_('View|All'))

    def add_to_query(self, query):
        return

class ItemFilterAudioVideoHelper(ItemFilter):
    """Item filters that work in conjunction with the audio/video filters."""

    def switch_to_filter(self, previous_filters):
        # allow audio/video filters to remain
        rv = set((self.key,))
        for filter_ in (u'audio', u'video'):
            if filter_ in previous_filters:
                rv.add(filter_)
        return rv

class ItemFilterUnplayed(ItemFilterAudioVideoHelper):
    """Filter for unplayed items."""
    key = u'unplayed'
    user_label = _('Unplayed')

    def add_to_query(self, query):
        query.add_condition('filename', 'IS NOT', None)
        query.add_condition('watched_time', 'IS', None)

class ItemFilterDownloaded(ItemFilterAudioVideoHelper):
    """Filter for downloaded items."""
    key = u'downloaded'
    user_label = _('Downloaded')

    def add_to_query(self, query):
        query.add_condition('downloaded_time', 'IS NOT', None)
        query.add_condition('expired', '=', 0)

class ItemFilterAudioVideo(ItemFilter):
    """Filter for audio/video on the all podcast tab."""

    def switch_to_filter(self, previous_filters):
        # allow downloaded/unplayed filters to remain
        rv = set((self.key,))
        for filter_ in (u'downloaded', u'unplayed'):
            if filter_ in previous_filters:
                rv.add(filter_)
        # make sure that at either downloaded or unplayed is selected
        if u'unplayed' not in rv and u'downloaded' not in rv:
            rv.add(u'downloaded')
        return rv

class ItemFilterVideo(ItemFilterAudioVideo):
    """Filter for video items."""
    key = u'video'
    user_label = _('Video')

    def add_to_query(self, query):
        query.add_condition('file_type', '=', 'video')

class ItemFilterAudio(ItemFilterAudioVideo):
    """Filter for audio items."""
    key = u'audio'
    user_label = _('Audio')

    def add_to_query(self, query):
        query.add_condition('file_type', '=', 'audio')

class ItemFilterWatchedFolderVideo(ItemFilter):
    """Filter for video items in watch folders.

    This works like the Video filter, but it doesn't automatically select
    other filters when selected
    """
    key = u'wf-video'
    user_label = _('Video')

    def add_to_query(self, query):
        query.add_condition('file_type', '=', 'video')

class ItemFilterAudio(ItemFilter):
    """Filter for audio items in watch folders.

    This works like the Audio filter, but it doesn't automatically select
    other filters when selected
    """
    key = u'wf-audio'
    user_label = _('Audio')

    def add_to_query(self, query):
        query.add_condition('file_type', '=', 'audio')

class ItemFilterMovies(ItemFilter):
    """Filter for movie items."""
    key = u'movies'
    user_label = _('Movies')

    def add_to_query(self, query):
        query.add_condition('kind', '=', 'movie')

class ItemFilterShows(ItemFilter):
    """Filter for show items."""
    key = u'shows'
    user_label = _('Shows')

    def add_to_query(self, query):
        query.add_condition('kind', '=', 'show')

class ItemFilterClips(ItemFilter):
    """Filter for clip items."""
    key = u'clips'
    user_label = _('Clips')

    def add_to_query(self, query):
        query.add_condition('kind', '=', 'clip')

class ItemFilterPodcasts(ItemFilter):
    """Filter for podcast items.

    Not: this means the user flagged the item as a podcast somehow, not that
    we downloaded it from a feed
    """
    key = u'podcasts'
    user_label = _('Podcasts')

    def add_to_query(self, query):
        query.add_condition('kind', '=', u'podcast')

def get_label(key):
    """Get the label to use for a filter key."""
    return ItemFilter.get_filter(key).user_label
