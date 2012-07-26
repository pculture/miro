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

"""``miro.frontends.widgets.widgetstatestore`` - Stores the state of the
Widgets frontend. See WidgetState design doc.
"""

from miro.messages import (SaveDisplayState, SaveViewState, SaveGlobalState,
        DisplayInfo, ViewInfo)
from miro import prefs
from miro import app

class WidgetStateStore(object):
    # A CUSTOM_VIEW is a view which dynamically decides which view it is 
    # supposed to be. The CUSTOM_VIEW has to be caught in widgetstatestore 
    # and replaced with the proper view for the given situation.
    CUSTOM_VIEW = 2 
    ALBUM_VIEW = 3
    LIST_VIEW = 1
    STANDARD_VIEW = 0
    DEFAULT_VIEW_TYPE = {
        u'tab': STANDARD_VIEW, # all-feeds
        u'device-audio': LIST_VIEW,
        u'device-video': STANDARD_VIEW,
        u'downloading': STANDARD_VIEW,
        u'feed': CUSTOM_VIEW,
        u'feed-folder': CUSTOM_VIEW,
        u'folder-contents': STANDARD_VIEW,
        u'music': LIST_VIEW,
        u'others': LIST_VIEW,
        u'playlist': LIST_VIEW,
        u'search': LIST_VIEW,
        u'sharing': LIST_VIEW,
        u'videos': STANDARD_VIEW,
     }
    DEFAULT_DISPLAY_FILTERS = ['all']
    DEFAULT_COLUMN_WIDTHS = {
        u'album': 100,
        u'artist': 110,
        u'date': 150,
        u'description': 160,
        u'date-added': 150,
        u'eta': 60,
        u'feed-name': 70,
        u'file-type': 70,
        u'genre': 65,
        u'multi-row-album': 200,
        u'kind': 70,
        u'length': 60,
        u'name': 200,
        u'rate': 60,
        u'rating': 75,
        u'playlist': 30,
        u'show': 70,
        u'size': 65,
        u'state': 20,
        u'status': 70,
        u'torrent-details': 160,
        u'track': 30,
        u'year': 40,
        u'drm': 40,
    }
    DEFAULT_SORT_COLUMN = {
        u'tab': u'feed-name', # all-feeds
        u'downloading': u'name',
        u'feed': u'-date',
        u'feed-folder': u'-date',
        u'folder-contents': u'artist',
        u'music': u'artist',
        u'others': u'name',
        u'playlist': u'playlist',
        u'search': u'name',
        u'videos': u'name',
    }
    DEFAULT_SORT_COLUMN[u'device-audio'] = DEFAULT_SORT_COLUMN[u'music']
    DEFAULT_SORT_COLUMN[u'device-video'] = DEFAULT_SORT_COLUMN[u'videos']
    DEFAULT_SORT_COLUMN[u'sharing'] = DEFAULT_SORT_COLUMN[u'videos']
    # DEFAULT_COLUMNS stores the default columns when using list view for
    # different display types.  We tweak it in _calc_default_columns()
    DEFAULT_COLUMNS = {
        u'videos':
            [u'state', u'name', u'length', u'date-added', u'feed-name',
             u'size'],
        u'music':
            [u'state', u'name', u'artist', u'album', u'track', u'length',
            u'genre', u'year', u'rating'],
        u'others':
            [u'name', u'feed-name', u'size', u'file-type'],
        u'downloading':
            [u'name', u'feed-name', u'eta', u'rate',
            u'size', u'status'],
        u'tab': # all-feeds
            [u'state', u'name', u'feed-name', u'length',
            u'size', u'date', u'status'],
        u'feed':
            [u'state', u'name', u'length', u'size', u'date', u'status'],
        u'feed-folder':
            [u'state', u'name', u'length', u'size', u'date', u'status'],
        u'search':
            [u'state', u'name', u'description', u'status', u'file-type',
            u'feed-name', u'date'],
        u'playlist':
            [u'playlist', u'name', u'artist', u'album', u'track', u'length',
                u'genre', u'year', u'rating'],
    }
    DEFAULT_COLUMNS[u'device-audio'] = (DEFAULT_COLUMNS[u'music'][:] +
                                        [u'status'])
    DEFAULT_COLUMNS[u'device-video'] = DEFAULT_COLUMNS[u'videos'][:]
    DEFAULT_COLUMNS[u'folder-contents'] = DEFAULT_COLUMNS[u'music'][:]
    DEFAULT_COLUMNS[u'sharing'] = DEFAULT_COLUMNS[u'music'][:] + [u'status']

    AVAILABLE_COLUMNS = dict((display, set(columns))
        for display, columns in DEFAULT_COLUMNS.iteritems()
    )
    # add available but non-default columns here:
    AVAILABLE_COLUMNS['music'] |= set([u'date', u'date-added', u'feed-name',
        u'size', u'file-type', u'status'])
    AVAILABLE_COLUMNS['others'] |= set([u'date', u'date-added', u'drm',
        u'rating'])
    AVAILABLE_COLUMNS['downloading'] |= set([u'torrent-details', u'date',
        u'file-type'])
    AVAILABLE_COLUMNS['search'] |= set([u'size', u'rating'])
    AVAILABLE_COLUMNS['videos'] |= set([u'description', u'date', u'rating',
        u'file-type', u'show', u'kind', u'status', u'genre'])
    AVAILABLE_COLUMNS[u'device-audio'] = AVAILABLE_COLUMNS[u'music'].copy()
    AVAILABLE_COLUMNS[u'device-video'] = AVAILABLE_COLUMNS[u'videos'].copy()
    AVAILABLE_COLUMNS[u'feed'] = ((AVAILABLE_COLUMNS['music'] |
        AVAILABLE_COLUMNS['videos'] | AVAILABLE_COLUMNS['downloading']) -
        set([u'feed-name']))

    ALL_COLUMNS = set(DEFAULT_COLUMN_WIDTHS)

    REPEAT_OFF, REPEAT_PLAYLIST, REPEAT_TRACK = range(3)

    # Sorters that should always be enabled when available, and should not
    # appear in the Sorts menu (#17696).
    # This needs to be handled here, though analagous properties (e.g.
    # NO_RESIZE_COLUMNS) are handled in widgetconst. #16783 refers to fixing the
    # WSS mess - these shouldn't be sets of strings anyway.
    MANDATORY_SORTERS = frozenset([u'name', u'multi-row-album'])

    def __init__(self):
        self.displays = {}
        self.views = {}

    def setup_displays(self, message):
        for display in message.displays:
            self.displays[display.key] = display

    def setup_views(self, message):
        for view in message.views:
            self.views[view.key] = view

    def setup_global_state(self, message):
        self.global_info = message.info

    def _save_display_state(self, display_type, display_id):
        display = self._get_display(display_type, display_id)
        m = SaveDisplayState(display)
        m.send_to_backend()

    def _save_view_state(self, display_type, display_id, view_type):
        view = self._get_view(display_type, display_id, view_type)
        m = SaveViewState(view)
        m.send_to_backend()

    def _save_global_state(self):
        m = SaveGlobalState(self.global_info)
        m.send_to_backend()

    def _get_display(self, display_type, display_id):
        display_id = unicode(display_id)
        key = (display_type, display_id)
        if not key in self.displays:
            new_display = DisplayInfo(key)
            self.displays[key] = new_display
            self._save_display_state(display_type, display_id)
        return self.displays[key]

    def _get_view(self, display_type, display_id, view_type):
        display_id = unicode(display_id)
        key = (display_type, display_id, view_type)
        if not key in self.views:
            new_view = ViewInfo(key)
            self.views[key] = new_view
            self._save_view_state(display_type, display_id, view_type)
        return self.views[key]

# Real DisplayState Properties:

    def get_selected_view(self, display_type, display_id):
        display = self._get_display(display_type, display_id)
        if display.selected_view is not None:
            view = display.selected_view
        else:
            view = WidgetStateStore.DEFAULT_VIEW_TYPE[display_type]
            if view == WidgetStateStore.CUSTOM_VIEW:
                if display_type in (u'feed', u'feed-folder'):
                    view = app.config.get(prefs.PODCASTS_DEFAULT_VIEW)
                else:
                    app.widgetapp.handle_soft_failure("Getting default view",
                                       "Unknown CUSTOM_VIEW, falling back to "
                                       "STANDARD_VIEW",
                                       with_exception=True)
                    view = WidgetStateStore.STANDARD_VIEW
        return view

    def set_selected_view(self, display_type, display_id, selected_view):
        display = self._get_display(display_type, display_id)
        display.selected_view = selected_view
        self._save_display_state(display_type, display_id)

    def get_filters(self, display_type, display_id):
        """Get the active filters

        :returns: set of active filter strings
        """
        display = self._get_display(display_type, display_id)
        if display.active_filters is None:
            return set(WidgetStateStore.DEFAULT_DISPLAY_FILTERS)
        return display.active_filters

    def set_filters(self, display_type, display_id, active_filters):
        """Set the active filters

        active_filters should be a set of filter key strings.
        """
        display = self._get_display(display_type, display_id)
        display.active_filters = active_filters
        self._save_display_state(display_type, display_id)

    def set_shuffle(self, display_type, display_id, shuffle):
        display = self._get_display(display_type, display_id)
        display.shuffle = shuffle
        self._save_display_state(display_type, display_id)

    def get_shuffle(self, display_type, display_id):
        display = self._get_display(display_type, display_id)
        if display.shuffle is None:
            display.shuffle = False
            return display.shuffle
        else:
            return display.shuffle

    def set_repeat(self, display_type, display_id, repeat):
        display = self._get_display(display_type, display_id)
        display.repeat = repeat
        self._save_display_state(display_type, display_id)

    def get_repeat(self, display_type, display_id):
        display = self._get_display(display_type, display_id)
        if display.repeat is None:
            display.repeat = WidgetStateStore.REPEAT_OFF
            return display.repeat
        else:
            return display.repeat

    def get_selection(self, display_type, display_id):
        """Returns the current selection for a display, or None if no
        selection has been saved.
        """
        display = self._get_display(display_type, display_id)
        return display.selection

    def set_selection(self, display_type, display_id, selection):
        display = self._get_display(display_type, display_id)
        display.selection = selection
        self._save_display_state(display_type, display_id)

    def get_sort_state(self, display_type, display_id):
        display = self._get_display(display_type, display_id)
        sort_state = display.sort_state
        if sort_state is None:
            return WidgetStateStore.DEFAULT_SORT_COLUMN[display_type]
        else:
            return sort_state

    def set_sort_state(self, display_type, display_id, sort_key):
        display = self._get_display(display_type, display_id)
        display.sort_state = sort_key
        self._save_display_state(display_type, display_id)

    def get_last_played_item_id(self, display_type, display_id):
        display = self._get_display(display_type, display_id)
        return display.last_played_item_id

    def set_last_played_item_id(self, display_type, display_id, id_):
        display = self._get_display(display_type, display_id)
        display.last_played_item_id = id_
        self._save_display_state(display_type, display_id)

# ViewState properties for list and album view

    def get_columns_enabled(self, display_type, display_id, view_type):
        view = self._get_view(display_type, display_id, view_type)
        # Copy the column list.  We may modify it in _add_manditory_columns()
        # and that shouldn't change the source value.
        if view.columns_enabled is not None:
            columns = list(view.columns_enabled)
        else:
            columns = self._calc_default_columns(display_type, view_type)
        available = WidgetStateStore.get_columns_available(display_type,
                display_id, view_type)
        self._add_manditory_columns(view_type, columns)
        # If a column used to be enableable for a view but now is not,
        # filter it out:
        return [x for x in columns if x in available]

    def _calc_default_columns(self, display_type, view_type):
        columns = list(WidgetStateStore.DEFAULT_COLUMNS[display_type])
        if view_type == self.get_album_view_type():
            # Remove columns that contain info in the album/artist column.
            filter_out = (u'artist', u'album', u'track', u'feed-name')
            columns = [n for n in columns if n not in filter_out]
        return columns

    def _add_manditory_columns(self, view_type, columns):
        """Add manditory columns to the list of columns enabled."""
        # We currently handle name and multi-row-album.  Add an assertion so
        # that if MANDATORY_SORTERS changes without this code changing, we'll
        # see a crash report.

        assert (WidgetStateStore.MANDATORY_SORTERS ==
                set((u'name', u'multi-row-album')))
        if u'name' not in columns:
            columns.append(u'name')
        if (view_type == self.get_album_view_type() and
                u'multi-row-album' not in columns):
            columns.insert(0, u'multi-row-album')

    def set_columns_enabled(self, display_type, display_id, view_type,
            enabled):
        view = self._get_view(display_type, display_id, view_type)
        view.columns_enabled = enabled
        self._save_view_state(display_type, display_id, view_type)

    def toggle_column_enabled(self, display_type, display_id, view_type,
            column):
        columns = self.get_columns_enabled(display_type, display_id, view_type)
        if column in columns:
            columns.remove(column)
        else:
            columns.append(column)
        self.set_columns_enabled(display_type, display_id, view_type, columns)

    def get_column_widths(self, display_type, display_id, view_type):
        # fetch dict containing the widths from the DisplayInfo
        view_info = self._get_view(display_type, display_id, view_type)
        column_widths = view_info.column_widths
        if column_widths is None:
            column_widths = {}
        # get widths for each enabled column
        columns = self.get_columns_enabled(display_type, display_id,
                view_type)
        for name in columns:
            default = WidgetStateStore.DEFAULT_COLUMN_WIDTHS[name]
            column_widths.setdefault(name, default)
        return column_widths.copy()

    def update_column_widths(self, display_type, display_id, view_type,
                             widths):
        view_info = self._get_view(display_type, display_id, view_type)
        if view_info.column_widths is None:
            view_info.column_widths = {}
        view_info.column_widths.update(widths)
        self._save_view_state(display_type, display_id, view_type)

# ViewState properties that are global to the whole frontend
    def get_item_details_expanded(self, view_type):
        return self.global_info.item_details_expanded[view_type]

    def set_item_details_expanded(self, view_type, expanded):
        self.global_info.item_details_expanded[view_type] = expanded
        self._save_global_state()

    def get_guide_sidebar_expanded(self):
        return self.global_info.guide_sidebar_expanded

    def set_guide_sidebar_expanded(self, expanded):
        self.global_info.guide_sidebar_expanded = expanded
        self._save_global_state()

    def get_tabs_width(self):
        return self.global_info.tabs_width

    def set_tabs_width(self, width):
        self.global_info.tabs_width = width
        self._save_global_state()

# Real ViewState properties:

    def get_scroll_position(self, display_type, display_id, view_type):
        view = self._get_view(display_type, display_id, view_type)
        if view.scroll_position is not None:
            scroll_position = view.scroll_position
        else:
            scroll_position = (0, 0)
        return scroll_position

    def set_scroll_position(self, display_type, display_id, view_type,
            scroll_position):
        view = self._get_view(display_type, display_id, view_type)
        view.scroll_position = scroll_position
        self._save_view_state(display_type, display_id, view_type)

# static properties of a display_type:

    @staticmethod
    def get_columns_available(display_type, display_id, view_type):
        available = WidgetStateStore.AVAILABLE_COLUMNS[display_type].copy()
        # copy the set, since we may modify it before returning it
        if view_type == WidgetStateStore.get_album_view_type():
            available.add(u'multi-row-album')
        return available

# static properties of a view_type:

    @staticmethod
    def is_list_view(view_type):
        return view_type == WidgetStateStore.LIST_VIEW

    @staticmethod
    def is_standard_view(view_type):
        return view_type == WidgetStateStore.STANDARD_VIEW

    @staticmethod
    def is_album_view(view_type):
        return view_type == WidgetStateStore.ALBUM_VIEW

# static properties:

    @staticmethod
    def get_columns():
        return WidgetStateStore.ALL_COLUMNS

    @staticmethod
    def get_toggleable_columns():
        return WidgetStateStore.ALL_COLUMNS - WidgetStateStore.MANDATORY_SORTERS

    # displays:

    @staticmethod
    def get_display_types():
        return WidgetStateStore.AVAILABLE_COLUMNS.keys()

    @staticmethod
    def get_repeat_off():
        return WidgetStateStore.REPEAT_OFF

    @staticmethod
    def get_repeat_playlist():
        return WidgetStateStore.REPEAT_PLAYLIST

    @staticmethod
    def get_repeat_track():
        return WidgetStateStore.REPEAT_TRACK

    # views:

    @staticmethod
    def get_list_view_type():
        return WidgetStateStore.LIST_VIEW

    @staticmethod
    def get_standard_view_type():
        return WidgetStateStore.STANDARD_VIEW

    @staticmethod
    def get_album_view_type():
        return WidgetStateStore.ALBUM_VIEW

    @staticmethod
    def get_all_view_types():
        return (WidgetStateStore.LIST_VIEW,
                WidgetStateStore.STANDARD_VIEW,
                WidgetStateStore.ALBUM_VIEW)
