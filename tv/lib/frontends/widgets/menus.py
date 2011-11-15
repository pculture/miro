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

"""Menu handling code."""

import collections
import logging

from miro import app
from miro import errors
from miro import prefs
from miro import signals
from miro import conversions
from miro.frontends.widgets.keyboard import (Shortcut, CTRL, ALT, SHIFT, CMD,
     MOD, RIGHT_ARROW, LEFT_ARROW, UP_ARROW, DOWN_ARROW, SPACE, ENTER, DELETE,
     BKSPACE, ESCAPE, F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12)
from miro.frontends.widgets.widgetconst import COLUMN_LABELS
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.plat.frontends.widgets import widgetset
# import menu widgets into our namespace for easy access
from miro.plat.frontends.widgets.widgetset import (Separator, Menu,
                                                   RadioMenuItem, CheckMenuItem)
from miro.gtcache import gettext as _

class MenuItem(widgetset.MenuItem):
    """Portable MenuItem class.

    This adds group handling to the platform menu items.
    """
    # group_map is used for the legacy menu updater code
    group_map = collections.defaultdict(set)

    def __init__(self, label, name, shortcut=None, groups=None,
                 **state_labels):
        widgetset.MenuItem.__init__(self, label, name, shortcut)
        # state_labels is used for the legacy menu updater code
        self.state_labels = state_labels
        if groups:
            if len(groups) > 1:
                raise ValueError("only support one group")
            MenuItem.group_map[groups[0]].add(self)

class MenuItemFetcher(object):
    """Get MenuItems by their name quickly.  """

    def __init__(self):
        self._cache = {}

    def __getitem__(self, name):
        if name in self._cache:
            return self._cache[name]
        else:
            menu_item = app.widgetapp.menubar.find(name)
            self._cache[name] = menu_item
            return menu_item

def setup_menubar(menubar):
    """Setup the main miro menubar.
    """
    menubar.add_initial_menus(get_app_menu())
    menubar.connect("activate", on_menubar_activate)

def get_app_menu():
    """Returns the default menu structure."""

    file_menu = Menu(_("_File"), "FileMenu", [
                    MenuItem(_("_Open"), "Open", Shortcut("o", MOD),
                             groups=["NonPlaying"]),
                    Menu(_("Import"), "Import", [
                            MenuItem(_("Search all my Files..."),
                                     "SearchAllMyFiles",
                                     groups=["NonPlaying"]),
                            MenuItem(_("Search in a Folder..."),
                                     "SearchInAFolder",
                                     groups=["NonPlaying"]),
                            MenuItem(_("Watch a Folder..."),
                                     "WatchAFolder",
                                     groups=["NonPlaying"]),
                            MenuItem(_("Choose Files...."),
                                     "ChooseFiles",
                                     groups=["NonPlaying"]),
                            ]),
                    Separator(),
                    MenuItem(_("Download from a URL"), "NewDownload",
                             groups=["NonPlaying"]),
                    Separator(),
                    MenuItem(_("Remove Item"), "RemoveItems",
                             groups=["LocalItemsSelected"],
                             plural=_("Remove Items")),
                    MenuItem(_("Edit _Item"), "EditItems", Shortcut("i", MOD),
                             groups=["LocalItemsSelected"],
                             plural=_("Edit _Items")),
                    MenuItem(_("_Save Item As"), "SaveItem",
                             Shortcut("s", MOD),
                             groups=["LocalPlayableSelected"],
                             plural=_("_Save Items As")),
                    MenuItem(_("Copy Item _URL"), "CopyItemURL",
                             Shortcut("u", MOD),
                             groups=["LocalItemSelected"]),
                    Separator(),
                    MenuItem(_("Check Version"), "CheckVersion"),
                    MenuItem(_("Preferences"), "EditPreferences"),
                    MenuItem(_("_Quit"), "Quit", Shortcut("q", MOD)),
                    ])

    sidebar_menu = Menu(_("_Sidebar"), "SidebarMenu", [
                    MenuItem(_("Add Podcast"), "NewPodcast",
                             Shortcut("n", MOD),
                             groups=["NonPlaying"]),
                    MenuItem(_("Add Source"), "NewGuide",
                             groups=["NonPlaying"]),
                    MenuItem(_("New Search Podcast"), "NewSearchPodcast",
                             groups=["NonPlaying"]),
                    MenuItem(_("_New Folder"), "NewPodcastFolder",
                             Shortcut("n", MOD, SHIFT),
                             groups=["NonPlaying"]),
                    Separator(),
                    MenuItem(_("Rename"), "RenameSomething",
                             groups=["RenameAllowed"],
                             # groups=["PodcastOrFolderSelected", "SiteSelected"],
                             feed=_("Rename Podcast"),
                             site=_("Rename Source")),
                    MenuItem(_("Remove"), "RemoveSomething",
                             groups=["RemoveAllowed"],
                             # groups=["PodcastsSelected", "SitesSelected"],
                             feed=_("Remove Podcast"),
                             feeds=_("Remove Podcasts"),
                             folder=_("Remove Folder"),
                             folders=_("Remove Folders"),
                             site=_("Remove Source"),
                             sites=_("Remove Sources")),
                    MenuItem(_("Update Podcast"), "UpdatePodcasts",
                             Shortcut("r", MOD),
                             groups=["PodcastsSelected"],
                             plural=_("Update Podcasts")),
                    MenuItem(_("Update All Podcasts and Library"),
                              "UpdateAllPodcasts",
                             Shortcut("r", MOD, SHIFT),
                             groups=["NonPlaying"]),
                    Separator(),
                    MenuItem(_("Import Podcasts (OPML)"), "ImportPodcasts",
                             groups=["NonPlaying"]),
                    MenuItem(_("Export Podcasts (OPML)"), "ExportPodcasts",
                             groups=["NonPlaying"]),
                    Separator(),
                    MenuItem(_("Share with a Friend"), "SharePodcast",
                             groups=["PodcastSelected"]),
                    MenuItem(_("Copy URL"), "CopyPodcastURL",
                             groups=["PodcastSelected"]),
                    ])

    playlists_menu = Menu(_("_Playlists"), "PlaylistsMenu", [
                    MenuItem(_("New _Playlist"), "NewPlaylist",
                             Shortcut("p", MOD),
                             groups=["NonPlaying"]),
                    MenuItem(_("New Playlist Folder"), "NewPlaylistFolder",
                             Shortcut("p", MOD, SHIFT),
                             groups=["NonPlaying"]),
                    Separator(),
                    MenuItem(_("Rename Playlist"),"RenamePlaylist",
                             groups=["PlaylistSelected"]),
                    MenuItem(_("Remove Playlist"),"RemovePlaylists",
                             groups=["PlaylistsSelected"],
                             plural=_("Remove Playlists"),
                             folders=_("Remove Playlist Folders"),
                             folder=_("Remove Playlist Folder")),
                    ])

    playback_menu = Menu(_("P_layback"), "PlaybackMenu", [
                    MenuItem(_("Play"), "PlayPauseItem",
                             groups=["PlayPause"]),
                    MenuItem(_("Stop"), "StopItem", Shortcut("d", MOD),
                             groups=["Playing"]),
                    Separator(),
                    MenuItem(_("Next Item"), "NextItem",
                             Shortcut(RIGHT_ARROW, MOD),
                             groups=["Playing"]),
                    MenuItem(_("Previous Item"), "PreviousItem",
                             Shortcut(LEFT_ARROW, MOD),
                             groups=["Playing"]),
                    Separator(),
                    MenuItem(_("Skip Forward"), "FastForward",
                             groups=["Playing"]),
                    MenuItem(_("Skip Back"), "Rewind",
                             groups=["Playing"]),
                    Separator(),
                    MenuItem(_("Volume Up"), "UpVolume",
                             Shortcut(UP_ARROW, MOD)),
                    MenuItem(_("Volume Down"), "DownVolume",
                             Shortcut(DOWN_ARROW,MOD)),
                    Separator(),
                    MenuItem(_("Go to Currently Playing"),
                             "GotoCurrentlyPlaying",
                             Shortcut("l", MOD),
                             groups=["Playing"]),
                    Separator(),
                    MenuItem(_("_Fullscreen"), "Fullscreen",
                             Shortcut("f", MOD),
                             groups=["PlayingVideo"]),
                    MenuItem(_("_Toggle Detached/Attached"), "ToggleDetach",
                             Shortcut("t", MOD),
                             groups=["PlayingVideo"]),
                    Menu(_("Audio Track"), "AudioTrackMenu", [
                            MenuItem(_("None Available"), "NoAudioTracks",
                                     groups=["NeverEnabled"]),
                            ]),
                    Menu(_("Subtitles"), "SubtitlesMenu", [
                            MenuItem(_("None Available"), "NoneAvailable",
                                     groups=["NeverEnabled"]),
                            Separator(),
                            MenuItem(_("Select a Subtitles File..."),
                                     "SubtitlesSelect",
                                     groups=["PlayingLocalVideo"])
                            ]),
                    ])

    sorts_menu = Menu(_("Sorts"), "ViewMenu", _get_view_menu())
    convert_menu = Menu(_("_Convert"), "ConvertMenu", _get_convert_menu())
    help_menu = Menu(_("_Help"), "HelpMenu", [
                    MenuItem(_("About %(name)s",
                               {'name': app.config.get(prefs.SHORT_APP_NAME)}),
                             "About")
                    ])

    if app.config.get(prefs.DONATE_URL):
        help_menu.append(MenuItem(_("Donate"), "Donate"))

    if app.config.get(prefs.HELP_URL):
        help_menu.append(MenuItem(_("Help"), "Help", Shortcut(F1)))
    help_menu.append(Separator())
    help_menu.append(MenuItem(_("Diagnostics"), "Diagnostics"))
    if app.config.get(prefs.BUG_REPORT_URL):
        help_menu.append(MenuItem(_("Report a Bug"), "ReportBug"))
    if app.config.get(prefs.TRANSLATE_URL):
        help_menu.append(MenuItem(_("Translate"), "Translate"))
    if app.config.get(prefs.PLANET_URL):
        help_menu.append(MenuItem(_("Planet Miro"), "Planet"))

    all_menus = [file_menu, sidebar_menu, playlists_menu, playback_menu,
            sorts_menu, convert_menu, help_menu ]

    if app.debugmode:
        all_menus.append(Menu(_("Dev"), "DevMenu", [
                MenuItem(_("Profile Message"), "ProfileMessage"),
                MenuItem(_("Profile Redraw"), "ProfileRedraw"),
                MenuItem(_("Test Crash Reporter"), "TestCrashReporter"),
                MenuItem(_("Test Soft Crash Reporter"),
                    "TestSoftCrashReporter"),
                MenuItem(_("Memory Stats"), "MemoryStats"),
                MenuItem(_("Force Feedparser Processing"),
                    "ForceFeedparserProcessing"),
                MenuItem(_("Clog Backend"), "ClogBackend")
                ])
        )
    return all_menus

def _get_convert_menu():
    menu = list()
    sections = conversions.conversion_manager.get_converters()
    for index, section in enumerate(sections):
        for converter in section[1]:
            handler_name = make_convert_handler(converter)
            item = MenuItem(converter.displayname, handler_name,
                            groups=["LocalPlayablesSelected"])
            menu.append(item)
        if index+1 < len(sections):
            menu.append(Separator())
    menu.append(Separator())
    menu.append(MenuItem(_("Show Conversion Folder"), "RevealConversionFolder"))
    return menu

def add_subtitle_encoding_menu(menubar, category_label, *encodings):
    """Helper method to set up the subtitles encoding menu.

    This method should be called for each category of subtitle encodings (East
    Asian, Western European, Unicode, etc).  Pass it the list of encodings for
    that category.

    :param category_label: human-readable name for the category
    :param encodings: list of (label, encoding) tuples.  label is a
        human-readable name, and encoding is a value that we can pass to
        VideoDisplay.select_subtitle_encoding()
    """
    subtitles_menu = menubar.find("SubtitlesMenu")
    try:
        encoding_menu = menubar.find("SubtitleEncodingMenu")
    except KeyError:
        # first time calling this function, we need to set up the menu.
        encoding_menu = Menu(_("_Encoding"),
                "SubtitleEncodingMenu", [], groups=['PlayingVideo'])
        subtitles_menu.append(encoding_menu)
        default_item = RadioMenuItem(_('Default (UTF-8)'),
                "SubtitleEncoding-Default", 'subtitle-encoding',
                groups=['PlayingVideo'])
        encoding_menu.append(default_item)
        app.menu_manager.subtitle_encoding_enabled = True

    category_menu = Menu(category_label,
            "SubtitleEncodingCat%s" % encoding_menu.count(), [],
            groups=['PlayingVideo'])
    encoding_menu.append(category_menu)

    for encoding, name in encodings:
        label = '%s (%s)' % (name, encoding)
        category_menu.append(RadioMenuItem(label,
            'SubtitleEncoding-%s' % encoding,
            'subtitle-encoding', groups=["PlayingVideo"]))

action_handlers = {}
group_action_handlers = {}

def on_menubar_activate(menubar, action_name):
    callback = lookup_handler(action_name)
    if callback is not None:
        callback()

def lookup_handler(action_name):
    """For a given action name, get a callback to handle it.  Return
    None if no callback is found.
    """
    
    retval = _lookup_group_handler(action_name)
    if retval is None:
        retval = action_handlers.get(action_name)
    return retval

def _lookup_group_handler(action_name):
    try:
        group_name, callback_arg = action_name.split('-', 1)
    except ValueError:
        return None # split return tuple of length 1
    try:
        group_handler = group_action_handlers[group_name]
    except KeyError:
        return None
    else:
        return lambda: group_handler(callback_arg)

def action_handler(name):
    """Decorator for functions that handle menu actions."""
    def decorator(func):
        action_handlers[name] = func
        return func
    return decorator

def group_action_handler(action_prefix):
    def decorator(func):
        group_action_handlers[action_prefix] = func
        return func
    return decorator

def make_convert_handler(converter):
    return "ConvertItemTo-" + converter.identifier

def make_column_toggle_handler(name):
    return "ToggleColumn-" + name

# File menu
@action_handler("Open")
def on_open():
    app.widgetapp.open_video()

@action_handler("NewDownload")
def on_new_download():
    app.widgetapp.new_download()

@action_handler("CheckVersion")
def on_check_version():
    app.widgetapp.check_version()

@action_handler("RemoveItems")
def on_remove_items():
    app.widgetapp.remove_items()

@action_handler("EditItems")
def on_edit_items():
    app.widgetapp.edit_items()

@action_handler("SaveItem")
def on_save_item():
    app.widgetapp.save_item()

@group_action_handler("ConvertItemTo")
def on_convert(converter_id):
    app.widgetapp.convert_items(converter_id)

@action_handler("RevealConversionFolder")
def on_reveal_conversion_folder():
    app.widgetapp.reveal_conversions_folder()

@action_handler("CopyItemURL")
def on_copy_item_url():
    app.widgetapp.copy_item_url()

@action_handler("EditPreferences")
def on_edit_preferences():
    app.widgetapp.preferences()

@action_handler("Quit")
def on_quit():
    app.widgetapp.quit()

# Podcasts menu
@action_handler("NewPodcast")
def on_new_podcast():
    app.widgetapp.add_new_feed()

@action_handler("NewGuide")
def on_new_guide():
    app.widgetapp.add_new_guide()

@action_handler("NewSearchPodcast")
def on_new_search_podcast():
    app.widgetapp.add_new_search_feed()

@action_handler("NewPodcastFolder")
def on_new_podcast_folder():
    app.widgetapp.add_new_feed_folder()

@action_handler("WatchAFolder")
def on_watch_a_folder():
    app.widgetapp.add_new_watched_folder()

@action_handler("SearchAllMyFiles")
def on_search_all_my_files():
    app.widgetapp.import_search_all_my_files()

@action_handler("SearchInAFolder")
def on_search_in_a_folder():
    app.widgetapp.import_search_in_folder()

@action_handler("ChooseFiles")
def on_choose_files():
    app.widgetapp.import_choose_files()

@action_handler("RenameSomething")
def on_rename_podcast():
    app.widgetapp.rename_something()

@action_handler("RemoveSomething")
def on_remove_podcasts():
    app.widgetapp.remove_something()

@action_handler("UpdatePodcasts")
def on_update_podcasts():
    app.widgetapp.update_selected_feeds()

@action_handler("UpdateAllPodcasts")
def on_update_all_podcasts():
    app.widgetapp.update_all_feeds()

@action_handler("ImportPodcasts")
def on_import_podcasts():
    app.widgetapp.import_feeds()

@action_handler("ExportPodcasts")
def on_export_podcasts():
    app.widgetapp.export_feeds()

@action_handler("SharePodcast")
def on_share_podcast():
    app.widgetapp.share_feed()

@action_handler("CopyPodcastURL")
def on_copy_podcast_url():
    app.widgetapp.copy_feed_url()

# Playlists menu
@action_handler("NewPlaylist")
def on_new_playlist():
    app.widgetapp.add_new_playlist()

@action_handler("NewPlaylistFolder")
def on_new_playlist_folder():
    app.widgetapp.add_new_playlist_folder()

@action_handler("RenamePlaylist")
def on_rename_playlist():
    app.widgetapp.rename_something()

@action_handler("RemovePlaylists")
def on_remove_playlists():
    app.widgetapp.remove_something()

# Playback menu
@action_handler("PlayPauseItem")
def on_play_pause_item():
    app.widgetapp.on_play_clicked()

@action_handler("StopItem")
def on_stop_item():
    app.widgetapp.on_stop_clicked()

@action_handler("NextItem")
def on_next_item():
    app.widgetapp.on_forward_clicked()

@action_handler("PreviousItem")
def on_previous_item():
    app.widgetapp.on_previous_clicked()

@action_handler("FastForward")
def on_fast_forward():
    app.widgetapp.on_skip_forward()

@action_handler("Rewind")
def on_rewind():
    app.widgetapp.on_skip_backward()

@action_handler("UpVolume")
def on_up_volume():
    app.widgetapp.up_volume()

@action_handler("DownVolume")
def on_down_volume():
    app.widgetapp.down_volume()

@action_handler("GotoCurrentlyPlaying")
def on_goto_currently_playing():
    app.playback_manager.goto_currently_playing()

@action_handler("Fullscreen")
def on_fullscreen():
    app.playback_manager.toggle_fullscreen()

@action_handler("ToggleDetach")
def on_toggle_detach():
    app.widgetapp.on_toggle_detach_clicked()

@action_handler("SubtitlesSelect")
def on_subtitles_select():
    app.playback_manager.open_subtitle_file()

@group_action_handler("SubtitleEncoding")
def on_subtitle_encoding(converter):
    if converter == 'Default':
        app.playback_manager.select_subtitle_encoding(None)
    else:
        app.playback_manager.select_subtitle_encoding(converter)

# Sorts menu
@group_action_handler("ToggleColumn")
def on_toggle_column(name):
    app.widgetapp.toggle_column(name)

# Help menu
@action_handler("About")
def on_about():
    app.widgetapp.about()

@action_handler("Donate")
def on_donate():
    app.widgetapp.open_url(app.config.get(prefs.DONATE_URL))

@action_handler("Help")
def on_help():
    app.widgetapp.open_url(app.config.get(prefs.HELP_URL))

@action_handler("Diagnostics")
def on_diagnostics():
    app.widgetapp.diagnostics()

@action_handler("ReportBug")
def on_report_bug():
    app.widgetapp.open_url(app.config.get(prefs.BUG_REPORT_URL))

@action_handler("Translate")
def on_translate():
    app.widgetapp.open_url(app.config.get(prefs.TRANSLATE_URL))

@action_handler("Planet")
def on_planet():
    app.widgetapp.open_url(app.config.get(prefs.PLANET_URL))

@action_handler("ProfileMessage")
def on_profile_message():
    app.widgetapp.setup_profile_message()

@action_handler("ProfileRedraw")
def on_profile_redraw():
    app.widgetapp.profile_redraw()

class TestIntentionalCrash(Exception):
    pass

@action_handler("TestCrashReporter")
def on_test_crash_reporter():
    raise TestIntentionalCrash("intentional error here")

@action_handler("TestSoftCrashReporter")
def on_test_soft_crash_reporter():
    app.widgetapp.handle_soft_failure("testing soft crash reporter",
            'intentional error', with_exception=False)

@action_handler("MemoryStats")
def on_memory_stats():
    app.widgetapp.memory_stats()

@action_handler("ForceFeedparserProcessing")
def on_force_feedparser_processing():
    app.widgetapp.force_feedparser_processing()

@action_handler("ClogBackend")
def on_clog_backend():
    app.widgetapp.clog_backend()

def generate_action_groups(menu_structure):
    """Takes a menu structure and returns a map of action group name to
    list of menu actions in that group.
    """
    action_groups = {}
    for menu in menu_structure:
        if hasattr(menu, "groups"):
            for grp in menu.groups:
                action_groups.setdefault(grp, []).append(menu.action)
    return action_groups

class LegacyMenuUpdater(object):
    """This class contains the logic to update the menus based on enabled
    groups and state labels.

    Now that we can directly manipulate MenuItems, we probably can re-write
    this stuff in a cleaner and better way.
    """
    # NOTE: this code is probably extremely brittle.  If you want to change
    # something, you are probably better off rewriting it and moving it to
    # MenuManager
    #
    # FIXME: we should probably just move all this code to new classes
    # eventually

    def __init__(self):
        self.menu_item_fetcher = MenuItemFetcher()

    def update_menus(self):
        # reset enabled_groups and state_labels
        self.reset()
        # update enabled_groups and state_labels based on the state of the UI
        self._handle_selected_tabs()
        self._handle_selected_items()
        # update menu items based on enabled_groups and state_labels
        self.update_enabled_groups()
        self.update_state_labels()

    def update_enabled_groups(self):
        for group_name, items in MenuItem.group_map.iteritems():
            if group_name in self.enabled_groups:
                for item in items:
                    item.enable()
            else:
                for item in items:
                    item.disable()

    def update_state_labels(self):
        for state, names in self.states.iteritems():
            for name in names:
                menu_item = self.menu_item_fetcher[name]
                try:
                    new_label = menu_item.state_labels[state]
                except KeyError:
                    logging.warn("Error trying to set menu item %s to %s",
                                 name, state)
                else:
                    menu_item.set_label(new_label)

    def reset(self):
        self.states = {"feed": [],
                       "feeds": [],
                       "folder": [],
                       "folders": [],
                       "site": [],
                       "sites": [],
                       "plural": []}
        self.plural = False
        self.enabled_groups = set(['AlwaysOn'])
        if app.playback_manager.is_playing:
            self.enabled_groups.add('PlayPause')
            self.enabled_groups.add('Playing')
            item = app.playback_manager.get_playing_item()
            if item and item.remote:
                self.enabled_groups.add('LocalPlayableSelected_PlayPause')
                self.enabled_groups.add('LocalPlayableSelected_PlayPause')
            self.enabled_groups.add('PlayablesSelected_PlayPause')
            self.enabled_groups.add('PlayablesSelected_PlayPause')
            if app.playback_manager.is_playing_audio:
                # if it's playing audio, then we allow the user to do other
                # things just as if the window was detached
                self.enabled_groups.add('NonPlaying')
            else:
                if not item.remote:
                    self.enabled_groups.add('PlayingLocalVideo')
                self.enabled_groups.add('PlayingVideo')
            if app.playback_manager.detached_window is not None:
                self.enabled_groups.add('NonPlaying')
        else:
            self.enabled_groups.add('NonPlaying')

    def _handle_feed_selection(self, selected_feeds):
        """Handle the user selecting things in the feed list.

        ``selected_feeds`` is a list of ChannelInfo objects.
        """
        self.enabled_groups.add('PodcastsSelected')
        self.enabled_groups.add("RemoveAllowed")
        if len(selected_feeds) == 1:
            if (hasattr(selected_feeds[0], 'is_folder') and
                    selected_feeds[0].is_folder):
                self.states["folder"].append("RemoveSomething")
            else:
                self.states["feed"].append("RemoveSomething")
                self.states["feed"].append("RenameSomething")
                self.enabled_groups.add('PodcastSelected')
            self.enabled_groups.add('PodcastOrFolderSelected')
            self.enabled_groups.add("RenameAllowed")
        else:
            selected_folders = [s for s in selected_feeds if s.is_folder]
            if len(selected_folders) == len(selected_feeds):
                self.states["folders"].append("RemoveSomething")
            else:
                self.states["feeds"].append("RemoveSomething")
            self.states["plural"].append("UpdatePodcasts")

    def _handle_site_selection(self, selected_sites):
        """Handle the user selecting things in the site list.
        selected_sites is a list of GuideInfo objects
        """
        has_stores = bool([True for info in selected_sites if info.store])
        self.enabled_groups.add('SitesSelected')
        if not has_stores:
            self.enabled_groups.add("RemoveAllowed")
        if len(selected_sites) == 1:
            self.enabled_groups.add('SiteSelected')
            if not has_stores:
                self.enabled_groups.add("RenameAllowed")
                self.states["site"].append("RemoveSomething")
                self.states["site"].append("RenameSomething")
        elif not has_stores:
            self.states["sites"].append("RemoveSomething")
            self.states["sites"].append("RenameSomething")

    def _handle_connect_selection(self, selected_devices):
        selected_info = selected_devices[0]
        if selected_info.type == u'device':
            self.enabled_groups.add('DeviceSelected')

    def _handle_playlist_selection(self, selected_playlists):
        self.enabled_groups.add('PlaylistsSelected')
        if len(selected_playlists) == 1:
            if selected_playlists[0].is_folder:
                self.states["folder"].append("RemovePlaylists")
            self.enabled_groups.add('PlaylistSelected')
        else:
            selected_folders = [s for s in selected_playlists if s.is_folder]
            if len(selected_folders) == len(selected_playlists):
                self.states["folders"].append("RemovePlaylists")
            else:
                self.states["plural"].append("RemovePlaylists")

    def _handle_static_tab_selection(self, selected_static_tabs):
        """Handle the user selecting things in the static tab list.
        selected_sites is a list of GuideInfo objects
        """
        # we don't change menu items for the static tab list
        pass

    def _handle_selected_tabs(self):
        try:
            selection_type, selected_tabs = app.tabs.selection
        except errors.WidgetActionError:
            return
        if selection_type is None or selected_tabs[0].type == u'tab':
            pass
        elif selection_type == 'feed':
            self._handle_feed_selection(selected_tabs)
        elif selection_type == 'playlist':
            self._handle_playlist_selection(selected_tabs)
        elif selection_type in ('static', 'library'):
            self._handle_static_tab_selection(selected_tabs)
        elif selection_type in ('site', 'store'):
            self._handle_site_selection(selected_tabs)
        elif selection_type == 'connect':
            self._handle_connect_selection(selected_tabs)
        else:
            raise ValueError("Unknown tab list type: %s" % selection_type)

    def _handle_selected_items(self):
        """Update the menu items based on the current item list
        selection.
        """
        selection_info = app.item_list_controller_manager.get_selection_info()

        if selection_info.count > 0 and not selection_info.has_remote:
            if selection_info.count == 1:
                self.enabled_groups.add('LocalItemSelected')
            else:
                self.states['plural'].append('EditItems')
            self.enabled_groups.add('LocalItemsSelected')

        if selection_info.has_download:
            if not selection_info.has_remote:
                self.enabled_groups.add('LocalPlayablesSelected')
                self.enabled_groups.add('LocalPlayablesSelected_PlayPause')
            self.enabled_groups.add('PlayablesSelected')
            self.enabled_groups.add('PlayablesSelected_PlayPause')
            if not selection_info.has_file_type('audio'):
                self.enabled_groups.add('PlayableVideosSelected')
            if selection_info.count == 1:
                if not selection_info.has_remote:
                    self.enabled_groups.add('LocalPlayableSelected')
                    self.enabled_groups.add('LocalPlayableSelected_PlayPause')
                self.enabled_groups.add('PlayableSelected')
                self.enabled_groups.add('PlayableSelected_PlayPause')
            else:
                self.states["plural"].append("RemoveItems")

        can_play = app.item_list_controller_manager.can_play_items()
        if can_play:
            self.enabled_groups.add('PlayPause')
            if not selection_info.has_remote:
                self.enabled_groups.add('LocalPlayableSelected_PlayPause')
                self.enabled_groups.add('LocalPlayablesSelected_PlayPause')
            self.enabled_groups.add('PlayableSelected_PlayPause')
            self.enabled_groups.add('PlayablesSelected_PlayPause')
        app.widgetapp.window.videobox.handle_new_selection(can_play)

class MenuManager(signals.SignalEmitter):
    """Updates the menu based on the current selection.

    This includes enabling/disabling menu items, changing menu text
    for plural selection and enabling/disabling the play button.  The
    play button is obviously not a menu item, but it's pretty closely
    related

    Whenever code makes a change that could possibly affect which menu
    items should be enabled/disabled, it should call the
    update_menus() method.
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('radio-group-changed')
        self.create_signal('checked-changed')
        self.menu_item_fetcher = MenuItemFetcher()
        self.legacy_menu_updater = LegacyMenuUpdater()
        self.subtitle_encoding_enabled = False

    def _set_play_pause(self):
        if ((not app.playback_manager.is_playing
             or app.playback_manager.is_paused)):
            label = _('Play')
        else:
            label = _('Pause')
        self.menu_item_fetcher['PlayPauseItem'].set_label(label)

    def select_subtitle_encoding(self, encoding):
        if self.subtitle_encoding_enabled:
            if encoding is None:
                action_name = 'SubtitleEncoding-Default'
            else:
                action_name = 'SubtitleEncoding-%s' % encoding
            self.emit('radio-group-changed', 'subtitle-encoding', action_name)

    def update_menus(self):
        self._set_play_pause()
        self.legacy_menu_updater.update_menus()

    def _update_view_menu(self):
        display = app.display_manager.get_current_display()
        # fetch the enabled/available columns for this display
        if display is None:
            # no display?
            return
        column_info = display.get_column_info()
        if column_info is None:
            # display doesn't support togglable columns
            return
        columns_enabled = set(column_info[0])
        columns_available = column_info[1]
        # make available columns user selectable
        for column in columns_available:
            self.enabled_groups.add('column-%s' % column)
        # check the currently enabled columns
        checks = dict(('ToggleColumn-' + column, column in columns_enabled)
            for column in WidgetStateStore.get_toggleable_columns())
        self.emit('checked-changed', 'ListView', checks)

def _get_view_menu():
    return []
    menu = list()
    toggleable = WidgetStateStore.get_toggleable_columns()
    for name in sorted(toggleable, key=COLUMN_LABELS.get):
        groups = ['column-%s' % name]
        label = COLUMN_LABELS[name]
        handler_name = make_column_toggle_handler(name)
        menu.append(CheckMenuItem(label, handler_name, 'ListView', groups=groups))
    return menu
