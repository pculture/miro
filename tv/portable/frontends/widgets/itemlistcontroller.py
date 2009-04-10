# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""itemlistcontroller.py -- Controllers for item lists.

itemlist, itemlistcontroller and itemlistwidgets work together using the MVC
pattern.  itemlist handles the Model, itemlistwidgets handles the View and
itemlistcontroller handles the Controller.

This module contains the ItemListController base class along with controllers
that work for the static tabs which are pretty simple cases.
"""

import logging
import os
from urlparse import urljoin

from miro import app
from miro import messages
from miro import menubar
from miro import subscription
from miro.gtcache import gettext as _
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import separator
from miro.plat.frontends.widgets import widgetset
from miro.plat import resources

class ItemListDragHandler(object):
    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY | widgetset.DRAG_ACTION_MOVE

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

class ItemListController(object):
    """Base class for controllers that manage list of items.
    
    Attributes:
        widget -- Widget used to display this controller
    """
    def __init__(self, type, id):
        """Construct a ItemListController.

        type and id are the same as in the constructor to messages.TrackItems
        """
        self.type = type
        self.id = id
        self.current_item_view = None
        self._search_text = ''
        self._init_widget()
        item_lists = set(iv.item_list for iv in self.all_item_views())
        sorter = app.frontend_states_memory.query_sort_state(type, id)
        self.item_list_group = itemlist.ItemListGroup(item_lists, sorter)
        self._init_item_views()
        self.initialize_search()
        sorter = self.item_list_group.get_sort()
        self.widget.toolbar.change_sort_indicator(sorter.KEY, sorter.is_ascending())
        self.list_item_view.change_sort_indicator(sorter.KEY, sorter.is_ascending())

    def _init_widget(self):
        self.widget = itemlistwidgets.ItemContainerWidget()
        self.item_list = itemlist.ItemList()
        self.list_item_view = self.build_list_item_view()
        scroller = widgetset.Scroller(True, True)
        scroller.add(self.list_item_view)
        self.widget.list_view_vbox.pack_start(scroller, expand=True)
        self.widget.toolbar.connect_weak('sort-changed', self.on_sort_changed)
        self.list_item_view.connect_weak('sort-changed', self.on_sort_changed)
        self.build_widget()
        sorter = self.item_list.get_sort()
        if sorter is not None:
            self.widget.toolbar.change_sort_indicator(sorter.KEY, sorter.is_ascending())

    def build_list_item_view(self):
        return itemlistwidgets.ListItemView(self.item_list)

    def _init_item_views(self):
        self.context_menu_handler = self.make_context_menu_handler()
        context_callback = self.context_menu_handler.callback
        for item_view in self.all_item_views():
            item_view.connect_weak('selection-changed', self.on_selection_changed)
            item_view.connect_weak('hotspot-clicked', self.on_hotspot_clicked)
            item_view.connect_weak('key-press', self.on_key_press)
            item_view.connect_weak('row-double-clicked',
                    self.on_row_double_clicked)
            item_view.set_context_menu_callback(context_callback)
            item_view.set_drag_source(self.make_drag_handler())
            item_view.set_drag_dest(self.make_drop_handler())

    def initialize_search(self):
        search = app.inline_search_memory.get_search(self.type, self.id)
        if search != '':
            self.titlebar.set_search_text(search)
            self.set_search(search)

    def get_selection(self):
        """Get the currently selected items.  Returns a list of ItemInfos."""
        item_view = self.current_item_view
        if item_view is None:
            return []
        return [item_view.model[i][0] for i in item_view.get_selection()]

    def get_selection_for_playing(self):
        if self.current_item_view is None:
            item_view = self.default_item_view()
        else:
            item_view = self.current_item_view
        selection = self.get_selection()
        if len(selection) == 0:
            items = item_view.item_list.get_items()
        elif len(selection) == 1:
            id = selection[0].id
            items = item_view.item_list.get_items(start_id=id)
        else:
            items = selection
        return items
        
    def play_selection(self, presentation_mode='fit-to-bounds'):
        """Play the currently selected items."""
        items = self.get_selection_for_playing()
        if len(items) > 0:
            self._play_item_list(items, presentation_mode)
            
    def filter_playable_items(self, items):
        return [i for i in items if i.video_path is not None and i.video_path is not '' and i.downloaded]

    def _play_item_list(self, items, presentation_mode='fit-to-bounds'):
        playable = self.filter_playable_items(items)
        if len(playable) > 0:
            app.playback_manager.start_with_items(playable, presentation_mode)

    def set_search(self, search_text):
        """Set the search for all ItemViews managed by this controller.  """
        self._search_text = search_text
        self.item_list_group.set_search_text(search_text)
        for item_view in self.all_item_views():
            item_view.model_changed()
        app.inline_search_memory.set_search(self.type, self.id, search_text)

    def on_row_double_clicked(self, item_view, iter):
        info = item_view.model[iter][0]
        if info.downloaded:
            items = item_view.item_list.get_items(start_id=info.id)
            self._play_item_list(items)
        elif info.state == 'downloading':
            messages.PauseDownload(info.id).send_to_backend()
        elif info.state == 'paused':
            messages.ResumeDownload(info.id).send_to_backend()
        elif info.download_info is None:
            messages.StartDownload(info.id).send_to_backend()

    def on_sort_changed(self, object, sort_key, ascending):
        sorter = itemlist.SORT_KEY_MAP[sort_key](ascending)
        for item_list in self.item_list_group.item_lists:
            item_list.set_sort(sorter)
        for item_view in self.all_item_views():
            item_view.model_changed()
        self.widget.toolbar.change_sort_indicator(sort_key, ascending)
        self.list_item_view.change_sort_indicator(sort_key, ascending)
        app.frontend_states_memory.set_sort_state(self.type, self.id, sorter)

    def on_key_press(self, view, key, mods):
        if key == menubar.DELETE:
            return self.handle_delete()

    def handle_delete(self):
        app.widgetapp.remove_items(self.get_selection())
        return True

    def on_hotspot_clicked(self, itemview, name, iter):
        """Hotspot handler for ItemViews."""

        item_info = itemview.model[iter][0]
        show_details = itemview.model[iter][1]
        if name in ('download', 'thumbnail-download'):
            messages.StartDownload(item_info.id).send_to_backend()
        elif name == 'pause':
            messages.PauseDownload(item_info.id).send_to_backend()
        elif name == 'resume':
            messages.ResumeDownload(item_info.id).send_to_backend()
        elif name == 'cancel':
            messages.CancelDownload(item_info.id).send_to_backend()
        elif name == 'keep':
            messages.KeepVideo(item_info.id).send_to_backend()
        elif name == 'stop_seeding':
            messages.StopUpload(item_info.id).send_to_backend()
        elif name == 'start_seeding':
            messages.StartUpload(item_info.id).send_to_backend()
        elif name == 'delete':
            app.widgetapp.remove_items(selection=[item_info])
        elif name == 'remove':
            messages.RemoveVideosFromPlaylist(itemview.playlist_id, [item_info.id]).send_to_backend()
        elif name == 'details_toggle':
            itemview.model.update_value(iter, 1, not show_details)
            itemview.model_changed()
            itemview.invalidate_size_request()
        elif name == 'visit_webpage':
            app.widgetapp.open_url(item_info.permalink)
        elif name == 'visit_comments':
            app.widgetapp.open_url(item_info.commentslink)
        elif name == 'visit_filelink':
            app.widgetapp.open_url(item_info.file_url)
        elif name == 'visit_license':
            app.widgetapp.open_url(item_info.license)
        elif name == 'show_local_file':
            app.widgetapp.check_then_reveal_file(item_info.video_path)
        elif name.startswith('description-link:'):
            url = name.split(':', 1)[1]
            base_href = widgetutil.get_feed_info(item_info.feed_id).base_href
            if subscription.is_subscribe_link(url):
                messages.SubscriptionLinkClicked(url).send_to_backend()
            else:
                app.widgetapp.open_url(urljoin(base_href, url))
        elif name in ('play', 'thumbnail-play'):
            id = item_info.id
            items = itemview.item_list.get_items(start_id=id)
            self._play_item_list(items)

    def on_selection_changed(self, item_view):
        if (item_view is not self.current_item_view and
                item_view.num_rows_selected() == 0):
            # This is the result of us calling unselect_all() below
            return

        if item_view is not self.current_item_view:
            self.current_item_view = item_view
            for other_view in self.normal_item_views():
                if other_view is not item_view:
                    other_view.unselect_all()

        app.menu_manager.update_menus()

    def start_tracking(self):
        """Send the message to start tracking items."""
        messages.TrackItems(self.type, self.id).send_to_backend()
        app.info_updater.item_list_callbacks.add(self.type, self.id,
                self.handle_item_list)
        app.info_updater.item_changed_callbacks.add(self.type, self.id,
                self.handle_items_changed)

    def stop_tracking(self):
        """Send the message to stop tracking items."""
        messages.StopTrackingItems(self.type, self.id).send_to_backend()
        app.info_updater.item_list_callbacks.remove(self.type, self.id,
                self.handle_item_list)
        app.info_updater.item_changed_callbacks.remove(self.type, self.id,
                self.handle_items_changed)

    def handle_item_list(self, message):
        """Handle an ItemList message meant for this ItemContainer."""
        self.item_list_group.add_items(message.items)
        for item_view in self.all_item_views():
            item_view.model_changed()
        self.on_initial_list()

    def handle_items_changed(self, message):
        """Handle an ItemsChanged message meant for this ItemContainer."""
        self.item_list_group.remove_items(message.removed)
        self.item_list_group.update_items(message.changed)
        self.item_list_group.add_items(message.added)
        for item_view in self.all_item_views():
            item_view.model_changed()
        self.on_items_changed()

    def on_initial_list(self):
        """Called after we have receieved the initial list of items.

        Subclasses can override this method if they want.
        """
        pass

    def on_items_changed(self):
        """Called after we have changes to items

        Subclasses can override this method if they want.
        """
        pass

    def make_context_menu_handler(self):
        return itemcontextmenu.ItemContextMenuHandler()

    def make_drag_handler(self):
        return ItemListDragHandler()

    def make_drop_handler(self):
        return None

    def build_widget(self):
        """Build the widget for this controller."""
        raise NotImplementedError()

    def normal_item_views(self):
        """Return a list of ItemViews used by this controller."""
        raise NotImplementedError()

    def all_item_views(self):
        for item_view in self.normal_item_views():
            yield item_view
        yield self.list_item_view

    def default_item_view(self):
        """ItemView play from if no videos are selected."""
        raise NotImplementedError()

class SimpleItemListController(ItemListController):
    def __init__(self):
        ItemListController.__init__(self, self.type, self.id)

    def build_widget(self):
        self.titlebar = self.make_titlebar()
        self.item_view = self.build_item_view()
        self.widget.titlebar_vbox.pack_start(self.titlebar)
        scroller = widgetset.Scroller(False, True)
        scroller.add(self.item_view)
        self.widget.normal_view_vbox.pack_start(scroller, expand=True)

    def build_item_view(self):
        return itemlistwidgets.ItemView(self.item_list)

    def make_titlebar(self):
        icon = self._make_icon()
        titlebar = itemlistwidgets.ItemListTitlebar(self.title, icon)
        titlebar.connect('search-changed', self._on_search_changed)
        return titlebar

    def _on_search_changed(self, widget, search_text):
        self.set_search(search_text)

    def normal_item_views(self):
        return [self.item_view]

    def default_item_view(self):
        return self.item_view

    def _make_icon(self):
        image_path = resources.path("images/%s" % self.image_filename)
        return imagepool.get(image_path)

    def on_initial_list(self):
        self.check_for_empty_list()

    def on_items_changed(self):
        self.check_for_empty_list()

    def check_for_empty_list(self):
        list_empty = (self.item_list.get_count() == 0)
        self.widget.set_list_empty_mode(list_empty)

class SearchController(SimpleItemListController):
    type = 'search'
    id = None
    image_filename = 'icon-search_large.png'
    title = _("Video Search")

    def __init__(self):
        SimpleItemListController.__init__(self)
        self.toolbar = itemlistwidgets.SearchToolbar()
        self.toolbar.connect("save-search", self._on_save_search)
        if app.search_manager.text != '':
            self.toolbar.show()
        sep = separator.HSeparator((0.85, 0.85, 0.85), (0.95, 0.95, 0.95))
        self.widget.titlebar_vbox.pack_start(sep)
        self.widget.titlebar_vbox.pack_start(self.toolbar)

    def build_widget(self):
        SimpleItemListController.build_widget(self)
        text = _('No Results Found')
        self.widget.list_empty_mode_vbox.pack_start(
                itemlistwidgets.EmptyListHeader(text))

    def initialize_search(self):
        if app.search_manager.text != '':
            self.titlebar.set_search_text(app.search_manager.text)
        self.titlebar.set_search_engine(app.search_manager.engine)

    def on_initial_list(self):
        if (not app.search_manager.searching and app.search_manager.text != ''
                and self.item_list.get_count() == 0):
            self.widget.set_list_empty_mode(True)

    def on_items_changed(self):
        # Don't check for an empty list here.  Since items don't get removed
        # from the search feed, we don't need to do anything.  Also, it
        # results in a false positive just after the search starts when the
        # items from the last search get removed (#11255)
        pass

    def make_titlebar(self):
        icon = self._make_icon()
        titlebar = itemlistwidgets.SearchListTitlebar(self.title, icon)
        return titlebar

    def _on_save_search(self, widget):
        engine = self.titlebar.get_engine()
        search_text = self.titlebar.get_text()
        app.search_manager.perform_search(engine, search_text)
        if search_text != '':
            app.search_manager.save_search()

    def start_tracking(self):
        SimpleItemListController.start_tracking(self)
        self._started_handle = app.search_manager.connect('search-started',
                self._on_search_started)
        self._complete_handle = app.search_manager.connect('search-complete',
                self._on_search_complete)

    def stop_tracking(self):
        SimpleItemListController.stop_tracking(self)
        app.search_manager.disconnect(self._started_handle)
        app.search_manager.disconnect(self._complete_handle)

    def _on_search_started(self, search_manager):
        self.titlebar.set_search_text(search_manager.text)
        self.titlebar.set_search_engine(search_manager.engine)
        self.widget.set_list_empty_mode(False)
        if search_manager.text != '':
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def _on_search_complete(self, search_manager, result_count):
        if search_manager.text != '' and result_count == 0:
            self.widget.set_list_empty_mode(True)

class AudioVideoItemsController(SimpleItemListController):
    def build_item_view(self):
        return itemlistwidgets.ItemView(self.item_list, True)
    def build_list_item_view(self):
        return itemlistwidgets.ListItemView(self.item_list,
                display_download_info=False)

class VideoItemsController(AudioVideoItemsController):
    type = 'videos'
    id = None
    image_filename = 'icon-library_large.png'
    title = _("Video")

class AudioItemsController(AudioVideoItemsController):
    type = 'audios'
    id = None
    image_filename = 'icon-library_large.png'
    title = _("Audio")

class OtherItemsController(SimpleItemListController):
    type = 'others'
    id = None
    image_filename = 'icon-new_large.png'
    title = _("Other")

    def build_item_view(self):
        return itemlistwidgets.ItemView(self.item_list, True)

    def build_list_item_view(self):
        return itemlistwidgets.ListItemView(self.item_list,
                display_download_info=False)

class ItemListControllerManager(object):
    """Manages ItemListController objects.

    Attributes:

    displayed -- Currently displayed ItemListController or None (this one is
        currently being displayed in the right-hand side)
    all_controllers -- Set of all ItemListControllers in use (these are
        somewhere in the display stack, but not necessarily displayed
        currently).
    """

    def __init__(self):
        self.displayed = None
        self.all_controllers = set()

    def controller_displayed(self, item_list_controller):
        self.displayed = item_list_controller

    def controller_no_longer_displayed(self, item_list_controller):
        if item_list_controller is not self.displayed:
            logging.warn("controller is not displayed in "
                    "controller_no_longer_displayed()")
        self.displayed = None

    def controller_created(self, item_list_controller):
        self.all_controllers.add(item_list_controller)

    def controller_destroyed(self, item_list_controller):
        self.all_controllers.remove(item_list_controller)

    def play_selection(self, presentation_mode='fit-to-bounds'):
        if self.displayed is not None:
            self.displayed.play_selection(presentation_mode)

    def get_selection(self):
        if self.displayed is None:
            return []
        else:
            return self.displayed.get_selection()

    def get_current_playlist(self):
        """Get the items that would be played if we started playback."""
        if self.displayed is not None:
            selection = self.displayed.get_selection_for_playing()
            return self.displayed.filter_playable_items(selection)
        else:
            return []
