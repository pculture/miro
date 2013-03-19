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

"""itemlist.py -- Handles item data for our table views

This module defines ItemLists, which integres ItemTracker with the rest of the
widgets code.

It also defines several ItemTrackerQuery subclasses that correspond to tabs
in the interface.
"""

import collections

from miro import app
from miro import prefs
from miro.data import item
from miro.data import itemtrack
from miro.frontends.widgets import itemfilter
from miro.frontends.widgets import itemsort
from miro.plat.frontends.widgets.threads import call_on_ui_thread

class ItemList(itemtrack.ItemTracker):
    """ItemList -- Track a list of items for TableView

    ItemList extends ItemTracker to provide things we need to make implement
    the data model for our TableViews that contain lists of items.  The
    platform code takes uses ItemList to implement ItemListModel.

    Extra capabilities include:
        - set/get arbitrary attributes on items
        - grouping information
        - simpler interface to construct queries:
            - set_filters/select_filter changes the filters
            - set_sort changes the sort
    """

    # sentinel used to represent a group_info that hasn't been calculated
    NOT_CALCULATED = object()

    def __init__(self, tab_type, tab_id, sort=None, group_func=None,
                 filters=None, search_text=None):
        """Create a new ItemList

        Note: outside classes shouldn't call this directly.  Instead, they
        should use the app.item_list_pool.get() method.

        :param tab_type: type of tab that this list is for
        :param tab_id: id of the tab that this list is for
        :param sort: initial sort to use
        :param group_func: initial grouping to use
        :param filters: initial filters
        :param search_text: initial search text
        """
        self.tab_type = tab_type
        self.tab_id = tab_id
        self.base_query = self._make_base_query(tab_type, tab_id)
        self.item_attributes = collections.defaultdict(dict)
        self.filter_set = itemfilter.ItemFilterSet()
        if filters is not None:
            self.filter_set.set_filters(filters)
        if sort is None:
            self.sorter = itemsort.DateSort()
        else:
            self.sorter = sort
        self.search_text = search_text
        self.group_func = group_func
        itemtrack.ItemTracker.__init__(self, call_on_ui_thread,
                                       self._make_query(),
                                       self._make_item_source())

    def is_for_device(self):
        return self.tab_type.startswith('device-')

    def is_for_share(self):
        return self.tab_type == 'sharing'

    def device_id(self):
        # tab_id is the device_id + '-video' or '-audio'.  Remove the
        # suffix
        return self.tab_id.rsplit('-', 1)[0]

    def share_id(self):
        # - for sharing tabs the tab id "sharing-<share_id>"
        # - for playlist tabs, the tab id is
        #   "sharing-<share_id>-<playlist_id>"
        # This code should work for either
        return int(self.tab_id.split("-")[1])

    def _fetch_id_list(self):
        itemtrack.ItemTracker._fetch_id_list(self)
        self._reset_group_info()

    def _uncache_row_data(self, id_list):
        itemtrack.ItemTracker._uncache_row_data(self, id_list)
        # items have changed, so we need to reset all group info
        self._reset_group_info()

    def _make_base_query(self, tab_type, tab_id):
        if self.is_for_device():
            query = itemtrack.DeviceItemTrackerQuery()
        elif self.is_for_share():
            query = itemtrack.SharingItemTrackerQuery()
        else:
            query = itemtrack.ItemTrackerQuery()

        if tab_type == 'videos':
            query.add_condition('file_type', '=', 'video')
            query.add_condition('deleted', '=', False)
            if not app.config.get(prefs.SHOW_PODCASTS_IN_VIDEO):
                self.add_in_podcast_to_query(query)
        elif tab_type == 'music':
            if not app.config.get(prefs.SHOW_PODCASTS_IN_MUSIC):
                self.add_in_podcast_to_query(query)
            query.add_condition('file_type', '=', 'audio')
            query.add_condition('deleted', '=', False)
        elif tab_type == 'others':
            query.add_condition('file_type', '=', 'other')
            query.add_condition('deleted', '=', False)
        elif tab_type == 'search':
            query.add_condition('feed.orig_url', '=', 'dtv:search')
        elif tab_type == 'downloading':
            sql = ("((remote_downloader.state IN ('downloading', 'uploading', "
                   "'paused', 'uploading-paused', 'offline')) OR "
                   "(remote_downloader.state = 'failed' AND "
                   "feed.orig_url = 'dtv:manualFeed') OR "
                   "pending_manual_download) AND "
                   "remote_downloader.main_item_id=item.id")
            columns = ['remote_downloader.state',
                       'remote_downloader.main_item_id',
                       'feed.orig_url',
                       'pending_manual_download']
            query.add_complex_condition(columns, sql, ())
        elif tab_type == 'feed':
            query.add_condition('feed_id', '=', tab_id)
        elif tab_type == 'feed-folder' and tab_id == 'feed-base-tab':
            # all feeds tab
            query.add_condition('feed.orig_url', 'IS NOT', None)
            query.add_condition('feed.orig_url', '!=', 'dtv:manualFeed')
            query.add_condition('feed.orig_url', 'NOT LIKE', 'dtv:search%')
        elif tab_type == 'feed-folder':
            # NOTE: this also depends on the folder_id column of feed, but we
            # don't track that in any way.  If that changed while the user was
            # viewing the display, then they wouldn't see the changes.
            # However, the only way for this to change is drag and drop, so we
            # can ignore this.
            sql = ("feed_id in "
                   "(SELECT feed.id FROM feed WHERE feed.folder_id=?)")
            query.add_complex_condition(['feed_id'], sql, (tab_id,))
        elif tab_type == 'folder-contents':
            query.add_condition('parent_id', '=', tab_id)
        elif tab_type == 'playlist':
            query.add_condition('playlist_item_map.playlist_id', '=', tab_id)
        elif tab_type == 'device-video':
            query.add_condition('file_type', '=', u'video')
        elif tab_type == 'device-audio':
            query.add_condition('file_type', '=', u'audio')
        elif tab_type == 'sharing' and tab_id.startswith("sharing-"):
            # browsing a playlist on a share
            id_components = tab_id.split("-")
            if len(id_components) == 2:
                # browsing an entire share, no filters needed
                pass
            else:
                # browsing a playlist
                playlist_id = id_components[-1]
                if playlist_id == 'audio':
                    query.add_condition('file_type', '=', u'audio')
                elif playlist_id == 'video':
                    query.add_condition('file_type', '=', u'video')
                elif playlist_id == 'podcast':
                    query.add_condition(
                        'sharing_item_playlist_map.playlist_id', '=',
                        u'podcast')
                elif playlist_id == 'playlist':
                    query.add_condition(
                        'sharing_item_playlist_map.playlist_id', '=',
                        u'playlist')
                else:
                    query.add_condition(
                        'sharing_item_playlist_map.playlist_id', '=',
                        int(playlist_id))

        elif tab_type == 'sharing':
            # browsing an entire share, we don't need any filters on the query
            pass
        elif tab_type == 'manual':
            # for the manual tab, tab_id is a list of ids to play
            id_list = tab_id
            placeholders = ",".join("?" for i in xrange(len(id_list)))
            sql = "item.id IN (%s)" % placeholders
            query.add_complex_condition(['id'], sql, id_list)
        else:
            raise ValueError("Can't handle tab (%r, %r)" % (tab_type, tab_id))
        return query

    def add_in_podcast_to_query(self, query):
        columns = ['feed.orig_url', 'is_file_item']
        sql = ("feed.orig_url IN ('dtv:manualFeed', 'dtv:searchDownloads', "
               "'dtv:search') OR is_file_item")
        query.add_complex_condition(columns, sql)

    def _make_item_source(self):
        if self.is_for_device():
            device_info = app.tabs['connect'].get_tab(self.device_id())
            return item.DeviceItemSource(device_info)
        elif self.is_for_share():
            share_info = app.tabs['connect'].get_tab('sharing-%s' %
                                                     self.share_id())
            return item.SharingItemSource(share_info)
        else:
            return item.ItemSource()

    def _make_query(self):
        query = self.base_query.copy()
        self.filter_set.add_to_query(query)
        self.sorter.add_to_query(query)
        if self.search_text:
            query.set_search(self.search_text)
        return query

    def _update_query(self):
        self.change_query(self._make_query())

    # sorts/filters/search
    def select_filter(self, key):
        self.filter_set.select(key)
        self._update_query()

    def set_filters(self, filter_keys):
        self.filter_set.set_filters(filter_keys)
        self._update_query()

    def get_filters(self):
        return self.filter_set.active_filters

    def add_extension_filters(self, filters):
        return self.filter_set.add_extension_filters(filters)

    def set_sort(self, sorter):
        self.sorter = sorter
        self._update_query()

    def set_search(self, search_text):
        self.search_text = search_text
        self._update_query()

    def refresh_query(self):
        self.base_query = self._make_base_query(self.tab_type, self.tab_id)
        self._update_query()

    # attributes
    def set_attr(self, item_id, name, value):
        self.item_attributes[item_id][name] = value

    def get_attr(self, item_id, name, default=None):
        return self.item_attributes[item_id].get(name, default)

    def get_attrs(self, item_id):
        return self.item_attributes[item_id]

    def unset_attr(self, item_id, name):
        if name in self.item_attributes[item_id]:
            del self.item_attributes[item_id][name]

    # grouping
    def get_group_info(self, row):
        """Get the info about the group an info is inside.

        This method fetches the index of the info inside the group, the total
        size of the group, and the first info in the group.

        :returns: an (index, count, first_info) tuple
        :raises ValueError: if no groupping is set
        """
        if self.group_func is None:
            raise ValueError("no grouping set")
        if self.group_info[row] is ItemList.NOT_CALCULATED:
            self._calc_group_info(row)
        return self.group_info[row]

    def get_group_top(self, item_id):
        """Get the first info for an item's group.

        :param item_id: id of an item in the group
        """
        row = self.get_index(item_id)
        index, count, first_info = self.get_group_info(row)
        return first_info

    def get_grouping(self):
        """Get the function set with set_grouping."""
        return self.group_func

    def set_grouping(self, func):
        """Set a grouping function for this info list.

        Grouping functions input info objects and return values that will be
        used to segment the list into groups.  Adjacent infos with the same
        grouping value are part of the same group.

        get_group_info() can be used to find the position of an info inside
        its group.
        """
        self.group_func = func
        self._reset_group_info()

    def _reset_group_info(self):
        self.group_info = [ItemList.NOT_CALCULATED] * len(self)

    def _calc_group_info(self, row):
        # FIXME: for normal item lists, this is fairly fast, but it is slow in
        # a specific case:
        #
        # When the group function returns the same value for many items and
        # those items need to be loaded.  This actually can happen pretty
        # easily when you add a bunch of music files to miro, and we haven't
        # run mutagen on them yet.  In that case, when you first switch to the
        # music tab, basically all items will be in the same group.
        key = self.group_func(self.get_row(row))
        if key is None:
            # if group_func returns None, then put this item in a group by
            # itself.
            self.group_info[row] = (0, 1, self.get_row(row))
            return
        start = end = row
        while (start > 0 and
               self.group_func(self.get_row(start-1)) == key):
            start -= 1
        while (end < len(self) - 1 and
               self.group_func(self.get_row(end+1)) == key):
            end += 1
        total = end - start + 1
        for row in xrange(start, end+1):
            self.group_info[row] = (row-start, total, self.get_row(start))

class ItemTrackerUpdater(object):
    """Keep a list of ItemTrackers and call on_item_changes when needed.

    Note that this class is mostly used for ItemList objects, which works
    since it derives from ItemTracker.  However, it can also be used for raw
    ItemTrackers.
    """

    def __init__(self):
        self.trackers = set()
        self.device_trackers = set()
        self.sharing_trackers = set()

    def _set_for_tracker(self, item_tracker):
        source_type_map = {
            item.ItemSource: self.trackers,
            item.DeviceItemSource: self.device_trackers,
            item.SharingItemSource: self.sharing_trackers,
        }
        return source_type_map[type(item_tracker.item_source)]

    def add_tracker(self, item_tracker):
        self._set_for_tracker(item_tracker).add(item_tracker)

    def remove_tracker(self, item_tracker):
        try:
            self._set_for_tracker(item_tracker).remove(item_tracker)
        except KeyError:
            logging.warn("KeyError in ItemTrackerUpdater.remove_tracker")

    def on_item_changes(self, message):
        for tracker in self.trackers:
            tracker.on_item_changes(message)

    def on_device_item_changes(self, message):
        for tracker in self.device_trackers:
            tracker.on_item_changes(message)

    def on_sharing_item_changes(self, message):
        for tracker in self.sharing_trackers:
            tracker.on_item_changes(message)

class ItemListPool(object):
    """Pool of ItemLists that the frontend is using.

    This class keeps track of all active ItemList objects so that we can avoid
    creating 2 ItemLists for the same tab.  This helps with performance
    because we don't have to process the ItemChanges message twice.  Also, we
    want changes to the item list to be shared.  For example, if a user is
    playing items from a given tab and they change the filters on that tab, we
    want the PlaybackPlaylist to reflect those changes.
    """
    def __init__(self):
        self.all_item_lists = set()
        self._refcounts = {}

    def get(self, tab_type, tab_id, sort=None, group_func=None, filters=None,
           search_text=None):
        """Get an ItemList to use.

        This method will first try to re-use an existing ItemList from the
        pool.  If it can't, then a new ItemList will be created.

        sort, group_func, and filters are only used if a new ItemList is
        created.

        :returns: ItemList object.  When you are done with it, you must pass
        the ItemList to the release() method.
        """
        if tab_type != u'manual':
            for obj in self.all_item_lists:
                if obj.tab_type == tab_type and obj.tab_id == tab_id:
                    self._refcounts[obj] += 1
                    return obj
        # no existing list found, make new list
        new_list = ItemList(tab_type, tab_id, sort, group_func, filters,
                            search_text)
        self.all_item_lists.add(new_list)
        app.item_tracker_updater.add_tracker(new_list)
        self._refcounts[new_list] = 1
        return new_list

    def add_ref(self, item_list):
        """Add a reference to an existing ItemList

        Use this method if you are given an ItemList by another component and
        intend on keeping it around.  The ItemList will stay in the poll until
        both components call release()
        """
        if item_list in self._refcounts:
            self._refcounts[item_list] += 1
        else:
            raise ValueError("%s has already been released" % item_list)

    def release(self, item_list):
        """Release an item list.

        Call this when you're done using an ItemList.  Once this has been
        called for each time the list has been returned from get(), then that
        list will be removed from the pool and no longer get callbacks for the
        ItemChanges message.
        """
        self._refcounts[item_list] -= 1
        if self._refcounts[item_list] <= 0:
            self.all_item_lists.remove(item_list)
            del self._refcounts[item_list]
            item_list.destroy()
            app.item_tracker_updater.remove_tracker(item_list)

# grouping functions
def album_grouping(info):
    """Grouping function that groups infos by albums."""
    if (info.album_artist_sort_key != (u'',) or
        info.album_sort_key != (u'',)):
        return (info.album_artist_sort_key, info.album_sort_key)
    else:
        return None

def feed_grouping(info):
    """Grouping function that groups infos by their feed."""
    return info.feed_id

def video_grouping(info):
    """Grouping function that groups infos for the videos tab.

    For this group, we try to figure out what "show" the item is in.  If the
    user has set a show we use that, otherwise we use the podcast.

    """
    if info.show is not None:
        return info.show
    elif info.parent_title is not None:
        return info.parent_title_for_sort
    else:
        return None
