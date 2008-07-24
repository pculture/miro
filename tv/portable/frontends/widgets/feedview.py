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

"""Display the content for a feed."""

from miro.gtcache import gettext as _
from miro import messages
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import separator
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset

class DownloadsList(itemlist.FilteredItemList):
    def filter(self, item_info):
        return (item_info.download_info and 
                not item_info.download_info.finished)

class DownloadedList(itemlist.FilteredItemList):
    def filter(self, item_info):
        rv = (item_info.download_info and 
                item_info.download_info.finished)
        return rv

class HidableItemList(widgetset.VBox):
    """Widget that contains an item list, along with an expander to show/hide
    it.
    """

    def __init__(self, item_list):
        widgetset.VBox.__init__(self)
        self.expander = widgetset.Expander(item_list)
        self.expander.set_expanded(False)
        self.item_list = self.expander.child
        self.shown = False

    def show(self):
        if not self.shown:
            self.pack_start(self.expander)
            self.shown = True

    def hide(self):
        if self.shown:
            self.remove(self.expander)
            self.shown = False

    def make_header_label(self, text):
        self.header_label = widgetset.Label(text)
        self.header_label.set_size(0.85)
        self.header_label.set_bold(True)
        self.header_label.set_color((0.27, 0.27, 0.27))

    def make_label(self, header_text):
        hbox = widgetset.HBox()
        self.make_header_label(header_text)
        hbox.pack_start(self.header_label)
        self.info_label = widgetset.Label("")
        self.info_label.set_size(0.85)
        self.info_label.set_color((0.72, 0.72, 0.72))
        hbox.pack_start(self.info_label)
        self.expander.set_label(hbox)

    def get_count(self):
        return len(self.item_list.model)

class DownloadsHidableList(HidableItemList):
    def __init__(self):
        HidableItemList.__init__(self, DownloadsList())
        self.make_label("")

    def update_counts(self, downloads, watchable):
        if downloads > 0:
            self.header_label.set_text(_("%d Downloads") % downloads)
            self.show()
        else:
            self.hide()

class DownloadedHidableList(HidableItemList):
    def __init__(self):
        HidableItemList.__init__(self, DownloadedList())
        self.make_label(_("Downloaded"))

    def update_counts(self, downloads, watchable):
        if watchable > 0:
            text = _(" | %d Videos ") % watchable
            self.info_label.set_text(text)
            self.show()
        else:
            self.hide()

class FullList(HidableItemList):
    def __init__(self):
        HidableItemList.__init__(self, itemlist.ItemList())
        self.make_label(_("Full Channel"))
        self.show()

    def update_counts(self, downloads, watchable):
        text = _(" | %(videos)d Videos | %(downloads)d Downloading") % \
                { 'videos': watchable, 'downloads': downloads }
        self.info_label.set_text(text)

class TitlebarBackground(widgetset.Background):
    def draw(self, context, layout):
        if not context.style.use_custom_titlebar_background:
            return
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color((0.95, 0.95, 0.95))
        gradient.set_end_color((0.90, 0.90, 0.90))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)

class ToolbarBackground(widgetset.Background):
    def draw(self, context, layout):
        if not context.style.use_custom_titlebar_background:
            return
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color((0.90, 0.90, 0.90))
        gradient.set_end_color((0.79, 0.79, 0.79))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)

class TitleDrawer(widgetset.DrawingArea):
    def __init__(self, title):
        widgetset.DrawingArea.__init__(self)
        self.title = title

    def draw(self, context, layout):
        layout.set_font(2.5, bold=True, family="Helvetica")
        layout.set_text_color((0.31, 0.31, 0.31))
        layout.set_text_shadow(widgetutil.Shadow((1,1,1), 1, (1.5,-1.5), 0.5))
        textbox = layout.textbox(self.title)
        textbox.set_width(context.width)
        textbox.set_wrap_style('char')
        height = textbox.font.line_height()
        y = (context.height - height) / 2
        textbox.draw(context, 0, y, context.width, height)

class FeedView(itemlist.ItemContainerView):
    """Handles displaying a feed or feed folder"""

    def __init__(self, id, is_folder):
        self.is_folder = is_folder
        itemlist.ItemContainerView.__init__(self, 'feed', id)

    def on_autodownload_changed(self, widget, option):
        setting = ["all", "new", "off"][option]
        messages.AutodownloadChange(self.id, setting).send_to_backend()

    def build_widget(self):
        self.downloads_view = DownloadsHidableList()
        self.full_view = FullList()
        self.downloaded_view = DownloadedHidableList()
        self.all_item_views = [ 
                self.downloads_view, 
                self.full_view,
                self.downloaded_view,
        ]
        for view in self.all_item_views:
            view.item_list.connect('play-video', self.on_play_video)
        widget = widgetset.VBox()
        widget.pack_start(self.build_titlebar())
        if not self.is_folder:
            widget.pack_start(separator.HSeparator())
            widget.pack_start(self.build_toolbar())
        widget.pack_start(separator.HThinSeparator((0.7, 0.7, 0.7)))
        widget.pack_start(self.build_item_list_section(), expand=True)
        return widget

    def build_titlebar(self):
        feed_info = widgetutil.get_feed_info(self.id)
        hbox = widgetset.HBox()
        hbox.pack_start(widgetset.ImageDisplay(imagepool.get(feed_info.thumbnail)))
        hbox.pack_start(TitleDrawer(feed_info.name), padding=15, expand=True)
        background = TitlebarBackground()
        background.add(hbox)
        return background

    def make_toolbar_button(self, text):
        button = widgetset.Button(text, style='smooth')
        return button

    def build_toolbar(self):
        hbox = widgetset.HBox(spacing=5)
        toolbar_gray = (0.43, 0.43, 0.43)

        label = widgetset.Label(_('Auto Download'))
        label.set_size(0.85)
        label.set_color(toolbar_gray)
        label.set_bold(True)

        option_menu = widgetset.OptionMenu((_("All"), _("New"), _("Off")))
        option_menu.set_size(0.85)
        feed_info = widgetutil.get_feed_info(self.id)
        autodownload_mode = feed_info.autodownload_mode
        if autodownload_mode == 'all':
            option_menu.select_option(0)
        elif autodownload_mode == 'new':
            option_menu.select_option(1)
        elif autodownload_mode == 'off':
            option_menu.select_option(2)
        option_menu.connect('changed', self.on_autodownload_changed)
        
        send_button = self.make_toolbar_button(_("Send to a friend"))
        send_button.set_size(0.7)
        send_button.set_color(toolbar_gray)

        settings_button = self.make_toolbar_button(_("Settings"))
        settings_button.set_size(0.7)
        settings_button.set_color(toolbar_gray)

        hbox.pack_start(widgetutil.align_middle(label))
        hbox.pack_start(widgetutil.align_middle(option_menu))
        hbox.pack_end(widgetutil.align_middle(settings_button))
        hbox.pack_end(widgetutil.align_middle(send_button))
        background = ToolbarBackground()
        background.add(widgetutil.pad(hbox, top=4, bottom=4, left=10,
            right=10))
        return background

    def build_item_list_section(self):
        self.item_list_vbox = widgetset.VBox()
        background = widgetset.SolidBackground((1, 1, 1))
        background.add(self.item_list_vbox)
        scroller = widgetset.Scroller(False, True)
        scroller.add(background)
        return scroller

    def expand_lists(self, video_downloaded):
        feed_info = widgetutil.get_feed_info(self.id)
        autodownload_mode = feed_info.autodownload_mode
        if (not video_downloaded or autodownload_mode is None or
                autodownload_mode == 'off'):
            self.full_view.expander.set_expanded(True)
        self.downloaded_view.expander.set_expanded(True)

    def do_handle_item_list(self, message):
        video_downloaded = False
        for item_info in message.items:
            if self.downloaded_view.item_list.filter(item_info):
                video_downloaded = True
                break
        self.expand_lists(video_downloaded)
        for item_view in self.all_item_views:
            self.item_list_vbox.pack_start(item_view)
            item_view.item_list.items_added(message.items)
            item_view.item_list.model_changed()
        self.update_counts()

    def do_handle_items_changed(self, message):
        for item_view in self.all_item_views:
            item_view.item_list.items_removed(message.removed)
            item_view.item_list.items_added(message.added)
            item_view.item_list.items_changed(message.changed)
            item_view.item_list.model_changed()
        self.update_counts()

    def update_counts(self):
        downloads = self.downloads_view.get_count()
        watchable = self.downloaded_view.get_count()
        for item_view in self.all_item_views:
            item_view.update_counts(downloads, watchable)
