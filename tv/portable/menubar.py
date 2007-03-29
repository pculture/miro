# Defines menu, accelerator keys, and shortcuts
# THIS IS STILL A WORK IN PROGRESS. THE FORMAT IS NOT FINAL
from gtcache import gettext as _

CTRL, ALT, SHIFT, RIGHT_ARROW, LEFT_ARROW, SPACE, ENTER = range(7)

class ShortCut:
    def __init__(self, key, *modifiers):
        self.modifiers = modifiers
        self.key = key

Key = ShortCut

class MenuItem:
    def __init__(self, label, action, shortcut, enabled = True):
        self.label = label
        self.action = action
        self.shortcut = shortcut
        self.enabled = enabled

class Separator:
    pass

class Menu:
    def __init__(self, label, action, *menuitems):
        self.label = label
        self.action = action
        self.labels = {action:label}
        self.shortcuts = {}
        self.menuitems = menuitems
        for item in menuitems:
            if not isinstance(item, Separator):
                self.labels[item.action] = item.label
                self.shortcuts[item.action] = item.shortcut
            
    def getLabel(self, action):
        return self.labels[action]
    def getShortcut(self, action):
        return self.shortcuts[action]

class MenuBar:
    def __init__(self, *menus):
        self.menus = menus
        self.labels = {}
        self.shortcuts = {}
        for menu in menus:
            self.labels.update(menu.labels)
            self.shortcuts.update(menu.shortcuts)

    def __iter__(self):
        for menu in self.menus:
            yield menu
    def getLabel(self, action):
        try:
            return self.labels[action]
        except:
            return action
    def getShortcut(self, action):
        try:
            if self.shortcuts[action] is None:
                return ShortCut(None)
            else:
                return self.shortcuts[action]
        except:
            return ShortCut(None)

menubar = \
  MenuBar(
    Menu
   (_("_Video"), "Video",
    MenuItem(_("_Open"), "Open", Key("o", CTRL)),
    MenuItem(_("_Open Recent"), "OpenRecent", None),
    MenuItem(_("Check _Version"), "CheckVersion", None),
    Separator(),
    MenuItem(_("_Remove Video..."), "RemoveVideos", None, False),
    MenuItem(_("Save Video _As..."),
             "SaveVideo", Key("s",CTRL), False),
    MenuItem(_("Copy Video URL"), "CopyVideoURL", None, False),
    Separator(),
    MenuItem(_("P_references"), "EditPreferences", None),
    MenuItem(_("_Quit"),"Quit", Key("q",CTRL))),
   Menu
   (_("_Edit"), "Edit",
    MenuItem(_("Cu_t"), "Cut", Key("x", CTRL), False),
    MenuItem(_("_Copy"), "Copy", Key("c", CTRL), False),
    MenuItem(_("_Paste"), "Paste", Key("v", CTRL), False),
    MenuItem(_("Select _All"), "SelectAll", Key("a",CTRL))),
   Menu
   (_("_Channels"), "Channels",
    MenuItem(_("Add _Channel..."), "NewChannel", Key("n",CTRL)),
    MenuItem(_("New Searc_h Channel"), "NewSearchChannel", None),
    MenuItem(_("New _Folder..."), "NewChannelFolder", Key("n",CTRL, SHIFT)),
    MenuItem(_("New Channel _Guide..."), "NewGuide", None),
    Separator(),
    MenuItem(_("Re_name..."), "RenameChannel", None, False),
    MenuItem(_("Re_move..."), "RemoveChannels", None, False),
    MenuItem(_("_Update Channel"), "UpdateChannels", None, False),
    MenuItem(_("U_pdate All Channels"), "UpdateAllChannels", None),
    Separator(),
    MenuItem(_("_Send this channel to a friend"), "MailChannel",None, False),
    MenuItem(_("Copy Channel _Link"), "CopyChannelURL", None, False)),
   Menu
   (_("_Playlists"), "Playlists",
    MenuItem(_("New _Playlist..."), "NewPlaylist", Key("p",CTRL)),
    MenuItem(_("New Playlist _Folder..."), "NewPlaylistFolder",None),
    Separator(),
    MenuItem(_("Re_name..."),"RenamePlaylist",None, False),
    MenuItem(_("_Remove..."),"RemovePlaylists",None, False)),
   Menu
   (_("P_layback"), "Playback",
    MenuItem(_("_Play"), "PlayPauseVideo", Key(SPACE), False),
    MenuItem(_("_Stop Video"), "StopVideo", Key("d",CTRL), False),
    Separator(),
    MenuItem(_("_Next Video"), "NextVideo", Key(RIGHT_ARROW), False),
    MenuItem(_("_Previous Video"), "PreviousVideo", Key(LEFT_ARROW), False),
    Separator(),
    MenuItem(_("_Fullscreen"), "Fullscreen", Key("f", CTRL), False)),
   Menu
   (_("_Help"), "Help",
    MenuItem(_("_About"), "About", None),
    MenuItem(_("_Donate"), "Donate", None),
    MenuItem(_("_Help"), "Help", None)))
