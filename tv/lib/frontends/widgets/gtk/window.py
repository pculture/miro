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

"""miro.frontends.widgets.gtk.window -- GTK Window widget."""

import StringIO

import pango
import gobject
import gtk

from miro import app
from miro import config
from miro import prefs
from miro import signals
from miro import dialogs
from miro.gtcache import gettext as _
from miro.frontends.widgets.gtk import wrappermap, widgets
from miro.frontends.widgets.gtk import keymap
from miro.frontends.widgets import menus
from miro.plat import resources
from miro.plat import utils

# keeps the objects alive until destroy() is called
alive_windows = set()
running_dialogs = set()

def __get_fullscreen_stock_id():
    try:
        return gtk.STOCK_FULLSCREEN
    except StandardError:
        pass

STOCK_IDS = {
    "SaveItem": gtk.STOCK_SAVE,
    "CopyItemURL": gtk.STOCK_COPY,
    "RemoveItems": gtk.STOCK_REMOVE,
    "Fullscreen": __get_fullscreen_stock_id(),
    "StopItem": gtk.STOCK_MEDIA_STOP,
    "NextItem": gtk.STOCK_MEDIA_NEXT,
    "PreviousItem": gtk.STOCK_MEDIA_PREVIOUS,
    "PlayPauseItem": gtk.STOCK_MEDIA_PLAY,
    "Open": gtk.STOCK_OPEN,
    "EditPreferences": gtk.STOCK_PREFERENCES,
    "Quit": gtk.STOCK_QUIT,
    "Help": gtk.STOCK_HELP,
    "About": gtk.STOCK_ABOUT,
    "Translate": gtk.STOCK_EDIT
}

for i in range(1, 13):
    name = 'F%d' % i
    keymap.menubar_key_map[getattr(menus, name)] = name

def get_accel_string(shortcut):
    mod_str = ''.join(keymap.menubar_mod_map[mod] for mod in shortcut.modifiers)
    key_str = keymap.menubar_key_map.get(shortcut.shortcut, shortcut.shortcut)
    return mod_str + key_str

def get_stock_id(n):
    return STOCK_IDS.get(n, None)

class WrappedWindow(gtk.Window):
    def do_map(self):
        gtk.Window.do_map(self)
        wrappermap.wrapper(self).emit('show')

    def do_unmap(self):
        gtk.Window.do_unmap(self)
        wrappermap.wrapper(self).emit('hide')
    def do_focus_in_event(self, event):
        gtk.Window.do_focus_in_event(self, event)
        wrappermap.wrapper(self).emit('active-change')
    def do_focus_out_event(self, event):
        gtk.Window.do_focus_out_event(self, event)
        wrappermap.wrapper(self).emit('active-change')

    def do_key_press_event(self, event):
        ret = keymap.translate_gtk_event(event)
        if ret == None:
            return gtk.Window.do_key_press_event(self, event)
        key, modifiers = ret
        if wrappermap.wrapper(self).emit('key-press', key, modifiers):
            return # handler returned True, don't process the key more
        return gtk.Window.do_key_press_event(self, event)

gobject.type_register(WrappedWindow)

class WrappedMainWindow(WrappedWindow):
    def do_key_press_event(self, event):
        if (gtk.gdk.keyval_name(event.keyval) == 'Return' and
                event.state & gtk.gdk.MOD1_MASK and
                app.playback_manager.is_playing):
            # Hack for having 2 shortcuts for fullscreen
            app.widgetapp.on_fullscreen_clicked()
            return
        return WrappedWindow.do_key_press_event(self, event)

gobject.type_register(WrappedMainWindow)

class WindowBase(signals.SignalEmitter):
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('use-custom-style-changed')
        self.create_signal('key-press')
        self.create_signal('show')
        self.create_signal('hide')
        # FIXME - this is a weird place to have the menu code because
        # it causes all WindowBase subclasses to have all this extra
        # menu stuff.
        self.menu_structure = None
        self.menu_action_groups = None
        self._merge_id = None
        self._subtitle_tracks_cached = None
        self._setup_ui_manager()

    def set_window(self, window):
        self._window = window
        window.connect('style-set', self.on_style_set)
        wrappermap.add(window, self)
        self.calc_use_custom_style()

    def on_style_set(self, widget, old_style):
        old_use_custom_style = self.use_custom_style
        self.calc_use_custom_style()
        if old_use_custom_style != self.use_custom_style:
            self.emit('use-custom-style-changed')

    def calc_use_custom_style(self):
        base = self._window.style.base[gtk.STATE_NORMAL]
        # Decide if we should use a custom style.  Right now the
        # formula is the base color is a very light shade of
        # gray/white (lighter than #f0f0f0).
        self.use_custom_style = ((base.red == base.green == base.blue) and
                base.red >= 61680)

    def connect_menu_keyboard_shortcuts(self):
        self._window.add_accel_group(self.ui_manager.get_accel_group())

    def _add_menu(self, menu, outstream, parent=None):
        outstream.write('<menu action="%s">' % menu.action)
        for mem in menu.menuitems:
            if isinstance(mem, menus.Menu):
                self._add_menu(mem, outstream, menu)
            elif isinstance(mem, menus.Separator):
                self._add_separator(mem, outstream)
            elif isinstance(mem, menus.MenuItem):
                self._add_menuitem(mem, outstream)
        outstream.write('</menu>')

    def _add_menuitem(self, menu, outstream):
        if menu.action not in ("NoneAvailable", "SubtitlesSelect"):
            outstream.write('<menuitem action="%s" />' % menu.action)

    def _add_separator(self, menu, outstream):
        outstream.write("<separator />")

    def _setup_ui_manager(self):
        self.menu_structure = menus.get_menu()

        # make modifications to the menu structure here

        # on linux, we don't have a CheckVersion option because
        # we update with the package system.
        this_platform = config.get(prefs.APP_PLATFORM)
        if this_platform == 'linux':
            file_menu = self.menu_structure.get("FileMenu")
            file_menu.remove("CheckVersion")

        # If the renderer supports it, create a the subtitle encodings menu
        try:
            app.video_renderer.setup_subtitle_encoding_menu(self.menu_structure)
        except AttributeError:
            pass

        # generate action groups after making all modifications
        mag = menus.generate_action_groups(self.menu_structure)
        self.menu_action_groups = mag

        self.ui_manager = gtk.UIManager()
        self.make_actions()

        outstream = StringIO.StringIO()
        outstream.write('<ui><menubar name="MiroMenu">')
        extra_accelerators = []
        for mem in self.menu_structure.menuitems:
            self._add_menu(mem, outstream)
        outstream.write('</menubar>')

        for mem in self.menu_structure:
            if ((not isinstance(mem, menus.MenuItem) or
                 len(mem.shortcuts) <= 1)):
                continue
            for shortcut in mem.shortcuts[1:]:
                outstream.write('<accelerator action="%s%i" />' % \
                                (mem.action, id(shortcut)))
        outstream.write('</ui>')
        self.ui_manager.add_ui_from_string(outstream.getvalue())

    def make_action(self, action, label, groups, shortcuts=None):
        gtk_action = gtk.Action(action, label, None, get_stock_id(action))
        self.setup_action(gtk_action, groups, shortcuts)

    def make_radio_action(self, action, radio_group, label, groups,
            shortcuts):
        gtk_action = gtk.RadioAction(action, label, None,
                get_stock_id(action), 0)
        self.setup_action(gtk_action, groups, shortcuts)
        try:
            root_action = self.radio_group_actions[radio_group]
        except KeyError:
            # gtk_action is the first action for the group.
            self.radio_group_actions[radio_group] = gtk_action
        else:
            # There was already a gtk_action for this group
            gtk_action.set_group(root_action)

    def setup_action(self, gtk_action, groups, shortcuts):
        callback = menus.lookup_handler(gtk_action.get_name())
        if callback is not None:
            gtk_action.connect("activate", self.on_activate, callback)
        action_group_name = groups[0]
        action_group = self.action_groups[action_group_name]
        if shortcuts is None or len(shortcuts) == 0:
            action_group.add_action(gtk_action)
        else:
            action_group.add_action_with_accel(gtk_action,
                                               get_accel_string(shortcuts[0]))
            for shortcut in shortcuts[1:]:
                shortcut_name = gtk_action.get_name() + str(id(shortcut))
                extra_action = gtk.Action(shortcut_name, None, None, None)
                extra_action.set_visible(False)
                if callback is not None:
                    extra_action.connect('activate', self.on_activate,
                                         callback)
                action_group.add_action_with_accel(extra_action,
                                                   get_accel_string(shortcut))

    def make_check_action(self, action, label, groups, callback, index,
                          group=None):
        gtk_action = gtk.RadioAction(action, label, None, None, index)
        if group is not None:
            gtk_action.set_group(group)
        gtk_action.connect("activate", callback, index)
        self.action_groups[groups[0]].add_action(gtk_action)

    def make_actions(self):
        self.action_groups = {}
        self.radio_group_actions = {}

        for name in self.menu_action_groups.keys():
            self.action_groups[name] = gtk.ActionGroup(name)

        self.action_groups["Subtitles"] = gtk.ActionGroup("Subtitles")

        for mem in self.menu_structure:
            if isinstance(mem, menus.Separator):
                continue
            if isinstance(mem, menus.Menu):
                self.make_action(mem.action, mem.label, mem.groups)
            elif isinstance(mem, menus.RadioMenuItem):
                self.make_radio_action(mem.action, mem.radio_group, mem.label,
                        mem.groups, mem.shortcuts)
            elif isinstance(mem, menus.MenuItem):
                self.make_action(mem.action, mem.label, mem.groups,
                        mem.shortcuts)


        # make a bunch of SubtitleTrack# actions
        self.make_check_action("SubtitlesDisabled", _("Disable Subtitles"),
                               ["AlwaysOn"], self.on_subtitles_change, -1)
        radio_group = self.action_groups["AlwaysOn"].get_action("SubtitlesDisabled")
        for i in range(199):
            self.make_check_action("SubtitleTrack%d" % i, "", ["AlwaysOn"],
                                   self.on_subtitles_change, i, radio_group)

        for action_group in self.action_groups.values():
            self.ui_manager.insert_action_group(action_group, -1)

    def on_subtitles_select(self, action, track_index):
        action_group = self.action_groups["AlwaysOn"]
        action_group.get_action("SubtitlesDisabled").current_value = -2
        app.playback_manager.open_subtitle_file()

    def on_subtitles_change(self, action, track_index):
        if hasattr(self, "_ignore_on_subtitles_change"):
            return
        if action.get_property("current-value") != action.get_property("value"):
            return
        action_group = self.action_groups["AlwaysOn"]
        action_group.get_action("SubtitlesDisabled").current_value = track_index
        if track_index == -1:
            app.video_renderer.disable_subtitles()
        else:
            app.video_renderer.enable_subtitle_track(track_index)

    def select_subtitle_radio(self, track_index):
        self._ignore_on_subtitles_change = True
        action_group = self.action_groups["AlwaysOn"]
        action = action_group.get_action("SubtitlesDisabled")
        action.set_property('current-value', track_index)
        delattr(self, "_ignore_on_subtitles_change")

    def on_activate(self, action, callback):
        callback()

class Window(WindowBase):
    """The main Miro window.  """

    def __init__(self, title, rect=None):
        """Create the Miro Main Window.  Title is the name to give the
        window, rect specifies the position it should have on screen.
        """
        WindowBase.__init__(self)
        self.set_window(self._make_gtk_window())
        self._window.set_title(title)
        if rect:
            self._window.set_default_size(rect.width, rect.height)
            self._window.set_default_size(rect.width, rect.height)
            self._window.set_gravity(gtk.gdk.GRAVITY_CENTER)
            self._window.move(rect.x, rect.y)

        self.create_signal('active-change')
        self.create_signal('will-close')
        self.create_signal('did-move')
        alive_windows.add(self)

        self._window.connect('delete-event', self.on_delete)

    def _make_gtk_window(self):
        return WrappedWindow()

    def on_delete(self, widget, event):
        self.emit('will-close')
        return True

    def set_title(self, title):
        self._window.set_title(title)

    def show(self):
        if self not in alive_windows:
            raise ValueError("Window destroyed")
        self._window.show()

    def close(self):
        self._window.hide()

    def destroy(self):
        self._window.destroy()
        alive_windows.discard(self)

    def is_active(self):
        return self._window.is_active()

    def is_visible(self):
        return self._window.props.visible

    def set_content_widget(self, widget):
        """Set the widget that will be drawn in the content area for this
        window.

        It will be allocated the entire area of the widget, except the
        space needed for the titlebar, frame and other decorations.
        When the window is resized, content should also be resized.
        """
        self._add_content_widget(widget)
        widget._widget.show()
        self.content_widget = widget

    def _add_content_widget(self, widget):
        self._window.add(widget._widget)

    def get_content_widget(self, widget):
        """Get the current content widget."""
        return self.content_widget

    def get_frame(self):
        pos = self._window.get_position()
        size = self._window.get_size()
        return widgets.Rect(pos[0], pos[1], size[0], size[1])

    def check_position_and_fix(self):
        """This pulls the geometry of the monitor of the screen this
        window is on as well as the position of the window.

        It then makes sure that the position y is greater than the
        monitor geometry y.  This makes sure that the titlebar of
        the window is showing.
        """
        gtkwindow = self._window
        gdkwindow = gtkwindow.window
        screen = gtkwindow.get_screen()

        monitor = screen.get_monitor_at_window(gdkwindow)
        monitor_geom = screen.get_monitor_geometry(monitor)
        frame_extents = gdkwindow.get_frame_extents()
        position = gtkwindow.get_position()

        # if the frame is not visible, then we move the window so that
        # it is
        if frame_extents.y < monitor_geom.y:
            gtkwindow.move(position[0],
                           monitor_geom.y + (position[1] - frame_extents.y))

class MainWindow(Window):
    def __init__(self, title, rect):
        Window.__init__(self, title, rect)
        self.vbox = gtk.VBox()
        self._window.add(self.vbox)
        self.vbox.show()
        self._add_menubar()
        self.connect_menu_keyboard_shortcuts()
        self.create_signal('save-dimensions')
        self.create_signal('save-maximized')
        app.menu_manager.connect('enabled-changed', self.on_menu_change)
        app.menu_manager.connect('radio-group-changed', self.on_radio_change)
        app.playback_manager.connect('did-start-playing', self.on_playback_change)
        app.playback_manager.connect('will-play', self.on_playback_change)
        app.playback_manager.connect('did-stop', self.on_playback_change)

        self._window.connect('key-release-event', self.on_key_release)
        self._window.connect('window-state-event', self.on_window_state_event)
        self._window.connect('configure-event', self.on_configure_event)
        self.connect('will-close', self.on_close)
        self._clear_subtitles_menu()

    def _make_gtk_window(self):
        return WrappedMainWindow()

    def on_close(self, window):
        app.widgetapp.on_close()

    def on_configure_event(self, widget, event):
        (x, y) = self._window.get_position()
        (width, height) = self._window.get_size()
        self.emit('save-dimensions', x, y, width, height)

    def on_window_state_event(self, widget, event):
        maximized = (event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED) != 0
        self.emit('save-maximized', maximized)

    def on_key_release(self, widget, event):
        if app.playback_manager.is_playing:
            if gtk.gdk.keyval_name(event.keyval) in ('Right', 'Left',
                                                     'Up', 'Down'):
                return True

    def _add_menubar(self):
        self.menubar = self.ui_manager.get_widget("/MiroMenu")
        self.vbox.pack_start(self.menubar, expand=False)
        self.menubar.show_all()

    def on_menu_change(self, menu_manager):
        for name, action_group in self.action_groups.items():
            if name in menu_manager.enabled_groups:
                action_group.set_sensitive(True)
            else:
                action_group.set_sensitive(False)

        removeSomething = self.menu_structure.get("RemoveSomething").label
        updateFeeds = self.menu_structure.get("UpdateFeeds").label
        removePlaylists = self.menu_structure.get("RemovePlaylists").label
        removeItems = self.menu_structure.get("RemoveItems").label

        def get_state_label(action, state):
            menu = self.menu_structure.get(action)
            return menu.state_labels.get(state, menu.label)

        for state, actions in menu_manager.states.items():
            if "RemoveSomething" in actions:
                removeSomething = get_state_label("RemoveSomething", state)
            if "UpdateFeeds" in actions:
                updateFeeds = get_state_label("UpdateFeeds", state)
            if "RemovePlaylists" in actions:
                removePlaylists = get_state_label("RemovePlaylists", state)
            if "RemoveItems" in actions:
                removeItems = get_state_label("RemoveItems", state)

        action_groups = self.action_groups

        def change_label(group, action, newlabel):
            action_groups[group].get_action(action).set_property("label", newlabel)

        change_label("RemoveAllowed", "RemoveSomething", removeSomething)
        change_label("FeedsSelected", "UpdateFeeds", updateFeeds)
        change_label("PlaylistsSelected", "RemovePlaylists", removePlaylists)
        change_label("PlayablesSelected", "RemoveItems", removeItems)

        play_pause = self.menu_structure.get("PlayPauseItem").state_labels[menu_manager.play_pause_state]
        change_label("PlayPause", "PlayPauseItem", play_pause)

    def on_radio_change(self, menu_manager, radio_group, value):
        root_action = self.radio_group_actions[radio_group]
        for action in root_action.get_group():
            if action.get_name() == value:
                action.set_active(True)
                return

    def on_playback_change(self, playback_manager, *extra_args):
        self._ignore_on_subtitles_change = True
        if app.playback_manager.is_playing_audio:
            self._clear_subtitles_menu()
        else:
            tracks = app.video_renderer.get_subtitle_tracks()
            if len(tracks) == 0:
                self._clear_subtitles_menu()
            else:
                self._populate_subtitles_menu(tracks)
        delattr(self, "_ignore_on_subtitles_change")

    def _populate_subtitles_menu(self, tracks):
        enabled_track = app.video_renderer.get_enabled_subtitle_track()

        if self._subtitle_tracks_cached == (tuple(tracks), enabled_track):
            return

        self._subtitle_tracks_cached = (tuple(tracks), enabled_track)

        if self._merge_id is not None:
            self.ui_manager.remove_ui(self._merge_id)

        outstream = StringIO.StringIO()
        outstream.write('''<ui>
<menubar name="MiroMenu">
   <menu action="PlaybackMenu">
      <menu action="SubtitlesMenu">
''')
        for i, lang in tracks:
            outstream.write('         <menuitem action="SubtitleTrack%d"/>\n' % i)
        outstream.write('''         <separator/>
         <menuitem action="SubtitlesDisabled"/>
         <menuitem action="SubtitlesSelect"/>
      </menu>
   </menu>
</menubar>
</ui>''')

        self._merge_id = self.ui_manager.add_ui_from_string(outstream.getvalue())
        
        action_group = self.action_groups["AlwaysOn"]
        for i, lang in tracks:
            action_group.get_action("SubtitleTrack%d" % i).set_property("label", lang)

        action_group.get_action("SubtitlesDisabled").set_property("current-value", enabled_track)

    def _clear_subtitles_menu(self):
        if self._merge_id is not None:
            self.ui_manager.remove_ui(self._merge_id)
            self._subtitle_tracks_cached = None

        s = '''<ui>
<menubar name="MiroMenu">
<menu action="PlaybackMenu">
<menu action="SubtitlesMenu">
<menuitem action="NoneAvailable"/>
<menuitem action="SubtitlesSelect"/>
</menu>
</menu>
</menubar>
</ui>'''
        self._merge_id = self.ui_manager.add_ui_from_string(s)

    def _add_content_widget(self, widget):
        self.vbox.pack_start(widget._widget, expand=True)

_stock = {
    dialogs.BUTTON_OK.text: gtk.STOCK_OK,
    dialogs.BUTTON_CANCEL.text: gtk.STOCK_CANCEL,
    dialogs.BUTTON_YES.text: gtk.STOCK_YES,
    dialogs.BUTTON_NO.text: gtk.STOCK_NO,
    dialogs.BUTTON_QUIT.text: gtk.STOCK_QUIT,
    dialogs.BUTTON_REMOVE.text: gtk.STOCK_REMOVE,
    dialogs.BUTTON_DELETE.text: gtk.STOCK_DELETE,
    }

class DialogBase(WindowBase):
    def set_transient_for(self, window):
        self._window.set_transient_for(window._window)

    def run(self):
        running_dialogs.add(self)
        try:
            return self._run()
        finally:
            running_dialogs.remove(self)

    def _run(self):
        """Run the dialog.  Must be implemented by subclasses."""
        raise NotImplementedError()

    def destroy(self):
        self._window.destroy()

class Dialog(DialogBase):
    def __init__(self, title, description=None):
        """Create a dialog."""
        DialogBase.__init__(self)
        self.create_signal('open')
        self.create_signal('close')
        self.set_window(gtk.Dialog(title))
        self._window.set_default_size(425, -1)
        self.packing_vbox = gtk.VBox(spacing=20)
        self.packing_vbox.set_border_width(6)
        self._window.vbox.pack_start(self.packing_vbox, True, True)
        if description:
            label = gtk.Label(description)
            label.set_line_wrap(True)
            label.set_size_request(390, -1)
            label.set_selectable(True)
            self.packing_vbox.pack_start(label)
        self.extra_widget = None
        self.buttons_to_add = []
        wrappermap.add(self._window, self)

    def add_button(self, text):
        self.buttons_to_add.append(_stock.get(text, text))

    def pack_buttons(self):
        # There's a couple tricky things here:
        # 1) We need to add them in the reversed order we got them, since GTK
        # lays them out left-to-right
        #
        # 2) We can't use 0 as a response-id.  GTK only reserves positive
        # response_ids for the user.
        response_id = len(self.buttons_to_add)
        for text in reversed(self.buttons_to_add):
            self._window.add_button(text, response_id)
            response_id -= 1
        self.buttons_to_add = []
        self._window.set_default_response(1)

    def _run(self):
        self.pack_buttons()
        self._window.show_all()
        response = self._window.run()
        self._window.hide()
        if response == gtk.RESPONSE_DELETE_EVENT:
            return -1
        else:
            return response - 1 # response IDs started at 1

    def destroy(self):
        DialogBase.destroy(self)
        if hasattr(self, 'packing_vbox'):
            del self.packing_vbox

    def set_extra_widget(self, widget):
        if self.extra_widget:
            self.packing_vbox.remove(widget._widget)
        self.extra_widget = widget
        self.packing_vbox.pack_start(widget._widget)

    def get_extra_widget(self):
        return self.extra_widget

class FileDialogBase(DialogBase):
    def _run(self):
        ret = self._window.run()
        if ret == gtk.RESPONSE_OK:
            self._files = self._window.get_filenames()
            return 0

class FileOpenDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._files = None
        fcd = gtk.FileChooserDialog(title,
                                    action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_OPEN,
                                             gtk.RESPONSE_OK))

        self.set_window(fcd)

    def set_filename(self, text):
        self._window.set_filename(text)

    def set_select_multiple(self, value):
        self._window.set_select_multiple(value)

    def add_filters(self, filters):
        for name, ext_list in filters:
            f = gtk.FileFilter()
            f.set_name(name)
            for mem in ext_list:
                f.add_pattern('*.%s' % mem)
            self._window.add_filter(f)

        f = gtk.FileFilter()
        f.set_name(_('All files'))
        f.add_pattern('*')
        self._window.add_filter(f)

    def get_filenames(self):
        return [utils.FilenameType(f) for f in self._files]

    def get_filename(self):
        return utils.FilenameType(self._files[0])

class FileSaveDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._files = None
        fcd = gtk.FileChooserDialog(title,
                                    action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_SAVE,
                                             gtk.RESPONSE_OK))
        self.set_window(fcd)

    def set_filename(self, text):
        self._window.set_current_name(text)

    def get_filename(self):
        return utils.FilenameType(self._files[0])

class DirectorySelectDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._files = None
        choose_str =_('Choose').encode('utf-8')
        fcd = gtk.FileChooserDialog(title,
                                    action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                    buttons=(gtk.STOCK_CANCEL,
                                             gtk.RESPONSE_CANCEL,
                                             choose_str, gtk.RESPONSE_OK))
        self.set_window(fcd)

    def set_directory(self, text):
        self._window.set_filename(text)

    def get_directory(self):
        return utils.FilenameType(self._files[0])

class AboutDialog(Dialog):
    def __init__(self):
        Dialog.__init__(self,
                        _("About %(appname)s") % {
                'appname': config.get(prefs.SHORT_APP_NAME)})
        icon_pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(
                resources.share_path('icons/hicolor/128x128/apps/miro.png'),
                48, 48)
        self.packing_vbox.pack_start(gtk.image_new_from_pixbuf(icon_pixbuf))
        if config.get(prefs.APP_REVISION_NUM):
            version = "%s (%s)" % (
                config.get(prefs.APP_VERSION),
                config.get(prefs.APP_REVISION_NUM))
        else:
            version = "%s" % config.get(prefs.APP_VERSION)
        name_label = gtk.Label('<span size="xx-large" weight="bold">%s %s</span>' % (
                config.get(prefs.SHORT_APP_NAME), version))
        name_label.set_use_markup(True)
        self.packing_vbox.pack_start(name_label)
        copyright_text = _('%(copyright)s.  See license.txt file for details.\n'
                           '%(trademark)s') % (
            {"copyright": config.get(prefs.COPYRIGHT),
             "trademark": config.get(prefs.TRADEMARK)})
        copyright_label = gtk.Label('<small>%s</small>' % copyright_text)
        copyright_label.set_use_markup(True)
        copyright_label.set_justify(gtk.JUSTIFY_CENTER)
        self.packing_vbox.pack_start(copyright_label)
        self.packing_vbox.pack_start(gtk.Label(config.get(prefs.PROJECT_URL)))

        # this removes the newlines in the description so it wraps correctly
        adopters_data = file(resources.path('ADOPTERS'), 'r').read()
        first_double_newline = adopters_data.find('\n\n')
        adopters_data = adopters_data[first_double_newline+2:-1].replace('\n', ', ')

        # show the adopters
        adopters_buffer = gtk.TextBuffer()
        adopters_buffer.set_text(adopters_data)
        iter = adopters_buffer.get_start_iter()
        adopters_buffer.insert(iter,
            'Thank you to the following people who have adopted '
            'lines of Miro code to help support development! '
            'To help fund continued Miro development, visit the ')
        adopt_link_tag = adopters_buffer.create_tag(
            foreground='blue', underline=pango.UNDERLINE_SINGLE)
        adopt_link_tag.connect('event', self.on_adopt_link_event)
        adopters_buffer.insert_with_tags(iter, 'donation page',
                                         adopt_link_tag)
        adopters_buffer.insert(iter, '.\n\n')
        adopters_view = gtk.TextView(adopters_buffer)
        adopters_view.set_editable(False)
        adopters_view.set_cursor_visible(False)
        adopters_view.set_wrap_mode(gtk.WRAP_WORD)
        adopters_window = gtk.ScrolledWindow()
        adopters_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        adopters_window.add(adopters_view)
        adopters_window.set_size_request(-1, 100)
        self.packing_vbox.pack_start(adopters_window)

        self.add_button(_("Close"))
        self._window.set_has_separator(False)

    def on_adopt_link_event(self, texttag, widget, event, iter):
        if event.type == gtk.gdk.BUTTON_PRESS:
            resources.open_url('http://getmiro.com/donate/')

type_map = {
    0: gtk.MESSAGE_WARNING,
    1: gtk.MESSAGE_INFO,
    2: gtk.MESSAGE_ERROR
}

class AlertDialog(DialogBase):
    def __init__(self, title, description, alert_type):
        DialogBase.__init__(self)
        message_type = type_map.get(alert_type, gtk.MESSAGE_INFO)
        self.set_window(gtk.MessageDialog(type=message_type,
                                          message_format=description))
        self._window.set_title(title)

    def add_button(self, text):
        self._window.add_button(_stock.get(text, text), 1)
        self._window.set_default_response(1)

    def _run(self):
        self._window.set_modal(False)
        self._window.show_all()
        response = self._window.run()
        self._window.hide()
        if response == gtk.RESPONSE_DELETE_EVENT:
            return -1
        else:
            # response IDs start at 1
            return response - 1
