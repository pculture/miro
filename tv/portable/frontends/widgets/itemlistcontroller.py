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

"""itemlistcontroller.py -- Controllers for item lists.

itemlist, itemlistcontroller and itemlistwidgets work togetherusing the MVC
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
from miro import subscription
from miro.gtcache import gettext as _
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil
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
        self.widget = self.build_widget()
        item_lists = [iv.item_list for iv in self.all_item_views()]
        self.item_list_group = itemlist.ItemListGroup(item_lists)
        self.context_menu_handler = self.make_context_menu_handler()
        context_callback = self.context_menu_handler.callback
        for item_view in self.all_item_views():
            item_view.connect('hotspot-clicked', self.on_hotspot_clicked)
            item_view.connect('selection-changed', self.on_selection_changed)
            item_view.set_context_menu_callback(context_callback)
            item_view.set_drag_source(self.make_drag_handler())
            item_view.set_drag_dest(self.make_drop_handler())
        self.initialize_search()

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
        
    def play_selection(self):
        """Play the currently selected items."""
        items = self.get_selection_for_playing()
        if len(items) > 0:
            self._play_item_list(items)
            
    def filter_playable_items(self, items):
        return [i for i in items if i.video_path is not None and i.video_path is not '']

    def _play_item_list(self, items):
        playable = self.filter_playable_items(items)
        if len(playable) > 0:
            app.playback_manager.start_with_items(playable)

    def set_search(self, search_text):
        """Set the search for all ItemViews managed by this controller.  """
        self._search_text = search_text
        self.item_list_group.set_search_text(search_text)
        for item_view in self.all_item_views():
            item_view.model_changed()
        app.inline_search_memory.set_search(self.type, self.id, search_text)

    def on_sort_changed(self, sort_bar, sort_key, ascending):
        sort_key_map = {
                'date': itemlist.DateSort,
                'name': itemlist.NameSort,
                'length': itemlist.LengthSort,
                'size': itemlist.SizeSort
        }
        sorter = sort_key_map[sort_key](ascending)
        for item_view in self.all_item_views():
            item_view.item_list.set_sort(sorter)
            item_view.model_changed()

    def on_hotspot_clicked(self, itemview, name, iter):
        """Hotspot handler for ItemViews."""

        item_info, show_details, counter = itemview.model[iter]
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
            if not os.path.exists(item_info.video_path):
                basename = os.path.basename(item_info.video_path)
                dialogs.show_message(
                    _("Error Revealing File"),
                    _("The file \"%(filename)s\" was deleted from outside Miro.",
                      {"filename": basename}),
                    dialogs.WARNING_MESSAGE)
            else:
                app.widgetapp.open_file(item_info.video_path)
        elif name.startswith('description-link:'):
            url = name.split(':', 1)[1]
            base_href = widgetutil.get_feed_info(item_info.feed_id).base_href
            if subscription.is_subscribe_link(url):
                messages.SubscriptionLinkClicked(url).send_to_backend()
            else:
                app.widgetapp.open_url(urljoin(base_href, url))
        elif name == 'play':
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
            for other_view in self.all_item_views():
                if other_view is not item_view:
                    other_view.unselect_all()

        items = self.get_selection()
        app.menu_manager.handle_item_list_selection(items)

    def should_handle_message(self, message):
        """Inspect a ItemList or ItemsChanged message and figure out if it's
        meant for this ItemList.
        """
        return message.type == self.type and message.id == self.id

    def start_tracking(self):
        """Send the message to start tracking items."""
        messages.TrackItems(self.type, self.id).send_to_backend()

    def stop_tracking(self):
        """Send the message to stop tracking items."""
        messages.StopTrackingItems(self.type, self.id).send_to_backend()

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

    def all_item_views(self):
        """Return a list of ItemViews used by this controller."""
        raise NotImplementedError()

    def default_item_view(self):
        """ItemView play from if no videos are selected."""
        raise NotImplementedError()

class SimpleItemListController(ItemListController):
    def __init__(self):
        ItemListController.__init__(self, self.type, self.id)

    def build_widget(self):
        widget = itemlistwidgets.ItemContainerWidget()
        widget.sort_bar.connect('sort-changed', self.on_sort_changed)
        self.titlebar = self.make_titlebar()
        self.item_list = itemlist.ItemList()
        self.item_view = self.build_item_view()
        widget.titlebar_vbox.pack_start(self.titlebar)
        widget.content_vbox.pack_start(self.item_view)
        return widget

    def build_item_view(self):
        return itemlistwidgets.ItemView(self.item_list)

    def make_titlebar(self):
        icon = self._make_icon()
        titlebar = itemlistwidgets.ItemListTitlebar(self.title, icon)
        titlebar.connect('search-changed', self._on_search_changed)
        return titlebar

    def _on_search_changed(self, widget, search_text):
        self.set_search(search_text)

    def all_item_views(self):
        return [self.item_view]

    def default_item_view(self):
        return self.item_view

    def _make_icon(self):
        image_path = resources.path("images/%s" % self.image_filename)
        return imagepool.get(image_path)

class NewController(SimpleItemListController):
    type = 'new'
    id = None
    image_filename = 'icon-new_large.png'
    title = _("New Videos")

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
        self.widget.titlebar_vbox.pack_start(self.toolbar)

    def build_widget(self):
        widget = SimpleItemListController.build_widget(self)
        label = widgetset.Label(_('No Results Found'))
        label.set_size(2)
        self.no_results_label = widgetutil.HideableWidget(label)
        widget.content_vbox.pack_start(self.no_results_label)
        return widget

    def initialize_search(self):
        if app.search_manager.text != '':
            self.titlebar.set_search_text(app.search_manager.text)

    def on_initial_list(self):
        if (not app.search_manager.searching and app.search_manager.text != ''
                and self.item_list.get_count() == 0):
            self.no_results_label.show()

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
        self.no_results_label.hide()
        if search_manager.text != '':
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def _on_search_complete(self, search_manager, result_count):
        if search_manager.text != '' and result_count == 0:
            self.no_results_label.show()

class LibraryController(SimpleItemListController):
    type = 'library'
    id = None
    image_filename = 'icon-library_large.png'
    title = _("Library")

class IndividualDownloadsController(SimpleItemListController):
    type = 'individual_downloads'
    id = None
    image_filename = 'icon-individual_large.png'
    title = _("Single Items")

class ItemListControllerManager(object):
    """Manages ItemListController objects.

    Attributes:

    displayed -- Currently displayed ItemListController or None (this one is
        currently being displayed in the right-hand side)
    all_controllers -- Set of all ItemListControllers in use (these are
        somewhere in the display stack, but not neccesarily displayed
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

    def play_selection(self):
        if self.displayed is not None:
            self.displayed.play_selection()

    def get_selection(self):
        if self.displayed is None:
            return []
        else:
            return self.displayed.get_selection()

    def handle_item_list(self, message):
        for controller in self.all_controllers:
            if controller.should_handle_message(message):
                controller.handle_item_list(message)
        self.handle_playable_items()

    def handle_items_changed(self, message):
        for controller in self.all_controllers:
            if controller.should_handle_message(message):
                controller.handle_items_changed(message)
        self.handle_playable_items()

    def handle_playable_items(self):
        if self.displayed is not None:
            selection = self.displayed.get_selection_for_playing()
            playable = self.displayed.filter_playable_items(selection)
            has_playable = len(playable) > 0
        else:
            has_playable = False
        app.widgetapp.window.videobox.handle_new_selection(has_playable)
