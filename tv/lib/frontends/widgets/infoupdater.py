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

"""``miro.infoupdater`` -- The infoupdater module holds:

* :class:`InfoUpdater` -- Track channel/feed/playlist updates from the
backend.
"""
from miro import signals

class InfoUpdater(signals.SignalEmitter):
    """Track channel/feed/playlist updates from the backend.

    Signals:

    * feeds-added (self, info_list) -- New feeds were added
    * feeds-changed (self, info_list) -- Feeds were changed
    * feeds-removed (self, info_list) -- Feeds were removed
    * sites-added (self, info_list) -- New sites were added
    * sites-changed (self, info_list) -- Sites were changed
    * sites-removed (self, info_list) -- Sites were removed
    * playlists-added (self, info_list) -- New playlists were added
    * playlists-changed (self, info_list) -- Playlists were changed
    * playlists-removed (self, info_list) -- Playlists were removed
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        for prefix in ('feeds', 'sites', 'playlists'):
            self.create_signal('%s-added' % prefix)
            self.create_signal('%s-changed' % prefix)
            self.create_signal('%s-removed' % prefix)

    def handle_tabs_changed(self, message):
        if message.type == 'feed':
            signal_start = 'feeds'
        elif message.type == 'site':
            signal_start = 'sites'
        elif message.type == 'playlist':
            signal_start = 'playlists'
        else:
            return
        if message.added:
            self.emit('%s-added' % signal_start, message.added)
        if message.changed:
            self.emit('%s-changed' % signal_start, message.changed)
        if message.removed:
            self.emit('%s-removed' % signal_start, message.removed)
