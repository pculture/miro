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
import urllib

from miro import app
from miro import config
from miro import prefs
from miro import feed
from miro import startup
from miro import signals
from miro import messages
from miro import eventloop
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import newsearchchannel
from miro.frontends.widgets import removechannelsdialog
from miro.frontends.widgets import diagnostics
from miro.frontends.widgets import crashdialog
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import prefpanel
from miro.frontends.widgets import displays
from miro.frontends.widgets import menus
from miro.frontends.widgets import tablistmanager
from miro.frontends.widgets import playback
from miro.frontends.widgets import search
from miro.frontends.widgets import rundialog
from miro.frontends.widgets import watchedfolders
from miro.frontends.widgets import quitwhiledownloading
from miro.frontends.widgets import firsttimedialog
from miro.frontends.widgets.window import MiroWindow
from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.plat.frontends.widgets.widgetset import Rect

class Application:
    def __init__(self):
        app.widgetapp = self
        self.ignore_errors = False
        self.message_handler = WidgetsMessageHandler()
        self.default_guide_info = None
        self.window = None
        self.ui_initialized = False
        messages.FrontendMessage.install_handler(self.message_handler)
        app.info_updater = InfoUpdater()
        app.watched_folder_manager = watchedfolders.WatchedFolderManager()
        self.download_count = 0
        self.paused_count = 0
        self.unwatched_count = 0

    def startup(self):
        self.connect_to_signals()
        startup.install_movies_directory_gone_handler(self.handle_movies_gone)
        startup.install_first_time_handler(self.handle_first_time)
        startup.startup()

    def startup_ui(self):
        # Send a couple messages to the backend, when we get responses,
        # WidgetsMessageHandler() will call build_window()
        messages.TrackGuides().send_to_backend()
        messages.QuerySearchInfo().send_to_backend()
        messages.TrackWatchedFolders().send_to_backend()

        app.item_list_controller_manager = \
                itemlistcontroller.ItemListControllerManager()
        app.display_manager = displays.DisplayManager()
        app.menu_manager = menus.MenuManager()
        app.playback_manager = playback.PlaybackManager()
        app.search_manager = search.SearchManager()
        app.inline_search_memory = search.InlineSearchMemory()
        app.tab_list_manager = tablistmanager.TabListManager()
        self.ui_initialized = True

        self.window = MiroWindow(config.get(prefs.LONG_APP_NAME),
                                 self.get_main_window_dimensions())

    def handle_movies_gone(self, continue_callback):
        call_on_ui_thread(lambda: self.__handle_movies_gone(continue_callback))

    def __handle_movies_gone(self, continue_callback):
        title = _("Movies directory gone")
        description = _(
            "%(shortappname)s can't find the primary video directory "
            "located at:\n"
            "\n"
            "%(moviedirectory)s\n"
            "\n"
            "This may be because it is located on an external drive that "
            "is not connected.\n"
            "\n"
            "If you continue, the primary video directory will be reset "
            "to a location on this drive.  If you had videos downloaded "
            "this will cause %(shortappname)s to lose details about those "
            "videos.\n"
            "\n"
            "If you quit, then you can connect the drive or otherwise "
            "fix the problem and relaunch %(shortappname)s.",
            {"shortappname": config.get(prefs.SHORT_APP_NAME),
             "moviedirectory": config.get(prefs.MOVIES_DIRECTORY)}
        )
        ret = dialogs.show_choice_dialog(title, description,
                [dialogs.BUTTON_CONTINUE, dialogs.BUTTON_QUIT])

        if ret == dialogs.BUTTON_QUIT:
            self.do_quit()
            return

        continue_callback()

    def handle_first_time(self, continue_callback):
        call_on_ui_thread(lambda: self.__handle_first_time(continue_callback))

    def __handle_first_time(self, continue_callback):
        startup.mark_first_time()
        firsttimedialog.FirstTimeDialog(continue_callback).run()

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
        messages.TrackPausedCount().send_to_backend()
        messages.TrackNewCount().send_to_backend()
        messages.TrackUnwatchedCount().send_to_backend()

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

    def on_play_clicked(self, button=None):
        if app.playback_manager.is_playing:
            app.playback_manager.play_pause()
        else:
            self.play_selection()

    def play_selection(self):
        app.item_list_controller_manager.play_selection()

    def on_stop_clicked(self, button=None):
        app.playback_manager.stop()

    def on_forward_clicked(self, button=None):
        app.playback_manager.play_next_movie()

    def on_previous_clicked(self, button=None):
        app.playback_manager.play_prev_movie()

    def on_skip_forward(self):
        app.playback_manager.skip_forward()

    def on_skip_backward(self):
        app.playback_manager.skip_backward()

    def on_fast_forward(self, button=None):
        app.playback_manager.set_playback_rate(3.0)

    def on_fast_backward(self, button=None):
        app.playback_manager.set_playback_rate(-3.0)

    def on_stop_fast_playback(self, button):
        app.playback_manager.set_playback_rate(1.0)

    def on_fullscreen_clicked(self, button=None):
        app.playback_manager.fullscreen()

    def on_toggle_detach_clicked(self, button=None):
        app.playback_manager.toggle_detached_mode()

    def up_volume(self):
        slider = self.window.videobox.volume_slider
        v = min(slider.get_value() + 0.05, 1.0)
        slider.set_value(v)
        self.on_volume_change(slider, v)
        self.on_volume_set(slider)

    def down_volume(self):
        slider = self.window.videobox.volume_slider
        v = max(slider.get_value() - 0.05, 0.0)
        slider.set_value(v)
        self.on_volume_change(slider, v)
        self.on_volume_set(slider)

    def open_video(self):
        title = _('Open Files...')
        filenames = dialogs.ask_for_open_pathname(title, select_multiple=True)

        if not filenames:
            return

        filenames_good = [mem for mem in filenames if os.path.isfile(mem)]
        if len(filenames_good) != len(filenames):
            filenames_bad = set(filenames) - set(filenames_good)
            if len(filenames_bad) == 1:
                filename = list(filenames_bad)[0]
                dialogs.show_message(_('Open Files - Error'),
                                     _('File %(filename)s does not exist.',
                                       {"filename": filename}),
                                     dialogs.WARNING_MESSAGE)
            else:
                dialogs.show_message(_('Open Files - Error'),
                                    _('The following files do not exist:') +
                                    '\n' + '\n'.join(filenames_bad),
                                     dialogs.WARNING_MESSAGE)
        else:
            if len(filenames_good) == 1:
                messages.OpenIndividualFile(filenames_good[0]).send_to_backend()
            else:
                messages.OpenIndividualFiles(filenames_good).send_to_backend()

    def ask_for_url(self, title, description, error_title, error_description):
        """Ask the user to enter a url in a TextEntry box.

        If the URL the user enters is invalid, she will be asked to re-enter
        it again.  This process repeats until the user enters a valid URL, or
        clicks Cancel.

        The initial text for the TextEntry will be the clipboard contents (if
        it is a valid URL).
        """
        text = app.widgetapp.get_clipboard_text()
        if text is not None and feed.validate_feed_url(text):
            text = feed.normalize_feed_url(text)
        else:
            text = ""
        while 1:
            text = dialogs.ask_for_string(title, description, initial_text=text)
            if text == None:
                return

            normalized_url = feed.normalize_feed_url(text)
            if feed.validate_feed_url(normalized_url):
                return normalized_url

            title = error_title
            description = error_description

    def new_download(self):
        url = self.ask_for_url( _('New Download'),
                _('Enter the URL of the item to download'),
                _('New Download - Invalid URL'),
                _('The address you entered is not a valid url.\nPlease check the URL and try again.\n\nEnter the URL of the item to download'))
        if url is not None:
            messages.DownloadURL(url).send_to_backend()

    def check_version(self):
        # this gets called by the backend, so it has to send a message to
        # the frontend to open a dialog
        def up_to_date_callback():
            messages.MessageToUser(_("Miro is up to date"),
                                   _("Miro is up to date!")).send_to_frontend()

        messages.CheckVersion(up_to_date_callback).send_to_backend()

    def preferences(self):
        prefpanel.show_window()

    def remove_items(self, selection=None):
        if not selection:
            selection = app.item_list_controller_manager.get_selection()
            selection = [s for s in selection if s.downloaded]

            if not selection:
                return

        external_count = len([s for s in selection if s.is_external])
        total_count = len(selection)

        if total_count == 1 and external_count == 0:
            messages.DeleteVideo(selection[0].id).send_to_backend()
            return

        title = ngettext('Remove %(name)s',
                         'Remove %(count)d items',
                         total_count,
                         {"count": total_count, "name": selection[0].name})

        if external_count > 0:
            description = ngettext(
                'One of these items was not downloaded from a channel. '
                'Would you like to delete it or just remove it from the Library?',

                'Some of these items were not downloaded from a channel. '
                'Would you like to delete them or just remove them from the Library?',

                external_count
            )
            ret = dialogs.show_choice_dialog(title, description,
                                             [dialogs.BUTTON_REMOVE_ENTRY,
                                              dialogs.BUTTON_DELETE_FILE,
                                              dialogs.BUTTON_CANCEL])

        else:
            description = ngettext(
                'Are you sure you want to delete the item?',
                'Are you sure you want to delete all %(count)d items?',
                total_count,
                {"count": total_count}
            )
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

    def rename_item(self):
        selection = app.item_list_controller_manager.get_selection()
        selection = [s for s in selection if s.downloaded]

        if not selection:
            return

        item_info = selection[0]

        title = _('Rename Item')
        description = _('Enter the new name for the item')
        text = item_info.name

        name = dialogs.ask_for_string(title, description, initial_text=text)
        if name:
            messages.RenameVideo(item_info.id, name).send_to_backend()

    def save_item(self):
        selection = app.item_list_controller_manager.get_selection()
        selection = [s for s in selection if s.downloaded]

        if not selection:
            return

        title = _('Save Item As...')
        filename = selection[0].video_path
        filename = os.path.basename(filename)
        filename = dialogs.ask_for_save_pathname(title, filename)

        if not filename:
            return

        messages.SaveItemAs(selection[0].id, filename).send_to_backend()

    def copy_item_url(self):
        selection = app.item_list_controller_manager.get_selection()
        selection = [s for s in selection if s.downloaded]

        if not selection and app.playback_manager.is_playing:
            selection = [app.playback_manager.get_playing_item()]

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

    def add_new_channel_folder(self, add_selected=False):
        title = _('Create Channel Folder')
        description = _('Enter a name for the new channel folder')

        name = dialogs.ask_for_string(title, description)
        if name:
            if add_selected:
                t, infos = app.tab_list_manager.get_selection()
                child_ids = [info.id for info in infos]
            else:
                child_ids = None
            messages.NewChannelFolder(name, child_ids).send_to_backend()

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
        watched_feeds = False
        downloaded_items = False
        downloading_items = False

        for ci in channel_infos:
            if not ci.is_directory_feed:
                if ci.num_downloaded > 0:
                    downloaded_items = True

                if ci.has_downloading:
                    downloading_items = True
            else:
                watched_feeds = True

        ret = removechannelsdialog.run_dialog(channel_infos, downloaded_items,
                downloading_items, watched_feeds)
        if ret:
            for ci in channel_infos:
                if ci.is_directory_feed:
                    if ret[removechannelsdialog.STOP_WATCHING]:
                        messages.SetWatchedFolderVisible(ci.id, False).send_to_backend()
                else:
                    messages.DeleteChannel(ci.id, ci.is_folder,
                        ret[removechannelsdialog.KEEP_ITEMS]
                    ).send_to_backend()

    def update_selected_channels(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed':
            for ci in channel_infos:
                if ci.is_folder:
                    messages.UpdateChannelFolder(ci.id).send_to_backend()
                else:
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
                                 _('File %(filename)s does not exist.',
                                   {"filename": filename}),
                                 dialogs.WARNING_MESSAGE)

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
            self.mail_to_friend(ci.base_href, ci.name)

    def mail_to_friend(self, url, title):
        emailfriend_url = config.get(prefs.EMAILFRIEND_URL)
        if not emailfriend_url.endswith("?"):
            emailfriend_url += "?"
        query = urllib.urlencode({"url": url, "title": title})
        app.widgetapp.open_url(emailfriend_url + query)

    def copy_channel_url(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed' and len(channel_infos) == 1:
            app.widgetapp.copy_text_to_clipboard(channel_infos[0].base_href)

    def copy_site_url(self):
        t, site_infos = app.tab_list_manager.get_selection()
        if t == 'site':
            app.widgetapp.copy_text_to_clipboard(site_infos[0].url)

    def add_new_playlist(self):
        selection = app.item_list_controller_manager.get_selection()
        ids = [s.id for s in selection if s.downloaded]

        title = _('Create Playlist')
        description = _('Enter a name for the new playlist')

        name = dialogs.ask_for_string(title, description)
        if name:
            messages.NewPlaylist(name, ids).send_to_backend()

    def add_new_playlist_folder(self, add_selected=False):
        title = _('Create Playlist Folder')
        description = _('Enter a name for the new playlist folder')

        name = dialogs.ask_for_string(title, description)
        if name:
            if add_selected:
                t, infos = app.tab_list_manager.get_selection()
                child_ids = [info.id for info in infos]
            else:
                child_ids = None
            messages.NewPlaylistFolder(name, child_ids).send_to_backend()

    def rename_something(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        info = channel_infos[0]

        if t == 'feed' and info.is_folder:
            t = 'feed-folder'
        elif t == 'playlist' and info.is_folder:
            t = 'playlist-folder'

        if t == 'feed-folder':
            title = _('Rename Channel Folder')
            description = _('Enter a new name for the channel folder %(name)s',
                            {"name": info.name})

        elif t == 'feed' and not info.is_folder:
            title = _('Rename Channel')
            description = _('Enter a new name for the channel %(name)s',
                            {"name": info.name})

        elif t == 'playlist':
            title = _('Rename Playlist')
            description = _('Enter a new name for the playlist %(name)s',
                            {"name": info.name})

        elif t == 'playlist-folder':
            title = _('Rename Playlist Folder')
            description = _('Enter a new name for the playlist folder %(name)s',
                            {"name": info.name})
        elif t == 'site':
            title = _('Rename Site')
            description = _('Enter a new name for the site %(name)s',
                            {"name": info.name})

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
        title = ngettext('Remove playlist',
                         'Remove %(count)d playlists',
                         len(playlist_infos),
                         {"count": len(playlist_infos)})
        description = ngettext(
            'Are you sure you want to remove %(name)s?',
            'Are you sure you want to remove these %(count)s playlists?',
            len(playlist_infos),
            {"count": len(playlist_infos), "name": playlist_infos[0].name}
            )

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
            title = _('Remove %(name)s', {"name": info.name})
            description = _('Are you sure you want to remove %(name)s?',
                            {"name": info.name})
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

    def on_close(self):
        """This is called when the close button is pressed."""
        self.quit()

    def quit(self):
        if config.get(prefs.WARN_IF_DOWNLOADING_ON_QUIT) and self.download_count > 0:
            ret = quitwhiledownloading.rundialog(
                _("Are you sure you want to quit?"),
                ngettext(
                    "You have 1 download in progress.  Quit anyway?",
                    "You have %(count)d downloads in progress.  Quit anyway?",
                    self.download_count,
                    {"count": self.download_count}
                ),
                _("Warn me when I attempt to quit with downloads in progress")
            )
            if ret:
                self.do_quit()
        else:
            self.do_quit()

    def do_quit(self):
        if self.window is not None:
            self.window.close()
        if self.ui_initialized:
            if app.playback_manager.is_playing:
                app.playback_manager.stop()
            app.display_manager.deselect_all_displays()
        if self.window is not None:
            self.window.destroy()
        app.controller.shutdown()
        self.quit_ui()

    def connect_to_signals(self):
        signals.system.connect('error', self.handle_error)
        signals.system.connect('download-complete', self.handle_download_complete)
        signals.system.connect('update-available', self.handle_update_available)
        signals.system.connect('new-dialog', self.handle_dialog)
        signals.system.connect('shutdown', self.on_backend_shutdown)

    def handle_dialog(self, obj, dialog):
        call_on_ui_thread(rundialog.run, dialog)

    def handle_download_complete(self, obj, item):
        print "FIXME - DOWLOAD COMPLETE"

    def handle_update_available(self, obj, item):
        print "FIXME - update available!"

    def handle_up_to_date(self):
        print "FIXME - up to date!"

    def handle_error(self, obj, report):
        call_on_ui_thread(self.__handle_error, obj, report)

    def __handle_error(self, obj, report):
        if self.ignore_errors:
            logging.warn("Ignoring Error:\n%s", report)
            return

        ret = crashdialog.run_dialog(obj, report)
        if ret == crashdialog.IGNORE_ERRORS:
            self.ignore_errors = True

    def on_backend_shutdown(self, obj):
        logging.info('Shutting down...')

class InfoUpdater(signals.SignalEmitter):
    """Emits signals when we get channel/item updates from the backend.

    Signals:

        items-added (self, info_list) -- New items were added
        items-changed (self, info_list) -- Items were changed
        items-removed (self, info_list) -- Items were removed
        feeds-added (self, info_list) -- New feeds were added
        feeds-changed (self, info_list) -- Feeds were changed
        feeds-removed (self, info_list) -- Feeds were removed
        sites-added (self, info_list) -- New sites were added
        sites-changed (self, info_list) -- Sites were changed
        sites-removed (self, info_list) -- Sites were removed
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('items-added')
        self.create_signal('items-changed')
        self.create_signal('items-removed')
        self.create_signal('feeds-added')
        self.create_signal('feeds-changed')
        self.create_signal('feeds-removed')
        self.create_signal('sites-added')
        self.create_signal('sites-changed')
        self.create_signal('sites-removed')

    def handle_items_changed(self, message):
        if message.added:
            self.emit('items-added', message.added)
        if message.changed:
            self.emit('items-changed', message.changed)
        if message.removed:
            self.emit('items-removed', message.removed)

    def handle_tabs_changed(self, message):
        if message.type == 'feed':
            signal_start = 'feeds'
        elif message.type == 'guide':
            signal_start = 'sites'
        else:
            return
        if message.added:
            self.emit('%s-added' % signal_start, message.added)
        if message.changed:
            self.emit('%s-changed' % signal_start, message.changed)
        if message.removed:
            self.emit('%s-removed' % signal_start, message.removed)

class WidgetsMessageHandler(messages.MessageHandler):
    def __init__(self):
        messages.MessageHandler.__init__(self)
        # Messages that we need to see before the UI is ready
        self._pre_startup_messages = set([
            'guide-list',
            'search-info'
        ])

    def handle_startup_failure(self, message):
        dialogs.show_message(message.summary, message.description,
                dialogs.CRITICAL_MESSAGE)
        app.widgetapp.do_quit()

    def handle_startup_success(self, message):
        app.widgetapp.startup_ui()

    def _saw_pre_startup_message(self, name):
        self._pre_startup_messages.remove(name)
        if len(self._pre_startup_messages) == 0:
            app.widgetapp.build_window()

    def call_handler(self, method, message):
        # uncomment this next line if you need frontend messages
        # logging.debug("handling frontend %s", message)
        call_on_ui_thread(method, message)

    def handle_current_search_info(self, message):
        app.search_manager.set_search_info(message.engine, message.text)
        self._saw_pre_startup_message('search-info')

    def tablist_for_message(self, message):
        if message.type == 'feed':
            return app.tab_list_manager.feed_list
        elif message.type == 'audio-feed':
            return app.tab_list_manager.audio_feed_list
        elif message.type == 'playlist':
            return app.tab_list_manager.playlist_list
        elif message.type == 'guide':
            return app.tab_list_manager.site_list
        else:
            raise ValueError("Unknown Type: %s" % message.type)

    def handle_tab_list(self, message):
        tablist = self.tablist_for_message(message)
        tablist.reset_list(message)

    def handle_guide_list(self, message):
        app.widgetapp.default_guide_info = message.default_guide
        self.initial_guides = message.added_guides
        self._saw_pre_startup_message('guide-list')

    def update_default_guide(self, guide_info):
        app.widgetapp.default_guide_info = guide_info
        guide_tab = app.tab_list_manager.static_tab_list.get_tab('guide')
        guide_tab.update(guide_info)

    def handle_watched_folder_list(self, message):
        app.watched_folder_manager.handle_watched_folder_list(
                message.watched_folders)

    def handle_watched_folders_changed(self, message):
        app.watched_folder_manager.handle_watched_folders_changed(
                message.added, message.changed, message.removed)

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
            # some things don't have parents (e.g. sites)
            if hasattr(info, "parent_id"):
                tablist.add(info, info.parent_id)
            else:
                tablist.add(info)
        tablist.model_changed()
        app.info_updater.handle_tabs_changed(message)

    def handle_item_list(self, message):
        app.item_list_controller_manager.handle_item_list(message)

    def handle_items_changed(self, message):
        app.item_list_controller_manager.handle_items_changed(message)
        app.info_updater.handle_items_changed(message)

    def handle_download_count_changed(self, message):
        app.widgetapp.download_count = message.count
        static_tab_list = app.tab_list_manager.static_tab_list
        static_tab_list.update_download_count(message.count)

    def handle_paused_count_changed(self, message):
        app.widgetapp.paused_count = message.count

    def handle_new_count_changed(self, message):
        static_tab_list = app.tab_list_manager.static_tab_list
        static_tab_list.update_new_count(message.count)

    def handle_unwatched_count_changed(self, message):
        app.widgetapp.unwatched_count = message.count

    def handle_play_movie(self, message):
        app.playback_manager.start_with_items(message.item_infos)

    def handle_message_to_user(self, message):
        title = message.title or _("Message")
        desc = message.desc
        print "handle_message_to_user"
        dialogs.show_message(title, desc)

    def handle_notify_user(self, message):
        # if the user has selected that they aren't interested in this
        # notification type, return here...

        # otherwise, we default to sending the notification
        app.widgetapp.send_notification(message.title, message.body)

    def handle_search_complete(self, message):
        app.search_manager.handle_search_complete(message)
