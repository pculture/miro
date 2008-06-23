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

"""itemlist.py -- Classes that display a list of items.
"""

import itertools
from urlparse import urljoin

from miro import app
from miro import messages
from miro import signals
from miro.gtcache import gettext as _
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import use_custom_titlebar_background
from miro.plat import resources

def sort_items(item_list):
    item_list.sort(key=lambda i: i.release_date, reverse=True)

class ItemListBase(widgetset.TableView):
    """TableView containing a list of items."""
    def __init__(self):
        model = widgetset.TableModel('object')
        widgetset.TableView.__init__(self, model)
        self.set_draws_selection(False)
        renderer = style.ItemRenderer()
        self.add_column('item', 0, renderer, renderer.MIN_WIDTH)
        self.set_show_headers(False)
        self.allow_multiple_select(True)
        self.create_signal('play-video')
        self.item_iters = {}

    def do_hotspot_clicked(self, name, iter):
        item_info = self.model[iter][0]
        if name == 'download':
            messages.StartDownload(item_info.id).send_to_backend()
        elif name == 'pause':
            messages.PauseDownload(item_info.id).send_to_backend()
        elif name == 'resume':
            messages.ResumeDownload(item_info.id).send_to_backend()
        elif name == 'cancel':
            messages.CancelDownload(item_info.id).send_to_backend()
        elif name == 'keep':
            messages.KeepVideo(item_info.id).send_to_backend()
        elif name == 'delete':
            messages.DeleteVideo(item_info.id).send_to_backend()
        elif name.startswith('description-link:'):
            url = name.split(':', 1)[1]
            base_href = widgetutil.get_feed_info(item_info.feed_id).base_href
            app.widgetapp.open_url(urljoin(base_href, url))
        elif name == 'play':
            self.emit('play-video', item_info.video_path)
        else:
            print 'hotspot clicked: ', name, item_info.name

    def insert_sorted_items(self, item_list):
        insert_pos = self.model.first_iter()
        for item_info in item_list:
            while (insert_pos is not None and 
                    self.model[insert_pos][0].release_date > 
                    item_info.release_date):
                insert_pos = self.model.next_iter(insert_pos)
            iter = self.model.insert_before(insert_pos, item_info)
            self.item_iters[item_info.id] = iter

class ItemList(ItemListBase):
    def items_added(self, item_list):
        self.insert_sorted_items(item_list)

    def items_removed(self, id_list):
        for id in id_list:
            iter = self.item_iters.pop(id)
            self.model.remove(iter)

    def items_changed(self, item_list):
        for item_info in item_list:
            iter = self.item_iters[item_info.id]
            self.model.update(iter, item_info)

class FilteredItemList(ItemListBase):
    """ItemListBase that only contains a portion of the items (downloading and
    downloaded lists.)
    """
    def filter(self, item_info):
        raise NotImplentedError()

    def items_added(self, item_list):
        item_list = [info for info in item_list if self.filter(info)]
        self.insert_sorted_items(item_list)

    def items_removed(self, id_list):
        for id in id_list:
            try:
                iter = self.item_iters.pop(id)
            except KeyError:
                pass
            else:
                self.model.remove(iter)

    def items_changed(self, item_list):
        to_add = []
        for item_info in item_list:
            try:
                iter = self.item_iters[item_info.id]
            except KeyError:
                if self.filter(item_info):
                    to_add.append(item_info)
            else:
                if self.filter(item_info):
                    self.model.update(iter, item_info)
                else:
                    self.model.remove(iter)
                    del self.item_iters[item_info.id]
        sort_items(to_add)
        self.insert_sorted_items(to_add)

class ItemContainerView(signals.SignalEmitter):
    """Base class for views that display objects that contain items (feeds,
    playlists, folders, downloads tab, etc).
    """

    def __init__(self, feed_id):
        signals.SignalEmitter.__init__(self)
        self.create_signal('play-video')
        self.feed_id = feed_id
        self.widget = self.build_widget()
        self.start_tracking()

    def build_widget(self):
        raise NotImplementedError()

    def do_handle_item_list(self, message):
        """Handle an incomming item list.  They will be already sorted.
        """

    def do_handle_items_changed(self, message):
        """Handle an items changed message.  They will already be sorted.
        """

    def handle_item_list(self, message):
        sort_items(message.items)
        self.do_handle_item_list(message)

    def handle_items_changed(self, message):
        sort_items(message.added)
        self.do_handle_items_changed(message)

    def on_play_video(self, item_list, path):
        self.emit('play-video', path) # Just forward it along

    def start_tracking(self):
        messages.TrackItemsForFeed(self.feed_id).send_to_backend()

    def stop_tracking(self):
        messages.StopTrackingItemsForFeed(self.feed_id).send_to_backend()

class SimpleItemContainer(ItemContainerView):
    def __init__(self):
        ItemContainerView.__init__(self, self.feed_id)

    def build_widget(self):
        vbox = widgetset.VBox()
        vbox.pack_start(self.build_titlebar())
        self.item_list = ItemList()
        scroller = widgetset.Scroller(False, True)
        scroller.add(self.item_list)
        vbox.pack_start(scroller, expand=True)
        return vbox

    def build_titlebar(self):
        hbox = widgetset.HBox()
        image_path = resources.path("wimages/%s" % self.image_filename)
        hbox.pack_start(widgetset.ImageDisplay(imagepool.get(image_path)))
        title = widgetset.Label(self.title)
        title.set_size(2.5)
        title.set_color((0.31, 0.31, 0.31))
        hbox.pack_start(title, padding=15)
        if not use_custom_titlebar_background:
            return hbox
        else:
            background = widgetset.SolidBackground((0.91, 0.91, 0.91))
            background.add(hbox)
            return background

    def do_handle_item_list(self, message):
        self.item_list.items_added(message.items)
        self.item_list.model_changed()

    def do_handle_items_changed(self, message):
        self.item_list.items_added(message.added)
        self.item_list.items_changed(message.changed)
        self.item_list.items_removed(message.removed)
        self.item_list.model_changed()

class DownloadsView(SimpleItemContainer):
    feed_id = messages.TrackItemsForFeed.DOWNLOADING
    image_filename = 'icon-downloading_large.png'
    title = _("Downloads")

class NewView(SimpleItemContainer):
    feed_id = messages.TrackItemsForFeed.NEW
    image_filename = 'icon-new_large.png'
    title = _("New Videos")

class LibraryView(SimpleItemContainer):
    feed_id = messages.TrackItemsForFeed.LIBRARY
    image_filename = 'icon-library_large.png'
    title = _("Library")
