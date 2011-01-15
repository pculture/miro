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
DEFAULT_LIST_VIEW_DISPLAYS = set([u'music', u'others', u'audio-feed', u'playlist', u'search'])
DEFAULT_DISPLAY_FILTERS = [u'view-all']
DEFAULT_COLUMN_WIDTHS = {
    u'state': 20, u'name': 130, u'artist': 110, u'album': 100, u'track': 30,
    u'feed-name': 70, u'length': 60, u'genre': 65, u'year': 40, u'rating': 75,
    u'size': 65, u'status': 70, u'date': 70, u'eta': 60, u'rate': 60,
}
DEFAULT_SORT_COLUMN = {
    u'videos': 'name', u'music': 'artist', u'others': 'name',
    u'downloading': 'eta', u'all-feed-video': 'feed-name', u'feed': 'date',
    u'audio-feed': 'date', u'playlist': 'artist', u'search': 'artist',
}

# column properties
COLUMN_LABELS = {
    u'state': u'', u'name': _('Name'), u'artist': _('Artist'),
    u'album': _('Album'), u'track': _('Track'), u'year': _('Year'),
    u'genre': _('Genre'), u'rating': _('Rating'), u'date': _('Date'),
    u'length': _('Length'), u'status': _('Status'), u'size': _('Size'),
    u'feed-name': _('Feed'), u'eta': _('ETA'), u'rate': _('Speed'),
    u'date-added': _('Date Added'), u'last-played': _('Last Played'),
}
NO_RESIZE_COLUMNS = set(['state', 'rating'])
NO_PAD_COLUMNS = set()
COLUMN_WIDTH_WEIGHTS = {
    u'name': 1.0,
    u'artist': 0.7,
    u'album': 0.7,
    u'feed-name': 0.5,
    u'status': 0.2,
}

# Display State default; also used to populate View menu
COLUMNS_AVAILABLE = {
    u'videos': [u'state', u'name', u'length', u'feed-name', u'size'],
    u'music': [u'state', u'name', u'artist', u'album', u'track', u'feed-name',
        u'length', u'genre', u'year', u'rating', u'size'],
    u'others': [u'name', u'feed-name', u'size', u'rating'],
    u'downloading': [u'name', u'feed-name', u'status', u'eta', u'rate'],
    u'all-feed-video': [u'state', u'name', u'feed-name', u'length', u'status',
        u'size'],
    u'feed': [u'state', u'name', u'length', u'status', u'size', u'date'],
    u'audio-feed': [u'state', u'name', u'length', u'status', u'size', u'date'],
    u'playlist': [u'state', u'name', u'artist', u'album', u'track', u'feed-name',
        u'length', u'genre', u'year', u'rating', u'size'],
    u'search': [u'state', u'name', u'artist', u'album', u'track', u'feed-name',
        u'length', u'genre', u'year', u'rating', u'size'],
}

COLUMNS_AVAILABLE[u'device-video'] = COLUMNS_AVAILABLE[u'videos']
COLUMNS_AVAILABLE[u'device-audio'] = COLUMNS_AVAILABLE[u'music']

# TODO: no display has type 'all-feed-video' yet
# TODO: rename 'feed' to 'video-feed'
# TODO: replace 'playlist' with 'audio-playlist' and 'video-playlist'
# TODO: special stuff for 'converting' type
# TODO: handle future display types 'device-video' and 'device-audio' ?
