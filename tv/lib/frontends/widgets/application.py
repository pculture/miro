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

"""``miro.frontends.widgets.application`` -- The application module
holds :class:`Application` and the portable code to handle the high
level running of the Miro application.

It also holds:

* :class:`WidgetsMessageHandler` -- frontend message handler
* :class:`DisplayStateStore` -- stores state of each display
"""

import cProfile
import gc
import os
import logging
import sys
import urllib

from miro import app
from miro import config
from miro import crashreport
from miro import data
from miro import prefs
from miro import feed
from miro import startup
from miro import signals
from miro import messages
from miro import eventloop
from miro import conversions
from miro import filetypes
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import infoupdater
from miro.frontends.widgets import newsearchfeed
from miro.frontends.widgets import newfeed
from miro.frontends.widgets import newfolder
from miro.frontends.widgets import newwatchedfolder
from miro.frontends.widgets import itemedit
from miro.frontends.widgets import addtoplaylistdialog
from miro.frontends.widgets import searchfilesdialog
from miro.frontends.widgets import removefeeds
from miro.frontends.widgets import diagnostics
from miro.frontends.widgets import crashdialog
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import prefpanel
from miro.frontends.widgets import displays
from miro.frontends.widgets import menus
from miro.frontends.widgets import tablistmanager
from miro.frontends.widgets import playback
from miro.frontends.widgets import search
from miro.frontends.widgets import rundialog
from miro.frontends.widgets import watchedfolders
from miro.frontends.widgets import stores
from miro.frontends.widgets import quitconfirmation
from miro.frontends.widgets import firsttimedialog
from miro.frontends.widgets import feedsettingspanel
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.frontends.widgets.window import MiroWindow
from miro.plat.utils import get_plat_media_player_name_path
from miro.plat import resources
from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.plat.frontends.widgets import widgetset
from miro import fileutil

class Application:
    """This class holds the portable application code.  Each platform
    extends this class with a platform-specific version.
    """
    def __init__(self):
        app.widgetapp = self
        self.ignore_errors = False
        self.message_handler = WidgetsMessageHandler()
        self.window = None
        self.ui_initialized = False
        messages.FrontendMessage.install_handler(self.message_handler)
        app.item_list_pool = itemlist.ItemListPool()
        app.item_tracker_updater = itemlist.ItemTrackerUpdater()
        app.info_updater = infoupdater.InfoUpdater()
        app.saved_items = set()
        app.watched_folder_manager = watchedfolders.WatchedFolderManager()
        app.store_manager = stores.StoreManager()
        self.download_count = 0
        self.paused_count = 0
        self.unwatched_count = 0
        app.frontend_config_watcher = config.ConfigWatcher(call_on_ui_thread)
        self.crash_reports_to_handle = []
        app.widget_state = WidgetStateStore()

    def exception_handler(self, typ, value, traceback):
        report = crashreport.format_crash_report("in frontend thread",
            exc_info=(typ, value, traceback), details=None)
        # we might be inside of some UI function where we can't run a dialog
        # box.  For example cell renderers on GTK.  Use call_on_ui_thread() to
        # get a fresh main loop iteration.
        call_on_ui_thread(lambda: self.handle_crash_report(report))

    def handle_soft_failure(self, when, details, with_exception):
        if app.debugmode:
            if with_exception:
                exc_info = sys.exc_info()
            else:
                exc_info = None
            report = crashreport.format_crash_report(when, exc_info, details)
            self.handle_crash_report(report)
        else:
            crashreport.issue_failure_warning(when, details, with_exception)

    def startup(self):
        """Connects to signals, installs handlers, and calls :meth:`startup`
        from the :mod:`miro.startup` module.
        """
        app.frontend = WidgetsFrontend()
        self.connect_to_signals()
        startup.install_movies_directory_gone_handler(self.handle_movies_directory_gone)
        startup.install_first_time_handler(self.handle_first_time)
        startup.startup()

    def startup_ui(self):
        """Starts up the widget ui by sending a bunch of messages
        requesting data from the backend.  Also sets up managers,
        initializes the ui, and displays the :class:`MiroWindow`.
        """
        data.init()
        # Send a couple messages to the backend, when we get responses,
        # WidgetsMessageHandler() will call build_window()
        messages.TrackGuides().send_to_backend()
        messages.QuerySearchInfo().send_to_backend()
        messages.TrackWatchedFolders().send_to_backend()
        messages.QueryDisplayStates().send_to_backend()
        messages.QueryViewStates().send_to_backend()
        messages.QueryGlobalState().send_to_backend()
        messages.TrackChannels().send_to_backend()

        self.setup_globals()
        self.ui_initialized = True

        title = app.config.get(prefs.LONG_APP_NAME)
        if app.debugmode:
            title += ' (%s - %s)' % (app.config.get(prefs.APP_VERSION),
                                     app.config.get(prefs.APP_REVISION_NUM))
        self.window = MiroWindow(title, self.get_main_window_dimensions())
        self.window.connect_weak('key-press', self.on_key_press)
        self.window.connect_weak('on-shown', self.on_shown)
        self._window_show_callback = self.window.connect_weak('show',
                self.on_window_show)

    def setup_globals(self):
        app.item_list_controller_manager = \
                itemlistcontroller.ItemListControllerManager()
        app.playback_manager = playback.PlaybackManager()
        app.menu_manager = menus.MenuManager()
        app.menu_manager.setup_menubar(self.menubar)
        app.search_manager = search.SearchManager()
        app.inline_search_memory = search.InlineSearchMemory()
        app.tabs = tablistmanager.TabListManager()

    def on_config_changed(self, obj, key, value):
        """Any time a preference changes, this gets notified so that we
        can adjust things.
        """
        raise NotImplementedError()

    def on_window_show(self, window):
        m = messages.FrontendStarted()
        # Use call_on_ui_thread to introduce a bit of a delay.  On GTK it uses
        # gobject.add_idle(), so it won't run until the GUI processing is
        # idle.  I'm (BDK) not sure what happens on Cocoa, but it's worth a
        # try there as well.
        call_on_ui_thread(m.send_to_backend)
        self.window.disconnect(self._window_show_callback)
        del self._window_show_callback

    def on_shown(self, widget):
        """Called after the window has been shown (later than on_window_show).
        This is useful for e.g. restoring a saved selection, which is overridden
        by the default first-row selection if done too early.
        """
        app.startup_timer.log_time("window shown")
        app.startup_timer.log_total_time()
        logging.debug('on_shown')
        app.tabs.on_shown()

    def on_key_press(self, window, key, mods):
        if app.playback_manager.is_playing:
            return playback.handle_key_press(key, mods)

    def handle_movies_directory_gone(self, msg, movies_dir,
                                     allow_continue=False):
        call_on_ui_thread(self._handle_movies_directory_gone, msg, movies_dir,
                          allow_continue)

    def _handle_movies_directory_gone(self, msg, movies_dir, allow_continue):
        # Make sure we close the upgrade dialog before showing a new one
        self.message_handler.close_upgrade_dialog()

        title = _("Movies folder gone")
        description = _(
            "%(shortappname)s can't use your primary video folder, which "
            "is currently set to:\n"
            "\n"
            "%(moviedirectory)s\n"
            "\n"
            "%(reason)s\n"
            "\n",
            {"shortappname": app.config.get(prefs.SHORT_APP_NAME),
             "moviedirectory": movies_dir,
             "reason":msg,
            })
        if allow_continue:
            description += _(
                "You may continue with the current folder, choose a new "
                "folder or quit and try to fix the issue manually.")
            buttons = [
                dialogs.BUTTON_CONTINUE,
                dialogs.BUTTON_CHOOSE_NEW_FOLDER,
                dialogs.BUTTON_QUIT
            ]
        else:
            description += _(
                "You choose a new folder or quit and try to fix the issue "
                "manually.")
            buttons = [
                dialogs.BUTTON_CHOOSE_NEW_FOLDER,
                dialogs.BUTTON_QUIT
            ]
        choice = dialogs.show_choice_dialog(title, description, buttons)
        if choice == dialogs.BUTTON_CONTINUE:
            startup.fix_movies_gone(None)
            return
        elif choice == dialogs.BUTTON_CHOOSE_NEW_FOLDER:
            title = _("Choose new primary video folder")
            new_movies_dir = dialogs.ask_for_directory(title, movies_dir)
            if new_movies_dir is not None:
                startup.fix_movies_gone(new_movies_dir)
                return
        self.do_quit()

    def handle_first_time(self, continue_callback):
        call_on_ui_thread(lambda: self._handle_first_time(continue_callback))

    def _handle_first_time(self, continue_callback):
        # handle very weird condition where the user upgraded their DB and was
        # shown the first time dialog.  #16383, comment #9.
        self.message_handler.close_upgrade_dialog()
        startup.mark_first_time()
        firsttimedialog.FirstTimeDialog(continue_callback).run()

    def build_window(self):
        app.startup_timer.log_time("in build_window")
        app.display_manager = displays.DisplayManager()
        app.tabs['site'].extend(self.message_handler.initial_guides)
        app.tabs['store'].extend(self.message_handler.initial_stores)
        videobox = self.window.videobox
        videobox.volume_slider.set_value(app.config.get(prefs.VOLUME_LEVEL))
        videobox.volume_slider.connect('changed', self.on_volume_change)
        videobox.volume_slider.connect('released', self.on_volume_set)
        videobox.volume_muter.connect('clicked', self.on_volume_mute)
        videobox.controls.play.connect('clicked', self.on_play_clicked)
        videobox.controls.stop.connect('clicked', self.on_stop_clicked)
        videobox.controls.forward.connect('clicked', self.on_forward_clicked)
        videobox.controls.forward.connect('held-down', self.on_fast_forward)
        videobox.controls.forward.connect('released', self.on_stop_fast_playback)
        videobox.controls.previous.connect('clicked', self.on_previous_clicked)
        videobox.controls.previous.connect('held-down', self.on_fast_backward)
        videobox.controls.previous.connect('released', self.on_stop_fast_playback)
        videobox.playback_mode.shuffle.connect('clicked', self.on_shuffle_clicked)
        videobox.playback_mode.repeat.connect('clicked', self.on_repeat_clicked)
        self.set_left_width(app.widget_state.get_tabs_width())
        self.window.show()
        messages.TrackPlaylists().send_to_backend()
        messages.TrackDownloadCount().send_to_backend()
        messages.TrackPausedCount().send_to_backend()
        messages.TrackOthersCount().send_to_backend()
        messages.TrackNewVideoCount().send_to_backend()
        messages.TrackNewAudioCount().send_to_backend()
        messages.TrackUnwatchedCount().send_to_backend()

    def get_main_window_dimensions(self):
        """Override this to provide platform-specific Main Window dimensions.

        Must return a Rect.
        """
        return widgetset.Rect(100, 300, 800, 600)

    def get_right_width(self):
        """Returns the width of the right side of the splitter.
        """
        left_width = self.get_left_width()
        if left_width:
            return self.window.get_frame().get_width() - left_width
        else:
            return None

    def get_left_width(self):
        if hasattr(self.window, 'splitter'):
            return self.window.splitter.get_left_width()
        else:
            return None

    def set_left_width(self, width):
        self.window.splitter.set_left_width(width)

    def on_volume_change(self, slider, volume):
        app.playback_manager.set_volume(volume)

    def on_volume_mute(self, button=None):
        slider = self.window.videobox.volume_slider
        if slider.get_value() == 0:
            value = getattr(self, "previous_volume_value", 0.75)
        else:
            self.previous_volume_value = slider.get_value()
            value = 0.0

        slider.set_value(value)
        self.on_volume_change(slider, value)
        self.on_volume_set(slider)

    def on_volume_set(self, slider):
        self.on_volume_value_set(slider.get_value())

    def on_volume_value_set(self, value):
        app.config.set(prefs.VOLUME_LEVEL, value)
        app.config.save()

    def on_play_clicked(self, button=None):
        if app.playback_manager.is_playing:
            app.playback_manager.toggle_paused()
        else:
            self.play_selection()

    def play_selection(self):
        app.item_list_controller_manager.play_selection()

    def resume_play_selection(self):
        app.item_list_controller_manager.resume_play_selection()

    def enable_net_lookup_for_selection(self):
        selection = app.item_list_controller_manager.get_selection()
        id_list = [info.id for info in selection
                   if info.downloaded and not info.net_lookup_enabled]
        m = messages.SetNetLookupEnabled(id_list, True)
        m.send_to_backend()

    def disable_net_lookup_for_selection(self):
        selection = app.item_list_controller_manager.get_selection()
        id_list = [info.id for info in selection
                   if info.downloaded and info.net_lookup_enabled]
        m = messages.SetNetLookupEnabled(id_list, False)
        m.send_to_backend()

    def on_stop_clicked(self, button=None):
        app.playback_manager.stop()

    def on_forward_clicked(self, button=None):
        app.playback_manager.play_next_item()

    def on_previous_clicked(self, button=None):
        app.playback_manager.play_prev_item(from_user=True)

    def on_skip_forward(self):
        app.playback_manager.skip_forward()

    def on_skip_backward(self):
        app.playback_manager.skip_backward()

    def on_fast_forward(self, button=None):
        app.playback_manager.fast_forward()

    def on_fast_backward(self, button=None):
        app.playback_manager.fast_backward()

    def on_stop_fast_playback(self, button):
        app.playback_manager.stop_fast_playback()

    def on_shuffle_clicked(self, button=None):
        app.playback_manager.toggle_shuffle()

    def on_repeat_clicked(self, button=None):
        app.playback_manager.toggle_repeat()

    def on_toggle_detach_clicked(self, button=None):
        app.playback_manager.toggle_detached_mode()

    def up_volume(self):
        slider = self.window.videobox.volume_slider
        v = min(slider.get_value() + 0.05, widgetconst.MAX_VOLUME)
        slider.set_value(v)
        self.on_volume_change(slider, v)
        self.on_volume_set(slider)

    def down_volume(self):
        slider = self.window.videobox.volume_slider
        v = max(slider.get_value() - 0.05, 0.0)
        slider.set_value(v)
        self.on_volume_change(slider, v)
        self.on_volume_set(slider)

    def toggle_column(self, name):
        current_display = app.display_manager.get_current_display()
        if current_display:
            current_display.toggle_column_enabled(unicode(name))

    def share_item(self, item):
        share_items = {"file_url": item.url,
                       "item_name": item.title}
        if item.feed_url:
            share_items["feed_url"] = item.feed_url
        query_string = "&".join([
            "%s=%s" % (key, urllib.quote(val.encode('utf-8')))
            for key, val in share_items.items()])
        share_url = "%s/item/?%s" % (app.config.get(prefs.SHARE_URL),
                                     query_string)
        self.open_url(share_url)

    def share_feed(self):
        t, channel_infos = app.tabs.selection
        if t == 'feed' and len(channel_infos) == 1:
            ci = channel_infos[0]
            share_items = {"feed_url": ci.base_href}
            query_string = "&".join([
                "%s=%s" % (key, urllib.quote(val.encode('utf8')))
                for key, val in share_items.items()])
            share_url = "%s/feed/?%s" % (app.config.get(prefs.SHARE_URL),
                                         query_string)
            self.open_url(share_url)

    def delete_backup_databases(self):
        dbs = app.db.get_backup_databases()
        for mem in dbs:
            fileutil.remove(mem)

    def check_then_reveal_file(self, filename):
        if not os.path.exists(filename):
            basename = os.path.basename(filename)
            dialogs.show_message(
                _("Error Revealing File"),
                _("The file %(filename)s was deleted from outside %(appname)s.",
                  {"filename": basename,
                   "appname": app.config.get(prefs.SHORT_APP_NAME)}),
                dialogs.WARNING_MESSAGE)
        else:
            self.reveal_file(filename)

    def reveal_conversions_folder(self):
        self.reveal_file(conversions.get_conversions_folder())

    def open_video(self):
        title = _('Open Files...')
        audio_extensions = [mem[1:] for mem in filetypes.AUDIO_EXTENSIONS]
        video_extensions = [mem[1:] for mem in filetypes.VIDEO_EXTENSIONS]
        torrent_extensions = [mem[1:] for mem in filetypes.TORRENT_EXTENSIONS]
        all_extensions = (audio_extensions + video_extensions
                          + torrent_extensions)
        filenames = dialogs.ask_for_open_pathname(
            title,
            filters=[
                (_('All Media Files'), all_extensions),
                (_('Video Files'), video_extensions),
                (_('Audio Files'), audio_extensions),
                (_('Torrent Files'), torrent_extensions)
                ],
            select_multiple=True)

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
            messages.MessageToUser(_("%(appname)s is up to date",
                                     {'appname': app.config.get(prefs.SHORT_APP_NAME)}),
                                   _("%(appname)s is up to date!",
                                     {'appname': app.config.get(prefs.SHORT_APP_NAME)})).send_to_frontend()

        messages.CheckVersion(up_to_date_callback).send_to_backend()

    def preferences(self):
        prefpanel.show_window()

    def remove_items(self, selection=None):
        # remove items that the user has selected
        if not selection:
            selection = app.item_list_controller_manager.get_selection()
            selection = [s for s in selection if s.downloaded]

        # if the user hasn't selected any items, try removing the
        # item currently playing
        if not selection and app.playback_manager.is_playing:
            selection = [app.playback_manager.get_playing_item()]

        if not selection:
            return

        def playback_finished_if_playing_selection():
            if app.playback_manager.is_playing:
                item = app.playback_manager.get_playing_item()
                # bz:17555
                # Snarf the id out.  Turns out that while the ItemInfo id
                # is the same but the object is different so the boolean
                # expression fails.
                if item is not None and item.id in [s.id for s in selection]:
                    app.playback_manager.on_movie_finished()

        external_count = len([s for s in selection if s.is_external])
        failed_count = len([s for s in selection if s.is_failed_download])
        folder_count = len([s for s in selection if s.is_container_item])
        total_count = len(selection)

        if total_count == 1 and external_count == folder_count == 0:
            playback_finished_if_playing_selection()
            messages.DeleteVideos([selection[0]]).send_to_backend()
            return

        if failed_count == total_count:
            # all our selection is failed downloads, just cancel them
            for item in selection:
                messages.CancelDownload(item.id).send_to_backend()
            return

        title = ngettext('Remove item', 'Remove items', total_count)

        if external_count > 0:
            description = ngettext(
                'One of these items was not downloaded from a podcast. '
                'Would you like to delete it or just remove it from the '
                'Library?',

                'Some of these items were not downloaded from a podcast. '
                'Would you like to delete them or just remove them from the '
                'Library?',

                external_count
            )
            if folder_count > 0:
                description += '\n\n' + ngettext(
                    'One of these items is a folder.  Deleting/Removing a '
                    "folder will delete/remove it's contents",

                    'Some of these items are folders.  Deleting/Removing a '
                    "folder will delete/remove it's contents",

                    folder_count
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
            if folder_count > 0:
                description += '\n\n' + ngettext(
                    'One of these items is a folder.  Deleting a '
                    "folder will delete it's contents",

                    'Some of these items are folders.  Deleting a '
                    "folder will delete it's contents",

                    folder_count
                )
            ret = dialogs.show_choice_dialog(title, description,
                                             [dialogs.BUTTON_DELETE,
                                              dialogs.BUTTON_CANCEL])
        to_delete = []
        to_remove = []

        if ret in (dialogs.BUTTON_OK, dialogs.BUTTON_DELETE_FILE,
                dialogs.BUTTON_DELETE):
            playback_finished_if_playing_selection()
            for mem in selection:
                to_delete.append(mem)

        elif ret == dialogs.BUTTON_REMOVE_ENTRY:
            playback_finished_if_playing_selection()
            for mem in selection:
                if mem.is_external:
                    to_remove.append(mem)
                else:
                    to_delete.append(mem)

        if to_remove:
            messages.RemoveVideoEntries(to_remove).send_to_backend()
        if to_delete:
            messages.DeleteVideos(to_delete).send_to_backend()

    def edit_items(self):
        selection = app.item_list_controller_manager.get_selection()
        selection = [s for s in selection if s.downloaded]
        if not selection:
            return

        dialog = itemedit.ItemEditDialog()
        for item in selection:
            dialog.add_item(item)
        # TODO: should return a dict for each item changed to avoid writing to
        # files that haven't been modified
        change_dict = dialog.run()

        if change_dict:
            ids = [s.id for s in selection]
            # TODO: message for MoveItem and MoveItems
            messages.EditItems(ids, change_dict).send_to_backend()

    def save_item(self):
        selection = app.item_list_controller_manager.get_selection()
        selection = [s for s in selection if s.downloaded]

        if not selection:
            return

        title = _('Save Item As...')
        filename = selection[0].filename
        filename = os.path.basename(filename)
        filename = dialogs.ask_for_save_pathname(title, filename)

        if not filename:
            return

        messages.SaveItemAs(selection[0].id, filename).send_to_backend()

    def set_media_kind(self, kind):
        logging.debug('set media kind = %s', kind)
        selection = app.item_list_controller_manager.get_selection()
        if not selection:
            return
        messages.SetMediaKind(selection, kind).send_to_backend()

    def convert_items(self, converter_id):
        selection = app.item_list_controller_manager.get_selection()
        for item_info in selection:
            conversions.convert(converter_id, item_info, update_last=True)

    def copy_item_url(self):
        selection = app.item_list_controller_manager.get_selection()

        if not selection and app.playback_manager.is_playing:
            selection = [app.playback_manager.get_playing_item()]

        if not selection:
            return

        selection = selection[0]
        if selection.url:
            app.widgetapp.copy_text_to_clipboard(selection.url)

    def add_new_feed(self):
        url = newfeed.run_dialog()
        if url is not None:
            messages.NewFeed(url).send_to_backend()

    def import_search_all_my_files(self):
        # opens search files dialog with the default search dir
        dir_ = resources.get_default_search_dir()
        searchfilesdialog.SearchFilesDialog(dir_).run()

    def import_search_in_folder(self):
        # opens a dialog asking the user to select a folder
        # and then it opens the search files dialog and
        # searches that folder.
        dir_ = dialogs.ask_for_directory(
            _("Choose directory to search for media files"),
            initial_directory=resources.get_default_search_dir())

        if dir_:
            searchfilesdialog.SearchFilesDialog(dir_).run()

    def import_choose_files(self):
        # opens dialog allowing you to choose files and folders
        audio_extensions = [mem[1:] for mem in filetypes.AUDIO_EXTENSIONS]
        video_extensions = [mem[1:] for mem in filetypes.VIDEO_EXTENSIONS]
        files_ = dialogs.ask_for_open_pathname(
            _("Choose files to import"),
            filters=[
                (_("Video Files"), video_extensions),
                (_("Audio Files"), audio_extensions)
                ],
            select_multiple=True)

        if files_:
            messages.AddFiles(files_).send_to_backend()

    def add_new_watched_folder(self):
        ret = newwatchedfolder.run_dialog()
        if ret is not None:
            path, showinsidebar = ret
            messages.NewWatchedFolder(path, showinsidebar).send_to_backend()

    def add_new_search_feed(self):
        data = newsearchfeed.run_dialog()

        if not data:
            return

        if data[0] == "feed":
            messages.NewFeedSearchFeed(data[1], data[2]).send_to_backend()
        elif data[0] == "search_engine":
            messages.NewFeedSearchEngine(data[1], data[2]).send_to_backend()
        elif data[0] == "url":
            messages.NewFeedSearchURL(data[1], data[2]).send_to_backend()

    def add_new_feed_folder(self, add_selected=False):
        name = newfolder.run_dialog(u'feed')
        if name is not None:
            if add_selected:
                t, infos = app.tabs.selection
                child_ids = [info.id for info in infos]
            else:
                child_ids = None
            messages.NewFeedFolder(name, child_ids).send_to_backend()

    def add_new_guide(self):
        url = self.ask_for_url(_('Add Source'),
                _('Enter the URL of the source to add'),
                _('Add Source - Invalid URL'),
                _("The address you entered is not a valid url.\n"
                  "Please check the URL and try again.\n\n"
                  "Enter the URL of the source to add"))

        if url is not None:
            messages.NewGuide(url).send_to_backend()

    def remove_something(self):
        t, infos = app.tabs.selection_and_children
        if any(info.type == 'tab' for info in infos):
            return
        if t == 'feed':
            self.remove_feeds(infos)
        elif t == 'site':
            self.remove_sites(infos)
        elif t == 'playlist':
            self.remove_playlists(infos)

    def remove_feeds(self, channel_infos):
        has_watched_feeds = False
        downloaded_items = False
        downloading_items = False

        for ci in channel_infos:
            if not ci.is_directory_feed:
                if ci.num_downloaded > 0:
                    downloaded_items = True

                if ci.has_downloading:
                    downloading_items = True
            else:
                has_watched_feeds = True

        ret = removefeeds.run_dialog(channel_infos, downloaded_items,
                downloading_items, has_watched_feeds)
        if ret:
            for ci in channel_infos:
                if ci.is_directory_feed:
                    messages.SetWatchedFolderVisible(ci.id, False).send_to_backend()
                else:
                    messages.DeleteFeed(ci.id, ci.is_folder,
                        ret[removefeeds.KEEP_ITEMS]
                    ).send_to_backend()

    def update_selected_feeds(self):
        t, channel_infos = app.tabs.selection
        if t == 'feed':
            for ci in channel_infos:
                if ci.is_folder:
                    messages.UpdateFeedFolder(ci.id).send_to_backend()
                else:
                    messages.UpdateFeed(ci.id).send_to_backend()

    def update_all_feeds(self):
        messages.UpdateAllFeeds().send_to_backend()

    def import_feeds(self):
        title = _('Import OPML File')
        filename = dialogs.ask_for_open_pathname(title,
                filters=[(_('OPML Files'), ['opml'])])
        if not filename:
            return

        if os.path.isfile(filename):
            messages.ImportFeeds(filename).send_to_backend()
        else:
            dialogs.show_message(_('Import OPML File - Error'),
                                 _('File %(filename)s does not exist.',
                                   {"filename": filename}),
                                 dialogs.WARNING_MESSAGE)

    def export_feeds(self):
        title = _('Export OPML File')
        slug = app.config.get(prefs.SHORT_APP_NAME).lower()
        slug = slug.replace(' ', '_').replace('-', '_')
        filepath = dialogs.ask_for_save_pathname(title, "%s_subscriptions.opml" % slug)

        if not filepath:
            return

        messages.ExportSubscriptions(filepath).send_to_backend()

    def feed_settings(self):
        t, channel_infos = app.tabs.selection
        if t == 'feed' and len(channel_infos) == 1:
            feedsettingspanel.run_dialog(channel_infos[0])

    def copy_feed_url(self):
        t, channel_infos = app.tabs.selection
        if t == 'feed' and len(channel_infos) == 1:
            app.widgetapp.copy_text_to_clipboard(channel_infos[0].url)

    def copy_site_url(self):
        t, site_infos = app.tabs.selection
        if t == 'site':
            app.widgetapp.copy_text_to_clipboard(site_infos[0].url)

    def add_new_playlist(self):
        selection = app.item_list_controller_manager.get_selection()
        ids = [s.id for s in selection if s.downloaded and
               not getattr(s, 'host', False) and not s.device]

        title = _('Create Playlist')
        description = _('Enter a name for the new playlist')

        name = dialogs.ask_for_string(title, description)
        if name:
            messages.NewPlaylist(name, ids).send_to_backend()

    def add_to_playlist(self):
        selection = app.item_list_controller_manager.get_selection()
        ids = [s.id for s in selection if s.downloaded]

        data = addtoplaylistdialog.run_dialog()

        if not data:
            return

        if data[0] == "existing":
            messages.AddVideosToPlaylist(data[1].id, ids).send_to_backend()
        elif data[0] == "new":
            messages.NewPlaylist(data[1], ids).send_to_backend()

    def add_new_playlist_folder(self, add_selected=False):
        title = _('Create Playlist Folder')
        description = _('Enter a name for the new playlist folder')

        name = dialogs.ask_for_string(title, description)
        if name:
            if add_selected:
                t, infos = app.tabs.selection
                child_ids = [info.id for info in infos]
            else:
                child_ids = None
            messages.NewPlaylistFolder(name, child_ids).send_to_backend()

    def rename_something(self):
        t, channel_infos = app.tabs.selection
        info = channel_infos[0]

        if t == 'feed' and info.is_folder:
            t = 'feed-folder'
        elif t == 'playlist' and info.is_folder:
            t = 'playlist-folder'

        if t == 'feed-folder':
            title = _('Rename Podcast Folder')
            description = _('Enter a new name for the podcast folder %(name)s',
                            {"name": info.name})

        elif t == 'feed':
            title = _('Rename Podcast')
            description = _('Enter a new name for the podcast %(name)s',
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
            title = _('Rename Source')
            description = _('Enter a new name for the source %(name)s',
                            {"name": info.name})

        else:
            raise AssertionError("Unknown tab type: %s" % t)

        name = dialogs.ask_for_string(title, description,
                                      initial_text=info.name)
        if name:
            messages.RenameObject(t, info.id, name).send_to_backend()

    def revert_feed_name(self):
        t, channel_infos = app.tabs.selection
        if not channel_infos:
            return
        info = channel_infos[0]
        messages.RevertFeedTitle(info.id).send_to_backend()

    def remove_playlists(self, playlist_infos):
        title = ngettext('Remove playlist', 'Remove playlists', len(playlist_infos))
        description = ngettext(
            'Are you sure you want to remove this playlist?',
            'Are you sure you want to remove these %(count)s playlists?',
            len(playlist_infos),
            {"count": len(playlist_infos)}
            )

        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_REMOVE,
                                          dialogs.BUTTON_CANCEL])

        if ret == dialogs.BUTTON_REMOVE:
            for pi in playlist_infos:
                messages.DeletePlaylist(pi.id, pi.is_folder).send_to_backend()

    def remove_sites(self, infos):
        title = ngettext('Remove source', 'Remove sources', len(infos))
        description = ngettext(
            'Are you sure you want to remove this source?',
            'Are you sure you want to remove these %(count)s sources?',
            len(infos),
            {"count": len(infos)}
            )

        ret = dialogs.show_choice_dialog(title, description,
                [dialogs.BUTTON_REMOVE, dialogs.BUTTON_CANCEL])

        if ret == dialogs.BUTTON_REMOVE:
            for si in infos:
                messages.DeleteSite(si.id).send_to_backend()

    def music_tab_clicked(self):
        """User clicked the Music tab for the first time, so ask them about
        importing media.
        """
        app.config.set(prefs.MUSIC_TAB_CLICKED, True)
        dialog = firsttimedialog.MusicSetupDialog()
        dialog.run()
        if dialog.import_path():
            app.watched_folder_manager.add(dialog.import_path())

    def quit_ui(self):
        """Quit  out of the UI event loop."""
        raise NotImplementedError()

    def about(self):
        dialogs.show_about()

    def diagnostics(self):
        diagnostics.run_dialog()

    def setup_profile_message(self):
        """Devel method: save profile time for a frontend message."""

        # NOTE: strings are purposefully untranslated.  Should we spend
        # translator time these strings?
        message_choices = []
        message_labels = []
        for name in dir(messages):
            obj = getattr(messages, name)
            if (type(obj) is type and
                    issubclass(obj, messages.FrontendMessage) and
                    obj is not messages.FrontendMessage):
                message_choices.append(obj)
                message_labels.append(name)

        index = dialogs.ask_for_choice(
                ("Select Message to Profile"),
                ("The next time the the message is handled, Miro will "
                    "write out profile timing data for it."),
                message_labels)
        if index is not None:
            message_obj = message_choices[index]
            message_label = message_labels[index]
            title = _("Select File to write Profile to")
            path = dialogs.ask_for_save_pathname(title,
                    'miro-profile-%s.prof' % message_label.lower())
            if path is not None:
                self.message_handler.profile_next_message(message_obj, path)

    def clog_backend(self):
        """Dev method: hog the backend to simluate the backend being
        unresponsive.

        NB: strings not translated on purpose.
        """
        title = 'Clog backend'
        description = ('Make the backend busy by sleeping for a specified '
                      'number of seconds to simulate a clogged backend.\n\n'
                      'WARNING: use judiciously!\n\n'
                      'Default is 0 seconds.')
        initial_text = '0'
        n = dialogs.ask_for_string(title, description, initial_text)
        if n == None:
            return
        try:
            n = int(n)
        except ValueError:
            n = 0
        messages.ClogBackend(n).send_to_backend()

    def profile_redraw(self):
        """Devel method: profile time to redraw part of the interface."""

        # NOTE: strings are purposefully untranslated.  Should we spend
        # translator time these strings?
        message_labels = ['Right Side', 'Left Side']

        index = dialogs.ask_for_choice(
                ("Select Area to Profile"),
                ("Miro will redraw the widget in that area 10 times and "
                    "write out profile timing data for it."),
                message_labels)
        if index is not None:
            if index == 0:
                widget = self.window.splitter.right
            else:
                widget = self.window.splitter.left

            title = _("Select File to write Profile to")
            path = dialogs.ask_for_save_pathname(title,
                    'miro-profile-redraw.prof')
            if path is not None:
                def profile_code():
                    for x in xrange(10):
                        widget.redraw_now()
                cProfile.runctx('profile_code()', globals(), locals(),
                        path)

    def memory_stats(self):
        """Printout statistics of objects in memory."""
        self._printout_memory_stats('MEMORY STATS BEFORE GARBAGE COLLECTION')
        gc.collect()
        self._printout_memory_stats('MEMORY STATS AFTER GARBAGE COLLECTION')

    def force_feedparser_processing(self):
        messages.ForceFeedparserProcessing().send_to_backend()

    def _printout_memory_stats(self, title):
        # base_classes is a list of base classes that we care about.  If you
        # want to check memory usage for a different class, add it to the
        # list.
        base_classes = [
                widgetset.Widget,
                itemlistcontroller.ItemListController,
        ]
        # gc.get_objects() returns all objects tracked by the garbage
        # collector.  I'm pretty sure this should all of our python objects.
        objects = gc.get_objects()
        counts = {}
        for obj in objects:
            for base_class in base_classes:
                if isinstance(obj, base_class):
                    key = '%s: %s' % (base_class.__name__,
                            obj.__class__.__name__)
                    counts[key] = counts.get(key, 0) + 1
                    continue
        lines = [
                '%s:' % title,
                '-' * 40,
        ]
        data = counts.items()
        data.sort()
        for label, count in data:
            lines.append('%-30s: %s' % (label, count))
        logging.debug('\n'.join(lines))

    def on_close(self):
        """This is called when the close button is pressed."""
        self.quit()

    def quit(self):
        ok1 = self._confirm_quit_if_downloading()
        ok2 = self._confirm_quit_if_converting()
        ok3 = self._confirm_quit_if_sharing()
        if ok1 and ok2 and ok3:
            self.do_quit()

    def _confirm_quit_if_sharing(self):
        # Pre-grab variables so test and the message is consistent.
        session_count = app.sharing_manager.session_count()
        if (app.config.get(prefs.SHARE_WARN_ON_QUIT) and session_count > 0):
            ret = quitconfirmation.rundialog(
                _("Are you sure you want to quit?"),
                ngettext(
                    ("You have %(count)d active connection to your media "
                     "library. Quit anyway?"),
                    ("You have %(count)d active connections to your media "
                     "library. Quit anyway?"),
                    session_count,
                    {"count": session_count}
                ),
                _("Warn me when I attempt to quit when others are connected "
                  "to my media library"),
                prefs.SHARE_WARN_ON_QUIT
            )
            return ret
        return True

    def _confirm_quit_if_downloading(self):
        if app.config.get(prefs.WARN_IF_DOWNLOADING_ON_QUIT) and self.download_count > 0:
            ret = quitconfirmation.rundialog(
                _("Are you sure you want to quit?"),
                ngettext(
                    "You have %(count)d download in progress.  Quit anyway?",
                    "You have %(count)d downloads in progress.  Quit anyway?",
                    self.download_count,
                    {"count": self.download_count}
                ),
                _("Warn me when I attempt to quit with downloads in progress"),
                prefs.WARN_IF_DOWNLOADING_ON_QUIT
            )
            return ret
        return True

    def _confirm_quit_if_converting(self):
        running_count = conversions.conversion_manager.running_tasks_count()
        pending_count = conversions.conversion_manager.pending_tasks_count()
        conversions_count = running_count + pending_count
        if app.config.get(prefs.WARN_IF_CONVERTING_ON_QUIT) and conversions_count > 0:
            ret = quitconfirmation.rundialog(
                _("Are you sure you want to quit?"),
                ngettext(
                    "You have %(count)d conversion in progress.  Quit anyway?",
                    "You have %(count)d conversions in progress or pending.  Quit anyway?",
                    conversions_count,
                    {"count": conversions_count}
                ),
                _("Warn me when I attempt to quit with conversions in progress"),
                prefs.WARN_IF_CONVERTING_ON_QUIT
            )
            return ret
        return True

    def do_quit(self):
        if prefpanel.is_window_shown():
            prefpanel.hide_window()
        if self.ui_initialized:
            if app.playback_manager.is_playing:
                app.playback_manager.stop()
            app.display_manager.deselect_all_displays()
            app.item_list_controller_manager.undisplay_controller()
        if self.window is not None:
            self.window.destroy()
        width = self.get_left_width()
        if width:
            app.widget_state.set_tabs_width(width)
        app.controller.shutdown()
        self.quit_ui()

    def connect_to_signals(self):
        signals.system.connect('error', self.handle_error)
        signals.system.connect('update-available', self.handle_update_available)
        signals.system.connect('new-dialog', self.handle_dialog)
        signals.system.connect('shutdown', self.on_backend_shutdown)
        signals.system.connect('download-complete',
                               self.handle_download_complete)
        app.frontend_config_watcher.connect("changed", self.on_config_changed)

    def handle_unwatched_count_changed(self):
        pass

    def handle_download_complete(self, obj, item):
        # Frontend subclasses may override this.
        pass

    def handle_dialog(self, obj, dialog):
        call_on_ui_thread(rundialog.run, dialog)

    def handle_update_available(self, obj, item):
        print "Update available! -- not implemented"

    def handle_up_to_date(self):
        print "Up to date! -- not implemented"

    def handle_error(self, obj, report):
        call_on_ui_thread(self.handle_crash_report, report)

    def handle_crash_report(self, report):
        self.crash_reports_to_handle.append(report)
        if len(self.crash_reports_to_handle) > 1:
            # another call to handle_crash_report() is running a dialog, wait
            # until it returns
            return

        while self.crash_reports_to_handle:
            report = self.crash_reports_to_handle[0]
            # if we're ignoring this error, log it
            if self.ignore_errors:
                headers = crashreport.extract_headers(report)
                logging.warn("Ignoring Error:\n%s", headers)
            else:
                ret = crashdialog.run_dialog(report)
                if ret == crashdialog.IGNORE_ERRORS:
                    self.ignore_errors = True
            # save the crash report to disk
            crashreport.save_crash_report(report)
            self.crash_reports_to_handle = self.crash_reports_to_handle[1:]

    def on_backend_shutdown(self, obj):
        logging.info('Shutting down...')

class WidgetsMessageHandler(messages.MessageHandler):
    """Handles frontend messages.

    There's a method to handle each frontend message type.  See
    :mod:`miro.messages` (``lib/messages.py``) and
    :mod:`miro.messagehandler` (``lib/messagehandler.py``) for
    more details.
    """
    def __init__(self):
        messages.MessageHandler.__init__(self)
        # Messages that we need to see before the UI is ready
        self._pre_startup_messages = set([
            'guide-list',
            'store-list',
            'search-info',
            'display-states',
            'view-states',
            'global-state',
        ])
        if app.config.get(prefs.OPEN_CHANNEL_ON_STARTUP) is not None or \
                app.config.get(prefs.OPEN_FOLDER_ON_STARTUP) is not None:
                    self.library_filters = {
                            'video': 'all',
                            'audio': 'unwatched'
                    }
        self.progress_dialog = None
        self.dbupgrade_progress_dialog = None
        self._profile_info = None
        self._startup_failure_mode = self._database_failure_mode = False

    def profile_next_message(self, message_obj, path):
        self._profile_info = (message_obj, path)

    def handle_sharing_disappeared(self, message):
        share = message.share
        host = share.host
        port = share.port
        if share.mount and app.playback_manager.is_playing:
            item = app.playback_manager.get_playing_item()
            if (item and item.remote and
              item.host == host and item.port == port):
                app.playback_manager.stop()
        logging.debug('SHARING DISAPPEARED')
        message = messages.TabsChanged('connect', [], [], [share.id])
        typ, selected_tabs = app.tabs.selection
        if typ == u'connect' and share in selected_tabs:
            app.tabs.select_guide()
        # Call directly: already in frontend.
        self.handle_tabs_changed(message)
        # Now, reply to backend, and eject the share.
        if share.mount:
            messages.StopTrackingShare(share.share_id).send_to_backend()

    def handle_downloader_sync_command_complete(self, message):
        # We used to need this command, but with the new ItemList code it's
        # obsolute.
        logging.debug('DownloaderSyncCommandComplete')

    def handle_jettison_tabs(self, message):
        typ = message.type
        item_ids = message.ids

        tablist = app.tabs[typ]
        view = tablist.view
        iter_ = view.model.first_iter()
        if not iter_:
            app.widgetapp.handle_soft_failure('handle_jettison_tabs',
                "no tabs to jettison from sidebar model?",
                with_exception=False)
            return
        # XXX warning XXX: this code doesn't handle removing an iter's children
        # from the iter map when we remove the iter; removing a parent without
        # its children would cause #17362-like segfaults. Currently this is OK
        # because we only ever jettison leaf nodes. If for some reason that were
        # ever to change, it is crucial to implement proper orphan cleanup here.
        iter_ = view.model.child_iter(iter_)
        while iter_:
            row = view.model[iter_]
            if row[0].id in item_ids:
                # no segfaulty iters in map (iter_map rule 0, see TabList)
                del tablist.iter_map[row[0].id]
                iter_ = view.model.remove(iter_)
            else:
                child_iter = view.model.child_iter(iter_)
                while child_iter:
                    row = view.model[child_iter]
                    if row[0].id in item_ids:
                        # no segfaulty iters in map
                        del tablist.iter_map[row[0].id]
                        child_iter = view.model.remove(child_iter)
                    else:
                        child_iter = view.model.next_iter(child_iter)
                iter_ = view.model.next_iter(iter_)
        tablist.model_changed()

    def handle_sharing_connect_failed(self, message):
        name = message.share.name
        title = _('Connect failed')
        description = _('Connection to share %(name)s failed.\n\n'
                        'The share is either unreachable or incompatible '
                        'with %(appname)s sharing.',
                        {"name": name,
                         "appname": app.config.get(prefs.SHORT_APP_NAME)})
        dialogs.show_message(title, description, dialogs.INFO_MESSAGE)
        app.tabs.select_guide()

    def handle_show_warning(self, message):
        dialogs.show_message(message.title, message.description,
                             dialogs.WARNING_MESSAGE)

    def handle_frontend_quit(self, message):
        if self.dbupgrade_progress_dialog:
            self.dbupgrade_progress_dialog.destroy()
            self.dbupgrade_progress_dialog = None
        app.widgetapp.do_quit()

    def handle_database_upgrade_start(self, message):
        if self.dbupgrade_progress_dialog is None:
            if message.doing_db_upgrade:
                title = _('Upgrading database')
                text = _(
                    "%(appname)s is upgrading your database of podcasts "
                    "and files.  This one-time process can take a long "
                    "time if you have a large number of items in "
                    "%(appname)s (it can even take more than 30 minutes).",
                    {"appname": app.config.get(prefs.SHORT_APP_NAME)})
            else:
                title = _('Preparing Items')
                text = _("%(appname)s shutdown improperly and needs to "
                         "prepare your items for display.",
                         {"appname": app.config.get(prefs.SHORT_APP_NAME)})
            self.dbupgrade_progress_dialog = dialogs.DBUpgradeProgressDialog(
                    title, text)
            self.dbupgrade_progress_dialog.run()
            # run() will return when we destroy the dialog because of a future
            # message.
            return

    def handle_database_upgrade_progress(self, message):
        self.dbupgrade_progress_dialog.update(message.stage,
                message.stage_progress, message.total_progress)

    def handle_database_upgrade_end(self, message):
        # we don't do anything here because we actually want to keep the
        # dialog shown until just before we pop up the main window
        pass

    def close_upgrade_dialog(self):
        if self.dbupgrade_progress_dialog:
            self.dbupgrade_progress_dialog.destroy()
            self.dbupgrade_progress_dialog = None

    def handle_startup_failure(self, message):
        if self._startup_failure_mode:
            logging.info("already in startup failure mode--skipping")
            return
        self._startup_failure_mode = True
        # We may still have the DB upgrade dialog open.  If so, close it.
        self.close_upgrade_dialog()

        dialogs.show_message(message.summary, message.description,
                dialogs.CRITICAL_MESSAGE)
        app.widgetapp.do_quit()

    def handle_startup_database_failure(self, message):
        if self._database_failure_mode:
            logging.info("already in db failure mode--skipping")
            return
        self._database_failure_mode = True
        # We may still have the DB upgrade dialog open.  If so, close it.
        self.close_upgrade_dialog()

        ret = dialogs.show_choice_dialog(
            message.summary, message.description,
            choices=[dialogs.BUTTON_QUIT, dialogs.BUTTON_START_FRESH])
        if ret == dialogs.BUTTON_START_FRESH:
            def start_fresh():
                try:
                    app.db.reset_database()
                except Exception:
                    logging.exception(
                        "gah!  exception in the "
                        "handle_startup_database_failure section")
                app.widgetapp.do_quit()
            eventloop.add_urgent_call(start_fresh, "start fresh and quit")

        else:
            app.widgetapp.do_quit()

    def startup_failed(self):
        return self._startup_failure_mode or self._database_failure_mode

    def handle_startup_success(self, message):
        app.widgetapp.startup_ui()
        signals.system.emit('startup-success')

    def _saw_pre_startup_message(self, name):
        if name not in self._pre_startup_messages:
            # we get here with the (audio-)?feed-tab-list messages when
            # OPEN_(CHANNEL|FOLDER)_ON_STARTUP isn't defined
            return
        self._pre_startup_messages.remove(name)
        if len(self._pre_startup_messages) == 0:
            self.close_upgrade_dialog()
            app.widgetapp.build_window()

    def call_handler(self, method, message):
        if self.startup_failed():
            logging.warn("skipping message: %s because startup failed",
                         message)
            return
        # uncomment this next line if you need frontend messages
        # logging.debug("handling frontend %s", message)
        if (self._profile_info is not None and
                isinstance(message, self._profile_info[0])):
            call_on_ui_thread(self.profile_message, method, message)
        else:
            call_on_ui_thread(method, message)

    def profile_message(self, method, message):
        cProfile.runctx('method(message)',
                globals(), locals(), self._profile_info[1])
        self._profile_info = None

    def handle_current_search_info(self, message):
        app.search_manager.set_initial_search_info(message.engine, message.text)
        self._saw_pre_startup_message('search-info')

    def handle_tab_list(self, message):
        tablist = app.tabs[message.type]
        tablist.setup_list(message)
        if 'feed' in message.type:
            pre_startup_message = message.type + '-tab-list'
            self._saw_pre_startup_message(pre_startup_message)

    def handle_guide_list(self, message):
        self.initial_guides = message.added_guides
        self._saw_pre_startup_message('guide-list')
        app.tabs['site'].default_info = message.default_guide
        app.tabs['site'].setup_list(message)

    def handle_store_list(self, message):
        self.initial_stores = message.visible_stores
        self._saw_pre_startup_message('store-list')
        app.store_manager.handle_guide_list(message.visible_stores)
        app.store_manager.handle_guide_list(message.hidden_stores)
        app.tabs['store'].setup_list(message)

    def handle_stores_changed(self, message):
        app.store_manager.handle_stores_changed(message.added,
                                                message.changed,
                                                message.removed)

    def update_default_guide(self, guide_info):
        app.tabs['site'].default_info = guide_info
        guide_tab = app.tabs['site'].get_tab(guide_info.id)
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
        tablist = app.tabs[message.type]
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
        app.connection_pools.on_tabs_changed(message)
        app.info_updater.handle_tabs_changed(message)

    def handle_item_changes(self, message):
        app.item_tracker_updater.on_item_changes(message)

    def handle_device_item_changes(self, message):
        app.item_tracker_updater.on_device_item_changes(message)

    def handle_sharing_item_changes(self, message):
        app.item_tracker_updater.on_sharing_item_changes(message)

    def handle_download_count_changed(self, message):
        app.widgetapp.download_count = message.count
        library_tab_list = app.tabs['library']
        library_tab_list.update_download_count(message.count,
                                               message.non_downloading_count)

    def handle_paused_count_changed(self, message):
        app.widgetapp.paused_count = message.count

    def handle_others_count_changed(self, message):
        library_tab_list = app.tabs['library']
        library_tab_list.update_others_count(message.count)

    def handle_new_video_count_changed(self, message):
        library_tab_list = app.tabs['library']
        library_tab_list.update_new_video_count(message.count)

    def handle_new_audio_count_changed(self, message):
        library_tab_list = app.tabs['library']
        library_tab_list.update_new_audio_count(message.count)

    def handle_unwatched_count_changed(self, message):
        app.widgetapp.unwatched_count = message.count
        app.widgetapp.handle_unwatched_count_changed()

    def handle_converter_list(self, message):
        app.menu_manager.add_converters(message.converters)

    def handle_conversions_count_changed(self, message):
        library_tab_list = app.tabs['library']
        library_tab_list.update_converting_count(message.running_count,
                message.other_count)

    def handle_conversion_tasks_list(self, message):
        current_display = app.display_manager.get_current_display()
        if isinstance(current_display, displays.ConvertingDisplay):
            current_display.controller.handle_task_list(message.running_tasks,
                    message.pending_tasks, message.finished_tasks)

    def handle_conversion_task_created(self, message):
        current_display = app.display_manager.get_current_display()
        if isinstance(current_display, displays.ConvertingDisplay):
            current_display.controller.handle_task_added(message.task)

    def handle_conversion_task_removed(self, message):
        current_display = app.display_manager.get_current_display()
        if isinstance(current_display, displays.ConvertingDisplay):
            current_display.controller.handle_task_removed(message.task)

    def handle_all_conversion_task_removed(self, message):
        current_display = app.display_manager.get_current_display()
        if isinstance(current_display, displays.ConvertingDisplay):
            current_display.controller.handle_all_tasks_removed()

    def handle_conversion_task_changed(self, message):
        current_display = app.display_manager.get_current_display()
        if isinstance(current_display, displays.ConvertingDisplay):
            current_display.controller.handle_task_changed(message.task)

    def handle_device_changed(self, message):
        current_display = app.display_manager.get_current_display()
        if isinstance(current_display, displays.DeviceDisplayMixin):
            current_display.controller.handle_device_changed(message.device)

    def handle_current_sync_information(self, message):
        current_display = app.display_manager.get_current_display()
        if isinstance(current_display, displays.DeviceDisplay):
            current_display.handle_current_sync_information(message)

    def handle_device_sync_changed(self, message):
        current_display = app.display_manager.get_current_display()
        if isinstance(current_display, displays.DeviceDisplay):
            current_display.handle_device_sync_changed(message)

    def handle_play_movies(self, message):
        app.playback_manager.start_with_items(message.item_infos)

    def handle_stop_playing(self, message):
        app.playback_manager.stop()

    def handle_open_in_external_browser(self, message):
        app.widgetapp.open_url(message.url)

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
        if app.widgetapp.ui_initialized:
            app.search_manager.handle_search_complete(message)

    def handle_current_display_states(self, message):
        app.widget_state.setup_displays(message)
        self._saw_pre_startup_message('display-states')

    def handle_current_view_states(self, message):
        app.widget_state.setup_views(message)
        self._saw_pre_startup_message('view-states')

    def handle_current_global_state(self, message):
        app.widget_state.setup_global_state(message)
        self._saw_pre_startup_message('global-state')

    def handle_progress_dialog_start(self, message):
        self.progress_dialog = dialogs.ProgressDialog(message.title)
        self.progress_dialog.run()
        # run() will return when we destroy the dialog because of a future
        # message.

    def handle_progress_dialog(self, message):
        self.progress_dialog.update(message.description, message.progress)

    def handle_progress_dialog_finished(self, message):
        self.progress_dialog.destroy()
        self.progress_dialog = None

    def handle_feedless_download_started(self, message):
        library_tab_list = app.tabs['library']
        library_tab_list.blink_tab("downloading")

    def handle_metadata_progress_update(self, message):
        if not app.item_list_controller_manager or not app.tabs:
            return # got a metadata update before the UI opens
        app.item_list_controller_manager.update_metadata_progress(
            message.target, message.finished, message.finished_local,
            message.eta, message.total)
        app.tabs.update_metadata_progress(
            message.target, message.finished_local, message.eta,
            message.total)

    def handle_set_net_lookup_enabled_finished(self, message):
        prefpanel.enable_net_lookup_buttons()

    def handle_net_lookup_counts(self, message):
        prefpanel.update_net_lookup_counts(message.net_lookup_count,
                                           message.total_count)

class WidgetsFrontend(app.Frontend):
    def call_on_ui_thread(self, func, *args, **kwargs):
        call_on_ui_thread(func, *args, **kwargs)

    def run_choice_dialog(self, title, description, buttons):
        return dialogs.show_choice_dialog(title, description, buttons)

    def quit(self):
        app.widgetapp.do_quit()
