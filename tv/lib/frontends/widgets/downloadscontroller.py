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

from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets.itemlistwidgets import (
    DownloadTitlebar, DownloadStatusToolbar)
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import prefpanel

from miro import app
from miro import messages
from miro import downloader
from miro import prefs

class DownloadsController(itemlistcontroller.ItemListController):
    def __init__(self):
        itemlistcontroller.ItemListController.__init__(
            self, u'downloading', u'downloading')
        self.toolbar = None
        self.update_buttons()

    def build_widget(self):
        self.titlebar.switch_to_view(self.widget.selected_view)
        self.widget.titlebar_vbox.pack_start(self.titlebar)

        self.status_toolbar = DownloadStatusToolbar()
        self.widget.statusbar_vbox.pack_start(self.status_toolbar)

        self._update_free_space()

    def on_config_change(self, obj, key, value):
        itemlistcontroller.ItemListController.on_config_change(self, obj, key,
                value)
        if ((key == prefs.PRESERVE_X_GB_FREE.key
             or key == prefs.PRESERVE_DISK_SPACE.key)):
            self.status_toolbar.update_free_space()

    def make_titlebar(self):
        titlebar = DownloadTitlebar()
        titlebar.connect('search-changed', self._on_search_changed)
        titlebar.connect("pause-all", self._on_pause_all)
        titlebar.connect("resume-all", self._on_resume_all)
        titlebar.connect("cancel-all", self._on_cancel_all)
        titlebar.connect("settings", self._on_settings)
        titlebar.hide_album_view_button()
        return titlebar

    def make_context_menu_handler(self):
        return itemcontextmenu.ItemContextMenuHandler()

    def _on_search_changed(self, widget, search_text):
        self.set_search(search_text)

    def _update_free_space(self):
        self.status_toolbar.update_free_space()

    # The pause_all/resume_all and cancel_all disables the automatic sorting
    # mechanism until the operations are complete, because even though the
    # operation affects all items in the list the status updates for these
    # items are not batched.
    #
    # When complete, the backend is expected to send a reply indicating that
    # all operations (up to this point) are complete and at that point we can
    # re-enable the sort again.  See DownloadSyncCommandComplete().  We hope
    # for the best that the remote command to do whatever's needed should not
    # take more than a second or two which should be accurate for a moderately
    # sized download list.
    def _on_pause_all(self, widget):
        messages.PauseAllDownloads().send_to_backend()

    def _on_resume_all(self, widget):
        messages.ResumeAllDownloads().send_to_backend()

    def _on_cancel_all(self, widget):
        messages.CancelAllDownloads().send_to_backend()

    def _on_settings(self, widget):
        prefpanel.show_window("downloads")

    def handle_item_list_changes(self):
        itemlistcontroller.ItemListController.handle_item_list_changes(self)
        self.update_rates()
        self.update_buttons()

    def update_rates(self):
        self.status_toolbar.update_rates(
            app.download_state_manager.total_down_rate,
            app.download_state_manager.total_up_rate)

    def update_buttons(self):
        items = self.item_list.get_items()
        if len(items) == 0:
            self.titlebar.set_button_enabled("resume", False)
            self.titlebar.set_button_enabled("pause", False)
            self.titlebar.set_button_enabled("cancel", False)
        else:
            all_paused = all_downloading = True
            for item in items:
                if item.is_paused:
                    all_downloading = False
                else:
                    all_paused = False
            self.titlebar.set_button_enabled("resume", not all_downloading)
            self.titlebar.set_button_enabled("pause", not all_paused)
            self.titlebar.set_button_enabled("cancel", True)
