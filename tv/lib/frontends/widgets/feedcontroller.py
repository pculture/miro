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

"""Controller for Feeds."""

from miro.gtcache import gettext as _
from miro import app
from miro.gtcache import ngettext
from miro import messages
from miro.frontends.widgets import feedsettingspanel
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import itemrenderer
from miro.frontends.widgets import widgetutil

class FeedController(itemlistcontroller.ItemListController):
    """Controller object for feeds."""
    def __init__(self, id_, is_folder, is_directory_feed):
        self.is_folder = is_folder
        self.is_directory_feed = is_directory_feed
        self.titlebar = None
        if is_folder:
            type_ = u'feed-folder'
        else:
            type_ = u'feed'
        itemlistcontroller.ItemListController.__init__(self, type_, id_)
        self.show_resume_playing_button = True

    def make_context_menu_handler(self):
        return itemcontextmenu.ItemContextMenuHandler()

    def build_widget(self):
        feed_info = widgetutil.get_feed_info(self.id)

        self.titlebar.connect('filter-clicked', self.on_filter_clicked)
        self.titlebar.switch_to_view(self.widget.selected_view)
        self.titlebar.connect('search-changed', self._on_search_changed)
        self.widget.titlebar_vbox.pack_start(self.titlebar)
        if not self.is_folder and not self.is_directory_feed:
            self.widget.statusbar_vbox.pack_start(
                self._make_toolbar(feed_info))

        # this only gets shown when the user is searching for things
        # in the feed and there are no results.
        text = _('No Results')
        self.widget.list_empty_mode_vbox.pack_start(
                itemlistwidgets.EmptyListHeader(text))

    def build_renderer(self):
        feed_info = widgetutil.get_feed_info(self.id)
        return itemrenderer.ItemRenderer(display_channel=self.is_folder,
                is_podcast=(not feed_info.is_directory_feed))

    def make_titlebar(self):
        feed_info = widgetutil.get_feed_info(self.id)
        if feed_info.is_directory_feed:
            titlebar = itemlistwidgets.WatchedFolderTitlebar()
        elif feed_info.is_folder:
            titlebar = itemlistwidgets.ChannelFolderTitlebar()
        else:
            titlebar = itemlistwidgets.ChannelTitlebar()
            titlebar.connect('save-search', self._on_save_search)
        if not self.is_directory_feed:
            titlebar.hide_album_view_button()
        return titlebar

    def get_saved_search_text(self):
        if not self.is_folder:
            return self.titlebar.get_search_text()
        else:
            return None

    def get_saved_search_source(self):
        if not self.is_folder:
            return 'channel', self.id
        else:
            return None

    def _on_search_changed(self, widget, search_text):
        self.set_search(search_text)
        self._update_counts()

    def _on_save_search(self, widget, search_text):
        info = widgetutil.get_feed_info(self.id)
        messages.NewFeedSearchFeed(info, search_text).send_to_backend()

    def _make_toolbar(self, feed_info):
        toolbar = itemlistwidgets.FeedToolbar()
        toolbar.autodownload_button.show()
        toolbar.settings_button.show()
        toolbar.set_autodownload_mode(feed_info.autodownload_mode)
        toolbar.connect('show-settings', self._on_show_settings)
        toolbar.connect('remove-feed', self._on_remove_feed)
        toolbar.connect('auto-download-changed',
                self._on_auto_download_changed)
        return toolbar

    def _on_remove_feed(self, widget):
        info = widgetutil.get_feed_info(self.id)
        app.widgetapp.remove_feeds([info])

    def _on_show_settings(self, widget):
        info = widgetutil.get_feed_info(self.id)
        feedsettingspanel.run_dialog(info)

    def _on_auto_download_changed(self, widget, setting):
        messages.AutodownloadChange(self.id, setting).send_to_backend()

    def on_items_changed(self):
        self._update_counts()

    def _update_counts(self):
        # FIXME: either find out a UI for these counts or delete them.
        return
        downloads = self.downloading_view.item_list.get_count()
        watchable = self.downloaded_view.item_list.get_count()
        full_count = (self.full_view.item_list.get_count() +
                self._show_more_count)
        info = widgetutil.get_feed_info(self.id)
        if info.autodownload_mode == 'off' or info.unwatched < info.max_new:
            # don't count videos queued for other reasons
            autoqueued_count = 0
        else:
            autoqueued_count = len([i for i in
                                    self.full_view.item_list.get_items()
                                    if i.pending_auto_dl])
        self._update_downloading_section(downloads)
        self._update_downloaded_section(watchable)
        self._update_full_section(downloads, full_count, autoqueued_count)

    def _update_downloading_section(self, downloads):
        if downloads > 0:
            text = ngettext("%(count)d Downloading",
                            "%(count)d Downloading",
                            downloads,
                            {"count": downloads})
            self.downloading_section.set_header(text)
            self.downloading_section.show()
        else:
            self.downloading_section.hide()

    def _update_downloaded_section(self, watchable):
        if watchable > 0:
            text = ngettext("%(count)d Item",
                            "%(count)d Items",
                            watchable,
                            {"count": watchable})
            text = u"|  %s  " % text
            self.downloaded_section.set_info(text)
            self.downloaded_section.show()
        else:
            self.downloaded_section.hide()

    def _update_full_section(self, downloads, items, autoqueued_count):
        if self._search_text == '':
            itemtext = ngettext("%(count)d Item",
                                "%(count)d Items",
                                items,
                                {"count": items})
            downloadingtext = ngettext("%(count)d Downloading",
                                       "%(count)d Downloading",
                                       downloads,
                                       {"count": downloads})
            if autoqueued_count:
                queuedtext = ngettext("%(count)d Download Queued Due To "
                                      "Unplayed Items (See Settings)",
                                      "%(count)d Downloads Queued Due To "
                                      "Unplayed Items (See Settings)",
                                      autoqueued_count,
                                      {"count": autoqueued_count})

            text = u"|  %s" % itemtext
            if downloads:
                text = text + u"  |  %s" % downloadingtext
            if autoqueued_count:
                text = text + u"  |  %s" % queuedtext
        else:
            text = ngettext("%(count)d Item Matches Search",
                    "%(count)d Items Match Search",
                    items, {"count": items})
            text = u"|  %s" % text
        self.full_section.set_info(text)

class AllFeedsController(FeedController):
    TYPE = u'tab'

    def __init__(self):
        FeedController.__init__(self, u'feed-base-tab', True, True)

    def make_titlebar(self):
        return itemlistwidgets.AllFeedsTitlebar()

    def get_item_list_grouping(self):
        return itemlist.feed_grouping

    def get_multi_row_album_mode(self):
        return 'feed'
