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

"""miro.frontends.wigets.gtk.window -- GTK Window widget."""

import StringIO

import gobject
import gtk

from miro import app
from miro import config
from miro import prefs
from miro import menubar
from miro import signals
from miro import dialogs
from miro.gtcache import gettext as _
from miro.frontends.widgets.gtk import wrappermap, widgets
from miro.frontends.widgets.gtk import keymap
from miro.frontends.widgets import menus
from miro.plat import resources

alive_windows = set() # Keeps the objects alive until destroy() is called
running_dialogs = set()

def __get_fullscreen_stock_id():
    try:
        return gtk.STOCK_FULLSCREEN
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        pass

STOCK_IDS = {
    "SaveItem": gtk.STOCK_SAVE,
    "CopyItemURL": gtk.STOCK_COPY,
    "RemoveItems": gtk.STOCK_REMOVE,
    "Fullscreen": __get_fullscreen_stock_id(),
    "StopVideo": gtk.STOCK_MEDIA_STOP,
    "NextVideo": gtk.STOCK_MEDIA_NEXT,
    "PreviousVideo": gtk.STOCK_MEDIA_PREVIOUS,
    "PlayPauseVideo": gtk.STOCK_MEDIA_PLAY,
    "Open": gtk.STOCK_OPEN,
    "EditPreferences": gtk.STOCK_PREFERENCES,
    "Quit": gtk.STOCK_QUIT,
    "Help": gtk.STOCK_HELP,
    "About": gtk.STOCK_ABOUT,
    "Translate": gtk.STOCK_EDIT
}

for i in range(1, 13):
    name = 'F%d' % i
    keymap.menubar_key_map[getattr(menubar, name)] = name

def get_accel_string(shortcut):
    mod_str = ''.join(keymap.menubar_mod_map[mod] for mod in shortcut.modifiers)
    try:
        key_str = keymap.menubar_key_map[shortcut.key]
    except KeyError:
        key_str = shortcut.key
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
        key, modifiers = keymap.translate_gtk_event(event)
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
        # Decide if we should use a custom style.  Right now the formula is
        # the base color is a very light shade of gray/white (lighter than
        # #f0f0f0).
        self.use_custom_style = ((base.red == base.green == base.blue) and
                base.red >= 61680)

class Window(WindowBase):
    """The main Miro window.  """

    def __init__(self, title, rect=None):
        """Create the Miro Main Window.  Title is the name to give the window,
        rect specifies the position it should have on screen.
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

        It will be allocated the entire area of the widget, except the space
        needed for the titlebar, frame and other decorations.  When the window
        is resized, content should also be resized.
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

class MainWindow(Window):
    def __init__(self, title, rect):
        Window.__init__(self, title, rect)
        self.vbox = gtk.VBox()
        self._window.add(self.vbox)
        self.vbox.show()
        self.add_menus()
        self.create_signal('save-dimensions')
        self.create_signal('save-maximized')
        app.menu_manager.connect('enabled-changed', self.on_menu_change)

        self._window.connect('key-release-event', self.on_key_release)
        self._window.connect('window-state-event', self.on_window_state_event)
        self._window.connect('configure-event', self.on_configure_event)
        self.connect('will-close', self.on_close)

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
            if gtk.gdk.keyval_name(event.keyval) in ('Right', 'Left', 'Up', 'Down'):
                return True

    def add_menus(self):
        self.ui_manager = gtk.UIManager()
        self.make_actions()
        uistring = StringIO.StringIO()
        uistring.write('<ui><menubar name="MiroMenu">')
        for menu in menubar.menubar:
            uistring.write('<menu action="Menu%s">' % menu.action)
            for menuitem in menu.menuitems:
                if isinstance(menuitem, menubar.Separator):
                    uistring.write("<separator />")
                else:
                    uistring.write('<menuitem action="%s" />' % menuitem.action)
            uistring.write('</menu>')
        uistring.write('</menubar></ui>')
        self.ui_manager.add_ui_from_string(uistring.getvalue())
        self.menubar = self.ui_manager.get_widget("/MiroMenu")
        self.vbox.pack_start(self.menubar, expand=False)
        self.menubar.show_all()
        self._window.add_accel_group(self.ui_manager.get_accel_group())

    def make_action(self, action, label, shortcuts=None):
        gtk_action = gtk.Action(action, label, None, get_stock_id(action))
        callback = menus.lookup_handler(action)
        if callback is not None:
            gtk_action.connect("activate", self.on_activate, callback)
        action_group_name = menus.get_action_group_name(action)
        action_group = self.action_groups[action_group_name]
        if shortcuts is None or len(shortcuts) == 0:
            action_group.add_action(gtk_action)
        else:
            action_group.add_action_with_accel(gtk_action,
                    get_accel_string(shortcuts[0]))

    def make_actions(self):
        self.action_groups = {}
        for name in menus.action_group_names():
            self.action_groups[name] = gtk.ActionGroup(name)

        for menu in menubar.menubar:
            self.make_action('Menu' + menu.action, menu.label)
            for menuitem in menu.menuitems:
                if isinstance(menuitem, menubar.Separator):
                    continue
                self.make_action(menuitem.action, menuitem.label,
                        menuitem.shortcuts)
        for action_group in self.action_groups.values():
            self.ui_manager.insert_action_group(action_group, -1)

    def on_menu_change(self, menu_manager):
        for name, action_group in self.action_groups.items():
            if name in menu_manager.enabled_groups:
                action_group.set_sensitive(True)
            else:
                action_group.set_sensitive(False)

        removeFeeds = menubar.menubar.getLabel("RemoveFeeds")
        updateFeeds = menubar.menubar.getLabel("UpdateFeeds")
        removePlaylists = menubar.menubar.getLabel("RemovePlaylists")
        removeItems = menubar.menubar.getLabel("RemoveItems")

        for state, actions in menu_manager.states.items():
            if "RemoveFeeds" in actions:
                removeFeeds = menubar.menubar.getLabel("RemoveFeeds", state)
            if "UpdateFeeds" in actions:
                updateFeeds = menubar.menubar.getLabel("UpdateFeeds", state)
            if "RemovePlaylists" in actions:
                removePlaylists = menubar.menubar.getLabel("RemovePlaylists", state)
            if "RemoveItems" in actions:
                removeItems = menubar.menubar.getLabel("RemoveItems", state)

        self.action_groups["FeedsSelected"].get_action("RemoveFeeds").set_property("label", removeFeeds)
        self.action_groups["FeedsSelected"].get_action("UpdateFeeds").set_property("label", updateFeeds)
        self.action_groups["PlaylistsSelected"].get_action("RemovePlaylists").set_property("label", removePlaylists)
        self.action_groups["PlayableSelected"].get_action("RemoveItems").set_property("label", removeItems)

        play_pause = menubar.menubar.getLabel("PlayPauseVideo", menu_manager.play_pause_state)
        self.action_groups["PlayableSelected"].get_action("PlayPauseVideo").set_property("label", play_pause)

    def on_activate(self, action, callback):
        callback()

    def _add_content_widget(self, widget):
        self.vbox.pack_start(widget._widget, expand=True)


_stock = { dialogs.BUTTON_OK.text : gtk.STOCK_OK,
           dialogs.BUTTON_CANCEL.text : gtk.STOCK_CANCEL,
           dialogs.BUTTON_YES.text : gtk.STOCK_YES,
           dialogs.BUTTON_NO.text : gtk.STOCK_NO,
           dialogs.BUTTON_QUIT.text : gtk.STOCK_QUIT,
           dialogs.BUTTON_REMOVE.text : gtk.STOCK_REMOVE,
           dialogs.BUTTON_DELETE.text : gtk.STOCK_DELETE,
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
        self.set_window(gtk.FileChooserDialog(title,
                               action=gtk.FILE_CHOOSER_ACTION_OPEN,
                               buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK)))

    def set_filename(self, text):
        self._window.set_filename(text)

    def set_select_multiple(self, value):
        self._window.set_select_multiple(value)

    def add_filters(self, filters):
        for name, ext_list in filters:
            filter = gtk.FileFilter()
            filter.set_name(name)
            for mem in ext_list:
                filter.add_pattern('*.%s' % mem)
            self._window.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name(_('All files'))
        filter.add_pattern('*')
        self._window.add_filter(filter)

    def get_filenames(self):
        return self._files

    def get_filename(self):
        return self._files[0]

class FileSaveDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._files = None
        self.set_window(gtk.FileChooserDialog(title,
                               action=gtk.FILE_CHOOSER_ACTION_SAVE,
                               buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_SAVE, gtk.RESPONSE_OK)))

    def set_filename(self, text):
        self._window.set_current_name(text)

    def get_filename(self):
        return self._files[0]

class DirectorySelectDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._files = None
        choose_str =_('Choose').encode('utf-8')
        self.set_window(gtk.FileChooserDialog(title,
                               action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                               buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        choose_str, gtk.RESPONSE_OK)))

    def set_directory(self, text):
        self._window.set_filename(text)

    def get_directory(self):
        return self._files[0]

class AboutDialog(DialogBase):
    def __init__(self):
        DialogBase.__init__(self)
        self._text = None

        ab = gtk.AboutDialog()
        ab.set_name(config.get(prefs.SHORT_APP_NAME))
        if config.get(prefs.APP_REVISION_NUM):
            ab.set_version("%s (r%s)" %
                           (config.get(prefs.APP_VERSION),
                            config.get(prefs.APP_REVISION_NUM)))
        else:
            ab.set_version("%s" % config.get(prefs.APP_VERSION))
        ab.set_website(config.get(prefs.PROJECT_URL))
        ab.set_copyright(_(
            '%(copyright)s.  See LICENSE file for details.\n'
            'Miro and Miro logo are trademarks of the Participatory '
            'Culture Foundation.',
            {"copyright": config.get(prefs.COPYRIGHT)}
        ))
        self._window = ab

    def _run(self):
        self._window.run()

type_map = {
    0: gtk.MESSAGE_WARNING,
    1: gtk.MESSAGE_INFO,
    2: gtk.MESSAGE_ERROR
}

class AlertDialog(DialogBase):
    def __init__(self, title, description, alert_type):
        DialogBase.__init__(self)
        message_type = type_map.get(alert_type, gtk.MESSAGE_INFO)
        self.set_window(gtk.MessageDialog(type=message_type, message_format=description))
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
            return response - 1 # response IDs started at 1
