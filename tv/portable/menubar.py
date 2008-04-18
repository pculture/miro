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

# Defines menu, accelerator keys, and shortcuts
# THIS IS STILL A WORK IN PROGRESS. THE FORMAT IS NOT FINAL
from miro.gtcache import gettext as _
from miro import config
from miro import prefs
from string import Template
from miro import app

CTRL, ALT, SHIFT, CMD, RIGHT_ARROW, LEFT_ARROW, UP_ARROW, DOWN_ARROW, SPACE, ENTER, DELETE, BKSPACE, F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12 = range(24)
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
    def __init__(self, label, action, shortcuts, impl = None, enabled = True, **stateLabels):
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
        self.menuitems = menuitems
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
        except:
            return ()

class MenuBar:
    def __init__(self, *menus):
        self.menus = menus
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

VideoItems = [
    MenuItem(_("_Open"), "Open", (Key("o", MOD),)),
    MenuItem(_("_Download Video"), "NewDownload", ()),
    #MenuItem(_("Op_en Recent"), "OpenRecent", ()),
    MenuItem(_("Check _Version"), "CheckVersion", ()),
    Separator(),
    MenuItem(_("_Remove Video"), "RemoveVideos", (Key(DELETE),Key(BKSPACE, MOD)), enabled=False,
             plural=_("_Remove Videos")),
    MenuItem(_("Re_name Video"), "RenameVideo", (), enabled=False),
    MenuItem(_("Save Video _As..."), "SaveVideo", (Key("s",MOD),), enabled=False,
             plural=_("Save Videos _As...")),
    MenuItem(_("Copy Video _URL"), "CopyVideoURL", (Key("u", MOD),), enabled=False),
    Separator(),
    MenuItem(_("_Options..."), "EditPreferences", ()),
    MenuItem(_("_Quit"),"Quit", (Key("q",MOD),)),
]

if platform == "gtk-x11":
    del VideoItems[2] # No "Check version" on GTK platforms. We use
                      # the package management system instead

EditItems = [
    MenuItem(_("Cu_t"), "ClipboardCut", (Key("x",MOD),)),
    MenuItem(_("_Copy"), "ClipboardCopy", (Key("c",MOD),)),
    MenuItem(_("_Paste"), "ClipboardPaste", (Key("v",MOD),)),
    MenuItem(_("Select _All"), "ClipboardSelectAll", (Key("a",MOD),)),
    MenuItem(_("_Delete"), "ClipboardSelectAll", (Key(DELETE),Key(BKSPACE,MOD))),
]

ChannelItems = [
    MenuItem(_("Add _Channel"), "NewChannel", (Key("n",MOD),)),
    MenuItem(_("New Searc_h Channel..."), "NewSearchChannel", ()),
    MenuItem(_("New _Folder..."), "NewChannelFolder", (Key("n",MOD,SHIFT),)),
    MenuItem(_("Add Channel _Guide..."), "NewGuide", ()),
    Separator(),
    MenuItem(_("Re_name Channel..."), "RenameChannel", (), enabled=False),
    MenuItem(_("_Remove Channel..."), "RemoveChannels", (Key(DELETE),Key(BKSPACE, MOD)), enabled=False,
             plural=_("_Remove Channels..."),
             folders=_("_Remove Channel Folders..."),
             folder=_("_Remove Channel Folder..."),
             ),
    MenuItem(_("_Update Channel..."), "UpdateChannels", (Key("r",MOD),Key(F5)), enabled=False,
             plural=_("_Update Channels...")),
    MenuItem(_("Update _All Channels"), "UpdateAllChannels", (Key("r",MOD,SHIFT),)),
    Separator(),
    MenuItem(_("_Import Channels (OPML)..."), "ImportChannels", ()),
    MenuItem(_("E_xport Channels (OPML)..."), "ExportChannels", ()),
    Separator(),
    MenuItem(_("_Send this channel to a friend"), "MailChannel", (), enabled=False),
    MenuItem(_("Copy Channel _Link"), "CopyChannelURL", (), enabled=False),
]
PlaylistItems = [
    MenuItem(_("New _Playlist"), "NewPlaylist", (Key("p",MOD),)),
    MenuItem(_("New Playlist Fol_der"), "NewPlaylistFolder",(Key("p",MOD,SHIFT),)),
    Separator(),
    MenuItem(_("Re_name Playlist"),"RenamePlaylist",(), enabled=False),
    MenuItem(_("_Remove Playlist"),"RemovePlaylists", (Key(DELETE),Key(BKSPACE, MOD)), enabled=False,
             plural=_("_Remove Playlists"),
             folders=_("_Remove Playlist Folders"),
             folder=_("_Remove Playlist Folder"),
             ),
]

if platform == "windows-xul":
    fullscreen_shortcuts = (Key("f", MOD), Key(ENTER, ALT))
else:
    fullscreen_shortcuts = (Key("f", MOD), )

PlaybackItems = [
    MenuItem(_("_Play"), "PlayPauseVideo", (Key(SPACE, MOD), ), enabled=False,
             play=_("_Play"),
             pause=_("_Pause")),
    MenuItem(_("_Stop"), "StopVideo", (Key("d",MOD),), enabled=False),
    Separator(),
    MenuItem(_("_Next Video"), "NextVideo", (Key(RIGHT_ARROW, MOD),), enabled=False),
    MenuItem(_("_Previous Video"), "PreviousVideo", (Key(LEFT_ARROW, MOD),), enabled=False),
    Separator(),
    MenuItem(_("Skip _Forward"), "FastForward", (Key(RIGHT_ARROW),), enabled=False),
    MenuItem(_("Skip _Back"), "Rewind", (Key(LEFT_ARROW),), enabled=False),
    Separator(),
    MenuItem(_("Volume _Up"), "UpVolume", (Key(UP_ARROW, MOD),), enabled=False),
    MenuItem(_("Volume _Down"), "DownVolume", (Key(DOWN_ARROW,MOD),), enabled=False),
    Separator(),
    MenuItem(_("_Fullscreen"), "Fullscreen", fullscreen_shortcuts, enabled=False),
]

HelpItems = [
    MenuItem(_("_About"), "About", ()),
    MenuItem(_("_Donate"), "Donate", ()),
    MenuItem(_("_Help"), "Help", (Key(F1),)),
    Separator(),
    MenuItem(_("Report a _Bug"), "ReportBug", ()),
    MenuItem(_("_Translate"), "Translate", ()),
    MenuItem(_("_Planet"), "Planet", ()),
]

if platform == "gtk-x11":
    main_title = _("_Video")
else:
    main_title = _("_File")

menubar = \
        MenuBar(Menu(main_title, "Video", *VideoItems),
                Menu(_("_Channels"), "Channels", *ChannelItems),
                Menu(_("_Playlists"), "Playlists", *PlaylistItems),
                Menu(_("P_layback"), "Playback", *PlaybackItems),
                Menu(_("_Help"), "Help", *HelpItems),
                )

traymenu = Menu("Miro","Miro",
                MenuItem(_("Play Unwatched ($numUnwatched)"), "PlayUnwatched", ()),
                MenuItem(_("Pause All Downloads ($numDownloading)"), "PauseDownloads", ()),
                MenuItem(_("Resume All Downloads ($numPaused)"), "ResumeDownloads", ()),
                Separator(),
                MenuItem(_("Options..."), "EditPreferences", ()),
                Separator(),
                MenuItem(_("Hide Window"),"RestoreWindow", (),
                         restore=_("Show Window")),
                MenuItem(_("Quit"),"Quit", ()),
                )                
