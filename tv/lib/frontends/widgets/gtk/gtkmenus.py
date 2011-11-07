# Miro - an RSS based video player application
# Copyright (C) 2011
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

"""gtkmenus.py -- Manage menu layout."""

import gtk

from miro import app
from miro import prefs
from miro.frontends.widgets.gtk import base
from miro.frontends.widgets.gtk import keymap
from miro.frontends.widgets.gtk import wrappermap

def _setup_accel(widget, name, shortcut=None):
    """Setup accelerators for a menu item.

    This method sets an accel path for the widget and optionally connects a
    shortcut to that accel path.
    """
    # The GTK docs say that we should set the path using this form:
    # <Window-Name>/Menu/Submenu/MenuItem
    # ...but this is hard to do because we don't yet know what window/menu
    # this menu item is going to be added to.  gtk.Action and gtk.ActionGroup
    # don't follow the above suggestion, so we don't need to either.
    path = "<MiroActions>/MenuBar/%s" % name
    widget.set_accel_path(path)
    if shortcut is not None:
        accel_string = keymap.get_accel_string(shortcut)
        key, mods = gtk.accelerator_parse(accel_string)
        if gtk.accel_map_lookup_entry(path) is None:
            gtk.accel_map_add_entry(path, key, mods)
        else:
            gtk.accel_map_change_entry(path, key, mods, True)

# map menu names to GTK stock ids.
_STOCK_IDS = {
    "SaveItem": gtk.STOCK_SAVE,
    "CopyItemURL": gtk.STOCK_COPY,
    "RemoveItems": gtk.STOCK_REMOVE,
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
try:
    _STOCK_IDS['Fullscreen'] = gtk.STOCK_FULLSCREEN
except AttributeError:
    # fullscreen not available on all GTK versions
    pass

class MenuItemBase(base.Widget):
    """Base class for MenuItem and Separator."""

    def show(self):
        """Show this menu item."""
        self._widget.show()

    def hide(self):
        """Hide and disable this menu item."""
        self._widget.hide()

    def remove_from_parent(self):
        """Remove this menu item from it's parent Menu."""
        parent_menu = self._widget.get_parent()
        if parent_menu is None:
            return
        parent_menu_item = parent_menu.get_attach_widget()
        if parent_menu_item is None:
            return
        parent_menu_item.remove(self._widget)

    def _set_accel_group(self, accel_group):
        # menu items don't care about the accel group, their parent Menu
        # handles it for them
        pass

class MenuItem(MenuItemBase):
    """Single item in the menu that can be clicked

    :param label: The label it has (must be internationalized)
    :param name: String identifier for this item
    :param shortcuts: None, the Shortcut, or tuple of Shortcut objects.

    Signals:
    - activate: menu item was clicked

    Example:

    >>> MenuItem(_("Preferences"), "EditPreferences")
    >>> MenuItem(_("Cu_t"), "ClipboardCut", Shortcut("x", MOD))
    >>> MenuItem(_("_Update Podcasts and Library"), "UpdatePodcasts",
    ...          (Shortcut("r", MOD), Shortcut(F5)))
    >>> MenuItem(_("_Play"), "PlayPauseItem",
    ...          play=_("_Play"), pause=_("_Pause"))
    """

    def __init__(self, label, name, shortcuts=None, groups=None,
            **state_labels):
        MenuItemBase.__init__(self)
        self.name = name
        self.set_widget(self.make_widget(label))
        self.wrapped_widget_connect('activate', self._on_activate)
        self._widget.show()
        self.create_signal('activate')
        # FIXME:  Our contstructor arguments are all messed up.  We ignore
        # group and state_labels and only support 1 shortcut.
        if shortcuts is None:
            shortcuts = ()
        if not isinstance(shortcuts, tuple):
            shortcuts = (shortcuts,)
        self.shortcuts = shortcuts
        self._setup_shortcut()

    def _on_activate(self, menu_item):
        self.emit('activate')
        gtk_menubar = self._find_menubar()
        if gtk_menubar is not None:
            try:
                menubar = wrappermap.wrapper(gtk_menubar)
            except KeyError:
                app.widgetapp.handle_soft_failure('menubar activate',
                    'no wrapper for gtk.MenuBar', with_exception=True)
            else:
                menubar.emit('activate', self.name)

    def _find_menubar(self):
        """Find the MenuBar that this menu item is attached to."""
        menu_item = self._widget
        while True:
            parent_menu = menu_item.get_parent()
            if isinstance(parent_menu, gtk.MenuBar):
                return parent_menu
            elif parent_menu is None:
                return None
            menu_item = parent_menu.get_attach_widget()
            if menu_item is None:
                return None

    def make_widget(self, label):
        """Create the menu item to use for this widget.

        Subclasses will probably want to override this.
        """
        if self.name in _STOCK_IDS:
            return gtk.ImageMenuItem(stock_id=_STOCK_IDS[self.name])
        else:
            return gtk.MenuItem(label)

    def _setup_shortcut(self):
        """Setup our shortcuts.  """
        if len(self.shortcuts) == 0:
            _setup_accel(self._widget, self.name, None)
        else:
            _setup_accel(self._widget, self.name, self.shortcuts[0])
        # FIXME: we only handle a single shortcut, but we input multiple ones
        # in the constructor.

    def set_label(self, new_label):
        self._widget.set_label(new_label)

class RadioMenuItem(MenuItem):
    """MenuItem that toggles on/off and is grouped with other RadioMenuItems.
    """

    def __init__(self, label, name, radio_group, shortcuts=None,
            groups=None, **state_labels):
        MenuItem.__init__(self, label, name, shortcuts, groups,
                **state_labels)
        # FIXME: we don't do anything with radio_group.  We need to
        # re-implement this functionality

    def make_widget(self, label):
        return gtk.RadioMenuItem(label)

    @staticmethod
    def set_group(*items):
        """Set a list of RadioMenuItems to belong to the a group

        When any of the RadioMenuItems is turned on, the others will be
        turned off.
        """
        if len(items) < 2:
            raise ValueError("Need at least 2 items to make a radio group")
        for menu_item in items:
            group = menu_item._widget.get_group()
            if not (group is None or len(group) == 1):
                raise ValueError("%s is already in a group")
        first = items[0]
        for other in items[1:]:
            other._widget.set_group(first._widget)

    def remove_from_group(self):
        """Remove this RadioMenuItem from its current group."""
        self.set_group(None)

class CheckMenuItem(MenuItem):
    """MenuItem that toggles on/off"""

    def __init__(self, label, name, check_group, shortcuts=None,
            groups=None, **state_labels):
        MenuItem.__init__(self, label, name, shortcuts, groups,
                **state_labels)
        # FIXME: we don't do anything with check_group.  We need to
        # re-implement this functionality

    def make_widget(self, label):
        return gtk.CheckMenuItem(label)

class Separator(MenuItemBase):
    """Separator item for menus"""

    def __init__(self):
        MenuItemBase.__init__(self)
        self.set_widget(gtk.SeparatorMenuItem())
        self._widget.show()
        # Set name to be None just so that it has a similar API to other menu
        # items.
        self.name = None

class MenuShell(base.Widget):
    """Common code shared between Menu and MenuBar.

    Subclasses must define a _menu attribute that's a gtk.MenuShell subclass.
    """

    def __init__(self):
        base.Widget.__init__(self)
        self._accel_group = None
        self.children = []

    def append(self, menu_item):
        """Add a menu item to the end of this menu."""
        self.children.append(menu_item)
        menu_item._set_accel_group(self._accel_group)
        self._menu.append(menu_item._widget)

    def insert(self, index, menu_item):
        """Insert a menu item in the middle of this menu."""
        self.children.insert(index, menu_item)
        menu_item._set_accel_group(self._accel_group)
        self._menu.insert(menu_item._widget, index)

    def remove(self, menu_item):
        """Remove a child menu item.

        :raises ValueError: menu_item is not a child of this menu
        """
        self.children.remove(menu_item)
        self._menu.remove(menu_item._widget)
        menu_item._set_accel_group(None)

    def index(self, name):
        """Get the position of a menu item in this list.

        :param name: name of the menu
        :returns: index of the menu item, or -1 if not found.
        """
        for i, menu_item in enumerate(self.children):
            if menu_item.name == name:
                return i
        return -1

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
            if isinstance(menu_item, MenuShell):
                submenu_find = menu_item._find(name)
                if submenu_find is not None:
                    return submenu_find
        return None

class Menu(MenuShell):
    """A Menu holds a list of MenuItems and Menus.

    Example:
    >>> Menu(_("P_layback"), "Playback", [
    ...      MenuItem(_("_Foo"), "Foo"),
    ...      MenuItem(_("_Bar"), "Bar")
    ...      ])
    >>> Menu("", "toplevel", [
    ...     Menu(_("_File"), "File", [ ... ])
    ...     ])
    """

    def __init__(self, label, name, child_items, groups=None):
        MenuShell.__init__(self)
        self.set_widget(gtk.MenuItem(label))
        self._widget.show()
        self.name = name
        # set up _menu for the MenuShell code
        self._menu = gtk.Menu()
        _setup_accel(self._menu, self.name)
        self._widget.set_submenu(self._menu)
        for item in child_items:
            self.append(item)
        # FIXME we ignore groups.  They're just there as a temporary measure
        # to keep the constructure signature the same.

    def _set_accel_group(self, accel_group):
        """Set the accel group for this widget.

        Accel groups get created by the MenuBar.  Whenever a menu or menu item
        is added to that menu bar, the parent calls _set_accel_group() to give
        the accel group to the child.
        """
        if accel_group == self._accel_group:
            return
        self._menu.set_accel_group(accel_group)
        self._accel_group = accel_group
        for child in self.children:
            child._set_accel_group(accel_group)

class MenuBar(MenuShell):
    """Displays a list of Menu items.

    Signals:

    - activate(menu_bar, name): a menu item was activated
    """

    def __init__(self):
        """Create a new MenuBar

        :param name: string id to use for our action group
        """
        MenuShell.__init__(self)
        self.create_signal('activate')
        self.set_widget(gtk.MenuBar())
        self._widget.show()
        self._accel_group = gtk.AccelGroup()
        # set up _menu for the MenuShell code
        self._menu = self._widget

    def get_accel_group(self):
        return self._accel_group

class MainWindowMenuBar(MenuBar):
    """MenuBar for the main window.

    This gets installed into app.widgetapp.menubar on GTK.
    """
    def add_initial_menus(self, menus):
        """Add the initial set of menus.

        We modify the menu structure slightly for GTK.
        """
        for menu in menus:
            self.append(menu)
        self._modify_initial_menus()

    def _modify_initial_menus(self):
        """Update the portable root menu with GTK-specific stuff."""
        # on linux, we don't have a CheckVersion option because
        # we update with the package system.
        this_platform = app.config.get(prefs.APP_PLATFORM)
        if this_platform == 'linux':
            self.find("CheckVersion").remove_from_parent()
