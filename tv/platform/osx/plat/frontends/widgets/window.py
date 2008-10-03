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

"""miro.plat.frontends.widgets.window -- Top-level Window class.  """

import weakref

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro import signals
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.helpers import NotificationForwarder
from miro.plat.frontends.widgets.base import Container, FlippedView
from miro.plat.frontends.widgets.layout import VBox, HBox, Alignment
from miro.plat.frontends.widgets.control import Button
from miro.plat.frontends.widgets.simple import Label

# Tracks all windows that haven't been destroyed.  This makes sure there
# object stay alive as long as the window is alive.
alive_windows = set()

class Window(signals.SignalEmitter):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPIfor a description of the API for this class."""
    def __init__(self, title, rect):
        signals.SignalEmitter.__init__(self, 'active-change')
        self.nswindow = NSWindow.alloc()
        self.nswindow.initWithContentRect_styleMask_backing_defer_(
                rect.nsrect,
                NSTitledWindowMask | NSClosableWindowMask | NSMiniaturizableWindowMask | NSResizableWindowMask,
                NSBackingStoreBuffered,
                NO)
        self.nswindow.setTitle_(title)
        self.nswindow.setMinSize_(NSSize(800, 600))
        self.content_view = FlippedView.alloc().initWithFrame_(rect.nsrect)
        self.content_view.setAutoresizesSubviews_(NO)
        self.nswindow.setContentView_(self.content_view)
        self.content_widget = None
        self.view_notifications = NotificationForwarder.create(self.content_view)
        self.view_notifications.connect(self.on_frame_change, 'NSViewFrameDidChangeNotification')
        self.window_notifications = NotificationForwarder.create(self.nswindow)
        self.window_notifications.connect(self.on_activate, 'NSWindowDidBecomeMainNotification')
        self.window_notifications.connect(self.on_deactivate, 'NSWindowDidResignMainNotification')
        wrappermap.add(self.nswindow, self)
        alive_windows.add(self)

    def on_frame_change(self, notification):
        self.place_child()

    def on_activate(self, notification):
        self.emit('active-change')

    def on_deactivate(self, notification):
        self.emit('active-change')

    def is_active(self):
        return self.nswindow.isMainWindow()

    def show(self):
        if self not in alive_windows:
            raise ValueError("Window destroyed")
        self.nswindow.makeKeyAndOrderFront_(nil)
        self.nswindow.makeMainWindow()

    def close(self):
        self.nswindow.orderOut_(nil)

    def destroy(self):
        self.nswindow.close()
        alive_windows.discard(self)

    def place_child(self):
        rect = self.nswindow.contentRectForFrameRect_(self.nswindow.frame())
        self.content_widget.place(NSRect(NSPoint(0, 0), rect.size),
                self.content_view)

    def hookup_content_widget_signals(self):
        self.content_widget.connect('size-request-changed',
                self.on_content_widget_size_request_change)

    def unhook_content_widget_signals(self):
        self.content_widget.disconnect('size-request-changed',
                self.on_content_widget_size_request_change)

    def on_content_widget_size_request_change(self, widget, old_size):
        self.update_size_constraints()

    def set_content_widget(self, widget):
        if self.content_widget:
            self.unhook_content_widget_signals()
        self.content_widget = widget
        self.hookup_content_widget_signals()
        self.place_child()
        self.update_size_constraints()

    def update_size_constraints(self):
        width, height = self.content_widget.get_size_request()
        self.nswindow.setContentMinSize_(NSSize(width, height))

    def get_content_widget(self):
        return self.content_widget

class MainWindow(Window):
    def __init__(self, title, rect):
        Window.__init__(self, title, rect)
        self.nswindow.setReleasedWhenClosed_(NO)

class Dialog:
    def __init__(self, title, description=None):
        self.title = title
        self.description = description
        self.buttons = []
        self.extra_widget = None

    def add_button(self, text):
        button = Button(text)
        button.connect('clicked', self.on_button_clicked, len(self.buttons))
        self.buttons.append(button)

    def on_button_clicked(self, button, code):
        NSApp().stopModalWithCode_(code)

    def build_text(self):
        vbox = VBox(spacing=6)
        if self.description:
            description_label = Label(self.description, wrap=True)
            description_label.set_bold(True)
            description_label.set_size_request(360, -1)
            vbox.pack_start(description_label)
        return vbox

    def build_buttons(self):
        hbox = HBox(spacing=12)
        for button in reversed(self.buttons):
            hbox.pack_start(button)
        alignment = Alignment(xalign=1.0, yscale=1.0)
        alignment.add(hbox)
        return alignment

    def build_content(self):
        vbox = VBox(spacing=12)
        vbox.pack_start(self.build_text())
        if self.extra_widget:
            vbox.pack_start(self.extra_widget)
        vbox.pack_start(self.build_buttons())
        alignment = Alignment(xscale=1.0, yscale=1.0)
        alignment.set_padding(12, 12, 17, 17)
        alignment.add(vbox)
        return alignment

    def build_window(self):
        self.content_widget = self.build_content()
        width, height = self.content_widget.get_size_request()
        width = max(width, 400)
        window = NSPanel.alloc()
        window.initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(400, 400, width, height),
                NSTitledWindowMask, NSBackingStoreBuffered, NO)
        view = FlippedView.alloc().initWithFrame_(NSMakeRect(0, 0, width,
            height))
        window.setContentView_(view)
        window.setTitle_(self.title)
        self.content_widget.place(view.frame(), view)
        if self.buttons:
            self.buttons[0].make_default()
        return window

    def run(self):
        self.window = self.build_window()
        response = NSApp().runModalForWindow_(self.window)
        if response < 0:
            return -1
        return response

    def destroy(self):
        for attr in ('window', 'buttons'):
            if hasattr(self, attr):
                delattr(self, attr)

    def set_extra_widget(self, widget):
        self.extra_widget = widget

    def get_extra_widget(self):
        return self.extra_widget

class FileSaveDialog:
    def __init__(self, title):
        self._title = title
        self._panel = NSSavePanel.savePanel()
        self._filename = None

    def set_filename(self, s):
        self._filename = s

    def get_filename(self):
        return self._filename

    def run(self):
        response = self._panel.runModalForDirectory_file_(NSHomeDirectory(), self._filename)
        if response == NSFileHandlingPanelOKButton:            
            self._filename = self._panel.filename()
            return 0
        self._filename = ""

    def close(self):
        self.nswindow.close()

    def destroy(self):
        self._panel = None

class FileOpenDialog:
    def __init__(self, title):
        self._title = title
        self._panel = NSOpenPanel.openPanel()
        self._filename = None
        self._directory = None
        self._types = None

    def set_directory(self, d):
        self._directory = d

    def set_filename(self, s):
        self._filename = s

    def add_filters(self, filters):
        self._types = []
        for _, t in filters:
            self._types += t

    def get_filename(self):
        return self._filename

    def run(self):
        response = self._panel.runModalForDirectory_file_types_(self._directory, self._filename, self._types)
        if response == NSFileHandlingPanelOKButton:            
            self._filename = self._panel.filenames()[0]
            return 0
        self._filename = ""

    def close(self):
        self.nswindow.close()

    def destroy(self):
        self._panel = None

class DirectorySelectDialog:
    def __init__(self, title):
        self._title = title
        self._panel = NSOpenPanel.openPanel()
        self._panel.setCanChooseFiles_(NO)
        self._panel.setCanChooseDirectories_(YES)
        self._directory = None

    def set_directory(self, d):
        self._directory = d

    def get_directory(self):
        return self._directory

    def run(self):
        response = self._panel.runModalForDirectory_file_types_(self._directory, None, None)
        if response == NSFileHandlingPanelOKButton:
            self._directory = self._panel.filenames()[0]
            return 0
        self._directory = ""

    def destroy(self):
        self._panel = None

class AboutDialog:
    def run(self):
        NSApplication.sharedApplication().orderFrontStandardAboutPanel_(nil)
    def destroy(self):
        pass

class AlertDialog:
    def __init__(self, title, message, alert_type):
        print alert_type
        self._nsalert = NSAlert.alloc().init();
        self._nsalert.setMessageText_(title)
        self._nsalert.setInformativeText_(message)
        self._nsalert.setAlertStyle_(alert_type)
    def add_button(self, text):
        self._nsalert.addButtonWithTitle_(text)
    def run(self):
        self._nsalert.runModal()
    def destroy(self):
        self._nsalert = nil
