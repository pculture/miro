# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

from miro import app, prefs
from miro.gtcache import gettext as _
from miro.frontends.widgets import browser
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil

class StaticTab(object):
    def __init__(self):
        self.unwatched = self.downloading = 0
        self.icon = widgetutil.make_surface(self.icon_name)

# this maps guide urls to titles we'd rather they use.
_guide_url_to_title_map = {
    prefs.CHANNEL_GUIDE_URL.default: _("Miro Guide")
    }

# this maps guide urls to icons we'd rather they use.
_guide_url_to_icon_map = {
    prefs.CHANNEL_GUIDE_URL.default: 'icon-guide'
    }

class ChannelGuideTab(StaticTab):
    id = 'guide'
    name = u''
    icon_name = 'icon-guide'
    tall = True

    def __init__(self):
        StaticTab.__init__(self)
        self._set_from_info(app.widgetapp.default_guide_info)
        self.browser = browser.BrowserNav(app.widgetapp.default_guide_info)

    def update(self, guide_info):
        self._set_from_info(guide_info)
        self.browser.guide_info = guide_info

    def _set_from_info(self, guide_info):
        if guide_info is None:
            return

        # XXX This code is a bit ugly, because we want to use pretty defaults for
        # the Miro Guide, but still allow themes to override

        if guide_info.default and guide_info.url in _guide_url_to_title_map:
            self.name = _guide_url_to_title_map[guide_info.url]
        else:
            self.name = guide_info.name

        if guide_info.default and guide_info.url in _guide_url_to_icon_map:
            # one of our default guides
            self.icon_name = _guide_url_to_icon_map[guide_info.url]
            self.icon = widgetutil.make_surface(self.icon_name)
        elif guide_info.faviconIsDefault:
            # theme guide that should use default favicon
            self.icon = widgetutil.make_surface(self.icon_name)
        else:
            # theme guide with a favicon
            surface = imagepool.get_surface(guide_info.favicon)
            if surface.width != 23 or surface.height != 23:
                self.icon = imagepool.get_surface(guide_info.favicon,
                                                  size=(23, 23))
            else:
                self.icon = surface

class SearchTab(StaticTab):
    id = 'search'
    name = _('Video Search')
    icon_name = 'icon-search'
    tall = True

class VideoLibraryTab(StaticTab):
    id = 'videos'
    name = _('Video')
    icon_name = 'icon-video'
    media_type = u'video'

class AudioLibraryTab(StaticTab):
    id = 'music'
    name = _('Music')
    icon_name = 'icon-audio'
    media_type = u'audio'

class OtherLibraryTab(StaticTab):
    id = 'others'
    name = _('Other')
    icon_name = 'icon-other'
    media_type = u'other'

class DownloadsTab(StaticTab):
    id = 'downloading'
    name = _('Downloading')
    icon_name = 'icon-downloading'

class VideoConversionsTab(StaticTab):
    id = 'conversions'
    name = _('Conversions')
    icon_name = 'icon-conversions'
