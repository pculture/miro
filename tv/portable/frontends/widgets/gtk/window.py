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

import gobject
import gtk

from miro import app
from miro import signals
from miro import dialogs
from miro.frontends.widgets.gtk import wrappermap

alive_windows = set() # Keeps the objects alive until destroy() is called

class WrappedWindow(gtk.Window):
    def do_delete_event(self, event):
        wrappermap.wrapper(self).on_delete()
    def do_focus_in_event(self, event):
        gtk.Window.do_focus_in_event(self, event)
        wrappermap.wrapper(self).emit('active-change')
    def do_focus_out_event(self, event):
        gtk.Window.do_focus_out_event(self, event)
        wrappermap.wrapper(self).emit('active-change')
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
        alive_windows.add(self)

    def on_delete(self):
        app.widgetapp.quit()
        return True

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
        self._window.add(widget._widget)
        self._window.child.show()
        self.content_widget = widget

    def get_content_widget(self, widget):
        """Get the current content widget."""
        return self.content_widget


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
