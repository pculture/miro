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

"""Controller for Downloads tab.
"""

from miro.gtcache import gettext as _

from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets.itemlistwidgets import (
    StandardView, HideableSection, ItemContainerWidget, DownloadToolbar,
    DownloadStatusToolbar, ItemListTitlebar)
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import prefpanel

from miro import messages
from miro import downloader
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class DownloadsController(itemlistcontroller.ItemListController):
    def __init__(self):
        itemlistcontroller.ItemListController.__init__(self, u'downloading',
                                                       u'downloading')
        for item_list in self.item_list_group.item_lists:
            item_list.resort_on_update = True

    def build_widget(self):
        self.titlebar = self.make_titlebar()
        self.widget.titlebar_vbox.pack_start(self.titlebar)

        self.status_toolbar = DownloadStatusToolbar()
        self.widget.statusbar_vbox.pack_start(self.status_toolbar)

        self._update_free_space()

    def make_titlebar(self):
        image_path = resources.path("images/icon-downloading_large.png")
        icon = imagepool.get(image_path)
        titlebar = ItemListTitlebar(_("Downloads"), icon)
        titlebar.connect('search-changed', self._on_search_changed)
        return titlebar

    def make_context_menu_handler(self):
        return itemcontextmenu.ItemContextMenuHandler()

    def build_standard_view(self):
        standard_view = StandardView(self.item_list)
        self.toolbar = DownloadToolbar()
        self.toolbar.connect("pause-all", self._on_pause_all)
        self.toolbar.connect("resume-all", self._on_resume_all)
        self.toolbar.connect("cancel-all", self._on_cancel_all)
        self.toolbar.connect("settings", self._on_settings)
        self.widget.titlebar_vbox.pack_start(self.toolbar)
        background = widgetset.SolidBackground((1, 1, 1))
        background.add(standard_view)
        scroller = widgetset.Scroller(False, True)
        scroller.add(background)
        self.widget.normal_view_vbox.pack_start(scroller, expand=True)
        return standard_view

    def _on_search_changed(self, widget, search_text):
        self.set_search(search_text)

    def _update_free_space(self):
        self.status_toolbar.update_free_space()

    def _on_pause_all(self, widget):
        messages.PauseAllDownloads().send_to_backend()

    def _on_resume_all(self, widget):
        messages.ResumeAllDownloads().send_to_backend()

    def _on_cancel_all(self, widget):
        messages.CancelAllDownloads().send_to_backend()

    def _on_settings(self, widget):
        prefpanel.show_window("downloads")

    def on_items_changed(self):
        self.status_toolbar.update_rates(
            downloader.total_down_rate, downloader.total_up_rate)
