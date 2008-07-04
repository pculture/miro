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

"""miro.frontends.wigets.gtk.window -- GTK Window widget."""

import StringIO

import gobject
import gtk

from miro import app
from miro import menubar
from miro import signals
from miro import dialogs
from miro.gtcache import gettext as _
from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets import menus

alive_windows = set() # Keeps the objects alive until destroy() is called

def __get_fullscreen_stock_id():
    try:
        return gtk.STOCK_FULLSCREEN
    except:
        pass

STOCK_IDS = {
    "SaveVideo": gtk.STOCK_SAVE,
    "CopyVideoURL": gtk.STOCK_COPY,
    "RemoveVideos": gtk.STOCK_REMOVE,
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

def get_stock_id(n):
    return STOCK_IDS.get(n, None)

class WrappedWindow(gtk.Window):
    def do_delete_event(self, event):
        wrappermap.wrapper(self).on_delete()
        return True
    def do_focus_in_event(self, event):
        gtk.Window.do_focus_in_event(self, event)
        wrappermap.wrapper(self).emit('active-change')
    def do_focus_out_event(self, event):
        gtk.Window.do_focus_out_event(self, event)
        wrappermap.wrapper(self).emit('active-change')
    def do_configure_event(self, event):
        wrappermap.wrapper(self).on_configure()
        gtk.Window.do_configure_event(self, event)

gobject.type_register(WrappedWindow)

class WindowBase(signals.SignalEmitter):
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('use-custom-style-changed')

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

    def __init__(self, title, rect):
        """Create the Miro Main Window.  Title is the name to give the window,
        rect specifies the position it should have on screen.
        """
        WindowBase.__init__(self)
        self.set_window(WrappedWindow())
        self._window.set_title(title)
        self._window.set_default_size(rect.width, rect.height)
        self.create_signal('active-change')
        self.create_signal('save-dimensions')
        alive_windows.add(self)

    def on_delete(self):
        app.widgetapp.quit()
        return True

    def on_configure(self):
        (x, y) = self._window.get_position()
        (width, height) = self._window.get_size()
        self.emit('save-dimensions', x, y, width, height)

    def show(self):
        if self not in alive_windows:
            raise ValueError("Window destroyed")
        self._window.show()

    def close(self):
        self._window.hide()

    def destroy(self):
        self.close()
        alive_windows.discard(self)

    def is_active(self):
        return self._window.is_active()

    def set_content_widget(self, widget):
        """Set the widget that will be drawn in the content area for this
        window.

        It will be allocated the entire area of the widget, except the space
        needed for the titlebar, frame and other decorations.  When the window
        is resived, content should also be resized.
        """
        self._add_content_widget(widget)
        widget._widget.show()
        self.content_widget = widget

    def _add_content_widget(self, widget):
        self._window.add(widget._widget)

    def get_content_widget(self, widget):
        """Get the current content widget."""
        return self.content_widget

class MainWindow(Window):
    def __init__(self, title, rect):
        Window.__init__(self, title, rect)
        self.vbox = gtk.VBox()
        self._window.add(self.vbox)
        self.vbox.show()
        self.add_menus()
        app.menu_manager.connect('enabled-changed', self.on_menu_change)

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

    def make_action(self, action, label):
        gtk_action = gtk.Action(action, label, None, get_stock_id(action))
        callback = menus.lookup_handler(action)
        if callback is not None:
            gtk_action.connect("activate", self.on_activate, callback)
        action_group_name = menus.get_action_group_name(action)
        action_group = self.action_groups[action_group_name]
        action_group.add_action(gtk_action)

    def make_actions(self):
        self.action_groups = {}
        for name in menus.action_group_names():
            self.action_groups[name] = gtk.ActionGroup(name)

        for menu in menubar.menubar:
            self.make_action('Menu' + menu.action, menu.label)
            for menuitem in menu.menuitems:
                if isinstance(menuitem, menubar.Separator):
                    continue
                self.make_action(menuitem.action, menuitem.label)
        for action_group in self.action_groups.values():
            self.ui_manager.insert_action_group(action_group, -1)

    def on_menu_change(self, menu_manager):
        for name, action_group in self.action_groups.items():
            if name in menu_manager.enabled_groups:
                action_group.set_sensitive(True)
            else:
                action_group.set_sensitive(False)

    def on_activate(self, action, callback):
        callback()

    def _add_content_widget(self, widget):
        self.vbox.pack_start(widget._widget, expand=True)


_stock = { dialogs.BUTTON_OK.text : gtk.STOCK_OK,
           dialogs.BUTTON_CANCEL.text : gtk.STOCK_CANCEL,
           dialogs.BUTTON_YES.text : gtk.STOCK_YES,
           dialogs.BUTTON_NO.text : gtk.STOCK_NO,
           dialogs.BUTTON_QUIT.text : gtk.STOCK_QUIT}

class Dialog(WindowBase):
    def __init__(self, title, description):
        """Create a dialog."""
        WindowBase.__init__(self)
        self.set_window(gtk.Dialog(title))
        self._window.set_default_size(425, -1)
        self.packing_vbox = gtk.VBox(spacing=20)
        self.packing_vbox.set_border_width(6)
        self._window.vbox.pack_start(self.packing_vbox, True, True)
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

    def run(self):
        self.pack_buttons()
        self._window.show_all()
        response = self._window.run()
        self._window.hide()
        if response == gtk.RESPONSE_DELETE_EVENT:
            return -1
        else:
            return response - 1 # response IDs started at 1

    def destroy(self):
        self._window.destroy()
        if hasattr(self, 'packing_vbox'):
            del self.packing_vbox

    def set_extra_widget(self, widget):
        if self.extra_widget:
            self.packing_vbox.remove(widget._widget)
        self.extra_widget = widget
        self.packing_vbox.pack_start(widget._widget)

    def get_extra_widget(self):
        return self.extra_widget

class FileOpenDialog:
    def __init__(self, title):
        self._text = None
        self._widget = gtk.FileChooserDialog(title,
                               action=gtk.FILE_CHOOSER_ACTION_OPEN,
                               buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))

    def close(self):
        self._window.hide()

    def destroy(self):
        self._widget.destroy()

    def set_filename(self, text):
        self._widget.set_filename(text)

    def add_filters(self, filters):
        for name, ext_list in filters:
            filter = gtk.FileFilter()
            filter.set_name(name)
            for mem in ext_list:
                filter.add_pattern('*.%s' % mem)
            self._widget.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name(_('All files'))
        filter.add_pattern('*')
        self._widget.add_filter(filter)

    def get_filename(self):
        return self._text

    def run(self):
        ret = self._widget.run()
        if ret == gtk.RESPONSE_OK:
            self._text = self._widget.get_filename()
            return 0

class FileSaveDialog:
    def __init__(self, title):
        self._text = None
        self._widget = gtk.FileChooserDialog(title,
                               action=gtk.FILE_CHOOSER_ACTION_SAVE,
                               buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_SAVE, gtk.RESPONSE_OK))

    def close(self):
        self._window.hide()

    def destroy(self):
        self._widget.destroy()

    def set_filename(self, text):
        self._widget.set_current_name(text)

    def get_filename(self):
        return self._text

    def run(self):
        ret = self._widget.run()
        if ret == gtk.RESPONSE_OK:
            self._text = self._widget.get_filename()
            return 0
