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

"""Application class.  Portable code to handle the high-level running of Miro.
"""

import os
import logging
import traceback
import urllib

from miro import app
from miro import autoupdate
from miro import config
from miro import prefs
from miro import feed
from miro import startup
from miro import signals
from miro import messages
from miro import eventloop
from miro.gtcache import gettext as _
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import newsearchchannel
from miro.frontends.widgets import diagnostics
from miro.frontends.widgets import prefpanel
from miro.frontends.widgets import displays
from miro.frontends.widgets import menus
from miro.frontends.widgets import tablistmanager
from miro.frontends.widgets import playback
from miro.frontends.widgets import search
from miro.frontends.widgets import rundialog
from miro.frontends.widgets.window import MiroWindow
from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.plat.frontends.widgets.widgetset import Rect

class Application:
    def __init__(self):
        app.widgetapp = self
        self.ignoreErrors = False
        self.message_handler = WidgetsMessageHandler()
        self.default_guide_info = None
        self.window = None
        messages.FrontendMessage.install_handler(self.message_handler)

    def startup(self):
        self.connect_to_signals()
        startup.startup()

    def startup_ui(self):
        # Send a couple messages to the backend, when we get responses,
        # WidgetsMessageHandler() will call build_window()
        messages.TrackGuides().send_to_backend()
        messages.QuerySearchInfo().send_to_backend()
        app.item_list_controller = None
        app.display_manager = displays.DisplayManager()
        app.menu_manager = menus.MenuManager()
        app.playback_manager = playback.PlaybackManager()
        app.search_manager = search.SearchManager()
        app.tab_list_manager = tablistmanager.TabListManager()
        self.window = MiroWindow(_("Miro"), self.get_main_window_dimensions())

        # FIXME - first-time startup somewhere around here

    def build_window(self):
        app.tab_list_manager.populate_tab_list()
        for info in self.message_handler.initial_guides:
            app.tab_list_manager.site_list.add(info)
        app.tab_list_manager.site_list.model_changed()
        app.tab_list_manager.handle_startup_selection()
        videobox = self.window.videobox
        videobox.volume_slider.set_value(config.get(prefs.VOLUME_LEVEL))
        videobox.volume_slider.connect('changed', self.on_volume_change)
        videobox.volume_slider.connect('released', self.on_volume_set)
        videobox.controls.play.connect('clicked', self.on_play_clicked)
        videobox.controls.stop.connect('clicked', self.on_stop_clicked)
        videobox.controls.forward.connect('clicked', self.on_forward_clicked)
        videobox.controls.forward.connect('held-down', self.on_fast_forward)
        videobox.controls.forward.connect('released', self.on_stop_fast_playback)
        videobox.controls.previous.connect('clicked', self.on_previous_clicked)
        videobox.controls.previous.connect('held-down', self.on_fast_backward)
        videobox.controls.previous.connect('released', self.on_stop_fast_playback)
        videobox.controls.fullscreen.connect('clicked', self.on_fullscreen_clicked)
        self.window.show()
        messages.TrackChannels().send_to_backend()
        messages.TrackPlaylists().send_to_backend()
        messages.TrackDownloadCount().send_to_backend()
        messages.TrackNewCount().send_to_backend()

    def get_main_window_dimensions(self):
        """Override this to provide platform-specific Main Window dimensions.

        Must return a Rect.
        """
        return Rect(100, 300, 800, 600)

    def on_volume_change(self, slider, volume):
        app.playback_manager.set_volume(volume)
        
    def on_volume_set(self, slider):
        config.set(prefs.VOLUME_LEVEL, slider.get_value())
        config.save()

    def on_play_clicked(self, button):
        if app.playback_manager.is_playing:
            app.playback_manager.play_pause()
        else:
            self.play_selection()

    def play_selection(self):
        if app.item_list_controller is not None:
            app.item_list_controller.play_selection()

    def on_stop_clicked(self, button):
        app.playback_manager.stop()

    def on_forward_clicked(self, button):
        app.playback_manager.play_next_movie()

    def on_previous_clicked(self, button):
        app.playback_manager.play_prev_movie()

    def on_fast_forward(self, button):
        app.playback_manager.set_playback_rate(3.0)

    def on_fast_backward(self, button):
        app.playback_manager.set_playback_rate(-3.0)

    def on_stop_fast_playback(self, button):
        app.playback_manager.set_playback_rate(1.0)

    def on_fullscreen_clicked(self, button):
        app.playback_manager.fullscreen()

    def next_video(self):
        pass

    def previous_video(self):
        pass

    def fast_forward(self):
        pass

    def rewind(self):
        psss

    def up_volume(self):
        pass

    def down_volume(self):
        pass

    def toggle_fullscreen(self):
        app.playback_manager.toggle_fullscreen()

    def open_video(self):
        title = _('Open Files...')
        # FIXME - should we list video types we know we can open?
        filename = dialogs.ask_for_open_pathname(title)

        if not filename:
            return

        if os.path.isfile(filename):
            # FIXME - play this file
            pass
        else:
            dialogs.show_message(_('Open Files... - Error'),
                                 _('File %s does not exist.') % filename)

    def ask_for_url(self, title, description, error_title, error_description):
        """Ask the user to enter a url in a TextEntry box.  
        
        If the URL the user enters is invalid, she will be asked to re-enter
        it again.  This process repeats until the user enters a valid URL, or
        clicks Cancel.

        The initial text for the TextEntry will be the clipboard contents (if
        it is a valid URL).
        """
        text = app.widgetapp.get_clipboard_text()
        if text is not None and feed.validateFeedURL(text):
            text = feed.normalizeFeedURL(text)
        else:
            text = ""
        while 1:
            text = dialogs.ask_for_string(title, description, initial_text=text)
            if text == None:
                return

            normalized_url = feed.normalizeFeedURL(text)
            if feed.validateFeedURL(normalized_url):
                return normalized_url

            title = error_title
            description = error_description

    def new_download(self):
        url = self.ask_for_url( _('New Download'),
                _('Enter the URL of the video to download'),
                _('New Download - Invalid URL'),
                _('The address you entered is not a valid url.\nPlease check the URL and try again.\n\nEnter the URL of the video to download'))
        if url is not None:
            messages.DownloadURL(url).send_to_backend()

    def _get_selected_items(self):
        if app.item_list_controller is None:
            return []
        else:
            return app.item_list_controller.get_selection()

    def preferences(self):
        prefpanel.run_dialog()

    def remove_videos(self):
        selection = self._get_selected_items()
        selection = [s for s in selection if s.downloaded]

        if not selection:
            return

        external_count = len([s for s in selection if s.is_external])
        total_count = len(selection)

        if len(selection) == 1:
            if external_count == 0:
                messages.DeleteVideo(selection[0].id).send_to_backend()
                return

            else:
                title = _('Remove %s') % selection[0].name
                description = _('Would you like to delete this file or just remove its entry from the Library?')
                ret = dialogs.show_choice_dialog(title, description,
                                                 [dialogs.BUTTON_REMOVE_ENTRY,
                                                  dialogs.BUTTON_DELETE_FILE,
                                                  dialogs.BUTTON_CANCEL])

        else:
            title = _('Removing %d items') % total_count
            if external_count > 0:
                description = _(
                    'One or more of these items was not downloaded from a channel. '
                    'Would you like to delete these items or just remove them from the Library?'
                )
                ret = dialogs.show_choice_dialog(title, description,
                                                 [dialogs.BUTTON_REMOVE_ENTRY,
                                                  dialogs.BUTTON_DELETE_FILE,
                                                  dialogs.BUTTON_CANCEL])

            else:
                description = _('Are you sure you want to delete all %d items?') % total_count
                ret = dialogs.show_choice_dialog(title, description,
                                                 [dialogs.BUTTON_DELETE,
                                                  dialogs.BUTTON_CANCEL])

        if ret in (dialogs.BUTTON_OK, dialogs.BUTTON_DELETE_FILE,
                dialogs.BUTTON_DELETE):
            for mem in selection:
                messages.DeleteVideo(mem.id).send_to_backend()

        elif ret == dialogs.BUTTON_REMOVE_ENTRY:
            for mem in selection:
                if mem.is_external:
                    messages.RemoveVideoEntry(mem.id).send_to_backend()
                else:
                    messages.DeleteVideo(mem.id).send_to_backend()

    def rename_video(self):
        selection = self._get_selected_items()
        selection = [s for s in selection if s.downloaded]

        if not selection:
            return

        video_item = selection[0]

        title = _('Rename Video')
        description = _('Enter the new name for the video')
        text = video_item.name

        name = dialogs.ask_for_string(title, description, initial_text=text)
        if name:
            messages.RenameVideo(video_item.id, name).send_to_backend()

    def save_video(self):
        selection = self._get_selected_items()
        selection = [s for s in selection if s.downloaded]

        if not selection:
            return

        title = _('Save Video As...')
        filename = selection[0].video_path
        filename = os.path.basename(filename)
        filename = dialogs.ask_for_save_pathname(title, filename)

        if not filename:
            return

        messages.SaveItemAs(selection[0].id, filename).send_to_backend()

    def copy_item_url(self):
        selection = self._get_selected_items()
        selection = [s for s in selection if s.downloaded]

        if not selection:
            return

        selection = selection[0]
        if selection.file_url:
            app.widgetapp.copy_text_to_clipboard(selection.file_url)

    def add_new_channel(self):
        url = self.ask_for_url(_('Add Channel'),
                _('Enter the URL of the channel to add'),
                _('Add Channel - Invalid URL'),
                _('The address you entered is not a valid url.\nPlease check the URL and try again.\n\nEnter the URL of the channel to add'))
        if url is not None:
            messages.NewChannel(url).send_to_backend()

    def add_new_search_channel(self):
        data = newsearchchannel.run_dialog()

        if not data:
            return

        if data[0] == "channel":
            messages.NewChannelSearchChannel(data[1], data[2]).send_to_backend()
        elif data[0] == "search_engine":
            messages.NewChannelSearchEngine(data[1], data[2]).send_to_backend()
        elif data[0] == "url":
            messages.NewChannelSearchURL(data[1], data[2]).send_to_backend()

    def add_new_channel_folder(self):
        title = _('Create Channel Folder')
        description = _('Enter a name for the new channel folder')

        name = dialogs.ask_for_string(title, description)
        if name:
            messages.NewChannelFolder(name).send_to_backend()

    def add_new_guide(self):
        url = self.ask_for_url(_('Add Guide'),
                _('Enter the URL of the Miro guide to add'),
                _('Add Guide - Invalid URL'),
                _('The address you entered is not a valid url.\nPlease check the URL and try again.\n\nEnter the URL of the Miro guide to add'))

        if url is not None:
            messages.NewGuide(url).send_to_backend()

    def remove_current_feed(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed':
            self.remove_feeds(channel_infos)

    def remove_feeds(self, channel_infos):
        # FIXME - this doesn't look right.  i would think we'd want to ask
        # a bunch of appropriate questions and then flip through the items
        # one by one.
        downloads = False
        downloading = False
        allDirectories = True
        for ci in channel_infos:
            if not ci.is_directory_feed:
                allDirectories = False
                if ci.unwatched > 0:
                    downloads = True
                    break
                if ci.has_downloading:
                    downloading = True

        if downloads:
            self.remove_feeds_with_downloads(channel_infos)
        elif downloading:
            self.remove_feeds_with_downloading(channel_infos)
        elif allDirectories:
            self.remove_directory_feeds(channel_infos)
        else:
            self.remove_feeds_normal(channel_infos)

    def remove_feeds_with_downloads(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Remove %s') % channel_infos[0].name
            description = _(
                 "What would you like to do with the videos in this channel that you've "
                 "downloaded?"
            )
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _(
                "What would you like to do with the videos in these channels that you've "
                "downloaded?"
            )

        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_KEEP_VIDEOS, 
                                          dialogs.BUTTON_DELETE_VIDEOS,
                                          dialogs.BUTTON_CANCEL])

        if ret == dialogs.BUTTON_KEEP_VIDEOS:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, True).send_to_backend()

        elif ret == dialogs.BUTTON_DELETE_VIDEOS:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def remove_feeds_with_downloading(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Remove %s') % channel_infos[0].name
            description = _(
                "Are you sure you want to remove %s?  Any downloads in progress will "
                "be canceled."
            ) % channel_infos[0].name
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _(
                "Are you sure you want to remove these %s channels?  Any downloads in "
                "progress will be canceled."
            ) % len(channel_infos)

        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_REMOVE, 
                                          dialogs.BUTTON_CANCEL])

        if ret == dialogs.BUTTON_REMOVE:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def remove_feeds_normal(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Remove %s') % channel_infos[0].name
            description = _(
                "Are you sure you want to remove %s?"
            ) % channel_infos[0].name
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _(
                "Are you sure you want to remove these %s channels?"
            ) % len(channel_infos)

        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_REMOVE, 
                                          dialogs.BUTTON_CANCEL])
        if ret == dialogs.BUTTON_REMOVE:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def remove_directory_feeds(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Stop watching %s') % channel_infos[0].name
            description = _(
                "Are you sure you want to stop watching %s?"
            ) % channel_infos[0].name
        else:
            title = _('Stop watching %s directories') % len(channel_infos)
            description = _(
                "Are you sure you want to stop watching these %s directories?"
            ) % len(channel_infos)
        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_STOP_WATCHING, 
                                          dialogs.BUTTON_CANCEL])
        if ret == dialogs.BUTTON_STOP_WATCHING:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def update_selected_channels(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed':
            channel_infos = [ci for ci in channel_infos if not ci.is_folder]
            for ci in channel_infos:
                messages.UpdateChannel(ci.id).send_to_backend()

    def update_all_channels(self):
        messages.UpdateAllChannels().send_to_backend()

    def import_channels(self):
        title = _('Import OPML File')
        filename = dialogs.ask_for_open_pathname(title,
                                      filters=[(_('OPML Files'), ['opml'])])
        if not filename:
            return

        if os.path.isfile(filename):
            messages.ImportChannels(filename).send_to_backend()
        else:
            dialogs.show_message(_('Import OPML File - Error'),
                                 _('File %s does not exist.') % filename)

    def export_channels(self):
        title = _('Export OPML File')
        filename = dialogs.ask_for_save_pathname(title, "miro_subscriptions.opml")

        if not filename:
            return

        messages.ExportChannels(filename).send_to_backend()

    def mail_channel(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed' and len(channel_infos) == 1:
            ci = channel_infos[0]
            query = urllib.urlencode({"url": ci.base_href, "title": ci.name})
            emailfriend_url = config.get(prefs.EMAILFRIEND_URL)
            if not emailfriend_url.endswith("?"):
                emailfriend_url += "?"
            app.widgetapp.open_url(emailfriend_url + query)

    def copy_channel_url(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed' and len(channel_infos) == 1:
            ci = channel_infos[0]
            app.widgetapp.copy_text_to_clipboard(ci.base_href)

    def copy_site_url(self):
        t, site_infos = app.tab_list_manager.get_selection()
        if t == 'site':
            app.widgetapp.copy_text_to_clipboard(site_infos[0].url)

    def add_new_playlist(self):
        selection = self._get_selected_items()
        ids = [s.id for s in selection if s.downloaded]

        title = _('Create Playlist')
        description = _('Enter a name for the new playlist')

        name = dialogs.ask_for_string(title, description)
        if name:
            messages.NewPlaylist(name, ids).send_to_backend()

    def add_new_playlist_folder(self):
        title = _('Create Playlist Folder')
        description = _('Enter a name for the new playlist folder')

        name = dialogs.ask_for_string(title, description)
        if name:
            messages.NewPlaylistFolder(name).send_to_backend()

    def rename_something(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        info = channel_infos[0]

        if t == 'feed' and info.is_folder:
            t = 'feed-folder'
        elif t == 'playlist' and info.is_folder:
            t = 'playlist-folder'

        if t == 'feed-folder':
            title = _('Rename Channel Folder')
            description = _('Enter a new name for the channel folder %s') % info.name

        elif t == 'feed' and not info.is_folder:
            title = _('Rename Channel')
            description = _('Enter a new name for the channel %s') % info.name

        elif t == 'playlist':
            title = _('Rename Playlist')
            description = _('Enter a new name for the playlist %s') % info.name

        elif t == 'playlist-folder':
            title = _('Rename Playlist Folder')
            description = _('Enter a new name for the playlist folder %s') % info.name
        elif t == 'site':
            title = _('Rename Site')
            description = _('Enter a new name for the site %s') % info.name

        else:
            raise AssertionError("Unknown tab type: %s" % t)

        name = dialogs.ask_for_string(title, description,
                                      initial_text=info.name)
        if name:
            messages.RenameObject(t, info.id, name).send_to_backend()

    def remove_current_playlist(self):
        t, infos = app.tab_list_manager.get_selection()
        if t == 'playlist':
            self.remove_playlists(infos)

    def remove_playlists(self, playlist_infos):
        if len(playlist_infos) == 1:
            title = _('Remove %s') % playlist_infos[0].name
            description = _('Are you sure you want to remove %s') % playlist_infos[0].name
        else:
            title = _('Remove %s playlists') % len(playlist_infos)
            description = _(
                'Are you sure you want to remove these %s playlists'
            ) % len(playlist_infos)

        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_REMOVE,
                                          dialogs.BUTTON_CANCEL])

        if ret == dialogs.BUTTON_REMOVE:
            for pi in playlist_infos:
                messages.DeletePlaylist(pi.id, pi.is_folder).send_to_backend()

    def remove_current_site(self):
        t, infos = app.tab_list_manager.get_selection()
        if t == 'site':
            info = infos[0] # Multiple guide selection is not allowed
            title = _('Remove %s') % info.name
            description = _('Are you sure you want to remove %s') % info.name
            ret = dialogs.show_choice_dialog(title, description,
                    [dialogs.BUTTON_REMOVE, dialogs.BUTTON_CANCEL])

            if ret == dialogs.BUTTON_REMOVE:
                messages.DeleteSite(info.id).send_to_backend()

    def quit_ui(self):
        """Quit  out of the UI event loop."""
        raise NotImplementedError()

    def about(self):
        dialogs.show_about()

    def diagnostics(self):
        diagnostics.run_dialog()

    def uiThreadFinished(self):
        """Called by the UI event thread when is finished processing and is
        about to exit. 
        """
        app.controller.onShutdown()

    def quit(self):
        # here we should should check if there are active downloads, etc.
        self.do_quit()

    def do_quit(self):
        if hasattr(self, 'window'):
            self.window.destroy()
        app.controller.shutdown()
        self.quit_ui()

    def connect_to_signals(self):
        signals.system.connect('error', self.handleError)
        signals.system.connect('download-complete', self.handleDownloadComplete)
        signals.system.connect('update-available', self.handle_update_available)
        signals.system.connect('startup-success', self.handleStartupSuccess)
        signals.system.connect('startup-failure', self.handleStartupFailure)
        signals.system.connect('new-dialog', self.handleDialog)
        signals.system.connect('shutdown', self.onBackendShutdown)

    def handleDialog(self, obj, dialog):
        call_on_ui_thread(rundialog.run, dialog)

    def handleStartupFailure(self, obj, summary, description):
        dialogs.show_message(summary, description)
        app.controller.shutdown()

    def handleStartupSuccess(self, obj):
        call_on_ui_thread(self.startup_ui)
        eventloop.addTimeout(3, autoupdate.check_for_updates, "Check for updates")

    def handleDownloadComplete(self, obj, item):
        print "DOWLOAD COMPLETE"

    def handle_update_available(self, obj, item):
        print "update available!"

    def handle_up_to_date(self):
        print "up to date!"

    def handleError(self, obj, report):
        # FIXME - I don't want to write the code in dialogs.py yet
        print 'INTERNAL ERROR:'
        print report
        return
        if self.ignoreErrors:
            logging.warn("Ignoring Error:\n%s", report)
            return

        def callback(dialog):
            if dialog.choice == dialogs.BUTTON_IGNORE:
                self.ignoreErrors = True
            else:
                app.controller.sendBugReport(report, dialog.textbox_value,
                        dialog.checkbox_value)

        chkboxdialog = dialogs.CheckboxTextboxDialog(_("Internal Error"), _("Miro has encountered an internal error. You can help us track down this problem and fix it by submitting an error report."), _("Include entire program database including all video and channel metadata with crash report"), False, _("Describe what you were doing that caused this error"), dialogs.BUTTON_SUBMIT_REPORT, dialogs.BUTTON_IGNORE)
        chkboxdialog.run(callback)

    def onBackendShutdown(self, obj):
        logging.info('Shutting down...')

class WidgetsMessageHandler(messages.MessageHandler):
    def __init__(self):
        messages.MessageHandler.__init__(self)
        # Messages that we need to see before the UI is ready
        self._pre_startup_messages = set([
            'guide-list',
            'search-info'
        ])

    def _saw_pre_startup_message(self, name):
        self._pre_startup_messages.remove(name)
        if len(self._pre_startup_messages) == 0:
            app.widgetapp.build_window()

    def call_handler(self, method, message):
        call_on_ui_thread(method, message)

    def handle_current_search_info(self, message):
        app.search_manager.set_search_info(message.engine, message.text)
        self._saw_pre_startup_message('search-info')

    def tablist_for_message(self, message):
        if message.type == 'feed':
            return app.tab_list_manager.feed_list
        elif message.type == 'playlist':
            return app.tab_list_manager.playlist_list
        elif message.type == 'guide':
            return app.tab_list_manager.site_list
        else:
            raise ValueError("Unknown Type: %s" % message.type)

    def handle_tab_list(self, message):
        tablist = self.tablist_for_message(message)
        for info in message.toplevels:
            tablist.add(info)
            if info.is_folder:
                for child_info in message.folder_children[info.id]:
                    tablist.add(child_info, info.id)
        tablist.model_changed()
        for info in message.toplevels:
            if info.is_folder:
                expanded = (info.id in message.expanded_folders)
                tablist.set_folder_expanded(info.id, expanded)

    def handle_guide_list(self, message):
        app.widgetapp.default_guide_info = message.default_guide
        self.initial_guides = message.added_guides
        self._saw_pre_startup_message('guide-list')

    def update_default_guide(self, guide_info):
        app.widgetapp.default_guide_info = guide_info
        guide_tab = app.tab_list_manager.static_tab_list.get_tab('guide')
        guide_tab.update(guide_info)

    def handle_tabs_changed(self, message):
        if message.type == 'guide':
            for info in list(message.changed):
                if info.default:
                    self.update_default_guide(info)
                    message.changed.remove(info)
                    break
        tablist = self.tablist_for_message(message)
        if message.removed:
            tablist.remove(message.removed)
        for info in message.changed:
            tablist.update(info)
        for info in message.added:
            tablist.add(info)
        tablist.model_changed()

    def handle_item_list(self, message):
        current_display = app.display_manager.current_display
        if isinstance(current_display, displays.ItemListDisplay):
            if current_display.controller.should_handle_message(message):
                current_display.controller.handle_item_list(message)
            else:
                logging.warn("wrong message for item controller (%s %s %s)",
                        message.type, message.id, current_display.controller)
        else:
            logging.warn("got item list, but display is: %s", current_display)

    def handle_items_changed(self, message):
        current_display = app.display_manager.current_display
        if isinstance(current_display, displays.ItemListDisplay):
            if current_display.controller.should_handle_message(message):
                current_display.controller.handle_items_changed(message)
            else:
                logging.warn("wrong message for item controller (%s %s %s)",
                        message.type, message.id, current_display.controller)
        else:
            logging.warn("got item list, but display is: %s", current_display)

    def handle_download_count_changed(self, message):
        static_tab_list = app.tab_list_manager.static_tab_list
        static_tab_list.update_download_count(message.count)

    def handle_new_count_changed(self, message):
        static_tab_list = app.tab_list_manager.static_tab_list
        static_tab_list.update_new_count(message.count)
