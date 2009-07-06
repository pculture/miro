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

"""miro.plat.frontends.widgets.window -- Top-level Window class.  """

from AppKit import *
from Foundation import *
from objc import YES, NO, nil
from PyObjCTools import AppHelper

from miro import menubar
from miro import signals
from miro.frontends.widgets import widgetconst
from miro.plat.frontends.widgets import osxmenus
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.helpers import NotificationForwarder
from miro.plat.frontends.widgets.base import Widget, Container, FlippedView
from miro.plat.frontends.widgets.layout import VBox, HBox, Alignment
from miro.plat.frontends.widgets.control import Button
from miro.plat.frontends.widgets.simple import Label
from miro.plat.frontends.widgets.rect import Rect, NSRectWrapper
from miro.plat.utils import filenameToUnicode

# Tracks all windows that haven't been destroyed.  This makes sure there
# object stay alive as long as the window is alive.
alive_windows = set()

class MiroWindow(NSWindow):
    def handle_keyDown(self, event):
        key = event.characters()
        if len(key) != 1 or not key.isalpha():
            key = osxmenus.REVERSE_KEYS_MAP.get(key)
        mods = osxmenus.translate_event_modifiers(event)
        responder = self.firstResponder()
        while responder is not None:
            wrapper = wrappermap.wrapper(responder)
            if isinstance(wrapper, Widget) or isinstance(wrapper, Window):
                if wrapper.emit('key-press', key, mods):
                    return True # signal handler returned True, stop processing
            responder = responder.nextResponder()

    def sendEvent_(self, event):
        if event.type() == NSKeyDown:
            # We grab the KeyDown event here instead of with a keyDown handler
            # because some keys (notable Cmd-> and Cmd-< aren't caught by that
            # method.
            if self.handle_keyDown(event):
                return
        return NSWindow.sendEvent_(self, event)

class Window(signals.SignalEmitter):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPIfor a description of the API for this class."""
    def __init__(self, title, rect):
        signals.SignalEmitter.__init__(self)
        self.create_signal('active-change')
        self.create_signal('will-close')
        self.create_signal('did-move')
        self.create_signal('key-press')
        self.create_signal('show')
        self.create_signal('hide')
        self.nswindow = MiroWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect.nsrect,
                self.get_style_mask(),
                NSBackingStoreBuffered,
                NO)
        self.nswindow.setTitle_(title)
        self.nswindow.setMinSize_(NSSize(800, 600))
        self.nswindow.setReleasedWhenClosed_(NO)
        self.content_view = FlippedView.alloc().initWithFrame_(rect.nsrect)
        self.content_view.setAutoresizesSubviews_(NO)
        self.nswindow.setContentView_(self.content_view)
        self.content_widget = None
        self.view_notifications = NotificationForwarder.create(self.content_view)
        self.view_notifications.connect(self.on_frame_change, 'NSViewFrameDidChangeNotification')
        self.window_notifications = NotificationForwarder.create(self.nswindow)
        self.window_notifications.connect(self.on_activate, 'NSWindowDidBecomeMainNotification')
        self.window_notifications.connect(self.on_deactivate, 'NSWindowDidResignMainNotification')
        self.window_notifications.connect(self.on_did_move, 'NSWindowDidMoveNotification')
        self.window_notifications.connect(self.on_will_close, 'NSWindowWillCloseNotification')
        wrappermap.add(self.nswindow, self)
        alive_windows.add(self)

    def get_style_mask(self):
        return NSTitledWindowMask | NSClosableWindowMask | NSMiniaturizableWindowMask | NSResizableWindowMask

    def set_title(self, title):
        self.nswindow.setTitle_(title)

    def on_frame_change(self, notification):
        self.place_child()

    def on_activate(self, notification):
        self.emit('active-change')

    def on_deactivate(self, notification):
        self.emit('active-change')

    def on_did_move(self, notification):
        self.emit('did-move')

    def on_will_close(self, notification):
        self.emit('will-close')
        self.emit('hide')

    def is_active(self):
        return self.nswindow.isMainWindow()

    def show(self):
        if self not in alive_windows:
            raise ValueError("Window destroyed")
        self.nswindow.makeKeyAndOrderFront_(nil)
        self.nswindow.makeMainWindow()
        self.emit('show')

    def close(self):
        self.nswindow.close()

    def destroy(self):
        self.window_notifications.disconnect()
        self.view_notifications.disconnect()
        self.nswindow.setContentView_(nil)
        wrappermap.remove(self.nswindow)
        alive_windows.discard(self)
        self.nswindow = None

    def place_child(self):
        rect = self.nswindow.contentRectForFrameRect_(self.nswindow.frame())
        self.content_widget.place(NSRect(NSPoint(0, 0), rect.size),
                self.content_view)

    def hookup_content_widget_signals(self):
        self.size_req_handler = self.content_widget.connect('size-request-changed',
                self.on_content_widget_size_request_change)

    def unhook_content_widget_signals(self):
        self.content_widget.disconnect(self.size_req_handler)
        self.size_req_handler = None

    def on_content_widget_size_request_change(self, widget, old_size):
        self.update_size_constraints()

    def set_content_widget(self, widget):
        if self.content_widget:
            self.content_widget.remove_viewport()
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
        
    def get_frame(self):
        frame = self.nswindow.frame()
        frame.size.height -= 22
        return NSRectWrapper(frame)

    def connect_menu_keyboard_shortcuts(self):
        # All OS X windows are connected to the menu shortcuts
        pass

class MainWindow(Window):
    def __init__(self, title, rect):
        Window.__init__(self, title, rect)
        self.nswindow.setReleasedWhenClosed_(NO)
    def close(self):
        self.nswindow.orderOut_(nil)

class DialogBase(object):
    def __init__(self):
        self.sheet_parent = None
    def set_transient_for(self, window):
        self.sheet_parent = window

class Dialog(DialogBase):
    def __init__(self, title, description=None):
        DialogBase.__init__(self)
        self.title = title
        self.description = description
        self.buttons = []
        self.extra_widget = None
        self.window = None
        self.running = False

    def add_button(self, text):
        button = Button(text)
        button.set_size(widgetconst.SIZE_NORMAL)
        button.connect('clicked', self.on_button_clicked, len(self.buttons))
        self.buttons.append(button)

    def on_button_clicked(self, button, code):
        if self.sheet_parent is not None:
            NSApp().endSheet_returnCode_(self.window, code)
        else:
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
        self.running = True
        if self.sheet_parent is None:
            response = NSApp().runModalForWindow_(self.window)
        else:
            delegate = SheetDelegate.alloc().init()
            NSApp().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
                self.window, self.sheet_parent.nswindow, 
                delegate, 'sheetDidEnd:returnCode:contextInfo:', 0)
            response = NSApp().runModalForWindow_(self.window)
            if self.window:
                # self.window won't be around if we call destroy() to cancel
                # the dialog
                self.window.orderOut_(nil)
        self.running = False

        if response < 0:
            return -1
        return response

    def destroy(self):
        if self.running:
            NSApp().stopModalWithCode_(-1)

        self.window.setContentView_(None)
        self.window.close()
        self.window = None
        self.buttons = None
        self.extra_widget = None

    def set_extra_widget(self, widget):
        self.extra_widget = widget

    def get_extra_widget(self):
        return self.extra_widget

class SheetDelegate(NSObject):
    @AppHelper.endSheetMethod
    def sheetDidEnd_returnCode_contextInfo_(self, sheet, return_code, info):
        NSApp().stopModalWithCode_(return_code)

class FileDialogBase(DialogBase):
    def __init__(self):
        DialogBase.__init__(self)
        self._types = None
        self._filename = None
        self._directory = None

    def run(self):
        self._panel.setAllowedFileTypes_(self._types)
        if self.sheet_parent is None:
            response = self._panel.runModalForDirectory_file_(self._directory, self._filename, self._types)
        else:
            delegate = SheetDelegate.alloc().init()
            self._panel.beginSheetForDirectory_file_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
                self._directory, self._filename,
                self.sheet_parent.nswindow, delegate, 'sheetDidEnd:returnCode:contextInfo:', 0)
            response = NSApp().runModalForWindow_(self._panel)
            self._panel.orderOut_(nil)
        return response

class FileSaveDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._title = title
        self._panel = NSSavePanel.savePanel()
        self._filename = None

    def set_filename(self, s):
        self._filename = filenameToUnicode(s)

    def get_filename(self):
        # Use encode('utf-8') instead of unicodeToFilename, because
        # unicodeToFilename has code to make sure nextFilename works, but it's
        # more important here to not change the filename.
        return self._filename.encode('utf-8')

    def run(self):
        response = FileDialogBase.run(self)            
        if response == NSFileHandlingPanelOKButton:            
            self._filename = self._panel.filename()
            return 0
        self._filename = ""

    def destroy(self):
        self._panel = None

class FileOpenDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._title = title
        self._panel = NSOpenPanel.openPanel()
        self._filenames = None

    def set_select_multiple(self, value):
        if value:
            self._panel.setAllowsMultipleSelection_(YES)
        else:
            self._panel.setAllowsMultipleSelection_(NO)

    def set_directory(self, d):
        self._directory = filenameToUnicode(d)

    def set_filename(self, s):
        self._filename = filenameToUnicode(s)

    def add_filters(self, filters):
        self._types = []
        for _, t in filters:
            self._types += t

    def get_filename(self):
        return self.get_filenames()[0]

    def get_filenames(self):
        # Use encode('utf-8') instead of unicodeToFilename, because
        # unicodeToFilename has code to make sure nextFilename works, but it's
        # more important here to not change the filename.
        return [f.encode('utf-8') for f in self._filenames]

    def run(self):
        response = FileDialogBase.run(self)            
        if response == NSFileHandlingPanelOKButton:            
            self._filenames = self._panel.filenames()
            return 0
        self._filename = ''
        self._filenames = None

    def destroy(self):
        self._panel = None

class DirectorySelectDialog(FileDialogBase):
    def __init__(self, title):
        FileDialogBase.__init__(self)
        self._title = title
        self._panel = NSOpenPanel.openPanel()
        self._panel.setCanChooseFiles_(NO)
        self._panel.setCanChooseDirectories_(YES)
        self._directory = None

    def set_directory(self, d):
        self._directory = filenameToUnicode(d)

    def get_directory(self):
        # Use encode('utf-8') instead of unicodeToFilename, because
        # unicodeToFilename has code to make sure nextFilename works, but it's
        # more important here to not change the filename.
        return self._directory.encode('utf-8')

    def run(self):
        response = FileDialogBase.run(self)            
        if response == NSFileHandlingPanelOKButton:
            self._directory = self._panel.filenames()[0]
            return 0
        self._directory = ""

    def destroy(self):
        self._panel = None

class AboutDialog(DialogBase):
    def run(self):
        NSApplication.sharedApplication().orderFrontStandardAboutPanel_(nil)
    def destroy(self):
        pass

class AlertDialog(DialogBase):
    def __init__(self, title, message, alert_type):
        DialogBase.__init__(self)
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

class PreferenceItem (NSToolbarItem):

    def setPanel_(self, panel):
        self.panel = panel

class ToolbarDelegate (NSObject):

    def initWithPanels_identifiers_window_(self, panels, identifiers, window):
        self = super(ToolbarDelegate, self).init()
        self.panels = panels
        self.identifiers = identifiers
        self.window = window
        return self

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return self.identifiers

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return self.identifiers

    def toolbarSelectableItemIdentifiers_(self, toolbar):
        return self.identifiers

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(self, toolbar, itemIdentifier, flag):
        panel = self.panels[itemIdentifier]
        item = PreferenceItem.alloc().initWithItemIdentifier_(itemIdentifier)
        item.setLabel_(panel[1])
        item.setImage_(NSImage.imageNamed_(u"pref_item_%s" % itemIdentifier))
        item.setAction_("switchPreferenceView:")
        item.setTarget_(self)
        item.setPanel_(panel[0])
        return item

    def validateToolbarItem_(self, item):
        return YES

    def switchPreferenceView_(self, sender):
        self.window.do_select_panel(sender.panel, YES)

class PreferencesWindow (Window):
    def __init__(self, title):
        Window.__init__(self, title, Rect(0, 0, 640, 440))
        self.panels = dict()
        self.identifiers = list()
        self.first_show = True
        self.nswindow.setShowsToolbarButton_(NO)
        self.nswindow.setReleasedWhenClosed_(NO)

    def get_style_mask(self):
        return NSTitledWindowMask | NSClosableWindowMask | NSMiniaturizableWindowMask
 
    def append_panel(self, name, panel, title, image_name):
        self.panels[name] = (panel, title)
        self.identifiers.append(name)

    def finish_panels(self):
        self.tbdelegate = ToolbarDelegate.alloc().initWithPanels_identifiers_window_(self.panels, self.identifiers, self)
        toolbar = NSToolbar.alloc().initWithIdentifier_(u"Preferences")
        toolbar.setAllowsUserCustomization_(NO)
        toolbar.setDelegate_(self.tbdelegate)

        self.nswindow.setToolbar_(toolbar)
       
    def select_panel(self, index):
        panel = self.identifiers[index]
        self.nswindow.toolbar().setSelectedItemIdentifier_(panel)
        self.do_select_panel(self.panels[panel][0], NO)

    def do_select_panel(self, panel, animate):
        wframe = self.nswindow.frame()
        vsize = list(panel.get_size_request())
        if vsize[0] < 500:
            vsize[0] = 500
        if vsize[1] < 200:
            vsize[1] = 200

        toolbarHeight = wframe.size.height - self.nswindow.contentView().frame().size.height
        wframe.origin.y += wframe.size.height - vsize[1] - toolbarHeight
        wframe.size = (vsize[0], vsize[1] + toolbarHeight)

        self.set_content_widget(panel)
        self.nswindow.setFrame_display_animate_(wframe, YES, animate)

    def show(self):
        if self.first_show:
            self.nswindow.center()
            self.first_show = False
        Window.show(self)
