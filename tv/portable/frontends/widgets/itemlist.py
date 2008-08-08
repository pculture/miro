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
from miro.frontends.widgets import style
from miro.frontends.widgets import separator
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import use_custom_titlebar_background
from miro.plat import resources

def sort_items(item_list):
    item_list.sort(key=lambda i: i.release_date, reverse=True)

class ItemListDragHandler(object):
    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def allowed_types(self):
        return ('downloaded-item',)

    def begin_drag(self, tableview, rows):
        videos = []
        for row in rows:
            item_info = row[0]
            if item_info.downloaded:
                videos.append(item_info)
        if videos:
            data = '-'.join(str(info.id) for info in videos)
            return {'downloaded-item':  data }
        else:
            return None

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
        app.item_list_manager.manage_item_list(self)
        self.set_context_menu_callback(self.on_context_menu)
        self.set_drag_source(ItemListDragHandler())
        self.set_background_color(widgetutil.WHITE)

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
            self.emit('play-video', item_info.id)
        else:
            print 'hotspot clicked: ', name, item_info.name

    def setup_info(self, info):
        """Initialize a newly recieved ItemInfo."""
        info.icon = imagepool.LazySurface(info.thumbnail, (154, 105))

    def get_items(self):
        return [row[0] for row in self.model]

    def get_watchable_videos(self, start_id=None):
        infos = self.get_items()
        if start_id is not None:
            for i in xrange(len(infos)):
                if infos[i].id == start_id:
                    break
            infos = infos[i:]
        return filter(lambda info: info.downloaded, infos)

    def insert_sorted_items(self, item_list):
        insert_pos = self.model.first_iter()
        for item_info in item_list:
            self.setup_info(item_info)
            while (insert_pos is not None and 
                    self.model[insert_pos][0].release_date > 
                    item_info.release_date):
                insert_pos = self.model.next_iter(insert_pos)
            iter = self.model.insert_before(insert_pos, item_info)
            self.item_iters[item_info.id] = iter

    def update_item(self, iter, item_info):
        self.setup_info(item_info)
        self.model.update(iter, item_info)

    def on_context_menu(self, tableview):
        selected = [self.model[iter][0] for iter in self.get_selection()]
        if len(selected) == 1:
            return self.make_context_menu_single(selected[0])
        else:
            return self.make_context_menu_multiple(selected)

    def _remove_context_menu_item(self, selection):
        return (_('Remove From the Library'), app.widgetapp.remove_videos)

    def _add_remove_context_menu_item(self, menu, selection):
        remove = self._remove_context_menu_item(selection)
        if remove is not None:
            menu.append(remove)

    def make_context_menu_single(self, item):
        if item.downloaded:
            def play_and_stop():
                app.playback_manager.start_with_items([item])

            menu = [
                (_('Play'), app.widgetapp.play_selection),
                (_('Play Just this Video'), play_and_stop),
                (_('Add to New Playlist'), app.widgetapp.add_new_playlist),
            ]
            self._add_remove_context_menu_item(menu, [item])
            if item.video_watched:
                menu.append((_('Mark as Unwatched'),
                    messages.MarkItemUnwatched(item.id).send_to_backend))
            else:
                menu.append((_('Mark as Watched'),
                    messages.MarkItemWatched(item.id).send_to_backend))
            if (item.download_info and item.download_info.torrent and
                    item.download_info.state != 'uploading'):
                menu.append((_('Restart Upload'),
                    messages.RestartUpload(item.id).send_to_backend))
        elif item.download_info is not None:
            menu = [
                    (_('Cancel Download'), 
                        messages.CancelDownload(item.id).send_to_backend)
            ]
            if item.download_info.state != 'paused':
                menu.append((_('Pause Download'),
                        messages.PauseDownload(item.id).send_to_backend))
            else:
                menu.append((_('Resume Download'),
                        messages.ResumeDownload(item.id).send_to_backend))
        else:
            menu = [
                (_('Download'),
                    messages.StartDownload(item.id).send_to_backend)
            ]
        return menu

    def make_context_menu_multiple(self, selection):
        watched = unwatched = downloaded = downloading = available = uploadable = 0
        for info in selection:
            if info.downloaded:
                downloaded += 1
                if info.video_watched:
                    watched += 1
                else:
                    unwatched += 1
            elif info.download_info is not None:
                downloading += 1
                if (info.download_info.torrent and
                        info.download_info.state != 'uploading'):
                    uploadable += 1
            else:
                available += 1

        menu = []
        if downloaded > 0:
            menu.append((_('%d Downloaded Items') % downloaded, None))
            menu.append((_('Play'), app.widgetapp.play_selection)),
            menu.append((_('Add to New Playlist'),
                app.widgetapp.add_new_playlist))
            self._add_remove_context_menu_item(menu, selection)
            if watched:
                def mark_unwatched():
                    for item in selection:
                        messages.MarkItemUnwatched(item.id).send_to_backend()
                menu.append((_('Mark as Unwatched'), mark_unwatched))
            if unwatched:
                def mark_watched():
                    for item in selection:
                        messages.MarkItemWatched(item.id).send_to_backend()
                menu.append((_('Mark as Watched'), mark_watched))

        if available > 0:
            if len(menu) > 0:
                menu.append(None)
            menu.append((_('%d Available Items') % available, None))
            def download_all():
                for item in selection:
                    messages.StartDownload(item.id).send_to_backend()
            menu.append((_('Download'), download_all))

        if downloading:
            if len(menu) > 0:
                menu.append(None)
            menu.append((_('%d Downloading Items') % downloading, None))
            def cancel_all():
                for item in selection:
                    messages.CancelDownload(item.id).send_to_backend()
            def pause_all():
                for item in selection:
                    messages.PauseDownload(item.id).send_to_backend()
            menu.append((_('Cancel Download'), cancel_all))
            menu.append((_('Pause Download'), pause_all))

        if uploadable > 0:
            def restart_all():
                for item in selection:
                    messages.RestartUpload(item.id).send_to_backend()
            menu.append((_('Restart Upload'), restart_all))

        return menu

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
            self.update_item(iter, item_info)

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
                    self.update_item(iter, item_info)
                else:
                    self.model.remove(iter)
                    del self.item_iters[item_info.id]
        sort_items(to_add)
        self.insert_sorted_items(to_add)

class ItemContainerView(signals.SignalEmitter):
    """Base class for views that display objects that contain items (feeds,
    playlists, folders, downloads tab, etc).
    """
    SORT_ITEMS = True

    def __init__(self, type, id):
        signals.SignalEmitter.__init__(self)
        self.create_signal('play-videos')
        self.type = type
        self.id = id
        self.widget = self.build_widget()
        self.start_tracking()

    def build_widget(self):
        raise NotImplementedError()

    def default_item_list(self):
        """Item list to play from if no videos are selected."""
        raise NotImplementedError()

    def should_handle_message(self, message):
        """Inspect a ItemList or ItemsChanged message and figure out if it's
        meant for this ItemList.
        """
        return message.type == self.type and message.id == self.id

    def do_handle_item_list(self, message):
        """Handle an incomming item list.  They will be already sorted.
        """
        pass

    def do_handle_items_changed(self, message):
        """Handle an items changed message.  They will already be sorted.
        """
        pass

    def handle_item_list(self, message):
        if self.SORT_ITEMS:
            sort_items(message.items)
        self.do_handle_item_list(message)

    def handle_items_changed(self, message):
        sort_items(message.added)
        self.do_handle_items_changed(message)

    def on_play_video(self, item_list, id):
        self.emit('play-videos', item_list.get_watchable_videos(start_id=id))

    def start_tracking(self):
        messages.TrackItems(self.type, self.id).send_to_backend()

    def stop_tracking(self):
        messages.StopTrackingItems(self.type, self.id).send_to_backend()

class SimpleItemContainer(ItemContainerView):
    def __init__(self):
        ItemContainerView.__init__(self, self.type, self.id)

    def make_item_list(self):
        return ItemList()

    def default_item_list(self):
        return self.item_list

    def build_widget(self):
        vbox = widgetset.VBox()
        vbox.pack_start(self.build_titlebar())
        vbox.pack_start(separator.HThinSeparator((0.7, 0.7, 0.7)))
        self.item_list = self.make_item_list()
        self.item_list.connect('play-video', self.on_play_video)
        scroller = widgetset.Scroller(False, True)
        scroller.add(self.item_list)
        vbox.pack_start(scroller, expand=True)
        return vbox

    def build_titlebar(self):
        hbox = widgetset.HBox()
        image_path = resources.path("wimages/%s" % self.image_filename)
        im = widgetutil.align(widgetset.ImageDisplay(imagepool.get(image_path)),
                              xscale=1, yscale=1)
        im.set_size_request(61, 61)
        hbox.pack_start(im)
        from miro.frontends.widgets.feedview import TitleDrawer
        hbox.pack_start(TitleDrawer(self.title), padding=15, expand=True)

        if not use_custom_titlebar_background:
            return hbox
        else:
            from miro.frontends.widgets.feedview import TitlebarBackground
            background = TitlebarBackground()
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
    type = 'downloads'
    id = None
    image_filename = 'icon-downloading_large.png'
    title = _("Downloads")

class NewView(SimpleItemContainer):
    type = 'new'
    id = None
    image_filename = 'icon-new_large.png'
    title = _("New Videos")

class LibraryView(SimpleItemContainer):
    type = 'library'
    id = None
    image_filename = 'icon-library_large.png'
    title = _("Library")

class IndividualDownloadsView(SimpleItemContainer):
    type = 'individual_downloads'
    id = None
    image_filename = 'icon-individual_large.png'
    title = _("Individual Downloads")
