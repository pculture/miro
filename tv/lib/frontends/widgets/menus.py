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
import itertools
import logging
import subprocess
import sqlite3
import time

from miro import app
from miro import errors
from miro import messages
from miro import prefs
from miro import signals
from miro import conversions
from miro.data import connectionpool
from miro.data.item import DBErrorItemInfo
from miro.frontends.widgets.keyboard import (Shortcut, CTRL, ALT, SHIFT, CMD,
     MOD, RIGHT_ARROW, LEFT_ARROW, UP_ARROW, DOWN_ARROW, SPACE, ENTER, DELETE,
     BKSPACE, ESCAPE, F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12)
from miro.frontends.widgets import dialogs
from miro.frontends.widgets.widgetconst import COLUMN_LABELS
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset
# import menu widgets into our namespace for easy access
from miro.plat.frontends.widgets.widgetset import (Separator, RadioMenuItem,
                                                   CheckMenuItem)
from miro.gtcache import gettext as _
from miro.plat import resources
from miro.plat import utils

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

_menu_item_counter = itertools.count()
def menu_item(label, shortcut=None, groups=None, **state_labels):
    def decorator(func):
        func.menu_item_info = {
            'label': label,
            'name': func.__name__,
            'shortcut': shortcut,
            'groups': groups,
            'state_labels': state_labels,
            'order': _menu_item_counter.next()
        }
        return func
    return decorator

class Menu(widgetset.Menu):
    """Portable menu class.

    This class adds some code to make writing menu items simpler.  Menu items
    can be added by defining an action handler method, and using the
    @menu_item decorator
    """
    # FIXME: the @menu_item functionality is totally optional, so most menus
    # are implemented without it.  The @menu_item approach is nicer through,
    # so we should switch the other classes to use it.

    def __init__(self, label, name, child_items=()):
        widgetset.Menu.__init__(self, label, name,
                                list(child_items) + self.make_items())

    def make_items(self):
        # list of (order, label, name, callback) tuples
        menu_item_methods = []
        for obj in self.__class__.__dict__.values():
            if callable(obj) and hasattr(obj, 'menu_item_info'):
                menu_item_methods.append(obj)
        menu_item_methods.sort(key=lambda obj: obj.menu_item_info['order'])
        menu_items = []
        for meth in menu_item_methods:
            constructor_args = meth.menu_item_info.copy()
            del constructor_args['order']
            menu_item = MenuItem(**constructor_args)
            menu_item.connect("activate", meth)
            menu_items.append(menu_item)
        return menu_items

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
                    MenuItem(_("Edit _Item Details..."), "EditItems",
                             Shortcut("i", MOD),
                             groups=["LocalItemsSelected"],
                             plural=_("Edit _Items")),
                    CheckMenuItem(_('Use album art and song info from online '
                                    'lookup database (Echonest)'),
                                  'UseEchonestData'),
                    Separator(),
                    MenuItem(_("Remove Item"), "RemoveItems",
                             groups=["LocalItemsSelected"],
                             plural=_("Remove Items")),
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
                            Menu(_("_Encoding"), "SubtitleEncodingMenu", []),
                            ]),
                    ])
    # hide the SubtitleEncodingMenu until it's populated with items.  On OSX,
    # we don't support it yet
    playback_menu.find("SubtitleEncodingMenu").hide()

    sorts_menu = Menu(_("Sorts"), "SortsMenu", [])
    convert_menu = Menu(_("_Convert"), "ConvertMenu", [
        MenuItem(_("Show Conversion Folder"), "RevealConversionFolder")
    ])
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
        all_menus.append(DevMenu())
    return all_menus

class DevMenu(Menu):
    def __init__(self):
        Menu.__init__(self, _("Dev"), "DevMenu")

    @menu_item(_("Profile Message"))
    def on_profile_message(menu_item):
        app.widgetapp.setup_profile_message()

    @menu_item(_("Profile Redraw"))
    def on_profile_redraw(menu_item):
        app.widgetapp.profile_redraw()

    class TestIntentionalCrash(StandardError):
        pass

    @menu_item(_("Test Crash Reporter"))
    def on_test_crash_reporter(menu_item):
        raise TestIntentionalCrash("intentional error here")

    @menu_item(_("Test Soft Crash Reporter"))
    def on_test_soft_crash_reporter(menu_item):
        app.widgetapp.handle_soft_failure("testing soft crash reporter",
                'intentional error', with_exception=False)

    @menu_item(_("Memory Stats"))
    def on_memory_stats(menu_item):
        app.widgetapp.memory_stats()

    @menu_item(_("Force Feedparser Processing"))
    def on_force_feedparser_processing(menu_item):
        app.widgetapp.force_feedparser_processing()

    @menu_item(_("Clog Backend"))
    def on_clog_backend(menu_item):
        app.widgetapp.clog_backend()

    @menu_item(_("Run Echoprint"))
    def on_run_echoprint(menu_item):
        print 'Running echoprint'
        print '-' * 50
        subprocess.call([utils.get_echoprint_executable_path()])
        print '-' * 50

    @menu_item(_("Run ENMFP"))
    def on_run_enmfp(menu_item):
        enmfp_info = utils.get_enmfp_executable_info()
        print 'Running enmfp-codegen'
        if 'env' in enmfp_info:
            print 'env: %s' % enmfp_info['env']
        print '-' * 50
        subprocess.call([enmfp_info['path']], env=enmfp_info.get('env'))
        print '-' * 50

    @menu_item(_("Run Donate Manager Power Toys"))
    def on_run_donate_manager_powertoys(menu_item):
        app.donate_manager.run_powertoys()

    @menu_item(_("Image Render Test"))
    def on_image_render_test(menu_item):
        t = widgetset.Table(4, 4)
        t.pack(widgetset.Label("ImageDisplay"), 1, 0)
        t.pack(widgetset.Label("ImageSurface.draw"), 2, 0)
        t.pack(widgetset.Label("ImageSurface.draw_rect"), 3, 0)
        t.pack(widgetset.Label("Normal"), 0, 1)
        t.pack(widgetset.Label("resize() called"), 0, 2)
        t.pack(widgetset.Label("crop_and_scale() called"), 0, 3)
        t.set_column_spacing(20)
        t.set_row_spacing(20)
        w = widgetset.Window("Image render test",
                             widgetset.Rect(100, 300, 800, 600))
        w.set_content_widget(t)

        path = resources.path("images/album-view-default-audio.png")
        image = widgetset.Image(path)
        resize = image.resize(image.width / 2, image.height / 2)
        crop_and_scale = image.crop_and_scale(20, 0,
                                              image.width-40, image.height,
                                              image.width, image.height)
        def add_to_table(widget, col, row):
            t.pack(widgetutil.align(widget, xalign=0, yalign=0), col, row)
        add_to_table(widgetset.ImageDisplay(image), 1, 1)
        add_to_table(widgetset.ImageDisplay(resize), 1, 2)
        add_to_table(widgetset.ImageDisplay(crop_and_scale), 1, 3)

        class ImageSurfaceDrawer(widgetset.DrawingArea):
            def __init__(self, image, use_draw_rect):
                self.image = widgetset.ImageSurface(image)
                self.use_draw_rect = use_draw_rect
                widgetset.DrawingArea.__init__(self)

            def size_request(self, layout):
                return self.image.width, self.image.height

            def draw(self, context, layout):
                if not self.use_draw_rect:
                    self.image.draw(context, 0, 0, image.width, image.height)
                else:
                    x_stride = int(image.width // 10)
                    y_stride = int(image.height // 10)
                    for x in range(0, int(image.width), x_stride):
                        for y in range(0, int(image.height), y_stride):
                            width = min(x_stride, image.width-x)
                            height = min(y_stride, image.height-y)
                            print x, y, width, height
                            self.image.draw_rect(context, x, y, x, y, width,
                                                 height)
        add_to_table(ImageSurfaceDrawer(image, False), 2, 1)
        add_to_table(ImageSurfaceDrawer(resize, False), 2, 2)
        add_to_table(ImageSurfaceDrawer(crop_and_scale, False), 2, 3)
        add_to_table(ImageSurfaceDrawer(image, True), 3, 1)
        add_to_table(ImageSurfaceDrawer(resize, True), 3, 2)
        add_to_table(ImageSurfaceDrawer(crop_and_scale, True), 3, 3)

        w.show()

    @menu_item(_("Set Echonest Retry Timeout"))
    def set_echonest_retry_timout(menu_item):
        # set LAST_RETRY_NET_LOOKUP to 1 week ago minus 1 minute
        new_value = int(time.time()) - (60 * 60 * 24 * 7) + 60
        app.config.set(prefs.LAST_RETRY_NET_LOOKUP, new_value)

    @menu_item(_("Test Database Error Item Rendering"))
    def test_database_error_item_rendering(menu_item):
        displayed = app.item_list_controller_manager.displayed
        if displayed is None:
            logging.warn("test_database_error_item_rendering: "
                         "no item list displayed")
            return
        # replace all currently loaded item infos with DBError items
        item_list = displayed.item_list
        changed_ids = []
        for item_id, item_info in item_list.row_data.items():
            if item_info is not None:
                item_list.row_data[item_id] = DBErrorItemInfo(item_id)
                changed_ids.append(item_id)
        item_list.emit('will-change')
        item_list.emit('items-changed', changed_ids)

    @menu_item(_("Force Main DB Save Error"))
    def on_force_device_db_save_error(menu_item):
        messages.ForceDBSaveError().send_to_backend()

    @menu_item(_("Force Device DB Save Error"))
    def on_force_device_db_save_error(menu_item):
        selection_type, selected_tabs = app.tabs.selection
        if (selection_type != 'connect' or
            len(selected_tabs) != 1 or
            not isinstance(selected_tabs[0], messages.DeviceInfo)):
            dialogs.show_message("Usage",
                                 "You must have a device tab selected to "
                                 "force a device database error")
            return
        messages.ForceDeviceDBSaveError(selected_tabs[0]).send_to_backend()

    @menu_item(_("Force Frontend DB Errors"))
    def force_frontend_backend_db_errors(menu_item):
        old_execute = connectionpool.Connection.execute
        def new_execute(*args, **kwargs):
            raise sqlite3.DatabaseError("Fake Error")
        connectionpool.Connection.execute = new_execute
        def undo():
            connectionpool.Connection.execute = old_execute
        app.db_error_handler.retry_callbacks.insert(0, undo)

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

    def update(self, reasons):
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

        if selection_info.has_download:
            if not selection_info.has_remote:
                if selection_info.count > 1:
                    self.states['plural'].append('EditItems')
                self.enabled_groups.add('LocalItemsSelected')
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

    Signals:
    - menus-updated(reasons): Emitted whenever update_menus() is called
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'menus-updated')
        self.menu_item_fetcher = MenuItemFetcher()
        self.subtitle_encoding_updater = SubtitleEncodingMenuUpdater()
        self.converter_list = []

    def setup_menubar(self, menubar):
        """Setup the main miro menubar.
        """
        menubar.add_initial_menus(get_app_menu())
        menubar.connect("activate", on_menubar_activate)
        self.menu_updaters = [
            LegacyMenuUpdater(),
            SortsMenuUpdater(),
            AudioTrackMenuUpdater(),
            SubtitlesMenuUpdater(),
            self.subtitle_encoding_updater,
            EchonestMenuHandler(menubar),
        ]

    def _set_play_pause(self):
        if ((not app.playback_manager.is_playing
             or app.playback_manager.is_paused)):
            label = _('Play')
        else:
            label = _('Pause')
        self.menu_item_fetcher['PlayPauseItem'].set_label(label)

    def add_subtitle_encoding_menu(self, category_label, *encodings):
        """Set up a subtitles encoding menu.

        This method should be called for each category of subtitle encodings
        (East Asian, Western European, Unicode, etc).  Pass it the list of
        encodings for that category.

        :param category_label: human-readable name for the category
        :param encodings: list of (label, encoding) tuples.  label is a
            human-readable name, and encoding is a value that we can pass to
            VideoDisplay.select_subtitle_encoding()
        """
        self.subtitle_encoding_updater.add_menu(category_label, encodings)

    def add_converters(self, converters):
        menu = app.widgetapp.menubar.find("ConvertMenu")
        position = itertools.count()
        for group_list in converters:
            for (identifier, title) in group_list:
                item = MenuItem(title, "ConvertItemTo-" + identifier,
                                groups=["LocalPlayablesSelected"])
                menu.insert(position.next(), item)
            menu.insert(position.next(), Separator())
        for i, group_list in enumerate(converters):
            self.converter_list.insert(i, group_list)

    def get_converters(self):
        """Get the current list of converters

        :returns: list of converter groups.  Each group will be a list of
        (identifier, title) tuples.
        """
        return self.converter_list

    def select_subtitle_encoding(self, encoding):
        if not self.subtitle_encoding_updater.has_encodings():
            # OSX never sets up the subtitle encoding menu
            return
        menu_item_name = self.subtitle_encoding_updater.action_name(encoding)
        try:
            self.menu_item_fetcher[menu_item_name].set_state(True)
        except KeyError:
            logging.warn("Error enabling subtitle encoding menu item: %s",
                         menu_item_name)

    def update_menus(self, *reasons):
        """Call this when a change is made that could change the menus

        Use reasons to describe why the menus could change.  Some MenuUpdater
        objects will do some optimizations based on that
        """
        reasons = set(reasons)
        self._set_play_pause()
        for menu_updater in self.menu_updaters:
            menu_updater.update(reasons)
        self.emit('menus-updated', reasons)

class MenuUpdater(object):
    """Base class for objects that dynamically update menus."""
    def __init__(self, menu_name):
        self.menu_name = menu_name
        self.first_update = False

    # we lazily access our menu item, since we are created before the menubar
    # is fully setup.
    def get_menu(self):
        try:
            return self._menu
        except AttributeError:
            self._menu = app.widgetapp.menubar.find(self.menu_name)
            return self._menu
    menu = property(get_menu)

    def update(self, reasons):
        if not self.first_update and not self.should_process_update(reasons):
            return
        self.first_update = False
        self.start_update()
        if not self.should_show_menu():
            self.menu.hide()
            return

        self.menu.show()
        if self.should_rebuild_menu():
            self.clear_menu()
            self.populate_menu()
        self.update_items()

    def should_process_update(self, reasons):
        """Test if we should ignore the update call.

        :param reasons: the reasons passed in to MenuManager.update_menus()
        """
        return True

    def clear_menu(self):
        """Remove items from our menu before rebuilding it."""
        for child in self.menu.get_children():
            self.menu.remove(child)

    def start_update(self):
        """Called at the very start of the update method.  """
        pass

    def should_show_menu(self):
        """Should we display the menu?  """
        return True

    def should_rebuild_menu(self):
        """Should we rebuild the menu structure?"""
        return False

    def populate_menu(self):
        """Add MenuItems to our menu."""
        pass

    def update_items(self):
        """Update our menu items."""
        pass

class SortsMenuUpdater(MenuUpdater):
    """Update the sorts menu for MenuManager."""
    def __init__(self):
        MenuUpdater.__init__(self, 'SortsMenu')
        self.current_sorts = []

    def should_process_update(self, reasons):
        return ('tab-selection-changed' in reasons or
                'item-list-view-changed' in reasons)

    def action_name(self, column_name):
        return "ToggleColumn-" + column_name

    def start_update(self):
        """Called at the very start of the update method.  """
        self.togglable_columns = self.columns_enabled = None
        display = app.display_manager.get_current_display()
        if display is None:
            # no display?
            return
        column_info = display.get_column_info()
        if column_info is None:
            # no togglable columns for this display
            return
        self.columns_enabled = column_info[0]
        untogglable = WidgetStateStore.MANDATORY_SORTERS
        self.togglable_columns = list(c for c in column_info[1]
                                      if c not in untogglable)
        self.togglable_columns.sort(key=COLUMN_LABELS.get)

    def should_show_menu(self):
        """Should we display the menu?  """
        return self.togglable_columns is not None

    def should_rebuild_menu(self):
        """Should we rebuild the menu structure?"""
        return self.togglable_columns != self.current_sorts

    def populate_menu(self):
        """Make a list of menu items for this menu."""
        for name in self.togglable_columns:
            label = COLUMN_LABELS[name]
            handler_name = self.action_name(name)
            self.menu.append(CheckMenuItem(label, handler_name))
        self.current_sorts = self.togglable_columns

    def update_items(self):
        """Update our menu items."""
        menu_names_to_enable = set(self.action_name(name)
                                   for name in self.columns_enabled)
        for menu_item in self.menu.get_children():
            if menu_item.name in menu_names_to_enable:
                menu_item.set_state(True)
            else:
                menu_item.set_state(False)

class AudioTrackMenuUpdater(MenuUpdater):
    """Update the audio track menu for MenuManager."""
    def __init__(self):
        MenuUpdater.__init__(self, 'AudioTrackMenu')
        self.currently_displayed_tracks = None

    def should_process_update(self, reasons):
        return 'playback-changed' in reasons

    def _on_track_change(self, menu_item, track_id):
        if app.playback_manager.is_playing:
            app.playback_manager.set_audio_track(track_id)

    def action_name(self, track_id):
        return 'ChangeAudioTrack-%s' % track_id

    def start_update(self):
        """Called at the very start of the update method.  """
        self.track_info = app.playback_manager.get_audio_tracks()
        self.enabled_track = app.playback_manager.get_enabled_audio_track()

    def should_rebuild_menu(self):
        """Should we rebuild the menu structure?"""
        return self.track_info != self.currently_displayed_tracks

    def populate_menu(self):
        """Add MenuItems to our menu."""
        if not self.track_info:
            self.make_empty_menu()
            self.currently_displayed_tracks = self.track_info
            return

        group = []
        for (track_id, label) in self.track_info:
            menu_item = RadioMenuItem(label, self.action_name(track_id))
            self.menu.append(menu_item)
            menu_item.connect('activate', self._on_track_change,
                              track_id)
            group.append(menu_item)

        for item in group[1:]:
            item.set_group(group[0])
        self.currently_displayed_tracks = self.track_info

    def make_empty_menu(self):
        menu_item = MenuItem(_("None Available"), "NoSubtitlesAvailable")
        menu_item.disable()
        self.menu.append(menu_item)

    def update_items(self):
        """Update our menu items."""
        if self.enabled_track is None:
            return
        enabled_name = self.action_name(self.enabled_track)
        for menu_item in self.menu.get_children():
            if menu_item.name == enabled_name:
                menu_item.set_state(True)
                return

class SubtitlesMenuUpdater(MenuUpdater):
    """Update the subtitles menu for MenuManager."""

    def __init__(self):
        MenuUpdater.__init__(self, 'SubtitlesMenu')
        self.none_available = MenuItem(_("None Available"), "NoneAvailable")
        self.none_available.disable()
        self.currently_displayed_tracks = None

    def should_process_update(self, reasons):
        return 'playback-changed' in reasons

    def on_change_track(self, menu_item, track_id):
        if app.playback_manager.is_playing:
            app.playback_manager.set_subtitle_track(track_id)

    def on_disable(self, menu_item):
        if app.playback_manager.is_playing:
            app.playback_manager.set_subtitle_track(None)

    def on_select_file_activate(self, menu_item):
        if app.playback_manager.is_playing:
            app.playback_manager.open_subtitle_file()

    def action_name(self, track_id):
        return 'ChangeSubtitles-%s' % track_id

    def start_update(self):
        """Called at the very start of the update method.  """
        self.enabled_track = app.playback_manager.get_enabled_subtitle_track()
        self.all_tracks = list(app.playback_manager.get_subtitle_tracks())

    def should_rebuild_menu(self):
        """Should we rebuild the menu structure?"""
        return self.currently_displayed_tracks != self.all_tracks

    def get_items(self):
        """Get the items that we actually should work with.

        This is a all of the child items in our menu, except the subtitle
        encoding menu.
        """
        return self.menu.get_children()[:-1]

    def clear_menu(self):
        # only clear the subtitle items, not the subtitle encoding submenu.
        for item in self.get_items():
            self.menu.remove(item)

    def populate_menu(self):
        """Add MenuItems to our menu."""
        to_add = self.make_items_for_tracks()
        to_add.append(Separator())
        select_file = MenuItem(_("Select a Subtitles file..."),
                               "SelectSubtitlesFile")
        select_file.connect("activate", self.on_select_file_activate)
        to_add.append(select_file)

        # insert menu items before the select subtitles encoding item
        for i, menu_item in enumerate(to_add):
            self.menu.insert(i, menu_item)
        self.currently_displayed_tracks = self.all_tracks

    def make_items_for_tracks(self):
        """Get MenuItems for subtitle tracks embedded in the video."""

        if not self.all_tracks:
            return [self.none_available]

        items = []
        first_item = None
        for track_id, label in self.all_tracks:
            menu_item = RadioMenuItem(label, self.action_name(track_id))
            menu_item.connect("activate", self.on_change_track, track_id)
            items.append(menu_item)
            if first_item is None:
                first_item = menu_item
            else:
                menu_item.set_group(first_item)

        items.append(Separator())
        disable = RadioMenuItem(_("Disable Subtitles"), "DisableSubtitles")
        disable.connect("activate", self.on_disable)
        disable.set_group(first_item)
        items.append(disable)
        return items

    def update_items(self):
        """Update our menu items."""
        menu_items = self.get_items()
        if app.playback_manager.is_playing_video:
            for item in menu_items:
                if item is not self.none_available:
                    item.enable()
            if self.enabled_track is not None:
                enabled_action_name = self.action_name(self.enabled_track)
            else:
                enabled_action_name = "DisableSubtitles"
            for item in menu_items:
                if item.name == enabled_action_name:
                    item.set_state(True)
                    break
        else:
            for item in menu_items:
                item.disable()

class SubtitleEncodingMenuUpdater(object):
    """Handles updating the subtitles encoding menu.

    This class is responsible for:
        - populating the subtitles encoding method
        - enabling/disabling the menu items
    """

    def __init__(self):
        self.menu_item_fetcher = MenuItemFetcher()
        self.default_item = None
        self.category_counter = itertools.count()

    def action_name(self, encoding):
        """Get the name of the menu item for a given encoding.

        :param: string name of the encoding, or None for the default encoding
        """
        if encoding is None:
            return 'SubtitleEncoding-Default'
        else:
            return 'SubtitleEncoding-%s' % encoding

    def has_encodings(self):
        return self.default_item is not None

    def update(self, reasons):
        encoding_menu = self.menu_item_fetcher["SubtitleEncodingMenu"]
        if app.playback_manager.is_playing_video:
            encoding_menu.enable()
        else:
            encoding_menu.disable()

    def add_menu(self, category_label, encodings):
        if not self.has_encodings():
            self.init_menu()
        category_menu = self.add_submenu(category_label)
        self.populate_submenu(category_menu, encodings)

    def init_menu(self):
        # first time calling this function, we need to set up the menu.
        encoding_menu = self.menu_item_fetcher["SubtitleEncodingMenu"]
        encoding_menu.show()
        self.default_item = RadioMenuItem(_('Default (UTF-8)'),
                                          self.action_name(None))
        self.default_item.set_state(True)
        self.default_item.connect("activate", self.on_activate, None)
        encoding_menu.append(self.default_item)

    def add_submenu(self, label):
        encoding_menu = self.menu_item_fetcher["SubtitleEncodingMenu"]
        name = "SubtitleEncodingCat-%s" % self.category_counter.next()
        category_menu = Menu(label, name, [])
        encoding_menu.append(category_menu)
        return category_menu

    def populate_submenu(self, category_menu, encodings):
        for encoding, name in encodings:
            label = '%s (%s)' % (name, encoding)
            menu_item = RadioMenuItem(label,
                                      self.action_name(encoding))
            menu_item.set_state(False)
            menu_item.connect("activate", self.on_activate, encoding)
            category_menu.append(menu_item)
            menu_item.set_group(self.default_item)

    def on_activate(self, menu_item, encoding):
        app.playback_manager.select_subtitle_encoding(encoding)

class EchonestMenuHandler(object):
    """Handles the echonest enable/disable checkbox

    Responsibilities:
        - Enabling/Disabling the menu item depending on the selection
        - Handling the callback
    """

    def __init__(self, meunbar):
        self.menu_item = app.widgetapp.menubar.find("UseEchonestData")
        self.menu_item.connect("activate", self.on_activate)

    def on_activate(self, button):
        selection = app.item_list_controller_manager.get_selection()
        id_list = [info.id for info in selection if info.downloaded]
        m = messages.SetNetLookupEnabled(id_list, button.get_state())
        m.send_to_backend()

    def update(self, reasons):
        ilc_manager = app.item_list_controller_manager
        selection_info = ilc_manager.get_selection_info()
        if (selection_info.has_download and
            not ilc_manager.displayed_type().startswith("device-")):
            self.menu_item.enable()
        else:
            self.menu_item.disable()
        self.update_check_value()

    def update_check_value(self):
        selection = app.item_list_controller_manager.get_selection()
        has_enabled = has_disabled = False
        for info in selection:
            if info.net_lookup_enabled:
                has_enabled = True
            else:
                has_disabled = True
        if has_enabled and has_disabled:
            self.menu_item.set_state(None)
        elif has_enabled:
            self.menu_item.set_state(True)
        else:
            self.menu_item.set_state(False)
