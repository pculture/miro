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

"""miro.frontends.widgets.gtk.window -- GTK Window widget."""

import StringIO

import gobject
import gtk
import os

from miro import app
from miro import prefs
from miro import signals
from miro import dialogs
from miro.fileobject import FilenameType
from miro.gtcache import gettext as _
from miro.frontends.widgets.gtk import gtkmenus
from miro.frontends.widgets.gtk import keymap
from miro.frontends.widgets.gtk import layout
from miro.frontends.widgets.gtk import widgets
from miro.frontends.widgets.gtk import wrappermap
from miro.plat import resources

# keeps the objects alive until destroy() is called
alive_windows = set()
running_dialogs = set()

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
        if self.activate_key(event): # event activated a menu item
            return

        if self.propagate_key_event(event): # event handled by widget
            return

        ret = keymap.translate_gtk_event(event)
        if ret is not None:
            key, modifiers = ret
            rv = wrappermap.wrapper(self).emit('key-press', key, modifiers)
            if not rv:
                gtk.Window.do_key_press_event(self, event)

    def _get_focused_wrapper(self):
        """Get the wrapper of the widget with keyboard focus"""
        focused = self.get_focus()
        # some of our widgets created children for their use
        # (GtkSearchTextEntry).  If we don't find a wrapper for
        # focused, try it's parents
        while focused is not None:
            try:
                wrapper = wrappermap.wrapper(focused)
            except KeyError:
                focused = focused.get_parent()
            else:
                return wrapper
        return None

    def change_focus_using_wrapper(self, direction):
        my_wrapper = wrappermap.wrapper(self)
        focused_wrapper = self._get_focused_wrapper()
        if direction == gtk.DIR_TAB_FORWARD:
            to_focus = my_wrapper.get_next_tab_focus(focused_wrapper, True)
        elif direction == gtk.DIR_TAB_BACKWARD:
            to_focus = my_wrapper.get_next_tab_focus(focused_wrapper, False)
        else:
            return False
        if to_focus is not None:
            to_focus.focus()
            return True
        return False

    def do_focus(self, direction):
        if not self.change_focus_using_wrapper(direction):
            gtk.Window.do_focus(self, direction)

gobject.type_register(WrappedWindow)

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
        # Decide if we should use a custom style.  Right now the
        # formula is the base color is a very light shade of
        # gray/white (lighter than #f0f0f0).
        self.use_custom_style = ((base.red == base.green == base.blue) and
                base.red >= 61680)

    def connect_menu_keyboard_shortcuts(self):
        """Connect the shortcuts for the app menu to this window."""
        self._window.add_accel_group(app.widgetapp.menubar.get_accel_group())

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

        self._window.connect('delete-event', self.on_delete_window)

    def on_delete_window(self, widget, event):
        # when the user clicks on the X in the corner of the window we
        # want that to close the window, but also trigger our
        # will-close signal and all that machinery unless the window
        # is currently hidden--then we don't do anything.
        if not self._window.window.is_visible():
            return
        self.close()
        return True

    def _make_gtk_window(self):
        return WrappedWindow()

    def set_title(self, title):
        self._window.set_title(title)

    def get_title(self):
        self._window.get_title()

    def show(self):
        if self not in alive_windows:
            raise ValueError("Window destroyed")
        self._window.show()

    def close(self):
        if hasattr(self, "_closing"):
            return
        self._closing = True
        self.emit('will-close')
        self._window.hide()
        del self._closing

    def destroy(self):
        self.close()
        self._window.destroy()
        alive_windows.discard(self)

    def is_active(self):
        return self._window.is_active()

    def is_visible(self):
        return self._window.props.visible

    def get_next_tab_focus(self, current, is_forward):
        return None

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

    def set_frame(self, x=None, y=None, width=None, height=None):
        if x is not None or y is not None:
            pos = self._window.get_position()
            x = x if x is not None else pos[0]
            y = y if y is not None else pos[1]
            self._window.move(x, y)

        if width is not None or height is not None:
            size = self._window.get_size()
            width = width if width is not None else size[0]
            height = height if height is not None else size[1]
            self._window.resize(width, height)

    def get_monitor_geometry(self):
        """Returns a Rect of the geometry of the monitor that this
        window is currently on.

        :returns: Rect
        """
        gtkwindow = self._window
        gdkwindow = gtkwindow.window
        screen = gtkwindow.get_screen()

        monitor = screen.get_monitor_at_window(gdkwindow)
        return screen.get_monitor_geometry(monitor)

    def check_position_and_fix(self):
        """This pulls the geometry of the monitor of the screen this
        window is on as well as the position of the window.

        It then makes sure that the position y is greater than the
        monitor geometry y.  This makes sure that the titlebar of
        the window is showing.
        """
        gtkwindow = self._window
        gdkwindow = gtkwindow.window
        monitor_geom = self.get_monitor_geometry()

        frame_extents = gdkwindow.get_frame_extents()
        position = gtkwindow.get_position()

        # if the frame is not visible, then we move the window so that
        # it is
        if frame_extents.y < monitor_geom.y:
            gtkwindow.move(position[0],
                           monitor_geom.y + (position[1] - frame_extents.y))

class DialogWindow(Window):
    def __init__(self, title, rect=None):
        Window.__init__(self, title, rect)
        self._window.set_resizable(False)

class MainWindow(Window):
    def __init__(self, title, rect):
        Window.__init__(self, title, rect)
        self.vbox = gtk.VBox()
        self._window.add(self.vbox)
        self.vbox.show()
        self._add_app_menubar()
        self.create_signal('save-dimensions')
        self.create_signal('save-maximized')
        self.create_signal('on-shown')
        self._window.connect('key-release-event', self.on_key_release)
        self._window.connect('window-state-event', self.on_window_state_event)
        self._window.connect('configure-event', self.on_configure_event)
        self._window.connect('map-event', lambda w, a: self.emit('on-shown'))

    def _make_gtk_window(self):
        return WrappedWindow()

    def on_delete_window(self, widget, event):
        app.widgetapp.on_close()
        return True

    def on_configure_event(self, widget, event):
        (x, y) = self._window.get_position()
        (width, height) = self._window.get_size()
        self.emit('save-dimensions', x, y, width, height)

    def on_window_state_event(self, widget, event):
        maximized = bool(
            event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED)
        self.emit('save-maximized', maximized)

    def on_key_release(self, widget, event):
        if app.playback_manager.is_playing:
            if gtk.gdk.keyval_name(event.keyval) in ('Right', 'Left',
                                                     'Up', 'Down'):
                return True

    def _add_app_menubar(self):
        self.menubar = app.widgetapp.menubar
        self.vbox.pack_start(self.menubar._widget, expand=False)
        self.connect_menu_keyboard_shortcuts()

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
        self.extra_widget = None
        self.buttons_to_add = []
        wrappermap.add(self._window, self)
        self.description = description

    def build_content(self):
        packing_vbox = layout.VBox(spacing=20)
        packing_vbox._widget.set_border_width(6)
        if self.description is not None:
            label = gtk.Label(self.description)
            label.set_line_wrap(True)
            label.set_size_request(390, -1)
            label.set_selectable(True)
            packing_vbox._widget.pack_start(label)
        if self.extra_widget:
            packing_vbox._widget.pack_start(self.extra_widget._widget)
        return packing_vbox

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
        packing_vbox = self.build_content()
        self._window.vbox.pack_start(packing_vbox._widget, True, True)
        self._window.show_all()
        response = self._window.run()
        self._window.hide()
        if response == gtk.RESPONSE_DELETE_EVENT:
            return -1
        else:
            return response - 1 # response IDs started at 1

    def destroy(self):
        DialogBase.destroy(self)

    def set_extra_widget(self, widget):
        self.extra_widget = widget

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
        return [FilenameType(f) for f in self._files]

    def get_filename(self):
        if self._files is None:
            # clicked Cancel
            return None
        else:
            return FilenameType(self._files[0])

    # provide a common interface for file chooser dialogs
    get_path = get_filename
    def set_path(self, path):
        # set_filename puts the whole path in the filename field
        self._window.set_current_folder(os.path.dirname(path))
        self._window.set_current_name(os.path.basename(path))

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
        if self._files is None:
            # clicked Cancel
            return None
        else:
            return FilenameType(self._files[0])

    # provide a common interface for file chooser dialogs
    get_path = get_filename
    def set_path(self, path):
        # set_filename puts the whole path in the filename field
        self._window.set_current_folder(os.path.dirname(path))
        self._window.set_current_name(os.path.basename(path))

class DirectorySelectDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._files = None
        choose_str =_('Choose').encode('utf-8')
        fcd = gtk.FileChooserDialog(
            title,
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(gtk.STOCK_CANCEL,
                     gtk.RESPONSE_CANCEL,
                     choose_str, gtk.RESPONSE_OK))
        self.set_window(fcd)

    def set_directory(self, text):
        self._window.set_filename(text)

    def get_directory(self):
        if self._files is None:
            # clicked Cancel
            return None
        else:
            return FilenameType(self._files[0])

    # provide a common interface for file chooser dialogs
    get_path = get_directory
    set_path = set_directory

class AboutDialog(Dialog):
    def __init__(self):
        Dialog.__init__(self,
            _("About %(appname)s",
              {'appname': app.config.get(prefs.SHORT_APP_NAME)}))
        self.add_button(_("Close"))
        self._window.set_has_separator(False)

    def build_content(self):
        packing_vbox = layout.VBox(spacing=20)
        icon_pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(
                resources.share_path('icons/hicolor/128x128/apps/miro.png'),
                48, 48)
        packing_vbox._widget.pack_start(gtk.image_new_from_pixbuf(icon_pixbuf))
        if app.config.get(prefs.APP_REVISION_NUM):
            version = "%s (%s)" % (
                app.config.get(prefs.APP_VERSION),
                app.config.get(prefs.APP_REVISION_NUM))
        else:
            version = "%s" % app.config.get(prefs.APP_VERSION)
        name_label = gtk.Label(
            '<span size="xx-large" weight="bold">%s %s</span>' % (
                app.config.get(prefs.SHORT_APP_NAME), version))
        name_label.set_use_markup(True)
        packing_vbox._widget.pack_start(name_label)
        copyright_text = _(
            '%(copyright)s.  See license.txt file for details.\n'
            '%(trademark)s',
            {"copyright": app.config.get(prefs.COPYRIGHT),
             "trademark": app.config.get(prefs.TRADEMARK)})
        copyright_label = gtk.Label('<small>%s</small>' % copyright_text)
        copyright_label.set_use_markup(True)
        copyright_label.set_justify(gtk.JUSTIFY_CENTER)
        packing_vbox._widget.pack_start(copyright_label)

        # FIXME - make the project url clickable
        packing_vbox._widget.pack_start(
            gtk.Label(app.config.get(prefs.PROJECT_URL)))

        contributor_label = gtk.Label(
            _("Thank you to all the people who contributed to %(appname)s "
              "%(version)s:",
              {"appname": app.config.get(prefs.SHORT_APP_NAME),
               "version": app.config.get(prefs.APP_VERSION)}))
        contributor_label.set_justify(gtk.JUSTIFY_CENTER)
        packing_vbox._widget.pack_start(contributor_label)

        # get contributors, remove newlines and wrap it
        contributors = open(resources.path('CREDITS'), 'r').readlines()
        contributors = [c[2:].strip()
                        for c in contributors if c.startswith("* ")]
        contributors = ", ".join(contributors)

        # show contributors
        contrib_buffer = gtk.TextBuffer()
        contrib_buffer.set_text(contributors)

        contrib_view = gtk.TextView(contrib_buffer)
        contrib_view.set_editable(False)
        contrib_view.set_cursor_visible(False)
        contrib_view.set_wrap_mode(gtk.WRAP_WORD)
        contrib_window = gtk.ScrolledWindow()
        contrib_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        contrib_window.add(contrib_view)
        contrib_window.set_size_request(-1, 100)
        packing_vbox._widget.pack_start(contrib_window)

        # FIXME - make the project url clickable
        donate_label = gtk.Label(
            _("To help fund continued %(appname)s development, visit the "
              "donation page at:",
              {"appname": app.config.get(prefs.SHORT_APP_NAME)}))
        donate_label.set_justify(gtk.JUSTIFY_CENTER)
        packing_vbox._widget.pack_start(donate_label)

        packing_vbox._widget.pack_start(
            gtk.Label(app.config.get(prefs.DONATE_URL)))
        return packing_vbox

    def on_contrib_link_event(self, texttag, widget, event, iter_):
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
        self.description = description

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
