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

# Defines menu, accelerator keys, and shortcuts
# THIS IS STILL A WORK IN PROGRESS. THE FORMAT IS NOT FINAL
from miro.gtcache import gettext as _
from miro import config
from miro import prefs
from string import Template

CTRL, ALT, SHIFT, CMD, RIGHT_ARROW, LEFT_ARROW, UP_ARROW, DOWN_ARROW, SPACE, ENTER, DELETE, BKSPACE, ESCAPE, F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12 = range(25)
platform = config.get(prefs.APP_PLATFORM)

if platform == "osx":
   MOD = CMD
else:
   MOD = CTRL

class ShortCut:
    def __init__(self, key, *modifiers):
        self.modifiers = modifiers
        self.key = key

Key = ShortCut

class MenuItem:
    def __init__(self, label, action, shortcuts, impl=None, enabled=True, **stateLabels):
        self.label = label
        self.action = action
        self.shortcuts = shortcuts
        self.enabled = enabled
        self.stateLabels = stateLabels
        self.impl = impl

class Separator:
    pass

class Menu:
    def __init__(self, label, action, *menuitems):
        self.label = label
        self.action = action
        self.labels = {action:label}
        self.stateLabels = {}
        self.shortcuts = {}
        self.impls = {}
        self.menuitems = list(menuitems)
        for item in menuitems:
            if not isinstance(item, Separator):
                self.labels[item.action] = item.label
                self.shortcuts[item.action] = item.shortcuts
                self.impls[item.action] = item.impl
                if item.stateLabels:
                    self.stateLabels[item.action] = item.stateLabels
            
    def getLabel(self, action, state=None, variables=None):
        if variables == None:
            variables = {}
        if state is None:
            try:
                return Template(self.labels[action]).substitute(**variables)
            except KeyError:
                return action
        else:
            try:
                return Template(self.stateLabels[action][state]).substitute(**variables)
            except KeyError:
                return self.getLabel(action)

    def getShortcuts(self, action):
        try:
            return self.shortcuts[action]
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return ()
    
    def findItem(self, itemAction):
        for item in self.menuitems:
            if hasattr(item, 'action') and item.action == itemAction:
                return item
        return None
    
    def extractMenuItem(self, itemAction):
        item = self.findItem(itemAction)
        if item is not None:
            self.menuitems.remove(item)
        return item

class MenuBar:
    def __init__(self, *menus):
        self.menus = list(menus)
        self.labels = {}
        self.stateLabels = {}
        self.shortcuts = {}
        self.impls = {}
        for menu in menus:
            self.labels.update(menu.labels)
            self.stateLabels.update(menu.stateLabels)
            self.shortcuts.update(menu.shortcuts)
            self.impls.update(menu.impls)

    def __iter__(self):
        for menu in self.menus:
            yield menu

    def getLabel(self, action, state=None, variables=None):
        if variables == None:
            variables = {}

        if state is None:
            try:
                return Template(self.labels[action]).substitute(**variables)
            except KeyError:
                return action
        else:
            try:
                return Template(self.stateLabels[action][state]).substitute(**variables)
            except KeyError:
                return self.getLabel(action)

    def getShortcuts(self, action):
        try:
            if self.shortcuts[action] is None:
                return ()
            else:
                return self.shortcuts[action]
        except KeyError:
            return ()

    def getShortcut(self, action):
        all = self.getShortcuts(action)
        if len(all) > 0:
            return all[0]
        else:
            return ShortCut(None)

    def getImpl(self, action):
        try:
            return self.impls[action]
        except KeyError:
            return None
    
    def addImpl(self, action, impl):
        self.impls[action] = impl
    
    def findMenu(self, menuAction):
        for menu in self.menus:
            if hasattr(menu, 'action') and menu.action == menuAction:
                return menu
        return None
    
    def extractMenuItem(self, menuAction, itemAction):
        menu = self.findMenu(menuAction)
        if menu is not None:
            return menu.extractMenuItem(itemAction)
        return None

VideoItems = [
    MenuItem(_("_Open"), "Open", (Key("o", MOD),)),
    MenuItem(_("_Download Item"), "NewDownload", ()),
    MenuItem(_("Check _Version"), "CheckVersion", ()),
    Separator(),
    MenuItem(_("_Remove Item"), "RemoveItems", (Key(BKSPACE, MOD),), enabled=False,
             plural=_("_Remove Items")),
    MenuItem(_("Re_name Item"), "RenameItem", (), enabled=False),
    MenuItem(_("Save Item _As"), "SaveItem", (Key("s",MOD),), enabled=False,
             plural=_("Save Items _As")),
    MenuItem(_("Copy Item _URL"), "CopyItemURL", (Key("u", MOD),), enabled=False),
    Separator(),
    MenuItem(_("_Options"), "EditPreferences", ()),
    MenuItem(_("_Quit"), "Quit", (Key("q",MOD),)),
]

# FIXME - move this to platform-specific code
if platform == "gtk-x11":
    del VideoItems[2] # No "Check version" on GTK platforms. We use
                      # the package management system instead

EditItems = [
    MenuItem(_("Cu_t"), "ClipboardCut", (Key("x",MOD),)),
    MenuItem(_("_Copy"), "ClipboardCopy", (Key("c",MOD),)),
    MenuItem(_("_Paste"), "ClipboardPaste", (Key("v",MOD),)),
    MenuItem(_("Select _All"), "ClipboardSelectAll", (Key("a",MOD),)),
]

SidebarItems = [
    MenuItem(_("Add _Feed"), "NewFeed", (Key("n",MOD),)),
    MenuItem(_("Add Site"), "NewGuide", ()),
    MenuItem(_("New Searc_h Feed"), "NewSearchFeed", ()),
    MenuItem(_("New _Folder"), "NewFeedFolder", (Key("n",MOD,SHIFT),)),
    Separator(),
    MenuItem(_("Re_name"), "RenameFeed", (), enabled=False),
    MenuItem(_("_Remove"), "RemoveFeeds", (Key(BKSPACE, MOD),), enabled=False,
             folder=_("_Remove Folder"),
             ),
    MenuItem(_("_Update Feed"), "UpdateFeeds", (Key("r",MOD),Key(F5)), enabled=False,
             plural=_("_Update Feeds")),
    MenuItem(_("Update _All Feeds"), "UpdateAllFeeds", (Key("r",MOD,SHIFT),)),
    Separator(),
    MenuItem(_("_Import Feeds (OPML)"), "ImportFeeds", ()),
    MenuItem(_("E_xport Feeds (OPML)"), "ExportFeeds", ()),
    Separator(),
    MenuItem(_("_Share with a Friend"), "ShareFeed", (), enabled=False),
    MenuItem(_("Copy URL"), "CopyFeedURL", (), enabled=False),
]

PlaylistItems = [
    MenuItem(_("New _Playlist"), "NewPlaylist", (Key("p",MOD),)),
    MenuItem(_("New Playlist Fol_der"), "NewPlaylistFolder",(Key("p",MOD,SHIFT),)),
    Separator(),
    MenuItem(_("Re_name Playlist"),"RenamePlaylist",(), enabled=False),
    MenuItem(_("_Remove Playlist"),"RemovePlaylists", (Key(BKSPACE, MOD),), enabled=False,
             plural=_("_Remove Playlists"),
             folders=_("_Remove Playlist Folders"),
             folder=_("_Remove Playlist Folder"),
             ),
]

# FIXME - move this to platform-specific code
if platform == "windows-xul":
    fullscreen_shortcuts = (Key("f", MOD), Key(ENTER, ALT))
else:
    fullscreen_shortcuts = (Key("f", MOD), )

PlaybackItems = [
    MenuItem(_("_Play"), "PlayPauseVideo", (), enabled=False,
             play=_("_Play"),
             pause=_("_Pause")),
    MenuItem(_("_Stop"), "StopVideo", (Key("d",MOD),), enabled=False),
    Separator(),
    MenuItem(_("_Next Video"), "NextVideo", (Key(RIGHT_ARROW, MOD),), enabled=False),
    MenuItem(_("_Previous Video"), "PreviousVideo", (Key(LEFT_ARROW, MOD),), enabled=False),
    Separator(),
    MenuItem(_("Skip _Forward"), "FastForward", (), enabled=False),
    MenuItem(_("Skip _Back"), "Rewind", (), enabled=False),
    Separator(),
    MenuItem(_("Volume _Up"), "UpVolume", (Key(UP_ARROW, MOD),), enabled=False),
    MenuItem(_("Volume _Down"), "DownVolume", (Key(DOWN_ARROW,MOD),), enabled=False),
    Separator(),
    MenuItem(_("_Fullscreen"), "Fullscreen", fullscreen_shortcuts, enabled=False),
    MenuItem(_("_Toggle Detached/Attached"), "ToggleDetach", (Key("t",MOD),), enabled=False),
]

HelpItems = [
    MenuItem(_("_About %(name)s", {'name': config.get(prefs.SHORT_APP_NAME)}), "About", ())]
if config.get(prefs.DONATE_URL):
   HelpItems.append(MenuItem(_("_Donate"), "Donate", ()))
if config.get(prefs.HELP_URL):
   HelpItems.append(MenuItem(_("_Help"), "Help", (Key(F1),)))
HelpItems.extend([Separator(),
                   MenuItem(_("Diagnostics"), "Diagnostics", ())])
if config.get(prefs.BUG_REPORT_URL):
    HelpItems.append(MenuItem(_("Report a _Bug"), "ReportBug", ()))
if config.get(prefs.TRANSLATE_URL):
    HelpItems.append(MenuItem(_("_Translate"), "Translate", ()))
if config.get(prefs.PLANET_URL):
   HelpItems.append(MenuItem(_("_Planet Miro"), "Planet", ()))

# FIXME - move this to platform-specific code
if platform == "gtk-x11":
    main_title = _("_Video")
else:
    main_title = _("_File")

# FIXME - changes this so that computations are performed as needed
# allowing platforms to change the menu structures before computing
# menubar.
menubar = MenuBar(Menu(main_title, "Video", *VideoItems),
                  Menu(_("_Sidebar"), "Sidebar", *SidebarItems),
                  Menu(_("_Playlists"), "Playlists", *PlaylistItems),
                  Menu(_("P_layback"), "Playback", *PlaybackItems),
                  Menu(_("_Help"), "Help", *HelpItems),
                 )
