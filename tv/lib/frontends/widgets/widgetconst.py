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

"""``miro.frontends.widgets.widgetconst`` -- Constants for the widgets
frontend.
"""

from miro.gtcache import gettext as _

# Control sizes
SIZE_NORMAL = -1
SIZE_SMALL = -2

DIALOG_NOTE_COLOR = (0.5, 0.5, 0.5)
MAX_VOLUME = 3.0

TEXT_JUSTIFY_LEFT = 0
TEXT_JUSTIFY_RIGHT = 1
TEXT_JUSTIFY_CENTER = 2

# Display State defaults
DEFAULT_LIST_VIEW_DISPLAYS = set(['music', 'others', 'audio-feed', 'playlist', 'search'])
DEFAULT_DISPLAY_FILTERS = ['view-all']
DEFAULT_COLUMN_WIDTHS = {
    'state': 20, 'name': 130, 'artist': 110, 'album': 100, 'track': 30,
    'feed-name': 70, 'length': 60, 'genre': 65, 'year': 40, 'rating': 75,
    'size': 65, 'status': 70,
}
DEFAULT_SORT_COLUMN = {
    'videos': 'name', 'music': 'artist', 'others': 'name',
    'downloading': 'eta', 'all-feed-video': 'feed-name', 'feed': 'date',
    'audio-feed': 'date', 'playlist': 'artist', 'search': 'artist',
}

# column properties
COLUMN_LABELS = {
    'state': u'', 'name': _('Name'), 'artist': _('Artist'),
    'album': _('Album'), 'track': _('Track'), 'year': _('Year'),
    'genre': _('Genre'), 'rating': _('Rating'), 'date': _('Date'),
    'length': _('Length'), 'status': _('Status'), 'size': _('Size'),
    'feed-name': _('Feed'), 'eta': _('ETA'), 'rate': _('Speed'),
    'date-added': _('Date Added'), 'last-played': _('Last Played'),
}
NO_RESIZE_COLUMNS = set(['state', 'rating'])
NO_PAD_COLUMNS = set(['rating'])
COLUMN_WIDTH_WEIGHTS = {
    'name': 1,
    'artist': 0.7,
    'album': 0.7,
    'feed-name': 0.5,
    'status': 0.2,
}

# Display State default; also used to populate View menu
COLUMNS_AVAILABLE = {
    'videos': ['state', 'name', 'length', 'feed-name', 'size'],
    'music': ['state', 'name', 'artist', 'album', 'track', 'feed-name',
        'length', 'genre', 'year', 'rating', 'size'],
    'others': ['name', 'feed-name', 'size', 'rating'],
        'downloading': ['name', 'feed-name', 'status', 'eta', 'rate'],
    'all-feed-video': ['state', 'name', 'feed-name', 'length', 'status',
        'size'],
    'feed': ['state', 'name', 'length', 'status', 'size'],
    'audio-feed': ['state', 'name', 'length', 'status', 'size'],
    'playlist': ['state', 'name', 'artist', 'album', 'track', 'feed-name',
        'length', 'genre', 'year', 'rating', 'size'],
    'search': ['state', 'name', 'artist', 'album', 'track', 'feed-name',
        'length', 'genre', 'year', 'rating', 'size'],
}

# TODO: no display has type 'all-feed-video' yet
# TODO: rename 'feed' to 'video-feed'
# TODO: replace 'playlist' with 'audio-playlist' and 'video-playlist'
# TODO: special stuff for 'converting' type
# TODO: handle future display types 'device-video' and 'device-audio' ?
