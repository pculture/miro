# Defines menu, accelerator keys, and shortcuts
# THIS IS STILL A WORK IN PROGRESS. THE FORMAT IS NOT FINAL
from gtcache import gettext as _
import config
import prefs
from string import Template

CTRL, ALT, SHIFT, CMD, RIGHT_ARROW, LEFT_ARROW, UP_ARROW, DOWN_ARROW, SPACE, ENTER, DELETE, BKSPACE, F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12 = range(24)
_ = lambda x : x
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
    def __init__(self, label, action, shortcuts, enabled = True, **stateLabels):
        self.label = label
        self.action = action
        self.shortcuts = shortcuts
        self.enabled = enabled
        self.stateLabels = stateLabels

class Separator:
    pass

class Menu:
    def __init__(self, label, action, *menuitems):
        self.label = label
        self.action = action
        self.labels = {action:label}
        self.stateLabels = {}
        self.shortcuts = {}
        self.menuitems = menuitems
        for item in menuitems:
            if not isinstance(item, Separator):
                self.labels[item.action] = item.label
                self.shortcuts[item.action] = item.shortcuts
                if item.stateLabels:
                    self.stateLabels[item.action] = item.stateLabels
            
    def getLabel(self, action, state=None, variables={}):
        if state is None:
           try:
               print self.labels[action]
               print Template(self.labels[action])
               print variables
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
        for menu in menus:
            self.labels.update(menu.labels)
            self.stateLabels.update(menu.stateLabels)
            self.shortcuts.update(menu.shortcuts)

    def __iter__(self):
        for menu in self.menus:
            yield menu
    def getLabel(self, action, state=None, variables={}):
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

VideoItems = [
    MenuItem(_("_Open"), "Open", (Key("o", MOD),)),
    #MenuItem(_("Op_en Recent"), "OpenRecent", ()),
    MenuItem(_("Check _Version"), "CheckVersion", ()),
    Separator(),
    MenuItem(_("_Remove Video"), "RemoveVideos", (Key(DELETE),Key(BKSPACE, MOD)), False,
             plural=_("_Remove Videos")),
    MenuItem(_("Re_name Video"), "RenameVideo", (), False),
    MenuItem(_("Save Video _As..."), "SaveVideo", (Key("s",MOD),), False,
             plural=_("Save Videos _As...")),
    MenuItem(_("Copy Video _URL"), "CopyVideoURL", (Key("u", MOD),), False),
    Separator(),
    MenuItem(_("_Options"), "EditPreferences", ()),
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
    MenuItem(_("New Channel _Guide..."), "NewGuide", ()),
    Separator(),
    MenuItem(_("Re_name Channel..."), "RenameChannel", (), False),
    MenuItem(_("_Remove Channel..."), "RemoveChannels", (Key(DELETE),Key(BKSPACE, MOD)), False,
             plural=_("_Remove Channels..."),
             folders=_("_Remove Channel Folders..."),
             folder=_("_Remove Channel Folder..."),
             ),
    MenuItem(_("_Update Channel..."), "UpdateChannels", (Key("r",MOD),Key(F5)), False,
             plural=_("_Update Channels...")),
    MenuItem(_("Update _All Channels"), "UpdateAllChannels", (Key("r",MOD,SHIFT),)),
    Separator(),
    MenuItem(_("_Send this channel to a friend"), "MailChannel", (), False),
    MenuItem(_("Copy Channel _Link"), "CopyChannelURL", (), False),
]
PlaylistItems = [
    MenuItem(_("New _Playlist"), "NewPlaylist", (Key("p",MOD),)),
    MenuItem(_("New Playlist Fol_der"), "NewPlaylistFolder",(Key("p",MOD,SHIFT),)),
    Separator(),
    MenuItem(_("Re_name Playlist"),"RenamePlaylist",(), False),
    MenuItem(_("_Remove Playlist"),"RemovePlaylists",(), False,
             plural=_("_Remove Playlists"),
             folders=_("_Remove Playlist Folders"),
             folder=_("_Remove Playlist Folder"),
             ),
]

PlaybackItems = [
    MenuItem(_("_Play"), "PlayPauseVideo", (Key(SPACE),), False),
    MenuItem(_("_Stop"), "StopVideo", (Key("d",MOD),), False),
    Separator(),
    MenuItem(_("_Next Video"), "NextVideo", (Key(RIGHT_ARROW, MOD),), False),
    MenuItem(_("_Previous Video"), "PreviousVideo", (Key(LEFT_ARROW, MOD),), False),
    Separator(),
    MenuItem(_("Skip _Forward"), "FastForward", (Key(RIGHT_ARROW),), False),
    MenuItem(_("Skip _Back"), "Rewind", (Key(LEFT_ARROW),), False),
    Separator(),
    MenuItem(_("Volume _Up"), "UpVolume", (Key(UP_ARROW, MOD),), False),
    MenuItem(_("Volume _Down"), "DownVolume", (Key(DOWN_ARROW,MOD),), False),
    Separator(),
    MenuItem(_("_Fullscreen"), "Fullscreen", (Key("f", MOD),), False),
]

HelpItems = [
    MenuItem(_("_About"), "About", ()),
    MenuItem(_("_Donate"), "Donate", ()),
    MenuItem(_("_Help"), "Help", (Key(F1),)),
]

menubar = \
        MenuBar(Menu(_("_Video"), "Video", *VideoItems),
                Menu(_("_Channels"), "Channels", *ChannelItems),
                Menu(_("_Playlists"), "Playlists", *PlaylistItems),
                Menu(_("P_layback"), "Playback", *PlaybackItems),
                Menu(_("_Help"), "Help", *HelpItems),
                )

traymenu = Menu("Miro","Miro",
                MenuItem(_("Options"), "EditPreferences", ()),
                MenuItem(_("Play Unwatched ($numUnwatched)"), "PlayUnwatched", ()),
                MenuItem(_("Pause All Downloads ($numPaused)"), "PauseDownloads", ()),
                MenuItem(_("Restore All Downloads ($numDownloading)"), "RestoreDownloads", ()),
                Separator(),
                MenuItem(_("Minimize"),"RestoreWindow", (),
                         restore=_("Restore")),
                MenuItem(_("Close"),"Quit", ()),
                )                
