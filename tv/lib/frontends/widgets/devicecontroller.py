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

"""Controller for Devices tab.
"""
import operator
try:
    import cPickle as pickle
except ImportError:
    import pickle

from miro import app
from miro import displaytext
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro import messages

from miro.frontends.widgets import imagebutton
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import itemrenderer
from miro.frontends.widgets import itemtrack
from miro.frontends.widgets import segmented
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.conversions import conversion_manager

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class DeviceTabButtonSegment(segmented.TextButtonSegment):
    PARTS = {
        'off-far-left':     segmented._get_image('device-off-far-left'),
        'off-middle-left':  segmented._get_image('device-off-middle-left'),
        'off-center':       segmented._get_image('device-off-center'),
        'off-middle-right': segmented._get_image('device-off-middle-right'),
        'off-far-right':    segmented._get_image('device-off-far-right'),
        'on-far-left':      segmented._get_image('device-on-far-left'),
        'on-middle-left':   segmented._get_image('device-on-middle-left'),
        'on-center':        segmented._get_image('device-on-center'),
        'on-middle-right':  segmented._get_image('device-on-middle-right'),
        'on-far-right':     segmented._get_image('device-on-far-right')
    }

    MARGIN = 20
    TEXT_COLOR = {True: (1, 1, 1), False: widgetutil.css_to_color('#424242')}

    def size_request(self, layout):
        width, _ = segmented.TextButtonSegment.size_request(self, layout)
        return width, 23

class SizeProgressBar(widgetset.Background):
    GRADIENT_COLOR_TOP = widgetutil.css_to_color('#080808')
    GRADIENT_COLOR_BOTTOM = widgetutil.css_to_color('#515151')
    SIZE_COLOR_TOP = widgetutil.css_to_color('#829ac8')
    SIZE_COLOR_BOTTOM = widgetutil.css_to_color('#697fb0')
    SIZE_BORDER = widgetutil.css_to_color('#060606')

    def __init__(self):
        widgetset.Background.__init__(self)
        self.size_ratio = 0.0
        self.bg_surface = widgetutil.ThreeImageSurface('device-size-bg')
        self.fg_surface = widgetutil.ThreeImageSurface('device-size-fg')

    def set_progress(self, progress):
        self.size_ratio = progress
        self.queue_redraw()

    def draw(self, context, layout):
        self.bg_surface.draw(context, 0, 0, context.width)
        if self.size_ratio:
            self.fg_surface.draw(context, 0, 0,
                                 int(context.width * self.size_ratio))

class SizeWidget(widgetset.Background):
    def __init__(self):
        self.in_progress = False
        widgetset.Background.__init__(self)
        vbox = widgetset.VBox()
        # first line: size remaining on the left, sync status on the right
        line = widgetset.HBox()
        self.size_label = widgetset.Label(u"")
        self.size_label.set_bold(True)
        self.sync_label = widgetset.Label(u"")
        line.pack_start(self.size_label)
        line.pack_end(self.sync_label)
        vbox.pack_start(widgetutil.pad(line, bottom=10))

        # second line: bigger; size status on left, sync button on right
        line = widgetset.HBox()
        self.progress = SizeProgressBar()
        self.progress.set_size_request(425, 36)
        self.sync_button = widgetutil.ThreeImageButton(
            'device-sync', _("Sync Now"))
        self.sync_button.set_size_request(100, 39)
        line.pack_start(self.progress)
        line.pack_end(widgetutil.pad(self.sync_button, left=50))
        vbox.pack_start(line)
        self.add(widgetutil.align(vbox, 0.5, 1, 0, 0, top_pad=15,
                                  bottom_pad=15, right_pad=20))

    def draw(self, context, layout):
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color(widgetutil.css_to_color('#c2c2c2'))
        gradient.set_end_color(widgetutil.css_to_color('#a3a3a3'))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)

    def set_size(self, size, remaining):
        if size and remaining:
            self.progress.set_progress(1 - float(remaining) / size)
            self.size_label.set_text(
                _("%(used)s used / %(total)s total - %(percent)i%% full", {
                    'used': displaytext.size_string(size - remaining),
                    'total': displaytext.size_string(size),
                    'percent': 100 * (1 - float(remaining) / size)}))
        else:
            self.progress.set_progress(0)
            self.size_label.set_text(u"")

    def get_text(self):
        return self.sync_label.get_text()

    def set_sync_state(self, count):
        if self.in_progress:
            # don't update sync state while we're syncing
            return
        if count:
            self.sync_label.set_text(
                ngettext('1 file selected to sync',
                         '%(count)i files selected to sync',
                         count,
                         {'count': count}))
            self.sync_button.enable()
        else:
            self.sync_label.set_text(_("Up to date"))
            self.sync_button.disable()

    def set_in_progress(self, progress):
        self.in_progress = progress
        if progress:
            self.sync_label.set_text(u"")
            self.sync_button.set_text(_("In Progress"))
            self.sync_button.disable()
        else:
            self.sync_button.set_text(_("Sync Now"))
            self.set_sync_state(0)

class SyncProgressBar(widgetset.Background):
    PROGRESS_GRADIENT_TOP = (1, 1, 1)
    PROGRESS_GRADIENT_BOTTOM = widgetutil.css_to_color('#a0a0a0')

    BACKGROUND_GRADIENT_TOP = widgetutil.css_to_color('#0c0c0e')
    BACKGROUND_GRADIENT_BOTTOM = widgetutil.css_to_color('#3f4346')

    def __init__(self):
        widgetset.Background.__init__(self)
        self.progress_ratio = 0.0

    def set_progress(self, progress):
        self.progress_ratio = progress
        self.queue_redraw()

    def draw(self, context, layout):
        widgetutil.circular_rect(context, 0, 0, context.width, context.height)
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color(self.BACKGROUND_GRADIENT_TOP)
        gradient.set_end_color(self.BACKGROUND_GRADIENT_BOTTOM)
        context.gradient_fill(gradient)
        progress_width = (
            (context.width - context.height) * self.progress_ratio +
            context.height)
        widgetutil.circular_rect_negative(context, 1, 1,
                                          progress_width - 2,
                                          context.height - 2)
        gradient = widgetset.Gradient(1, 1, 1, context.height - 2)
        gradient.set_start_color(self.PROGRESS_GRADIENT_TOP)
        gradient.set_end_color(self.PROGRESS_GRADIENT_BOTTOM)
        context.gradient_fill(gradient)

class SyncProgressWidget(widgetset.Background):
    def __init__(self):
        widgetset.Background.__init__(self)

        vbox = widgetset.VBox()
        # first line: sync progess and cancel button
        line = widgetset.HBox()
        self.sync_progress = SyncProgressBar()
        self.sync_progress.set_size_request(400, 10)
        self.cancel_button = imagebutton.ImageButton('sync-cancel')
        line.pack_start(widgetutil.pad(self.sync_progress, 10, 10, 5, 5))
        line.pack_end(widgetutil.pad(self.cancel_button, 5, 5, 5, 5))
        vbox.pack_start(line)

        # second line: time remaining, all the way to the right
        line = widgetset.HBox()
        self.sync_files = widgetset.Label(u"")
        self.sync_remaining = widgetset.Label(u"")
        self.sync_remaining.set_bold(True)
        line.pack_start(widgetutil.align_left(self.sync_files, 5, 5, 5, 5))
        line.pack_end(widgetutil.align_right(self.sync_remaining, 5, 5, 5, 5))
        vbox.pack_start(line)

        self.add(widgetutil.pad(vbox, 10, 10, 10, 10))

    def set_text(self, text):
        self.sync_files.set_text(text)

    def set_status(self, progress, eta):
        self.sync_progress.set_progress(progress)
        if eta:
            self.sync_remaining.set_text(
                _('%(eta)s left',
                  {'eta': displaytext.time_string(int(eta))}))
        else:
            self.sync_remaining.set_text(_('%(percent)i%% percent complete',
                                           {'percent': int(progress * 100)}))

    def draw(self, context, layout):
        # we draw the rectangle off the bottom so that it's flat
        widgetutil.round_rect(context, 0, 0, context.width,
                              context.height + 10, 10)

        context.set_color(widgetutil.css_to_color('#9199bd'))
        context.fill()
        widgetutil.round_rect_reverse(context, 1, 1, context.width - 2,
                                      context.height + 10, 10)
        context.set_color(widgetutil.css_to_color('#bec1d0'))
        context.fill()

class SyncWidget(widgetset.VBox):
    list_label = _("Sync These Podcasts")

    def __init__(self):
        self.device = None
        self.bulk_change = False
        widgetset.VBox.__init__(self)
        self.create_signal('changed')
        self.sync_library = widgetset.Checkbox(self.title)
        self.sync_library.connect('toggled', self.sync_library_toggled)
        self.pack_start(widgetutil.pad(self.sync_library, top=50))
        self._pack_extra_buttons()

        self.feed_list = widgetset.VBox()
        self.feed_list.set_size_request(450, -1)
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
        background = widgetset.SolidBackground(
                widgetutil.css_to_color('#dddddd'))
        background.add(self.feed_list)
        scroller = widgetset.Scroller(False, True)
        scroller.set_child(background)
        self.feed_list.disable()
        self.pack_start(widgetutil.pad(scroller, top=20, bottom=5),
                        expand=True)

        line = widgetset.HBox(spacing=5)
        button = widgetutil.TitlebarButton(_("Select none"))
        button.connect('clicked', self.select_clicked, False)
        line.pack_end(button)
        button = widgetutil.TitlebarButton(_("Select all"))
        button.connect('clicked', self.select_clicked, True)
        line.pack_end(button)
        self.pack_start(widgetutil.pad(line, bottom=20))

    def _pack_extra_buttons(self):
        pass

    def set_device(self, device):
        self.device = device
        sync = self.device.database.setdefault(u'sync', {})
        if self.file_type not in sync:
            this_sync = {}
        else:
            this_sync = sync[self.file_type]
        self.sync_library.set_checked(
            this_sync.get('enabled', False))
        # OS X doesn't send the callback when we toggle it manually (#15392)
        self.sync_library_toggled(self.sync_library)

        if self.file_type != u'playlists':
            all_feeds = this_sync.get(u'all', True)
            self.sync_unwatched.set_checked(not all_feeds)

        for item in this_sync.get(u'items', []):
            if item in self.info_map:
                self.info_map[item].set_checked(True)

    def select_clicked(self, obj, value):
        self.bulk_change = True
        this_sync = self.device.database[u'sync'][self.file_type]
        items = set(this_sync.get(u'items', ()))
        for key, box in self.info_map.items():
            box.set_checked(value)
            if value:
                items.add(key)
            elif key in items:
                items.remove(key)
        self.bulk_change = False
        message = messages.ChangeDeviceSyncSetting(self.device,
                                                   self.file_type,
                                                   u'items', list(items))
        message.send_to_backend()
        self.emit('changed')

    def get_feeds(self):
        items = self.get_items()
        items.sort(key=operator.attrgetter('name'))
        return items

    def info_key(self, info):
        return info.url

    def sync_library_toggled(self, obj):
        checked = obj.get_checked()
        if checked:
            self.feed_list.enable()
        else:
            self.feed_list.disable()
        this_sync = self.device.database[u'sync'].get(self.file_type, {})
        value = this_sync.get(u'enabled', None)
        if not self.bulk_change and checked != value:
            message = messages.ChangeDeviceSyncSetting(self.device,
                                                       self.file_type,
                                                       u'enabled', checked)
            message.send_to_backend()
            self.emit('changed')
        return checked # make it easy for subclass

    def feed_toggled(self, obj, info):
        this_sync = self.device.database[u'sync'][self.file_type]
        key = self.info_key(info)
        items = set(this_sync.get(u'items', []))
        changed = False
        if obj.get_checked():
            if key not in items:
                items.add(key)
                changed = True
        elif key in items:
            items.remove(key)
            changed = True
        if not self.bulk_change and changed:
            message = messages.ChangeDeviceSyncSetting(self.device,
                                                       self.file_type,
                                                       u'items', list(items))
            message.send_to_backend()
            self.emit('changed')

    def checked_feeds(self):
        if not self.sync_library.get_checked():
            return []
        feeds = []
        items = self.device.database[u'sync'][self.file_type].get(u'items', ())
        for key in items:
            feed = self.find_info_by_key(key)
            if feed is not None:
                feeds.append(feed.id)
        return feeds

class PodcastSyncWidget(SyncWidget):
    file_type = u'podcasts'
    title = _("Sync Podcasts")

    def _pack_extra_buttons(self):
        self.sync_unwatched = widgetset.Checkbox(_("Only sync unplayed items"))
        self.sync_unwatched.connect('toggled', self.unwatched_toggled)
        self.pack_start(widgetutil.pad(self.sync_unwatched, left=20))

    def unwatched_toggled(self, obj):
        all_items = (not obj.get_checked())
        current = self.device.database[u'sync'][self.file_type].get(u'all')
        if current != all_items:
            message = messages.ChangeDeviceSyncSetting(self.device,
                                                       self.file_type,
                                                       u'all', all_items)
            message.send_to_backend()
            self.emit('changed')

    def sync_library_toggled(self, obj):
        if SyncWidget.sync_library_toggled(self, obj):
            self.sync_unwatched.enable()
        else:
            self.sync_unwatched.disable()

    def get_items(self):
        return [info for info in app.tabs['feed'].get_feeds()
                if not info.is_folder]

    def find_info_by_key(self, key):
        return app.tabs['feed'].find_feed_with_url(key)

class PlaylistSyncWidget(SyncWidget):
    file_type = u'playlists'
    list_label = _("Sync These Playlists")
    title = _("Sync Playlists")

    def get_items(self):
        return list(app.tabs['playlist'].get_playlists())

    def info_key(self, info):
        return info.name

    def find_info_by_key(self, key):
        return app.tabs['playlist'].find_playlist_with_name(key)

class DeviceSettingsWidget(widgetset.Background):
    def __init__(self):
        widgetset.Background.__init__(self)
        self.boxes = {}
        self.device = None

    def create_table(self):
        self.remove()
        def _get_conversion_name(id_):
            if id_ == 'copy':
                return _('Copy')
            else:
                return conversion_manager.lookup_converter(id_).name
        conversion_details = {
            'audio': _get_conversion_name(self.device.info.audio_conversion),
            'video': _get_conversion_name(self.device.info.video_conversion)
            }
        audio_conversion_names = [_('Device Default (%(audio)s)',
                                    conversion_details), _('Copy')]
        self.audio_conversion_values = [None, 'copy']
        video_conversion_names = [_('Device Default (%(video)s)',
                                    conversion_details), _('Copy')]
        self.video_conversion_values = [None, 'copy']
        for section_name, converters in conversion_manager.get_converters():
            for converter in converters:
                if converter.mediatype == 'video':
                    video_conversion_names.append(converter.name)
                    self.video_conversion_values.append(converter.identifier)
                elif converter.mediatype == 'audio':
                    audio_conversion_names.append(converter.name)
                    self.audio_conversion_values.append(converter.identifier)
        widgets = []
        for text, setting, type_ in (
            (_("Name of Device"), u'name', 'text'),
            (_("Video Conversion"), u'video_conversion', 'video_conversion'),
            (_("Audio Conversion"), u'audio_conversion', 'audio_conversion'),
            (_("Store video in this directory"), u'video_path', 'text'),
            (_("Store audio in this directory"), u'audio_path', 'text'),
            (_("Always show this device, even if "
               "'show all devices' is turned off"), u'always_show', 'bool')
            ):
            if type_ == 'text':
                widget = widgetset.TextEntry()
                widget.set_size_request(260, -1)
            elif type_.endswith('conversion'):
                if type_ == 'video_conversion':
                    options = video_conversion_names
                elif type_ == 'audio_conversion':
                    options = audio_conversion_names
                widget = widgetset.OptionMenu(options)
                widget.set_size_request(260, -1)
            elif type_== 'bool':
                widget = widgetset.Checkbox(text)
            else:
                raise RuntimeError('unknown settings widget: %r' % type_)
            self.boxes[setting] = widget
            if type_ != 'bool': # has a label already
                widgets.append((widgetset.Label(text), widget))
                if type_ == 'text':
                    widget.connect('focus-out', self.setting_changed, setting)
                else:
                    widget.connect('changed', self.setting_changed, setting)
            else:
                widgets.append((widget,))
                widget.connect('toggled', self.setting_changed, setting)
        table = widgetset.Table(2, len(widgets))
        for row, widget in enumerate(widgets):
            if len(widget) == 1: # checkbox
                table.pack(widget[0], 0, row, column_span=2)
            else:
                table.pack(widgetutil.align_right(widget[0]), 0, row)
                table.pack(widgetutil.align_left(widget[1]), 1, row)
        table.set_column_spacing(20)
        table.set_row_spacing(20)
        self.set_child(widgetutil.align(table, 0.5, top_pad=50))

    def set_device(self, device):
        if self.device is None:
            self.device = device
            self.create_table()
        else:
            self.device = device
        device_settings = device.database.get(u'settings', {})
        self.bulk_change = True
        for setting in u'name', u'video_path', u'audio_path':
            self.boxes[setting].set_text(device_settings.get(
                    setting,
                    getattr(device.info, setting)))
        for conversion in u'video', u'audio':
            value = device_settings.get(u'%s_conversion' % conversion)
            if conversion == u'video':
                index = self.video_conversion_values.index(value)
            else:
                index = self.audio_conversion_values.index(value)
            self.boxes[u'%s_conversion' % conversion].set_selected(index)
        if getattr(device.info, 'generic', False):
            self.boxes['always_show'].enable()
            self.boxes['always_show'].set_checked(
                device_settings.get(u'always_show', False))
        else:
            self.boxes['always_show'].disable()
            self.boxes['always_show'].set_checked(True)
        self.bulk_change = False

    def setting_changed(self, widget, setting_or_value, setting=None):
        if self.device is None:
            return
        if setting is None:
            value = None
            setting = setting_or_value
        else:
            value = setting_or_value
        if setting.endswith('conversion'):
            if setting == 'video_conversion':
                values = self.video_conversion_values
            elif setting == 'audio_conversion':
                values = self.audio_conversion_values
            value = values[value] # sends an index
        elif setting == 'name' or setting.endswith('path'):
            value = widget.get_text()
        elif setting == 'always_show':
            value = widget.get_checked()
        if value != self.device.database.get(u'settings', {}).get(setting,
                                                                  not value):
            message = messages.ChangeDeviceSetting(self.device, setting, value)
            message.send_to_backend()

class DeviceMountedView(widgetset.VBox):
    def __init__(self):
        self.device = None
        widgetset.VBox.__init__(self)

        self.button_row = segmented.SegmentedButtonsRow()

        for key, name in (
            ('main', _('Main')),
            ('podcasts', _('Podcasts')),
            ('playlists', _('Playlists')),
            ('settings', _('Settings'))):
            button = DeviceTabButtonSegment(key, name,
                                            self._tab_clicked)
            self.button_row.add_button(name.lower(), button)

        self.button_row.set_active('main')
        self.pack_start(widgetutil.align_center(
                        self.button_row.make_widget(), top_pad=50))

        self.tabs = {}
        self.tab_container = widgetset.Background()
        self.pack_start(self.tab_container, expand=True)


        label_size = widgetutil.font_scale_from_osx_points(16)
        vbox = widgetset.VBox()
        label = widgetset.Label(_("Drag individual video and audio files "
                                  "onto the device in the sidebar to copy "
                                  "them."))
        label.set_size(label_size)
        vbox.pack_start(widgetutil.align_center(label, top_pad=50))
        label = widgetset.Label(_("Use these options and the tabs above for "
                                  "automatic syncing."))
        label.set_size(label_size)
        vbox.pack_start(widgetutil.align_center(label, top_pad=10))

        self.device_size = SizeWidget()
        self.device_size.sync_button.connect('clicked', self.sync_clicked)
        self.pack_end(self.device_size)

        self.sync_container = widgetset.Background()
        self.pack_end(widgetutil.align_center(self.sync_container))

        self.add_tab('main', vbox)
        self.add_tab('podcasts', widgetutil.align_center(PodcastSyncWidget()))
        self.add_tab('playlists',
                     widgetutil.align_center(PlaylistSyncWidget()))
        self.add_tab('settings',
                     widgetutil.align_center(DeviceSettingsWidget()))

    def add_tab(self, key, widget):
        if not self.tabs:
            self.tab_container.set_child(widget)
        if key not in ('main', 'settings'):
            widget.child.connect('changed', self.sync_settings_changed)
        self.tabs[key] = widget

    def set_device(self, device):
        self.device = device
        self.device_size.set_size(device.size, device.remaining)
        if not self.device.mount:
            return
        for name in 'podcasts', 'playlists', 'settings':
            tab = self.tabs[name]
            tab.child.set_device(device)
        sync_manager = app.device_manager.get_sync_for_device(device,
                                                              create=False)
        if sync_manager is not None:
            self.set_sync_status(sync_manager.get_progress(),
                                 sync_manager.get_eta())

    def _tab_clicked(self, button):
        key = button.key
        self.button_row.set_active(key)
        self.tab_container.remove()
        self.tab_container.set_child(self.tabs[key])

    def _get_sync_state(self):
        sync_type = {}
        sync_ids = {}
        for file_type in u'podcasts', u'playlists':
            this_sync = self.device.database[u'sync'].get(file_type, {})
            widget = self.tabs[file_type].child
            sync_type[file_type] = (this_sync.get(u'all', True) and u'all' or
                                    u'unwatched')
            sync_ids[file_type] = widget.checked_feeds()
        return (sync_type[u'podcasts'],
                sync_ids[u'podcasts'],
                sync_ids[u'playlists'])

    def sync_settings_changed(self, obj):
        message = messages.QuerySyncInformation(self.device)
        message.send_to_backend()

    def sync_clicked(self, obj):
        message = messages.DeviceSyncFeeds(self.device)
        message.send_to_backend()

    def current_sync_information(self, count):
        self.device_size.set_sync_state(count)

    def set_sync_status(self, progress, eta):
        if not isinstance(self.sync_container.child, SyncProgressWidget):
            widget = SyncProgressWidget()
            widget.cancel_button.connect('clicked', self.cancel_sync)
            self.sync_container.set_child(widget)
            widget.set_text(self.device_size.get_text())
            self.device_size.set_in_progress(True)
        self.sync_container.child.set_status(progress, eta)

    def cancel_sync(self, obj):
        message = messages.CancelDeviceSync(self.device)
        message.send_to_backend()

    def sync_finished(self):
        self.sync_container.remove()
        self.device_size.set_in_progress(False)
        self.sync_settings_changed(self)

class DeviceItemList(itemlist.ItemList):
    def filter(self, item_info):
        return True

class UnknownDeviceView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        label = widgetset.Label()
        label.set_text(
            _("Your device isn't telling us its exact model number."))
        self.pack_start(widgetutil.align_center(label, left_pad=20, top_pad=50,
                                              bottom_pad=20))
        label = widgetset.Label()
        label.set_text(
            _('For optimal video conversion, select the device model.'))
        label.set_bold(True)
        self.pack_start(widgetutil.align_center(label, left_pad=20,
                                                bottom_pad=20)),

        self.device_choices = widgetset.VBox()
        self.pack_start(widgetutil.align_center(self.device_choices,
                                                left_pad=20, top_pad=20,
                                                bottom_pad=20))

        image = widgetset.ImageDisplay(
            imagepool.get(resources.path('images/sync-unknown.png')))
        self.pack_start(widgetutil.align_center(image, left_pad=20,
                                                bottom_pad=20))

        label = widgetset.Label()
        label.set_text(_("If you don't know the model or it doesn't appear "
                         "in the list, it's fine to choose the 'Generic' "
                         "device option."))
        label.set_bold(True)
        self.pack_start(widgetutil.align_center(label, left_pad=20,
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
            selected_button = rbg.get_selected()
            if selected_button is None:
                return # user didn't actually select a device
            messages.SetDeviceType(
                self.device,
                buttons_to_device_name[selected_button]).send_to_backend()

        select = widgetset.Button(_('This is my device'))
        select.connect('clicked', _clicked)
        self.device_choices.pack_start(widgetutil.pad(select, top=20))

class DeviceUnmountedView(widgetset.VBox):
    def __init__(self):
        widgetset.VBox.__init__(self)
        label = widgetset.Label()
        label.set_text(_('This device is not yet mounted.'))
        label.set_bold(True)
        label.set_size(1.5)
        self.pack_start(widgetutil.align_center(label, left_pad=20, top_pad=50,
                                              bottom_pad=20))
        self.device_text = widgetset.Label()
        self.device_text.set_size(1.5)
        self.device_text.set_wrap(True)
        self.pack_start(widgetutil.align_center(self.device_text, left_pad=20,
                                                bottom_pad=40))

        image = widgetset.ImageDisplay(
            imagepool.get(resources.path('images/sync-unmounted.png')))
        self.pack_start(widgetutil.align_center(image, left_pad=20,
                                                bottom_pad=20))

    def set_device(self, device):
        self.device_text.set_text(
            device.info.mount_instructions.replace('\n', '\n\n'))

class DeviceWidget(widgetset.VBox):
    def __init__(self, device):
        widgetset.VBox.__init__(self)
        # color is #f0f0f0
        self.device_view = widgetset.SolidBackground((0.94, 0.94, 0.94))
        self.pack_start(self.device_view, expand=True)
        self.set_device(device)

    def set_device(self, device):
        if not device.mount:
            view_class = DeviceUnmountedView
        elif not device.info.has_multiple_devices:
            view_class = DeviceMountedView
        else:
            view_class = UnknownDeviceView
        if isinstance(self.device_view.child, view_class):
            self.device_view.child.set_device(device)
        else:
            view = view_class()
            view.set_device(device)
            self.device_view.set_child(view)


    def current_sync_information(self, count):
        view = self.get_view()
        if isinstance(view, DeviceMountedView):
            view.current_sync_information(count)

    def set_sync_status(self, progress, eta):
        view = self.get_view()
        if isinstance(view, DeviceMountedView):
            view.set_sync_status(progress, eta)

    def sync_finished(self):
        view = self.get_view()
        if isinstance(view, DeviceMountedView):
            view.sync_finished()

    def get_view(self):
        return self.device_view.child

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

    def handle_current_sync_information(self, message):
        if message.device.id != self.device.id:
            return # not our device

        self.widget.current_sync_information(message.count)

    def handle_device_sync_changed(self, message):
        if message.device.id != self.device.id:
            return # not our device

        if message.finished:
            self.widget.sync_finished()
        else:
            self.widget.set_sync_status(message.progress, message.eta)

    def start_tracking(self):
        view = self.widget.get_view()
        if isinstance(view, DeviceMountedView):
            message = messages.QuerySyncInformation(self.device)
            message.send_to_backend()

    def stop_tracking(self):
        pass

class DeviceItemController(itemlistcontroller.AudioVideoItemsController):
    unwatched_label = u'' # everything is marked as played

    def __init__(self, device):
        self.device = device
        self.id = device.id
        tab_type = device.tab_type
        self.type = u'device-%s' % tab_type
        if tab_type == 'audio':
            self.titlebar_class = itemlistwidgets.MusicTitlebar
        else:
            self.titlebar_class = itemlistwidgets.VideosTitlebar

        itemlistcontroller.AudioVideoItemsController.__init__(self)
        if (u'%s_sort_state' % tab_type) in device.database:
            sort_key, ascending = device.database[u'%s_sort_state' % tab_type]
            for view in self.views.keys():
                self.on_sort_changed(self, sort_key, ascending, view)
        if (u'%s_view' % tab_type) in device.database:
            view_name = device.database[u'%s_view' % tab_type]
            if view_name  == u'list':
                view_type = WidgetStateStore.get_list_view_type()
            else:
                view_type = WidgetStateStore.get_standard_view_type()
        elif tab_type == 'audio':
            view_type = WidgetStateStore.get_list_view_type()
        else:
            view_type = WidgetStateStore.get_standard_view_type()

        self.set_view(None, view_type)

        self.titlebar.connect('list-view-clicked', self.save_view, 'list')
        self.titlebar.connect('normal-view-clicked',
                                    self.save_view, 'normal')
    def build_header_toolbar(self):
        sorts_enabled = app.widget_state.get_sorts_enabled(self.type, self.id)
        return itemlistwidgets.HeaderToolbar(sorts_enabled)

    def build_item_tracker(self):
        return itemtrack.ItemListTracker.create('device', self.device)

    def build_renderer(self):
        return itemrenderer.DeviceItemRenderer(display_channel=False)

    def make_drag_handler(self):
        return DeviceItemDragHandler()

    def on_sort_changed(self, obj, sort_key, ascending, view):
        itemlistcontroller.AudioVideoItemsController.on_sort_changed(
                        self, obj, sort_key, ascending, view)
        message = messages.SaveDeviceSort(self.device, self.device.tab_type,
                                          sort_key, ascending)
        message.send_to_backend()

    def save_view(self, toolbar, view):
        message = messages.SaveDeviceView(self.device, self.device.tab_type,
                                          view)
        message.send_to_backend()

    def handle_device_changed(self, device):
        if self.device.id != device.id:
            return
        self.device = device


class DeviceItemDragHandler(object):
    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def allowed_types(self):
        return ('device-audio-item', 'device-video-item')

    def begin_drag(self, tableview, rows):
        videos = [row[0] for row in rows]
        return { 'device-%s-item' % videos[0].file_type: pickle.dumps(videos) }
