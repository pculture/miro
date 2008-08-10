# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

from miro import app
from miro import config
from miro import prefs
from miro.gtcache import gettext as _
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import browser
from miro.frontends.widgets import widgetutil
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class StaticTab(object):
    def __init__(self):
        self.unwatched = self.downloading = 0
        self.icon = widgetutil.make_surface(self.icon_name)
        self.view = self.make_view()

class ChannelGuideTab(StaticTab):
    id = 'guide'
    name = _('Miro Guide')
    icon_name = 'icon-guide'

    def make_view(self):
        self.browser = browser.Browser(app.widgetapp.default_guide_info)
        return self.browser

    def update(self, guide_info):
        self.browser.guide_info = guide_info

class DummyView(widgetset.Alignment):
    def __init__(self, title):
        widgetset.Alignment.__init__(self, xalign=0.5, yalign=0.5)
        label = widgetset.Label(title)
        label.set_size(3)
        label.set_bold(True)
        label.set_color((1.0, 0, 0))
        self.add(label)

class DummyTab(StaticTab):
    def make_view(self):
        return DummyView(self.name)

class SearchTab(DummyTab):
    id = 'search'
    name = _('Video Search')
    icon_name = 'icon-search'

class LibraryTab(DummyTab):
    id = 'library'
    name = _('Library')
    icon_name = 'icon-library'

class IndividualDownloadsTab(DummyTab):
    id = 'individual_downloads'
    name = _('Single Items')
    icon_name = 'icon-individual'

class NewVideosTab(DummyTab):
    id = 'new'
    name = _('New')
    icon_name = 'icon-new'

class DownloadsTab(DummyTab):
    id = 'downloading'
    name = _('Downloading')
    icon_name = 'icon-downloading'
