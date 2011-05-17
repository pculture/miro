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

from collections import defaultdict

from miro.gtcache import gettext as _

# Control sizes
SIZE_NORMAL = -1
SIZE_SMALL = -2

DIALOG_NOTE_COLOR = (0.5, 0.5, 0.5)
MAX_VOLUME = 3.0

TEXT_JUSTIFY_LEFT = 0
TEXT_JUSTIFY_RIGHT = 1
TEXT_JUSTIFY_CENTER = 2

# cursors
CURSOR_NORMAL = 0
CURSOR_POINTING_HAND = 1

# column properties
# TODO: this stuff should probably be accessed through WSS, and COLUMN_LABELS
# should be in widgetstateconstantstest
COLUMN_LABELS = {
    u'state': _('State'),
    u'name': _('Name'),
    u'artist': _('Artist'),
    u'album': _('Album'),
    u'track': _('Track'),
    u'year': _('Year'),
    u'genre': _('Genre'),
    u'rating': _('Rating'),
    u'date': _('Date'),
    u'length': _('Time'),
    u'status': _('Status'),
    u'size': _('Size'),
    u'feed-name': _('Source'),
    u'eta': _('ETA'),
    u'torrent-details': _('Torrent details'),
    u'rate': _('Speed'),
    u'date-added': _('Date Added'),
    u'last-played': _('Last Played'),
    u'description': _('Description'),
    u'drm': _('DRM'),
    u'file-type': _('File Type'),
    u'show': _('Show'),
    u'kind': _('Video Kind'),
    u'playlist': _('Order'),
}
NO_RESIZE_COLUMNS = set(['state', 'rating'])
NO_PAD_COLUMNS = set(['state'])
COLUMN_WIDTH_WEIGHTS = {
    u'description': 1.2,
    u'name': 1.0,
    u'artist': 0.7,
    u'album': 0.7,
    u'feed-name': 0.5,
    u'status': 0.2,
}
