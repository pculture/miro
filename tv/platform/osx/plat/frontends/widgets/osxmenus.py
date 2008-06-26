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
from miro import menubar
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

def make_menu_item(menu_item):
    nsmenuitem = NSMenuItem.alloc().init()
    nsmenuitem.setTitleWithMnemonic_(menu_item.label.replace("_", "&"))
    if menu_item.action:
        handler = MenuHandler.alloc().initWithAction_(menu_item.action)
        nsmenuitem.setTarget_(handler)
        nsmenuitem.setAction_('handleMenuItem:')
        all_handlers.add(handler)
    return nsmenuitem

def populate_single_menu(nsmenu, miro_menu):
    for miro_item in miro_menu.menuitems:
        if isinstance(miro_item, menubar.Separator):
            item = NSMenuItem.separatorItem()
        else:
            item = make_menu_item(miro_item)
        nsmenu.addItem_(item)

def populate_menu():
    main_menu = NSApp().mainMenu()

    app_menu =  main_menu.itemAtIndex_(0).submenu()
    populate_single_menu(app_menu, menubar.menubar.menus[0])

    for menu in menubar.menubar.menus[1:]:
        nsmenu = NSMenu.alloc().init()
        nsmenu.setTitle_(menu.label.replace("_", ""))
        populate_single_menu(nsmenu, menu)
        nsmenuitem = make_menu_item(menu)
        nsmenuitem.setSubmenu_(nsmenu)
        main_menu.addItem_(nsmenuitem)
