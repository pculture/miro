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

"""statictabs.py -- Tabs that are always present."""

from miro.gtcache import gettext as _
from miro.frontends.widgets import widgetutil

class StaticTab(object):
    type = u'static'
    tall = True

    def __init__(self):
        self.unwatched = self.downloading = 0
        self.icon = widgetutil.make_surface(self.icon_name)
        self.active_icon = widgetutil.make_surface(
            self.icon_name + '_active')

class SearchTab(StaticTab):
    type = u'search'
    id = u'search'
    name = _('Video Search')
    icon_name = 'icon-search'

class VideoLibraryTab(StaticTab):
    type = u'videos'
    id = u'videos'
    name = _('Videos')
    icon_name = 'icon-video'
    media_type = u'video'

class AudioLibraryTab(StaticTab):
    type = u'music'
    id = u'music'
    name = _('Music')
    icon_name = 'icon-audio'
    media_type = u'audio'

class OthersTab(StaticTab):
    type = u'others'
    id = u'others'
    name = _('Misc')
    icon_name = 'icon-other'
    media_type = u'other'

class DownloadsTab(StaticTab):
    type = u'downloading'
    id = u'downloading'
    name = _('Downloading')
    icon_name = 'icon-downloading'

class ConvertingTab(StaticTab):
    type = u'converting'
    id = u'converting'
    name = _('Converting')
    icon_name = 'icon-converting'
