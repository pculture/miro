# Defines menu, accelerator keys, and shortcuts
# THIS IS STILL A WORK IN PROGRESS. THE FORMAT IS NOT FINAL
from gtcache import gettext as _
import platform

CTRL, ALT, SHIFT, CMD, RIGHT_ARROW, LEFT_ARROW, UP_ARROW, DOWN_ARROW, SPACE, ENTER = range(10)

class ShortCut:
    def __init__(self, key, *modifiers):
        self.modifiers = modifiers
        self.key = key

Key = ShortCut

class MenuItem:
    def __init__(self, label, action, shortcut, enabled = True, **stateLabels):
        self.label = label
        self.action = action
        self.shortcut = shortcut
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
                self.shortcuts[item.action] = item.shortcut
                if item.stateLabels:
                    self.stateLabels[item.action] = item.stateLabels
            
    def getLabel(self, action):
        return self.labels[action]
    def getShortcut(self, action):
        return self.shortcuts[action]

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
    def getLabel(self, action, state=None):
        if state is None:
            try:
                return self.labels[action]
            except KeyError:
                return action
        else:
            try:
                return self.stateLabels[action][state]
            except KeyError:
                return self.getLabel(action)
    def getShortcut(self, action):
        try:
            if self.shortcuts[action] is None:
                return ShortCut(None)
            else:
                return self.shortcuts[action]
        except KeyError:
            return ShortCut(None)

if platform.system() == "Darwin":
    # OS X Menu goes here
     menubar = \
MenuBar(
   Menu
   (_("_Video"), "Video",
    MenuItem(_("_Open"), "Open", Key("o", CMD)),
    MenuItem(_("_Open Recent"), "OpenRecent", None),
    MenuItem(_("Check _Version"), "CheckVersion", None),
    Separator(),
    MenuItem(_("Select _All"), "SelectAll", Key("a", CMD)),
    Separator(),
    MenuItem(_("_Remove Video (_x)"), "RemoveVideos", Key("x", CMD), False,
             plural=_("_Remove Videos (_x)")),
    MenuItem(_("_Save Video"), "SaveVideo", Key("s",CMD), False,
             plural=_("_Save Videos")),
    MenuItem(_("_Copy Video URL"), "CopyVideoURL", Key("c", CMD), False),
    Separator(),
    MenuItem(_("_Preferences"), "EditPreferences", Key("p",CMD)),
    MenuItem(_("_Quit"),"Quit", Key("q",CMD))),
   Menu
   (_("_Channels"), "Channels",
    MenuItem(_("Add _New Channel"), "NewChannel", Key("n",CMD,SHIFT)),
    MenuItem(_("New Searc_h Channel"), "NewSearchChannel", Key("h",CMD,SHIFT)),
    MenuItem(_("New _Folder"), "NewChannelFolder", Key("f",CMD,SHIFT)),
    MenuItem(_("New Channel _Guide"), "NewGuide", Key("g",CMD,SHIFT)),
    Separator(),
    MenuItem(_("Renam_e Channel"), "RenameChannel", Key("e",CMD,SHIFT), False),
    MenuItem(_("Remove Channel (_x)"), "RemoveChannels", Key("x",CMD,SHIFT), False,
             plural=_("Re_move Channels (x)")),
    MenuItem(_("_Update Channel"), "UpdateChannels", Key("u",CMD,SHIFT), False,
             plural=_("_Update Channels")),
    MenuItem(_("Update _All Channels"), "UpdateAllChannels", Key("a",CMD,SHIFT)),
    Separator(),
    MenuItem(_("_Send this channel to a friend"), "MailChannel", Key("s",CMD,SHIFT), False),
    MenuItem(_("_Copy Channel Link"), "CopyChannelURL", Key("c",CMD,SHIFT), False)),
   Menu
   (_("_Playlists"), "Playlists",
    MenuItem(_("New _Playlist"), "NewPlaylist", Key("p",CMD,SHIFT)),
    MenuItem(_("New Playlist Fol_der"), "NewPlaylistFolder",Key("d",CMD,SHIFT)),
    Separator(),
    MenuItem(_("Rename Playlist"),"RenamePlaylist",None, False),
    MenuItem(_("Remove Playlist"),"RemovePlaylists",None, False,
             plural=_("Remove Playlists"))),
   Menu
   (_("P_layback"), "Playback",
    MenuItem(_("Play"), "PlayPauseVideo", Key(SPACE), False),
    MenuItem(_("Stop"), "StopVideo", Key(ENTER), False),
    Separator(),
    MenuItem(_("Next Video"), "NextVideo", Key(RIGHT_ARROW, CMD), False),
    MenuItem(_("Previous Video"), "PreviousVideo", Key(LEFT_ARROW, CMD), False),
    Separator(),
    MenuItem(_("Fast Forward"), "FastForward", Key(RIGHT_ARROW), False),
    MenuItem(_("Rewind"), "Rewind", Key(LEFT_ARROW), False),
    Separator(),
    MenuItem(_("_Fullscreen"), "Fullscreen", Key("f", CMD), False),
    Separator(),
    MenuItem(_("Volume Up"), "UpVolume", Key(UP_ARROW, CMD), False),
    MenuItem(_("Volume Down"), "DownVolume", Key(DOWN_ARROW,CMD), False),
    MenuItem(_("Max Volume"), "MaxVolume", Key(UP_ARROW, ALT), False),
    MenuItem(_("Min Volume"), "MinVolume", Key(DOWN_ARROW, ALT), False),
    Separator(),
    MenuItem(_("_Mute"), "MuteVolume", Key("m", CTRL), False)),
   Menu
   (_("_Help"), "Help",
    MenuItem(_("About"), "About", None),
    MenuItem(_("Donate"), "Donate", None),
    MenuItem(_("Help"), "Help", None)))
    
elif platform.system() == "Windows":
    # Windows menu goes here
 menubar = \
  MenuBar(
   Menu
   (_("_Video"), "Video",
    MenuItem(_("_Open"), "Open", Key("o", CTRL)),
    MenuItem(_("_Open Recent"), "OpenRecent", None),
    MenuItem(_("Check _Version"), "CheckVersion", None),
    Separator(),
    MenuItem(_("Select _All"), "SelectAll", Key("a", CTRL)),
    Separator(),
    MenuItem(_("_Remove Video (_x)"), "RemoveVideos", Key("x", CTRL), False,
             plural=_("_Remove Videos (_x)")),
    MenuItem(_("_Save Video"), "SaveVideo", Key("s",CTRL), False,
             plural=_("_Save Videos")),
    MenuItem(_("_Copy Video URL"), "CopyVideoURL", Key("c", CTRL), False),
    Separator(),
    MenuItem(_("_Preferences"), "EditPreferences", Key("p",CTRL)),
    MenuItem(_("_Quit"),"Quit", Key("q",CTRL))),
   Menu
   (_("_Channels"), "Channels",
    MenuItem(_("Add _New Channel"), "NewChannel", Key("n",CTRL,SHIFT)),
    MenuItem(_("New Searc_h Channel"), "NewSearchChannel", Key("h",CTRL,SHIFT)),
    MenuItem(_("New _Folder"), "NewChannelFolder", Key("f",CTRL,SHIFT)),
    MenuItem(_("New Channel _Guide"), "NewGuide", Key("g",CTRL,SHIFT)),
    Separator(),
    MenuItem(_("Renam_e Channel"), "RenameChannel", Key("e",CTRL,SHIFT), False),
    MenuItem(_("Remove Channel (_x)"), "RemoveChannels", Key("x",CTRL,SHIFT), False,
             plural=_("Re_move Channels (x)")),
    MenuItem(_("_Update Channel"), "UpdateChannels", Key("u",CTRL,SHIFT), False,
             plural=_("_Update Channels")),
    MenuItem(_("Update _All Channels"), "UpdateAllChannels", Key("a",CTRL,SHIFT)),
    Separator(),
    MenuItem(_("_Send this channel to a friend"), "MailChannel", Key("s",CTRL,SHIFT), False),
    MenuItem(_("_Copy Channel Link"), "CopyChannelURL", Key("c",CTRL,SHIFT), False)),
   Menu
   (_("_Playlists"), "Playlists",
    MenuItem(_("New _Playlist"), "NewPlaylist", Key("p",CTRL,SHIFT)),
    MenuItem(_("New Playlist Fol_der"), "NewPlaylistFolder",Key("d",CTRL,SHIFT)),
    Separator(),
    MenuItem(_("Rename Playlist"),"RenamePlaylist",None, False),
    MenuItem(_("Remove Playlist"),"RemovePlaylists",None, False,
             plural=_("Remove Playlists"))),
   Menu
   (_("P_layback"), "Playback",
    MenuItem(_("Play"), "PlayPauseVideo", Key(SPACE), False),
    MenuItem(_("Stop"), "StopVideo", Key(ENTER), False),
    Separator(),
    MenuItem(_("Next Video"), "NextVideo", Key(RIGHT_ARROW, CTRL), False),
    MenuItem(_("Previous Video"), "PreviousVideo", Key(LEFT_ARROW, CTRL), False),
    Separator(),
    MenuItem(_("Fast Forward"), "FastForward", Key(RIGHT_ARROW), False),
    MenuItem(_("Rewind"), "Rewind", Key(LEFT_ARROW), False),
    Separator(),
    MenuItem(_("_Fullscreen"), "Fullscreen", Key("f", CTRL), False),
    Separator(),
    MenuItem(_("Volume Up"), "UpVolume", Key(UP_ARROW, CTRL), False),
    MenuItem(_("Volume Down"), "DownVolume", Key(DOWN_ARROW,CTRL), False),
    MenuItem(_("Max Volume"), "MaxVolume", Key(UP_ARROW, ALT), False),
    MenuItem(_("Min Volume"), "MinVolume", Key(DOWN_ARROW, ALT), False),
    Separator(),
    MenuItem(_("_Mute"), "MuteVolume", Key("m", CTRL), False)),
   Menu
   (_("_Help"), "Help",
    MenuItem(_("About"), "About", None),
    MenuItem(_("Donate"), "Donate", None),
    MenuItem(_("Help"), "Help", None)))
    
else:
    # GTK menu goes here
 menubar = \
  MenuBar(
   Menu
   (_("_Video"), "Video",
    MenuItem(_("_Open"), "Open", Key("o", CTRL)),
    MenuItem(_("_Open Recent"), "OpenRecent", None),
    MenuItem(_("Check _Version"), "CheckVersion", None),
    Separator(),
    MenuItem(_("Select _All"), "SelectAll", Key("a", CTRL)),
    Separator(),
    MenuItem(_("_Remove Video (_x)"), "RemoveVideos", Key("x", CTRL), False,
             plural=_("_Remove Videos (_x)")),
    MenuItem(_("_Save Video"), "SaveVideo", Key("s",CTRL), False,
             plural=_("_Save Videos")),
    MenuItem(_("_Copy Video URL"), "CopyVideoURL", Key("c", CTRL), False),
    Separator(),
    MenuItem(_("_Preferences"), "EditPreferences", Key("p",CTRL)),
    MenuItem(_("_Quit"),"Quit", Key("q",CTRL))),
   Menu
   (_("_Channels"), "Channels",
    MenuItem(_("Add _New Channel"), "NewChannel", Key("n",CTRL,SHIFT)),
    MenuItem(_("New Searc_h Channel"), "NewSearchChannel", Key("h",CTRL,SHIFT)),
    MenuItem(_("New _Folder"), "NewChannelFolder", Key("f",CTRL,SHIFT)),
    MenuItem(_("New Channel _Guide"), "NewGuide", Key("g",CTRL,SHIFT)),
    Separator(),
    MenuItem(_("Renam_e Channel"), "RenameChannel", Key("e",CTRL,SHIFT), False),
    MenuItem(_("Remove Channel (_x)"), "RemoveChannels", Key("x",CTRL,SHIFT), False,
             plural=_("Re_move Channels (x)")),
    MenuItem(_("_Update Channel"), "UpdateChannels", Key("u",CTRL,SHIFT), False,
             plural=_("_Update Channels")),
    MenuItem(_("Update _All Channels"), "UpdateAllChannels", Key("a",CTRL,SHIFT)),
    Separator(),
    MenuItem(_("_Send this channel to a friend"), "MailChannel", Key("s",CTRL,SHIFT), False),
    MenuItem(_("_Copy Channel Link"), "CopyChannelURL", Key("c",CTRL,SHIFT), False)),
   Menu
   (_("_Playlists"), "Playlists",
    MenuItem(_("New _Playlist"), "NewPlaylist", Key("p",CTRL,SHIFT)),
    MenuItem(_("New Playlist Fol_der"), "NewPlaylistFolder",Key("d",CTRL,SHIFT)),
    Separator(),
    MenuItem(_("Rename Playlist"),"RenamePlaylist",None, False),
    MenuItem(_("Remove Playlist"),"RemovePlaylists",None, False,
             plural=_("Remove Playlists"))),
   Menu
   (_("P_layback"), "Playback",
    MenuItem(_("Play"), "PlayPauseVideo", Key(SPACE), False),
    MenuItem(_("Stop"), "StopVideo", Key(ENTER), False),
    Separator(),
    MenuItem(_("Next Video"), "NextVideo", Key(RIGHT_ARROW, CTRL), False),
    MenuItem(_("Previous Video"), "PreviousVideo", Key(LEFT_ARROW, CTRL), False),
    Separator(),
    MenuItem(_("Fast Forward"), "FastForward", Key(RIGHT_ARROW), False),
    MenuItem(_("Rewind"), "Rewind", Key(LEFT_ARROW), False),
    Separator(),
    MenuItem(_("_Fullscreen"), "Fullscreen", Key("f", CTRL), False),
    Separator(),
    MenuItem(_("Volume Up"), "UpVolume", Key(UP_ARROW, CTRL), False),
    MenuItem(_("Volume Down"), "DownVolume", Key(DOWN_ARROW,CTRL), False),
    MenuItem(_("Max Volume"), "MaxVolume", Key(UP_ARROW, ALT), False),
    MenuItem(_("Min Volume"), "MinVolume", Key(DOWN_ARROW, ALT), False),
    Separator(),
    MenuItem(_("_Mute"), "MuteVolume", Key("m", CTRL), False)),
   Menu
   (_("_Help"), "Help",
    MenuItem(_("About"), "About", None),
    MenuItem(_("Donate"), "Donate", None),
    MenuItem(_("Help"), "Help", None)))
