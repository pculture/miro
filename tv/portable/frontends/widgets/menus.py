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

"""Menu handling code."""

from miro import app
from miro import prefs
from miro import signals
from miro import config

action_handlers = {}
def lookup_handler(action_name):
    """For a given action name from miro.menubar, get a callback to handle it.
    Return None if no callback is found.
    """
    return action_handlers.get(action_name)

def action_handler(name):
    """Decorator for functions that handle menu actions."""
    def decorator(func):
        action_handlers[name] = func
        return func
    return decorator

# Video menu

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

@action_handler("RenameItem")
def on_rename_item():
    app.widgetapp.rename_item()

@action_handler("SaveItem")
def on_save_item():
    app.widgetapp.save_item()

@action_handler("CopyItemURL")
def on_copy_item_url():
    app.widgetapp.copy_item_url()

@action_handler("EditPreferences")
def on_edit_preferences():
    app.widgetapp.preferences()

@action_handler("Quit")
def on_quit():
    app.widgetapp.quit()


# Feeds menu

@action_handler("NewFeed")
def on_new_feed():
    app.widgetapp.add_new_feed()

@action_handler("NewGuide")
def on_new_guidel():
    app.widgetapp.add_new_guide()

@action_handler("NewSearchFeed")
def on_new_search_feed():
    app.widgetapp.add_new_search_feed()

@action_handler("NewFeedFolder")
def on_new_feed_folder():
    app.widgetapp.add_new_feed_folder()

@action_handler("RenameFeed")
def on_rename_feed():
    app.widgetapp.rename_something()

@action_handler("RemoveFeeds")
def on_remove_feeds():
    app.widgetapp.remove_current_feed()

@action_handler("UpdateFeeds")
def on_update_feeds():
    app.widgetapp.update_selected_feeds()

@action_handler("UpdateAllFeeds")
def on_update_all_feeds():
    app.widgetapp.update_all_feeds()

@action_handler("ImportFeeds")
def on_import_feeds():
    app.widgetapp.import_feeds()

@action_handler("ExportFeeds")
def on_export_feeds():
    app.widgetapp.export_feeds()

@action_handler("ShareFeed")
def on_share_feed():
    app.widgetapp.share_feed()

@action_handler("CopyFeedURL")
def on_copy_feed_url():
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
    app.widgetapp.remove_current_playlist()

# Playback menu

@action_handler("PlayPauseVideo")
def on_play_pause_video():
    app.widgetapp.on_play_clicked()

@action_handler("StopVideo")
def on_play_pause_video():
    app.widgetapp.on_stop_clicked()

@action_handler("NextVideo")
def on_next_video():
    app.widgetapp.on_forward_clicked()

@action_handler("PreviousVideo")
def on_previous_video():
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

@action_handler("Fullscreen")
def on_fullscreen():
    app.widgetapp.on_fullscreen_clicked()

@action_handler("ToggleDetach")
def on_toggle_detach():
    app.widgetapp.on_toggle_detach_clicked()

# Help menu

@action_handler("About")
def on_about():
    app.widgetapp.about()

@action_handler("Donate")
def on_donate():
    app.widgetapp.open_url(config.get(prefs.DONATE_URL))

@action_handler("Help")
def on_help():
    app.widgetapp.open_url(config.get(prefs.HELP_URL))

@action_handler("Diagnostics")
def on_diagnostics():
    app.widgetapp.diagnostics()

@action_handler("ReportBug")
def on_report_bug():
    app.widgetapp.open_url(config.get(prefs.BUG_REPORT_URL))

@action_handler("Translate")
def on_translate():
    app.widgetapp.open_url(config.get(prefs.TRANSLATE_URL))

@action_handler("Planet")
def on_planet():
    app.widgetapp.open_url(config.get(prefs.PLANET_URL))

# action_group name -> list of MenuItem labels belonging to action_group
action_groups = {
    # group for items that should never be enabled
    'FakeGroup': [
        'NoneAvailable'
        ],
    'NonPlaying': [
        'Open',
        'NewDownload',
        'NewFeed',
        'NewGuide',
        'NewSearchFeed',
        'NewFeedFolder',
        'UpdateAllFeeds',
        'ImportFeeds',
        'ExportFeeds',
        'NewPlaylist',
        'NewPlaylistFolder',
        ],
    'FeedSelected': [
        'ShareFeed',
        'CopyFeedURL'
        ],
    'FeedOrFolderSelected': [
        'RenameFeed',
        ],
    'FeedsSelected': [
        'RemoveFeeds',
        'UpdateFeeds',
        ],
    'PlaylistSelected': [
        'RenamePlaylist',
        ],
    'PlaylistsSelected': [
        'RemovePlaylists',
        ],
    'PlayableSelected': [
        'RenameItem',
        'CopyItemURL',
        'SaveItem',
        ],
    'PlayablesSelected': [
        'RemoveItems',
        ],
    'PlayableVideosSelected': [
        ],
    'PlayPause': [
        'PlayPauseVideo',
        ],
    'Playing': [
        'StopVideo',
        'NextVideo',
        'PreviousVideo',
        'Rewind',
        'FastForward',
        ],
    'PlayingVideo': [
        'Fullscreen',
        'ToggleDetach',
        ],
    }

action_group_map = {}
def recompute_action_group_map():
    for group, actions in action_groups.items():
        for action in actions:
            if action not in action_group_map:
                action_group_map[action] = list()
            action_group_map[action].append(group)
recompute_action_group_map()

def action_group_names():
    return action_groups.keys() + ['AlwaysOn']

def get_action_group_name(action):
    return action_group_map.get(action, ['AlwaysOn'])[0]

def get_all_action_group_name(action):
    return action_group_map.get(action, ['AlwaysOn'])

class MenuManager(signals.SignalEmitter):
    """Updates the menu based on the current selection.

    This includes enabling/disabling menu items, changing menu text for plural
    selection and enabling/disabling the play button.  The play button is
    obviously not a menu item, but it's pretty closely related

    Whenever code makes a change that could possibly affect which menu items
    should be enabled/disabled, it should call the update_menus() method.
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('enabled-changed')
        self.enabled_groups = set(['AlwaysOn'])
        self.states = {}
        self.play_pause_state = "play"

    def reset(self):
        self.states = {"plural": [], "folder": [], "folders": []}
        self.enabled_groups = set(['AlwaysOn'])
        if app.playback_manager.is_playing:
            self.enabled_groups.add('PlayPause')
            self.enabled_groups.add('Playing')
            if not app.playback_manager.is_playing_audio:
                self.enabled_groups.add('PlayingVideo')
            if app.playback_manager.detached_window is not None:
                self.enabled_groups.add('NonPlaying')
        else:
            self.enabled_groups.add('NonPlaying')

    def _set_play_pause(self):
        if (not app.playback_manager.is_playing or
                app.playback_manager.is_paused):
            self.play_pause_state = 'play'
        else:
            self.play_pause_state = 'pause'

    def _handle_feed_selection(self, selected_feeds):
        """Handle the user selecting things in the feed list.  selected_feeds
        is a list of ChannelInfo objects
        """
        self.enabled_groups.add('FeedsSelected')
        if len(selected_feeds) == 1:
            if selected_feeds[0].is_folder:
                self.states["folder"].append("RemoveFeeds")
            else:
                self.enabled_groups.add('FeedSelected')
            self.enabled_groups.add('FeedOrFolderSelected')
        else:
            if len([s for s in selected_feeds if s.is_folder]) == len(selected_feeds):
                self.states["folders"].append("RemoveFeeds")
            else:
                self.states["plural"].append("RemoveFeeds")
            self.states["plural"].append("UpdateFeeds")

    def _handle_site_selection(self, selected_sites):
        """Handle the user selecting things in the site list.  selected_sites
        is a list of GuideInfo objects
        """
        pass # We don't change menu items for the site tab list

    def _handle_playlist_selection(self, selected_playlists):
        self.enabled_groups.add('PlaylistsSelected')
        if len(selected_playlists) == 1:
            if selected_playlists[0].is_folder:
                self.states["folder"].append("RemovePlaylists")
            self.enabled_groups.add('PlaylistSelected')
        else:
            if len([s for s in selected_playlists if s.is_folder]) == len(selected_playlists):
                self.states["folders"].append("RemovePlaylists")
            else:
                self.states["plural"].append("RemovePlaylists")

    def _handle_static_tab_selection(self, selected_static_tabs):
        """Handle the user selecting things in the static tab list.
        selected_sites is a list of GuideInfo objects
        """
        # we don't change menu items for the static tab list
        pass

    def _update_menus_for_selected_tabs(self):
        selection_type, selected_tabs = app.tab_list_manager.get_selection()
        if selection_type is None:
            pass
        elif selection_type in ('feed', 'audio-feed'):
            app.menu_manager._handle_feed_selection(selected_tabs)
        elif selection_type == 'playlist':
            app.menu_manager._handle_playlist_selection(selected_tabs)
        elif selection_type in ('static', 'library'):
            app.menu_manager._handle_static_tab_selection(selected_tabs)
        elif selection_type == 'site':
            app.menu_manager._handle_site_selection(selected_tabs)
        else:
            raise ValueError("Unknown tab list type: %s" % selection_type)

    def _update_menus_for_selected_items(self):
        """Update the menu items based on the current item list selection.
        """
        selected_items = app.item_list_controller_manager.get_selection()
        downloaded = False
        has_audio = False
        for item in selected_items:
            if item.downloaded:
                downloaded = True
            if item.file_type == 'audio':
                has_audio = True
        if downloaded:
            self.enabled_groups.add('PlayablesSelected')
            if not has_audio:
                self.enabled_groups.add('PlayableVideosSelected')
            if len(selected_items) == 1:
                self.enabled_groups.add('PlayableSelected')
            else:
                self.states["plural"].append("RemoveItems")

        if len(app.item_list_controller_manager.get_current_playlist()) > 0:
            self.enabled_groups.add('PlayPause')
            app.widgetapp.window.videobox.handle_new_selection(True)
        else:
            app.widgetapp.window.videobox.handle_new_selection(False)

    def update_menus(self):
        self.reset()
        self._update_menus_for_selected_tabs()
        self._update_menus_for_selected_items()
        self._set_play_pause()
        self.emit('enabled-changed')
