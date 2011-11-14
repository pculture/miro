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

"""menus.py -- Menu handling code."""

import logging
import struct

from objc import nil, NO, YES
import AppKit
from AppKit import *
from Foundation import *

from miro import app
from miro import prefs
from miro import signals
from miro.gtcache import gettext as _
from miro.frontends.widgets import keyboard
# import these names directly into our namespace for easy access
from miro.frontends.widgets.keyboard import Shortcut, MOD
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.plat.appstore import appstore_edition

MODIFIERS_MAP = {
    keyboard.MOD:   NSCommandKeyMask,
    keyboard.CMD:   NSCommandKeyMask,
    keyboard.SHIFT: NSShiftKeyMask,
    keyboard.CTRL:  NSControlKeyMask,
    keyboard.ALT:   NSAlternateKeyMask
}

if isinstance(NSBackspaceCharacter, int):
    backspace = NSBackspaceCharacter
else:
    backspace = ord(NSBackspaceCharacter)
    
KEYS_MAP = {
    keyboard.SPACE: " ",
    keyboard.ENTER: "\r",
    keyboard.BKSPACE: struct.pack("H", backspace),
    keyboard.DELETE: NSDeleteFunctionKey,
    keyboard.RIGHT_ARROW: NSRightArrowFunctionKey,
    keyboard.LEFT_ARROW: NSLeftArrowFunctionKey,
    keyboard.UP_ARROW: NSUpArrowFunctionKey,
    keyboard.DOWN_ARROW: NSDownArrowFunctionKey,
    '.': '.',
    ',': ','
}
# add function keys
for i in range(1, 13):
    portable_key = getattr(keyboard, "F%s" % i)
    osx_key = getattr(AppKit, "NSF%sFunctionKey" % i)
    KEYS_MAP[portable_key] = osx_key

REVERSE_MODIFIERS_MAP = dict((i[1], i[0]) for i in MODIFIERS_MAP.items())
REVERSE_KEYS_MAP = dict((i[1], i[0]) for i in KEYS_MAP.items() 
        if i[0] != keyboard.BKSPACE)
REVERSE_KEYS_MAP[u'\x7f'] = keyboard.BKSPACE
REVERSE_KEYS_MAP[u'\x1b'] = keyboard.ESCAPE

def make_modifier_mask(shortcut):
    mask = 0
    for modifier in shortcut.modifiers:
        mask |= MODIFIERS_MAP[modifier]
    return mask

VIEW_ITEM_MAP = {}

def _remove_mnemonic(label):
    """Remove the underscore used by GTK for mnemonics.
    
    We totally ignore them on OSX, since they are now deprecated.
    """
    return label.replace("_", "")

def handle_menu_activate(ns_menu_item):
    """Handle a menu item being activated.

    This gets called by our application delegate.
    """

    menu_item = ns_menu_item.representedObject()
    menu_item.emit("activate")
    menubar = menu_item._find_menubar()
    if menubar is not None:
        menubar.emit("activate", menu_item.name)

class MenuItemBase(signals.SignalEmitter):
    """Base class for MenuItem and Separator"""
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.name = None
        self.parent = None

    def show(self):
        self._menu_item.setHidden_(False)

    def hide(self):
        self._menu_item.setHidden_(True)

    def enable(self):
        self._menu_item.setEnabled_(True)

    def disable(self):
        self._menu_item.setEnabled_(False)

    def remove_from_parent(self):
        """Remove this menu item from it's parent Menu."""
        if self.parent is not None:
            self.parent.remove(self)

class MenuItem(MenuItemBase):
    """See the GTK version of this method for the current docstring."""

    # map Miro action names to standard OSX actions.
    _STD_ACTION_MAP = {
        "HideMiro":         (NSApp(), 'hide:'),
        "HideOthers":       (NSApp(), 'hideOtherApplications:'),
        "ShowAll":          (NSApp(), 'unhideAllApplications:'),
        "Cut":              (nil,     'cut:'),
        "Copy":             (nil,     'copy:'),
        "Paste":            (nil,     'paste:'),
        "Delete":           (nil,     'delete:'),
        "SelectAll":        (nil,     'selectAll:'),
        "Zoom":             (nil,     'performZoom:'),
        "Minimize":         (nil,     'performMiniaturize:'),
        "BringAllToFront":  (nil,     'arrangeInFront:'),
        "CloseWindow":      (nil,     'performClose:'),
    }

    def __init__(self, label, name, shortcut=None, groups=None,
            **state_labels):
        MenuItemBase.__init__(self)
        self.name = name
        self._menu_item = self._make_menu_item(label)
        self.create_signal('activate')
        self._setup_shortcut(shortcut)

    def _make_menu_item(self, label):
        menu_item = NSMenuItem.alloc().init()
        menu_item.setTitle_(_remove_mnemonic(label))
        # we set ourselves as the represented object for the menu item so we
        # can easily translate one to the other
        menu_item.setRepresentedObject_(self)
        if menu_item.action in self._STD_ACTION_MAP:
            menu_item.setTarget_(self._STD_ACTION_MAP[menu_item.action][0])
            menu_item.setAction_(self._STD_ACTION_MAP[menu_item.action][1])
        else:
            menu_item.setTarget_(NSApp().delegate())
            menu_item.setAction_('handleMenuActivate:')
        return menu_item

    def _setup_shortcut(self, shortcut):
        if shortcut is None:
            key = ''
            modifier_mask = 0
        elif isinstance(shortcut.shortcut, str):
            key = shortcut.shortcut
            modifier_mask = make_modifier_mask(shortcut)
        elif shortcut.shortcut in KEYS_MAP:
            key = KEYS_MAP[shortcut.shortcut]
            modifier_mask = make_modifier_mask(shortcut)
        else:
            logging.warn("Don't know how to handle shortcut: %s", shortcut)
            return
        self._menu_item.setKeyEquivalent_(key)
        self._menu_item.setKeyEquivalentModifierMask_(modifier_mask)

    def _change_shortcut(self, shortcut):
        self._setup_shortcut(shortcut)

    def set_label(self, new_label):
        self._menu_item.setTitle_(new_label)

    def _find_menubar(self):
        """Remove this menu item from it's parent Menu."""
        menu_item = self
        while menu_item.parent is not None:
            menu_item = menu_item.parent
        if isinstance(menu_item, MenuBar):
            return menu_item
        else:
            return None

class RadioMenuItem(MenuItem):
    """See the GTK version of this method for the current docstring."""
    def __init__(self, label, name, radio_group, shortcut=None,
            groups=None, **state_labels):
        MenuItem.__init__(self, label, name, shortcut, groups,
                **state_labels)
        self.others_in_group = set()
        # FIXME: we don't do anything with radio_group.  We need to
        # re-implement this functionality

    @staticmethod
    def set_group(*items):
        if len(items) < 2:
            raise ValueError("Need at least 2 items to make a radio group")
        for radio_menu_item in items:
            if radio_menu_item.others_in_group:
                raise ValueError("%s is already in a group")
        # re-implement this functionality
        whole_group = set(items)
        for radio_menu_item in items:
            others = whole_group - set([radio_menu_item])
            radio_menu_item.others_in_group = others

    def remove_from_group(self):
        """Remove this RadioMenuItem from its current group."""
        for other in self.others_in_group:
            other.others_in_group.remove(self)
        self.others_in_group = set()

    def do_activate(self):
        for other in self.others_in_group:
            other._menu_item.setState_(NSOffState)

class CheckMenuItem(MenuItem):
    """See the GTK version of this method for the current docstring."""
    def __init__(self, label, name, check_group, shortcut=None,
            groups=None, **state_labels):
        MenuItem.__init__(self, label, name, shortcut, groups,
                **state_labels)
        # FIXME: we don't do anything with check_group.  We need to
        # re-implement this functionality

    def do_activate(self):
        if self._menu_item.state() == NSOffState:
            self._menu_item.setState_(NSOnState)
        else:
            self._menu_item.setState_(NSOffState)

class Separator(MenuItemBase):
    """See the GTK version of this method for the current docstring."""
    def __init__(self):
        MenuItemBase.__init__(self)
        self._menu_item = NSMenuItem.separatorItem()

class MenuShell(signals.SignalEmitter):
    def __init__(self, nsmenu):
        signals.SignalEmitter.__init__(self)
        self._menu = nsmenu
        self.children = []
        self.parent = None

    def append(self, menu_item):
        """Add a menu item to the end of this menu."""
        self.children.append(menu_item)
        self._menu.addItem_(menu_item._menu_item)
        menu_item.parent = self

    def insert(self, index, menu_item):
        """Insert a menu item in the middle of this menu."""
        self.children.insert(index, menu_item)
        self._menu.insertItem_atIndex_(menu_item._menu_item, index)
        menu_item.parent = self

    def index(self, name):
        """Find the position of a child menu item."""
        for i, menu_item in enumerate(self.children):
            if menu_item.name == name:
                return i
        return -1

    def remove(self, menu_item):
        """Remove a child menu item.

        :raises ValueError: menu_item is not a child of this menu
        """
        self.children.remove(menu_item)
        self._menu.removeItem_(menu_item._menu_item)
        menu_item.parent = None

    def get_children(self):
        """Get the child menu items in order."""
        return self.children

    def find(self, name):
        """Search for a menu or menu item

        This method recursively searches the entire menu structure for a Menu
        or MenuItem object with a given name.

        :raises KeyError: name not found
        """
        found = self._find(name)
        if found is None:
            raise KeyError(name)
        else:
            return found

    def _find(self, name):
        """Low-level helper-method for find().

        :returns: found menu item or None.
        """
        for menu_item in self.get_children():
            if menu_item.name == name:
                return menu_item
            if isinstance(menu_item, Menu):
                submenu_find = menu_item._find(name)
                if submenu_find is not None:
                    return submenu_find
        return None

class Menu(MenuShell):
    """See the GTK version of this method for the current docstring."""
    def __init__(self, label, name, child_items=None, groups=None):
        MenuShell.__init__(self, NSMenu.alloc().init())
        self._menu.setTitle_(_remove_mnemonic(label))
        self.name = name
        if child_items is not None:
            for item in child_items:
                self.append(item)
        self._menu_item = NSMenuItem.alloc().init()
        self._menu_item.setTitle_(_remove_mnemonic(label))
        self._menu_item.setSubmenu_(self._menu)
        # Hack to set the services menu
        if name == "ServicesMenu":
            NSApp().setServicesMenu_(self._menu_item)
        # FIXME we ignore groups.  They're just there as a temporary measure
        # to keep the constructure signature the same.

class AppMenu(MenuShell):
    """Wrapper for the application menu (AKA the Miro menu)

    We need to special case this because OSX automatically creates the menu
    item.
    """
    def __init__(self):
        MenuShell.__init__(self, NSApp().mainMenu().itemAtIndex_(0).submenu())
        self.name = "Miro"

class MenuBar(MenuShell):
    """See the GTK version of this method for the current docstring."""
    def __init__(self):
        MenuShell.__init__(self, NSApp().mainMenu())
        self.create_signal('activate')
        self._add_app_menu()

    def _add_app_menu(self):
        """Add the app menu to this menu bar.

        We need to special case this because OSX automatically adds the
        NSMenuItem for the app menu, we just need to set up our wrappers.
        """
        self._app_menu = AppMenu()
        self.children.append(self._app_menu)
        self._app_menu.parent = self

    def add_initial_menus(self, menus):
        for menu in menus:
            self.append(menu)
        self._modify_initial_menus()

    def _extract_menu_item(self, name):
        """Helper method for changing the portable menu structure."""
        menu_item = self.find(name)
        menu_item.remove_from_parent()
        return menu_item

    def _modify_initial_menus(self):
        short_appname = app.config.get(prefs.SHORT_APP_NAME)
        # Application menu
        miroMenuItems = [
            self._extract_menu_item("About"),
            Separator(),
            self._extract_menu_item("Donate")
        ]

        if not appstore_edition():
            miroMenuItems += [
                self._extract_menu_item("CheckVersion")
            ]

        miroMenuItems += [
            Separator(),
            self._extract_menu_item("EditPreferences"),
            Separator(),
            Menu(_("Services"), "ServicesMenu", []),
            Separator(),
            MenuItem(_("Hide %(appname)s", {"appname": short_appname}),
                     "HideMiro", Shortcut("h", MOD)),
            MenuItem(_("Hide Others"), "HideOthers",
                     Shortcut("h", MOD, keyboard.ALT)),
            MenuItem(_("Show All"), "ShowAll"),
            Separator(),
            self._extract_menu_item("Quit")
        ]
        for item in miroMenuItems:
            self._app_menu.append(item)
        self._app_menu.find("EditPreferences").set_label(_("Preferences..."))
        self._app_menu.find("EditPreferences")._change_shortcut(
            Shortcut(",", MOD))
        self._app_menu.find("Quit").set_label(_("Quit %(appname)s",
                                       {"appname": short_appname}))

        # File menu
        closeWinItem = MenuItem(_("Close Window"), "CloseWindow",
                                Shortcut("w", MOD))
        self.find("FileMenu").append(closeWinItem)

        # Edit menu
        editMenuItems = [
            MenuItem(_("Cut"), "Cut", Shortcut("x", MOD)),
            MenuItem(_("Copy"), "Copy", Shortcut("c", MOD)),
            MenuItem(_("Paste"), "Paste", Shortcut("v", MOD)),
            MenuItem(_("Delete"), "Delete"),
            Separator(),
            MenuItem(_("Select All"), "SelectAll", Shortcut("a", MOD))
        ]
        editMenu = Menu(_("Edit"), "Edit", editMenuItems)
        self.insert(1, editMenu)

        # Playback menu
        presentMenuItems = [
            MenuItem(_("Present Half Size"), "PresentHalfSize", 
                     Shortcut("0", MOD),
                     groups=["PlayingVideo", "PlayableVideosSelected"]),
            MenuItem(_("Present Actual Size"), "PresentActualSize", 
                     Shortcut("1", MOD),
                     groups=["PlayingVideo", "PlayableVideosSelected"]),
            MenuItem(_("Present Double Size"), "PresentDoubleSize", 
                     Shortcut("2", MOD),
                     groups=["PlayingVideo", "PlayableVideosSelected"]),
        ]
        presentMenu = Menu(_("Present Video"), "Present", presentMenuItems)
        playback_menu = self.find("PlaybackMenu")
        playback_menu.insert(playback_menu.index('AudioTrackMenu'),
                             presentMenu)

        # Window menu
        windowMenuItems = [
            MenuItem(_("Zoom"), "Zoom"),
            MenuItem(_("Minimize"), "Minimize", Shortcut("m", MOD)),
            Separator(),
            MenuItem(_("Main Window"), "ShowMain",
                     Shortcut("M", MOD, keyboard.SHIFT)),
            Separator(),
            MenuItem(_("Bring All to Front"), "BringAllToFront"),
        ]
        windowMenu = Menu(_("Window"), "Window", windowMenuItems)
        self.insert(self.index("HelpMenu"), windowMenu)

        # Help Menu
        helpItem = self.find("Help")
        helpItem.set_label(_("%(appname)s Help", {"appname": short_appname}))
        helpItem._change_shortcut(Shortcut("?", MOD))

    def do_activate(self, name):
        # We handle a couple OSX-specific actions here
        if name == "PresentActualSize":
            NSApp().delegate().present_movie('natural-size')
        elif name == "PresentDoubleSize":
            NSApp().delegate().present_movie('double-size')
        elif name == "PresentHalfSize":
            NSApp().delegate().present_movie('half-size')
        elif name == "ShowMain":
            app.widgetapp.window.nswindow.makeKeyAndOrderFront_(sender)

def update_view_menu_state():
    # Error checking for display != None done below in try/except block
    display = app.display_manager.get_current_display()
    main_menu = NSApp().mainMenu()
    # XXX: should be using the tag to prevent interface and locale breakages
    view_menu = main_menu.itemAtIndex_(6)
    try:
        key = (display.type, display.id)
    except AttributeError:
        view_menu.setHidden_(True)
        return
    view_menu.setHidden_(False)
    enabled = app.widget_state.get_columns_enabled(
            display.type,
            display.id,
            display.controller.selected_view)

    for column in WidgetStateStore.get_toggleable_columns():
        menu_item = VIEW_ITEM_MAP[column]
        hidden = not column in WidgetStateStore.get_columns_available(
            display.type,
            display.id,
            display.controller.selected_view)
        menu_item.setHidden_(hidden)
        if hidden:
            continue
        if column in enabled:
            state = NSOnState
        else:
            state = NSOffState
        menu_item.setState_(state)

class ContextMenuHandler(NSObject):
    def initWithCallback_(self, callback):
        self = super(ContextMenuHandler, self).init()
        self.callback = callback
        return self

    def handleMenuItem_(self, sender):
        self.callback()

class MiroContextMenu(NSMenu):
    # Works exactly like NSMenu, except it keeps a reference to the menu
    # handler objects.
    def init(self):
        self = super(MiroContextMenu, self).init()
        self.handlers = set()
        return self

    def addItem_(self, item):
        if isinstance(item.target(), ContextMenuHandler):
            self.handlers.add(item.target())
        return NSMenu.addItem_(self, item)

def make_context_menu(menu_items):
    nsmenu = MiroContextMenu.alloc().init()
    for item in menu_items:
        if item is None:
            nsitem = NSMenuItem.separatorItem()
        else:
            label, callback = item
            nsitem = NSMenuItem.alloc().init()
            if isinstance(label, tuple) and len(label) == 2:
                label, icon_path = label
                image = NSImage.alloc().initWithContentsOfFile_(icon_path)
                nsitem.setImage_(image)
            if callback is None:
                font_size = NSFont.systemFontSize()
                font = NSFont.fontWithName_size_("Lucida Sans Italic", font_size)
                if font is None:
                    font = NSFont.systemFontOfSize_(font_size)
                attributes = {NSFontAttributeName: font}
                attributed_label = NSAttributedString.alloc().initWithString_attributes_(label, attributes)
                nsitem.setAttributedTitle_(attributed_label)
            else:
                nsitem.setTitle_(label)
                if isinstance(callback, list):
                    submenu = make_context_menu(callback)
                    nsmenu.setSubmenu_forItem_(submenu, nsitem)
                else:
                    handler = ContextMenuHandler.alloc().initWithCallback_(callback)
                    nsitem.setTarget_(handler)
                    nsitem.setAction_('handleMenuItem:')
        nsmenu.addItem_(nsitem)
    return nsmenu

def translate_event_modifiers(event):
    mods = set()
    flags = event.modifierFlags()
    if flags & NSCommandKeyMask:
        mods.add(keyboard.CMD)
    if flags & NSControlKeyMask:
        mods.add(keyboard.CTRL)
    if flags & NSAlternateKeyMask:
        mods.add(keyboard.ALT)
    if flags & NSShiftKeyMask:
        mods.add(keyboard.SHIFT)
    return mods

class SubtitleChangesHandler(NSObject):
    def selectSubtitleTrack_(self, sender):
        app.playback_manager.player.enable_subtitle_track(sender.tag())
        on_playback_change(app.playback_manager)
    def openSubtitleFile_(self, sender):
        app.playback_manager.open_subtitle_file()
    def disableSubtitles_(self, sender):
        app.playback_manager.player.disable_subtitles()
        on_playback_change(app.playback_manager)

class AudioTrackChangesHandler(NSObject):
    def selectAudioTrack_(self, sender):
        app.playback_manager.player.set_audio_track(sender.tag())
        on_playback_change(app.playback_manager)

subtitles_menu_handler = SubtitleChangesHandler.alloc().init()
audio_track_menu_handler = AudioTrackChangesHandler.alloc().init()

def on_menu_change(menu_manager):
    main_menu = NSApp().mainMenu()
    # XXX Flaky: we should be using the tag to prevent interface and language
    # XXX breakages.
    play_pause_menu_item = main_menu.itemAtIndex_(5).submenu().itemAtIndex_(0)
    play_pause = _menu_structure.get("PlayPauseItem").state_labels[app.menu_manager.play_pause_state]
    play_pause_menu_item.setTitleWithMnemonic_(play_pause.replace("_", "&"))

    update_view_menu_state()
    # Calling update() here does not result in
    # AppController.validateUserInterfaceItem_() running. Why?? -Kaz
    main_menu.update()

def on_playback_change(playback_manager):
    main_menu = NSApp().mainMenu()
    # XXX Flaky: we should be using the tag to prevent interface and language
    # XXX breakages.
    subtitles_menu_root = main_menu.itemAtIndex_(5).submenu().itemAtIndex_(18)
    subtitles_menu = NSMenu.alloc().init()
    subtitles_menu.setAutoenablesItems_(NO)
    subtitles_tracks = None

    audio_track_menu_root = main_menu.itemAtIndex_(5).submenu().itemAtIndex_(17)
    audio_track_menu = NSMenu.alloc().init()
    audio_track_menu.setAutoenablesItems_(NO)
    audio_tracks = None
    if app.playback_manager.is_playing and not app.playback_manager.is_playing_audio:
        subtitles_tracks = app.playback_manager.player.get_subtitle_tracks()
        audio_tracks = app.playback_manager.player.get_audio_tracks()
    populate_audio_track_menu(audio_track_menu, audio_tracks)
    populate_subtitles_menu(subtitles_menu, subtitles_tracks)
    # Keep the original None available unless we found valid tracks.
    audio_track_menu_root.setSubmenu_(audio_track_menu)
    subtitles_menu_root.setSubmenu_(subtitles_menu)

def populate_audio_track_menu(nsmenu, tracks):
    if tracks is not None and len(tracks) > 0:
        for track in tracks:
            item = NSMenuItem.alloc().init()
            item.setTag_(track[0])
            item.setTitle_(track[1])
            item.setEnabled_(YES)
            item.setTarget_(audio_track_menu_handler)
            item.setAction_('selectAudioTrack:')
            if track[2]:
                item.setState_(NSOnState)
            else:
                item.setState_(NSOffState)
            nsmenu.addItem_(item)
    else:
        item = NSMenuItem.alloc().init()
        item.setTitle_(_("None Available"))
        item.setEnabled_(NO)
        nsmenu.addItem_(item)

def populate_subtitles_menu(nsmenu, tracks):
    if tracks is not None and len(tracks) > 0:
        has_enabled_subtitle_track = False
        for track in tracks:
            item = NSMenuItem.alloc().init()
            item.setTag_(track[0])
            item.setTitle_(track[1])
            item.setEnabled_(YES)
            item.setTarget_(subtitles_menu_handler)
            item.setAction_('selectSubtitleTrack:')
            if track[2]:
                item.setState_(NSOnState)
                has_enabled_subtitle_track = True
            else:
                item.setState_(NSOffState)
            nsmenu.addItem_(item)

        nsmenu.addItem_(NSMenuItem.separatorItem())
    
        disable_item = NSMenuItem.alloc().init()
        disable_item.setTitle_(_("Disable Subtitles"))
        disable_item.setEnabled_(YES)
        disable_item.setTarget_(subtitles_menu_handler)
        disable_item.setAction_('disableSubtitles:')
        if has_enabled_subtitle_track:
            disable_item.setState_(NSOffState)
        else:
            disable_item.setState_(NSOnState)
        nsmenu.addItem_(disable_item)
    else:
        item = NSMenuItem.alloc().init()
        item.setTitle_(_("None Available"))
        item.setEnabled_(NO)
        nsmenu.addItem_(item)

    nsmenu.addItem_(NSMenuItem.separatorItem())

    load_item = NSMenuItem.alloc().init()
    load_item.setTitle_(_("Select a Subtitles file..."))
    enabled = ('PlayingLocalVideo' in app.menu_manager.enabled_groups and
               app.playback_manager.is_playing and
               not app.playback_manager.is_playing_audio)
    load_item.setEnabled_(enabled)
    load_item.setTarget_(subtitles_menu_handler)
    load_item.setAction_('openSubtitleFile:')
    nsmenu.addItem_(load_item)
