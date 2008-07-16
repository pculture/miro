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

"""menus.py -- Menu handling code."""

import logging

from AppKit import *
from Foundation import *

from miro import app
from miro.menubar import menubar, Menu, MenuItem, Separator, Key, MOD, SHIFT, CTRL, ALT
from miro.gtcache import gettext as _
from miro.frontends.widgets import menus

class MenuHandler(NSObject):
    def initWithAction_(self, action):
        self = NSObject.init(self)
        self.action = action
        return self

    def validateUserInterfaceItem_(self, menuitem):
        group_name = menus.get_action_group_name(self.action)
        return group_name in app.menu_manager.enabled_groups

    def handleMenuItem_(self, sender):
        handler = menus.lookup_handler(self.action)
        if handler is not None:
            handler()
        else:
            logging.warn("No handler for %s" % self.action)
# Keep a reference to each MenuHandler we create
all_handlers = set()

MODIFIERS_MAP = {
    MOD:   NSCommandKeyMask,
    SHIFT: NSShiftKeyMask,
    CTRL:  NSControlKeyMask,
    ALT:   NSAlternateKeyMask
}

def make_modifier_mask(shortcut):
    mask = 0
    for modifier in shortcut.modifiers:
        mask |= MODIFIERS_MAP[modifier]
    return mask

def make_menu_item(menu_item):
    nsmenuitem = NSMenuItem.alloc().init()
    nsmenuitem.setTitleWithMnemonic_(menu_item.label.replace("_", "&"))
    if isinstance(menu_item, MenuItem):
        if len(menu_item.shortcuts) > 0:
            shortcut = menu_item.shortcuts[0]
            if isinstance(shortcut.key, str):
                nsmenuitem.setKeyEquivalent_(shortcut.key)
                nsmenuitem.setKeyEquivalentModifierMask_(make_modifier_mask(shortcut))
        handler = MenuHandler.alloc().initWithAction_(menu_item.action)
        nsmenuitem.setTarget_(handler)
        nsmenuitem.setAction_('handleMenuItem:')
        all_handlers.add(handler)
    return nsmenuitem

def populate_single_menu(nsmenu, miro_menu):
    for miro_item in miro_menu.menuitems:
        if isinstance(miro_item, Separator):
            item = NSMenuItem.separatorItem()
        else:
            item = make_menu_item(miro_item)
        nsmenu.addItem_(item)

def populate_menu():
    # Application menu
    miroMenuItems = [
        menubar.extractMenuItem("Help", "About"),
        Separator(),
        menubar.extractMenuItem("Help", "Donate"),
        menubar.extractMenuItem("Video", "CheckVersion"),
        Separator(),
        menubar.extractMenuItem("Video", "EditPreferences"),
        Separator(),
        MenuItem(_("Services"), "ServicesMenu", ()),
        Separator(),
        MenuItem(_("Hide Miro"), "HideMiro", (Key("h", MOD),)),
        MenuItem(_("Hide Others"), "HideOthers", (Key("h", MOD, ALT),)),
        MenuItem(_("Show All"), "ShowAll", ()),
        Separator(),
        menubar.extractMenuItem("Video", "Quit")
    ]
    miroMenu = Menu("Miro", "Miro", *miroMenuItems)
    miroMenu.findItem("EditPreferences").label = _("Preferences...")
    miroMenu.findItem("EditPreferences").shortcuts = (Key(",", MOD),)
    miroMenu.findItem("Quit").label = _("Quit Miro")

    # File menu
    closeWinItem = MenuItem(_("Close Window"), "NewChannel", (Key("w", MOD),))
    menubar.findMenu("Video").menuitems.append(closeWinItem)

    # Edit menu
    editMenuItems = [
        MenuItem(_("Cut"), "Cut", (Key("x", MOD),)),
        MenuItem(_("Copy"), "Copy", (Key("c", MOD),)),
        MenuItem(_("Paste"), "Paste", (Key("v", MOD),)),
        MenuItem(_("Delete"), "Delete", ()),
        Separator(),
        MenuItem(_("Select All"), "SelectAll", (Key("a", MOD),))
    ]
    editMenu = Menu(_("Edit"), "Edit", *editMenuItems)
    menubar.menus.insert(1, editMenu)

    # Window menu
    windowMenuItems = [
        MenuItem(_("Zoom"), "Zoom", ()),
        MenuItem(_("Minimize"), "Minimize", (Key("m", MOD),)),
        Separator(),
        MenuItem(_("Main Window"), "ShowMain", (Key("0", MOD),)),
        Separator(),
        MenuItem(_("Bring All to Front"), "BringAllToFront", ()),
    ]
    windowMenu = Menu(_("Window"), "Window", *windowMenuItems)
    menubar.menus.insert(5, windowMenu)

    # Help Menu
    menubar.findMenu("Help").findItem("Help").label = _("Miro Help")

    # Now populate the main menu bar
    main_menu = NSApp().mainMenu()
    appMenu = main_menu.itemAtIndex_(0).submenu()
    populate_single_menu(appMenu, miroMenu)

    for menu in menubar.menus:
        nsmenu = NSMenu.alloc().init()
        nsmenu.setTitle_(menu.label.replace("_", ""))
        populate_single_menu(nsmenu, menu)
        nsmenuitem = make_menu_item(menu)
        nsmenuitem.setSubmenu_(nsmenu)
        main_menu.addItem_(nsmenuitem)


class ContextMenuHandler(NSObject):
    def initWithCallback_(self, callback):
        self = NSObject.init(self)
        self.callback = callback
        return self

    def handleMenuItem_(self, sender):
        self.callback()

class MiroContextMenu(NSMenu):
    # Works exactly like NSMenu, except it keeps a reference to the menu
    # handler objects.
    def init(self):
        self = NSMenu.init(self)
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
            nsitem.setTitle_(label)
            if callback:
                handler = ContextMenuHandler.alloc().initWithCallback_(callback)
                nsitem.setTarget_(handler)
                nsitem.setAction_('handleMenuItem:')
        nsmenu.addItem_(nsitem)
    return nsmenu
