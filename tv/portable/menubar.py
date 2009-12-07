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

# Defines menu, accelerator keys, and shortcuts.

from miro.gtcache import gettext as _
from miro import config
from miro import prefs
from string import Template

(CTRL, ALT, SHIFT, CMD, RIGHT_ARROW, LEFT_ARROW, UP_ARROW,
 DOWN_ARROW, SPACE, ENTER, DELETE, BKSPACE, ESCAPE,
 F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12) = range(25)
platform = config.get(prefs.APP_PLATFORM)

MOD = CTRL

def set_mod(modifier):
    """Allows the platform to change the MOD key.  OSX and
    Windows have different mod keys.

    Example:
    >>> set_mod(CTRL)
    >>> set_mod(CMD)
    """
    global MOD
    MOD = modifier

class Shortcut:
    """Defines a shortcut key combination used to trigger this
    menu item.

    The first argument is the shortcut key.  Other arguments are
    modifiers.

    Examples:

    >>> Shortcut("x", MOD)
    >>> Shortcut(BKSPACE, MOD)

    This is wrong:

    >>> Shortcut(MOD, "x")
    """
    def __init__(self, shortcut, *modifiers):
        self.shortcut = shortcut
        self.modifiers = modifiers

class MenuItem:
    """A menu item is a single item in the menu that can be clicked
    on that has an action.

    :param label: The label it has (must be internationalized)
    :param action: The action string for this menu item.
    :param shortcuts: None, the Shortcut, or tuple of Shortcut objects.
    :param enabled: Whether (True) or not (False) this menu item is
                    enabled by default.
    :param state_labels: If this menu item has states, then this is
                         the name/value pairs for all states.

    Example:

    >>> MenuItem(_("_Options"), "EditPreferences")
    >>> MenuItem(_("Cu_t"), "ClipboardCut", Shortcut("x", MOD))
    >>> MenuItem(_("_Update Feed"), "UpdateFeeds",
    ...          (Shortcut("r", MOD), Shortcut(F5)), enabled=False)
    >>> MenuItem(_("_Play"), "PlayPauseVideo", enabled=False,
    ...          play=_("_Play"), pause=_("_Pause"))
    """
    def __init__(self, label, action, shortcuts=None, enabled=True,
                 **state_labels):
        self.label = label
        self.action = action
        if shortcuts == None:
            shortcuts = ()
        if not isinstance(shortcuts, tuple):
            shortcuts = (shortcuts,)
        self.shortcuts = shortcuts
        self.enabled = enabled
        self.state_labels = state_labels

class Separator:
    """This denotes a separator in the menu.
    """
    def __init__(self):
        self.action = None

class Menu:
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
    def __init__(self, label, action, menuitems):
        self.label = label
        self.action = action
        self.menuitems = list(menuitems)

    def __iter__(self):
        for mem in self.menuitems:
            yield mem
            if isinstance(mem, Menu):
                for mem2 in mem:
                    yield mem2

    def has(self, action):
        for mem in self.menuitems:
            if mem.action == action:
                return True
        return False

    def get(self, action, default=None):
        for mem in self.menuitems:
            if mem.action == action:
                return mem
            if isinstance(mem, Menu):
                try:
                    return mem.get(action)
                except ValueError:
                    pass

        if default is not None:
            return default

        raise ValueError("%s is not in this menu." % action)

    def index(self, action):
        for i, mem in enumerate(self.menuitems):
            if mem.action == action:
                return i
        raise ValueError("%s not in this menu." % action)

    def remove(self, action):
        # FIXME - this won't remove separators--probably should do
        # a pass to remove a separator for two separators in a row
        # or a separator at the beginning or end of the list
        self.menuitems = [m for m in self.menuitems if m.action != action]

    def count(self):
        return len(menuitems)

    def insert(self, index, menuitem):
        self.menuitems.insert(menuitem, index)

    def append(self, menuitem):
        self.menuitems.append(menuitem)

EditItems = [
    MenuItem(_("Cu_t"), "ClipboardCut", Shortcut("x", MOD)),
    MenuItem(_("_Copy"), "ClipboardCopy", Shortcut("c", MOD)),
    MenuItem(_("_Paste"), "ClipboardPaste", Shortcut("v", MOD)),
    MenuItem(_("Select _All"), "ClipboardSelectAll", Shortcut("a", MOD)),
]

def get_menu():
    mbar = Menu("", "TopLevel", [
            Menu(_("_Video"), "VideoMenu", [
                    MenuItem(_("_Open"), "Open", Shortcut("o", MOD)),
                    MenuItem(_("_Download Item"), "NewDownload"),
                    MenuItem(_("Check _Version"), "CheckVersion"),
                    Separator(),
                    MenuItem(_("_Remove Item"), "RemoveItems",
                             Shortcut(BKSPACE, MOD), enabled=False,
                             plural=_("_Remove Items")),
                    MenuItem(_("Re_name Item"), "RenameItem", enabled=False),
                    MenuItem(_("Save Item _As"), "SaveItem",
                             Shortcut("s", MOD), enabled=False,
                             plural=_("Save Items _As")),
                    MenuItem(_("Copy Item _URL"), "CopyItemURL",
                             Shortcut("u", MOD), enabled=False),
                    Separator(),
                    MenuItem(_("_Options"), "EditPreferences"),
                    MenuItem(_("_Quit"), "Quit", Shortcut("q", MOD)),
                    ]),

            Menu(_("_Sidebar"), "SidebarMenu", [
                    MenuItem(_("Add _Feed"), "NewFeed", Shortcut("n", MOD)),
                    MenuItem(_("Add Site"), "NewGuide"),
                    MenuItem(_("New Searc_h Feed"), "NewSearchFeed"),
                    MenuItem(_("New _Folder"), "NewFeedFolder",
                             Shortcut("n", MOD, SHIFT)),
                    Separator(),
                    MenuItem(_("Re_name"), "RenameFeed", enabled=False),
                    MenuItem(_("_Remove"), "RemoveFeeds",
                             Shortcut(BKSPACE, MOD), enabled=False,
                             folder=_("_Remove Folder"),
                             ),
                    MenuItem(_("_Update Feed"), "UpdateFeeds",
                             (Shortcut("r", MOD), Shortcut(F5)), enabled=False,
                             plural=_("_Update Feeds")),
                    MenuItem(_("Update _All Feeds"), "UpdateAllFeeds",
                             Shortcut("r", MOD, SHIFT)),
                    Separator(),
                    MenuItem(_("_Import Feeds (OPML)"), "ImportFeeds"),
                    MenuItem(_("E_xport Feeds (OPML)"), "ExportFeeds"),
                    Separator(),
                    MenuItem(_("_Share with a Friend"), "ShareFeed",
                             enabled=False),
                    MenuItem(_("Copy URL"), "CopyFeedURL", enabled=False),
                    ]),

            Menu(_("_Playlists"), "PlaylistsMenu", [
                    MenuItem(_("New _Playlist"), "NewPlaylist",
                             Shortcut("p", MOD)),
                    MenuItem(_("New Playlist Fol_der"), "NewPlaylistFolder",
                             Shortcut("p", MOD, SHIFT)),
                    Separator(),
                    MenuItem(_("Re_name Playlist"),"RenamePlaylist",
                             enabled=False),
                    MenuItem(_("_Remove Playlist"),"RemovePlaylists",
                             Shortcut(BKSPACE, MOD), enabled=False,
                             plural=_("_Remove Playlists"),
                             folders=_("_Remove Playlist Folders"),
                             folder=_("_Remove Playlist Folder"),
                             ),
                    ]),

            Menu(_("P_layback"), "PlaybackMenu", [
                    MenuItem(_("_Play"), "PlayPauseVideo", enabled=False,
                             play=_("_Play"),
                             pause=_("_Pause")),
                    MenuItem(_("_Stop"), "StopVideo", Shortcut("d", MOD),
                             enabled=False),
                    Separator(),
                    MenuItem(_("_Next Video"), "NextVideo",
                             Shortcut(RIGHT_ARROW, MOD), enabled=False),
                    MenuItem(_("_Previous Video"), "PreviousVideo",
                             Shortcut(LEFT_ARROW, MOD), enabled=False),
                    Separator(),
                    MenuItem(_("Skip _Forward"), "FastForward", enabled=False),
                    MenuItem(_("Skip _Back"), "Rewind", enabled=False),
                    Separator(),
                    MenuItem(_("Volume _Up"), "UpVolume",
                             Shortcut(UP_ARROW, MOD), enabled=False),
                    MenuItem(_("Volume _Down"), "DownVolume",
                             Shortcut(DOWN_ARROW,MOD), enabled=False),
                    Separator(),
                    MenuItem(_("_Fullscreen"), "Fullscreen",
                             (Shortcut("f", MOD), Shortcut(ENTER, ALT)),
                             enabled=False),
                    MenuItem(_("_Toggle Detached/Attached"), "ToggleDetach",
                             Shortcut("t", MOD), enabled=False),
                    Menu(_("S_ubtitles"), "SubtitlesMenu", 
                         [
                            MenuItem(_("None Available"), "NoneAvailable", enabled=False)
                            ]),
                    ]),

            Menu(_("_Help"), "HelpMenu", [
                    MenuItem(_("_About %(name)s",
                               {'name': config.get(prefs.SHORT_APP_NAME)}),
                             "About", ())
                    ])
            ])

    help_menu = mbar.get("HelpMenu")
    if config.get(prefs.DONATE_URL):
        help_menu.append(MenuItem(_("_Donate"), "Donate"))

    if config.get(prefs.HELP_URL):
        help_menu.append(MenuItem(_("_Help"), "Help", Shortcut(F1)))
    help_menu.append(Separator())
    help_menu.append(MenuItem(_("Diagnostics"), "Diagnostics"))
    if config.get(prefs.BUG_REPORT_URL):
        help_menu.append(MenuItem(_("Report a _Bug"), "ReportBug"))
    if config.get(prefs.TRANSLATE_URL):
        help_menu.append(MenuItem(_("_Translate"), "Translate"))
    if config.get(prefs.PLANET_URL):
        help_menu.append(MenuItem(_("_Planet Miro"), "Planet"))
    return mbar
