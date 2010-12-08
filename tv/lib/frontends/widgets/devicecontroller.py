# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""Controller for Devices tab.
"""
import operator

from miro import app
from miro import displaytext
from miro.gtcache import gettext as _
from miro import messages

from miro.frontends.widgets import imagepool
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import segmented
from miro.frontends.widgets import widgetutil

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class DeviceTitlebar(itemlistwidgets.ItemListTitlebar):
    def _build_titlebar_extra(self):
        pass

class DeviceTabButtonSegment(segmented.TextButtonSegment):

    MARGIN = 20
    COLOR = (1, 1, 1)
    TEXT_COLOR = {True: COLOR, False: COLOR}

class LabeledProgressWidget(widgetset.HBox):
    def __init__(self):
        widgetset.HBox.__init__(self)
        self.progress = widgetset.ProgressBar()
        self.progress.set_size_request(500, -1)
        self.text = widgetset.Label()
        self.pack_start(self.progress, padding=20)
        self.pack_start(self.text)

    def set_progress(self, progress):
        self.progress.set_progress(progress)

    def set_text(self, text):
        self.text.set_text(text)

class SizeWidget(LabeledProgressWidget):
    def __init__(self, size=None, remaining=None):
        LabeledProgressWidget.__init__(self)
        self.set_size(size, remaining)

    def set_size(self, size, remaining):
        self.size = size
        self.remaining = remaining
        if size and remaining:
            self.set_progress(1 - float(remaining) / size)
            self.set_text('%s free' % displaytext.size_string(
                    remaining))
        else:
            self.set_progress(0)
            self.set_text('not mounted')

class SyncProgressWidget(LabeledProgressWidget):
    def __init__(self):
        LabeledProgressWidget.__init__(self)
        self.set_status(0, None)

    def set_status(self, progress, eta):
        self.set_progress(progress)
        if eta is not None:
            self.set_text(displaytext.time_string(int(eta)))
        else:
            self.set_text(_('unknown'))

class SyncWidget(widgetset.HBox):
    list_label = _("Sync These Feeds")

    def __init__(self):
        self.device = None
        widgetset.HBox.__init__(self)
        first_column = widgetset.VBox()
        self.sync_library = widgetset.Checkbox(self.title)
        self.sync_library.connect('toggled', self.sync_library_toggled)
        first_column.pack_start(self.sync_library)
        self.sync_group = widgetset.RadioButtonGroup()
        if self.file_type != 'playlists':
            # don't actually need to create buttons for playlists, since we
            # always sync all items
            all_button = widgetset.RadioButton(self.all_label, self.sync_group)
            all_button.connect('clicked', self.all_button_clicked)
            widgetset.RadioButton(self.unwatched_label,
                                  self.sync_group)
            for button in self.sync_group.get_buttons():
                button.disable()
                first_column.pack_start(button)
        self.pack_start(widgetutil.pad(first_column, 20, 0, 20, 20))

        second_column = widgetset.VBox()
        second_column.pack_start(widgetset.Label(self.list_label))
        self.feed_list = widgetset.VBox()
        self.info_map = {}
        feeds = self.get_feeds()
        if feeds:
            for info in feeds:
                checkbox = widgetset.Checkbox(info.name)
                checkbox.connect('toggled', self.feed_toggled, info)
                self.feed_list.pack_start(checkbox)
                self.info_map[self.info_key(info)] = checkbox
        else:
            self.sync_library.disable()
        scroller = widgetset.Scroller(False, True)
        scroller.set_child(self.feed_list)
        second_column.pack_start(scroller, expand=True)
        self.feed_list.disable()
        self.pack_start(widgetutil.pad(second_column, 20, 20, 20, 20),
                        expand=True)

    def set_device(self, device):
        self.device = device
        sync = self.device.database['sync']
        if self.file_type not in sync:
            sync[self.file_type] = {}

        this_sync = sync[self.file_type]
        self.sync_library.set_checked(
            this_sync.get('enabled', False))
        # OS X doesn't send the callback when we toggle it manually (#15392)
        self.sync_library_toggled(self.sync_library)

        if self.file_type != 'playlists':
            all_feeds = this_sync.get('all', True)
            # True == 1, False == 0
            self.sync_group.set_selected(
                self.sync_group.get_buttons()[not all_feeds])

        for item in this_sync.get('items', []):
            if item in self.info_map:
                self.info_map[item].set_checked(True)


    def get_feeds(self):
        feeds = []
        table_model = self.tab_list().view.model
        iter_ = table_model.first_iter()
        if iter_ is None:
            self.sync_library.disable()
        else:
            while iter_ is not None:
                row = table_model[iter_]
                if row[0].is_folder:
                    child_iter = table_model.child_iter(iter_)
                    while child_iter is not None:
                        row = table_model[child_iter]
                        feeds.append(row[0])
                        child_iter = table_model.next_iter(child_iter)
                else:
                    feeds.append(row[0])
                iter_ = table_model.next_iter(iter_)
        feeds.sort(key=operator.attrgetter('name'))
        return feeds

    def info_key(self, info):
        return info.url

    def sync_library_toggled(self, obj):
        checked = obj.get_checked()
        if checked:
            for button in self.sync_group.get_buttons():
                button.enable()
            self.feed_list.enable()
        else:
            for button in self.sync_group.get_buttons():
                button.disable()
            self.feed_list.disable()
        self.device.database['sync'][self.file_type]['enabled'] = checked

    def all_button_clicked(self, obj):
        self.device.database['sync'][self.file_type]['all'] = \
            obj.get_selected()

    def feed_toggled(self, obj, info):
        this_sync = self.device.database['sync'][self.file_type]
        key = self.info_key(info)
        items = set(this_sync.get('items', []))
        if obj.get_checked():
            items.add(key)
        else:
            if key in items:
                items.remove(key)
        this_sync['items'] = list(items)

    def find_info_by_key(self, key, tab_list):
        return tab_list.find_feed_with_url(key)

    def checked_feeds(self):
        if not self.sync_library.get_checked():
            return []
        tab_list = self.tab_list()
        feeds = []
        for key in self.device.database['sync'][self.file_type].get('items',
                                                                    ()):
            feed = self.find_info_by_key(key, tab_list)
            if feed is not None:
                feeds.append(feed.id)
        return feeds

class VideoFeedSyncWidget(SyncWidget):
    file_type = 'video'
    title = _("Sync Video Library")
    all_label = _("All videos")
    unwatched_label = _("Only unwatched videos")

    def tab_list(self):
        return app.tab_list_manager.feed_list

class AudioFeedSyncWidget(SyncWidget):
    file_type = 'audio'
    title = _("Sync Audio Library")
    all_label = _("All audio")
    unwatched_label =_("Only unplayed audio")

    def tab_list(self):
        return app.tab_list_manager.audio_feed_list

class PlaylistSyncWidget(SyncWidget):
    file_type = 'playlists'
    list_label = _("Sync These Playlists")
    title = _("Sync Playlists")
    all_label =_("All items")
    unwatched_label = _("Only unwatched items")

    def tab_list(self):
        return app.tab_list_manager.playlist_list

    def info_key(self, info):
        return info.name

    def find_info_by_key(self, key, tab_list):
        return tab_list.find_playlist_with_name(key)

class DeviceMountedView(widgetset.VBox):
    def __init__(self):
        self.device = None
        widgetset.VBox.__init__(self)

        self.button_row = segmented.SegmentedButtonsRow()
        for name in ('Main', 'Video', 'Audio', 'Playlists'):
            button = DeviceTabButtonSegment(name.lower(), name,
                                            self._tab_clicked)
            self.button_row.add_button(name.lower(), button)

        self.button_row.set_active('main')
        self.pack_start(widgetutil.align_center(
                        self.button_row.make_widget()))

        self.tabs = {}
        self.tab_container = widgetset.SolidBackground((1, 1, 1))
        self.pack_start(self.tab_container, expand=True)

        vbox = widgetset.VBox()
        label = widgetset.Label(_("To copy media onto the device, drag it "
                                  "onto the sidebar."))
        label.set_size(1.5)
        vbox.pack_start(widgetutil.align_center(label, top_pad=50))

        self.sync_container = widgetset.Background()
        self.sync_container.set_size_request(500, -1)
        button = widgetset.Button('Sync Now')
        button.set_size(1.5)
        button.connect('clicked', self.sync_clicked)
        self.sync_container.set_child(widgetutil.align_center(button))
        vbox.pack_start(widgetutil.align_center(self.sync_container,
                                                top_pad=50))

        self.device_size = SizeWidget()
        alignment = widgetset.Alignment(0.5, 1, 0, 0, bottom_pad=15,
                                        right_pad=20)
        alignment.add(self.device_size)
        vbox.pack_end(alignment)

        self.add_tab('main', vbox)
        self.add_tab('video', widgetutil.align_center(VideoFeedSyncWidget()))
        self.add_tab('audio', widgetutil.align_center(AudioFeedSyncWidget()))
        self.add_tab('playlists',
                     widgetutil.align_center(PlaylistSyncWidget()))

    def add_tab(self, key, widget):
        if not self.tabs:
            self.tab_container.set_child(widget)
        self.tabs[key] = widget

    def set_device(self, device):
        self.device = device
        self.device.database.set_bulk_mode(True)
        self.device_size.set_size(device.size, device.remaining)
        for name in 'video', 'audio', 'playlists':
            tab = self.tabs[name]
            tab.child.set_device(device)
        sync_manager = app.device_manager.get_sync_for_device(device,
                                                              create=False)
        if sync_manager is not None:
            self.set_sync_status(sync_manager.get_progress(),
                                 sync_manager.get_eta())
        self.device.database.set_bulk_mode(False)

    def _tab_clicked(self, button):
        key = button.key
        self.button_row.set_active(key)
        self.tab_container.remove()
        self.tab_container.set_child(self.tabs[key])

    def sync_clicked(self, obj):
        sync_type = {}
        sync_ids = {}
        for file_type in 'video', 'audio', 'playlists':
            this_sync = self.device.database['sync'][file_type]
            widget = self.tabs[file_type].child
            sync_type[file_type] = (this_sync.get('all', True) and 'all' or
                                    'unwatched')
            sync_ids[file_type] = widget.checked_feeds()

        message = messages.DeviceSyncFeeds(self.device,
                                           sync_type['video'],
                                           sync_ids['video'],
                                           sync_type['audio'],
                                           sync_ids['audio'],
                                           sync_ids['playlists'])
        message.send_to_backend()


    def set_sync_status(self, progress, eta):
        if not isinstance(self.sync_container.child, SyncProgressWidget):
            self._old_child = self.sync_container.child
            self.sync_container.remove()
            self.sync_container.set_child(SyncProgressWidget())

        self.sync_container.child.set_status(progress, eta)

    def sync_finished(self):
        self.sync_container.remove()
        self.sync_container.set_child(self._old_child)
        del self._old_child


class DeviceItemList(itemlist.ItemList):

    def filter(self, item_info):
        return True

class UnknownDeviceView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        label = widgetset.Label()
        label.set_text(_("We're not exactly sure what kind of phone this is."))
        label.set_bold(True)
        label.set_size(1.5)
        self.pack_start(widgetutil.align_center(label, left_pad=20, top_pad=50,
                                              bottom_pad=20))

        self.device_choices = widgetset.VBox()
        self.pack_start(widgetutil.align_center(self.device_choices,
                                                left_pad=20, top_pad=50,
                                                bottom_pad=20))

    def set_device(self, device):
        for child in self.device_choices.children:
            self.device_choices.remove(child)

        self.device = device
        possible_devices = sorted(device.info.devices)
        rbg = widgetset.RadioButtonGroup()

        buttons_to_device_name = {}
        for device_name in possible_devices:
            button = widgetset.RadioButton(device_name, rbg)
            self.device_choices.pack_start(button)
            buttons_to_device_name[button] = device_name

        def _clicked(*args):
            messages.SetDeviceType(
                self.device,
                buttons_to_device_name[rbg.get_selected()]).send_to_backend()

        select = widgetset.Button(_('This is my device'))
        select.connect('clicked', _clicked)
        self.device_choices.pack_start(widgetutil.pad(select, top=40))

class DeviceUnmountedView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        label = widgetset.Label()
        label.set_text(_('This phone is not yet mounted.'))
        label.set_bold(True)
        label.set_size(1.5)
        self.pack_start(widgetutil.align_center(label, left_pad=20, top_pad=50,
                                              bottom_pad=20))
        self.device_text = widgetset.Label()
        self.device_text.set_size(1.5)
        self.device_text.set_wrap(True)
        self.pack_start(widgetutil.align_center(self.device_text, left_pad=20))


    def set_device(self, device):
        self.device_text.set_text(
            device.info.mount_instructions.replace('\n', '\n\n'))

class DeviceWidget(widgetset.VBox):
    def __init__(self, device):
        widgetset.VBox.__init__(self)
        self.titlebar_view = widgetset.Background()
        self.device_view = widgetset.Background()
        self.pack_start(self.titlebar_view)
        self.pack_start(self.device_view, expand=True)
        self.set_device(device)

    def set_device(self, device):
        self.titlebar_view.remove()
        self.titlebar_view.set_child(self.make_titlebar(device))
        self.device_view.remove()
        if not device.mount:
            view = DeviceUnmountedView()
        elif not device.info.has_multiple_devices:
            view = DeviceMountedView()
        else:
            view = UnknownDeviceView()
        view.set_device(device)
        self.device_view.set_child(view)

    @staticmethod
    def make_titlebar(device):
        image_path = resources.path("images/phone-large.png")
        icon = imagepool.get(image_path)
        return DeviceTitlebar(device.name, icon)

    def set_sync_status(self, progress, eta):
        view = self.device_view.child
        if isinstance(view, DeviceMountedView):
            view.set_sync_status(progress, eta)

    def sync_finished(self):
        view = self.device_view.child
        if isinstance(view, DeviceMountedView):
            view.sync_finished()


class DeviceController(object):
    def __init__(self, device):
        self.device = device
        self.widget = DeviceWidget(device)

    def handle_device_changed(self, device):
        if device.id != self.device.id:
            # not our device
            return
        self.device = device
        self.widget.set_device(device)

    def handle_device_sync_changed(self, message):
        if message.device.id != self.device.id:
            return # not our device

        if message.finished:
            self.widget.sync_finished()
        else:
            self.widget.set_sync_status(message.progress, message.eta)

    def start_tracking(self):
        pass

    def stop_tracking(self):
        pass

class DeviceItemController(itemlistcontroller.AudioVideoItemsController):
    unwatched_label = u'' # everything is marked as played

    def __init__(self, device):
        self.device = device
        self.id = device.id
        tab_type = device.tab_type
        self.type = 'device-%s' % tab_type
        self.image_filename = 'icon-%s_large.png' % tab_type
        self.title = u'%s on %s' % (device.name, device.info.name)
        itemlistcontroller.AudioVideoItemsController.__init__(self)
        if ('%s_sort_state' % tab_type) in device.database:
            sort_key, ascending = device.database['%s_sort_state' % tab_type]
            self.on_sort_changed(self, sort_key, ascending)
        if ('%s_view' % tab_type) in device.database:
            view_type = device.database['%s_view' % tab_type]
        elif tab_type == 'audio':
            view_type = 'list'
        else:
            view_type = 'normal'

        if view_type == 'list':
            self.widget.switch_to_list_view()
        else:
            self.widget.switch_to_normal_view()

        self.widget.toolbar.connect('list-view-clicked', self.save_list_view)
        self.widget.toolbar.connect('normal-view-clicked',
                                    self.save_normal_view)

    def build_header_toolbar(self):
        return itemlistwidgets.HeaderToolbar()

    def start_tracking(self):
        app.info_updater.item_list_callbacks.add('device', self.device.id,
                self.handle_item_list)
        app.info_updater.item_changed_callbacks.add('device', self.device.id,
                self.handle_items_changed)
        messages.TrackItems('device', self.device).send_to_backend()

    def stop_tracking(self):
        app.info_updater.item_list_callbacks.remove('device', self.device.id,
                self.handle_item_list)
        app.info_updater.item_changed_callbacks.remove(
            'device',self.device.id, self.handle_items_changed)
        messages.StopTrackingItems('device', self.device).send_to_backend()

    def on_sort_changed(self, obj, sort_key, ascending):
        sorter = itemlist.SORT_KEY_MAP[sort_key](ascending)
        self.item_list_group.set_sort(sorter)
        self.list_item_view.model_changed()
        sort = (sort_key, ascending)
        self.widget.toolbar.change_sort_indicator(*sort)
        self.list_item_view.change_sort_indicator(*sort)
        self.device.database['%s_sort_state' % self.device.tab_type] = sort

    def save_list_view(self, toolbar=None):
        self.device.database['%s_view' % self.device.tab_type] = 'list'

    def save_normal_view(self, toolbar=None):
        self.device.database['%s_view' % self.device.tab_type] = 'normal'


