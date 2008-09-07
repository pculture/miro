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

"""Controller for Feeds."""

import logging

from miro.gtcache import gettext as _
from miro import messages
from miro.frontends.widgets import channelsettingspanel
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import separator
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil

class FeedController(itemlistcontroller.ItemListController):
    """Controller object for feeds."""

    def __init__(self, id, is_folder):
        self.is_folder = is_folder
        itemlistcontroller.ItemListController.__init__(self, 'feed', id)

    def make_context_menu_handler(self):
        return itemcontextmenu.ItemContextMenuHandler()

    def build_widget(self):
        feed_info = widgetutil.get_feed_info(self.id)
        icon = imagepool.get(feed_info.thumbnail, size=(61, 61))
        self._make_item_views()

        widget = itemlistwidgets.ItemContainerWidget()
        self.titlebar = itemlistwidgets.ChannelTitlebar(feed_info.name, icon)
        self.titlebar.connect('search-changed', self._on_search_changed)
        self.titlebar.connect('save-search', self._on_save_search)
        widget.titlebar_vbox.pack_start(self.titlebar)
        if not self.is_folder:
            sep = separator.HSeparator((0.85, 0.85, 0.85), (0.95, 0.95, 0.95))
            widget.titlebar_vbox.pack_start(sep)
            widget.titlebar_vbox.pack_start(self._make_toolbar(feed_info))
        widget.content_vbox.pack_start(self.downloading_section)
        widget.content_vbox.pack_start(self.full_section)
        widget.content_vbox.pack_start(self.downloaded_section)
        return widget

    def _on_search_changed(self, widget, search_text):
        self.set_search(search_text)

    def _on_save_search(self, widget, search_text):
        info = widgetutil.get_feed_info(self.id)
        messages.NewChannelSearchChannel(info, search_text).send_to_backend()

    def _make_item_views(self):
        self.downloading_view = itemlistwidgets.ItemView(
                itemlist.DownloadingItemList())
        self.downloaded_view = itemlistwidgets.ItemView(
                itemlist.DownloadedItemList())
        self.full_view = itemlistwidgets.ItemView(itemlist.ItemList())
        self.downloading_section = itemlistwidgets.HideableSection(
                "", self.downloading_view)
        self.downloaded_section = itemlistwidgets.HideableSection(
                _("Downloaded"), self.downloaded_view)
        self.full_section = itemlistwidgets.HideableSection(
                _("Full Channel"), self.full_view)

    def _make_toolbar(self, feed_info):
        toolbar = itemlistwidgets.FeedToolbar()
        toolbar.set_autodownload_mode(feed_info.autodownload_mode)
        toolbar.connect('show-settings', self._on_show_settings)
        toolbar.connect('send-to-a-friend', self._on_send_to_a_friend)
        toolbar.connect('auto-download-changed',
                self._on_auto_download_changed)
        return toolbar

    def all_item_views(self):
        return [self.downloading_view, self.full_view, self.downloaded_view]

    def default_item_view(self):
        return self.downloaded_view

    def _on_show_settings(self, widget):
        info = widgetutil.get_feed_info(self.id)
        channelsettingspanel.run_dialog(info)

    def _on_send_to_a_friend(self, widget):
        logging.warn('should send to friend')

    def _on_auto_download_changed(self, widget, setting):
        messages.AutodownloadChange(self.id, setting).send_to_backend()

    def _expand_lists_initially(self):
        video_downloaded = self.downloaded_view.item_list.get_count() > 0
        feed_info = widgetutil.get_feed_info(self.id)
        autodownload_mode = feed_info.autodownload_mode
        if (not video_downloaded or autodownload_mode is None or
                autodownload_mode == 'off'):
            self.full_section.expand()
        self.full_section.show()
        self.downloaded_section.expand()

    def on_initial_list(self):
        # We wait for the initial list of items to pack our item views because
        # we need to know which ones should be expanded
        self._expand_lists_initially()
        self._update_counts()

    def on_items_changed(self):
        self._update_counts()

    def _update_counts(self):
        downloads = self.downloading_view.item_list.get_count()
        watchable = self.downloaded_view.item_list.get_count()
        full_count = self.full_view.item_list.get_count()
        self._update_downloading_section(downloads)
        self._update_downloaded_section(watchable)
        self._update_full_section(downloads, full_count)

    def _update_downloading_section(self, downloads):
        if downloads > 0:
            text = _("%d Downloading") % downloads
            self.downloading_section.set_header(text)
            self.downloading_section.show()
        else:
            self.downloading_section.hide()

    def _update_downloaded_section(self, watchable):
        if watchable > 0:
            text = _("  |  %d Videos  ") % watchable
            self.downloaded_section.set_info(text)
            self.downloaded_section.show()
        else:
            self.downloaded_section.hide()

    def _update_full_section(self, downloads, videos):
        text = _(
            "  |  %(videos)d Videos  |  %(downloads)d Downloading"
        ) % { 'videos': videos, 'downloads': downloads }
        self.full_section.set_info(text)
