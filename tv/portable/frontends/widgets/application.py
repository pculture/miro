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
from miro import config
from miro import prefs
from miro import feed
from miro import startup
from miro import signals
from miro import messages
from miro.gtcache import gettext as _
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import displays
from miro.frontends.widgets import menus
from miro.frontends.widgets import tablistmanager
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
        messages.FrontendMessage.install_handler(self.message_handler)

    def startup(self):
        self.connect_to_signals()
        startup.startup()

    def startup_ui(self):
        # We need to wait until we have info about the channel guide before we
        # can show the ui
        messages.TrackGuides().send_to_backend()

    def build_window(self):
        app.tab_list_manager = tablistmanager.TabListManager()
        app.display_manager = displays.DisplayManager()
        app.menu_manager = menus.MenuManager()
        self.window = MiroWindow(_("Miro"), self.get_main_window_dimensions())
        app.tab_list_manager.handle_startup_selection()
        videobox = self.window.videobox
        videobox.time_slider.connect('changed', self.on_video_time_change)
        videobox.volume_slider.connect('changed', self.on_volume_change)
        videobox.controls.play.connect('clicked', self.on_play_clicked)
        videobox.controls.stop.connect('clicked', self.on_stop_clicked)
        videobox.controls.forward.connect('clicked', self.on_forward_clicked)
        videobox.controls.previous.connect('clicked', self.on_previous_clicked)
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

    def on_video_time_change(self, slider, time):
        print 'seek to: ', time

    def on_volume_change(self, slider, volume):
        print 'volume change: ', volume

    def on_play_clicked(self, button):
        pass

    def on_stop_clicked(self, button):
        pass

    def on_forward_clicked(self, button):
        # calls either next_video or fast_forward
        pass

    def on_previous_clicked(self, button):
        # calls either previous_video or rewind
        pass

    def next_video(self):
        pass

    def previous_video(self):
        pass

    def fast_forward(self):
        pass

    def rewind(self):
        psss

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

    def new_download(self):
        title = _('New Download')
        description = _('Enter the URL of the video to download')
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
                break

            title = _('New Download - Invalid URL')
            description = _('The address you entered is not a valid url.\nPlease check the URL and try again.\n\nEnter the URL of the video to download')

        # FIXME - implement download video
        # messages.NewChannel(normalized_url).send_to_backend()

    def add_new_channel(self):
        title = _('Add Channel')
        description = _('Enter the URL of the channel to add')
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
                break

            title = _('Add Channel - Invalid URL')
            description = _('The address you entered is not a valid url.\nPlease check the URL and try again.\n\nEnter the URL of the channel to add')

        messages.NewChannel(normalized_url).send_to_backend()

    def add_new_channel_folder(self):
        title = _('Create Channel Folder')
        description = _('Enter a name for the new channel folder')

        name = dialogs.ask_for_string(title, description)
        if name:
            messages.NewChannelFolder(name).send_to_backend()

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
            if not ci.is_folder:
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
            description = _("""\
What would you like to do with the videos in this channel that you've \
downloaded?""")
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _("""\
What would you like to do with the videos in these channels that you've \
downloaded?""")

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
            description = _("""\
Are you sure you want to remove %s?  Any downloads in progress will \
be canceled.""") % channel_infos[0].name
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _("""\
Are you sure you want to remove these %s channels?  Any downloads in \
progress will be canceled.""") % len(channel_infos)

        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_YES, 
                                          dialogs.BUTTON_NO])

        if ret == dialogs.BUTTON_YES:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def remove_feeds_normal(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Remove %s') % channel_infos[0].name
            description = _("""\
Are you sure you want to remove %s?""") % channel_infos[0].name
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _("""\
Are you sure you want to remove these %s channels?""") % len(channel_infos)

        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_YES, 
                                          dialogs.BUTTON_NO])
        if ret == dialogs.BUTTON_YES:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def remove_directory_feeds(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Stop watching %s') % channel_infos[0].name
            description = _("""\
Are you sure you want to stop watching %s?""") % channel_infos[0].name
        else:
            title = _('Stop watching %s directories') % len(channel_infos)
            description = _("""\
Are you sure you want to stop watching these %s directories?""") % len(channel_infos)
        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_YES, 
                                          dialogs.BUTTON_NO])
        if ret == dialogs.BUTTON_YES:
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

    def add_new_playlist(self):
        # FIXME - this is really brittle.  this violates the Law of Demeter
        # in ways that should make people cry.
        try:
            t = app.display_manager.current_display

            from miro.frontends.widgets.displays import FeedDisplay

            if isinstance(t, FeedDisplay):
                t = t.view
                t = t.full_view
                t = t.item_list
                selection = [t.model[i][0] for i in t.get_selection()]
                ids = [s.id for s in selection if s.downloaded]
            else:
                ids = []
        except:
            logging.exception("addNewPlaylist exception.")
            ids = []

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
        ci = channel_infos[0]

        if t == 'feed' and ci.is_folder:
            t = 'feed-folder'
        elif t == 'playlist' and ci.is_folder:
            t = 'playlist-folder'

        if t == 'feed-folder':
            title = _('Rename Channel Folder')
            description = _('Enter a new name for the channel folder %s') % \
                            ci.name

        elif t == 'feed' and not ci.is_folder:
            title = _('Rename Channel')
            description = _('Enter a new name for the channel %s') % \
                            ci.name

        elif t == 'playlist':
            title = _('Rename Playlist')
            description = _('Enter a new name for the playlist %s') % \
                            ci.name

        elif t == 'playlist-folder':
            title = _('Rename Playlist Folder')
            description = _('Enter a new name for the playlist folder %s') % \
                            ci.name

        else:
            return

        name = dialogs.ask_for_string(title, description,
                                      initial_text=ci.name)
        if name:
            messages.RenameObject(t, ci.id, name).send_to_backend()

    def remove_current_playlist(self):
        t, infos = app.tab_list_manager.get_selection()
        if t == 'playlist':
            self.remove_playlists(infos)

    def remove_playlists(self, playlist_infos):
        if len(playlist_infos) == 1:
            title = _('Remove %s') % playlist_infos[0].name
            description = _('Are you sure you want to remove %s') % \
                    playlist_infos[0].name
        else:
            title = _('Remove %s playlists') % len(playlist_infos)
            description = \
                    _('Are you sure you want to remove these %s playlists') % \
                    len(playlist_infos)

        ret = dialogs.show_choice_dialog(title, description,
                                         [dialogs.BUTTON_YES,
                                          dialogs.BUTTON_NO])

        if ret == dialogs.BUTTON_YES:
            for pi in playlist_infos:
                messages.DeletePlaylist(pi.id, pi.is_folder).send_to_backend()

    def quit_ui(self):
        """Quit  out of the UI event loop."""
        raise NotImplementedError()

    def about(self):
        dialogs.show_about()

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
            self.window.close()
        app.controller.shutdown()
        self.quit_ui()

    def connect_to_signals(self):
        signals.system.connect('error', self.handleError)
        signals.system.connect('download-complete', self.handleDownloadComplete)
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

    def handleDownloadComplete(self, obj, item):
        print "DOWLOAD COMPLETE"

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

        chkboxdialog = dialogs.CheckboxTextboxDialog(_("Internal Error"),_("Miro has encountered an internal error. You can help us track down this problem and fix it by submitting an error report."), _("Include entire program database including all video and channel metadata with crash report"), False, _("Describe what you were doing that caused this error"), dialogs.BUTTON_SUBMIT_REPORT, dialogs.BUTTON_IGNORE)
        chkboxdialog.run(callback)

    def onBackendShutdown(self, obj):
        logging.info('Shutting down...')

class WidgetsMessageHandler(messages.MessageHandler):
    def call_handler(self, method, message):
        call_on_ui_thread(method, message)

    def tablist_for_message(self, message):
        if message.type == 'feed':
            return app.tab_list_manager.feed_list
        elif message.type == 'playlist':
            return app.tab_list_manager.playlist_list
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
        app.widgetapp.build_window()

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
            print 'should update guides'
            return
        tablist = self.tablist_for_message(message)
        for id in message.removed:
            tablist.remove(id)
        for info in message.changed:
            tablist.update(info)
        for info in message.added:
            tablist.add(info)
        tablist.model_changed()

    def handle_item_list(self, message):
        current_display = app.display_manager.current_display
        if isinstance(current_display, displays.ItemListDisplay):
            if current_display.feed_id == message.feed_id:
                current_display.view.handle_item_list(message)
            else:
                logging.warn("wrong id for feed view (%s feed view: %s)",
                        message.feed_id, current_display.feed_id)
        else:
            logging.warn("got item list, but display is: %s", current_display)

    def handle_items_changed(self, message):
        current_display = app.display_manager.current_display
        if isinstance(current_display, displays.ItemListDisplay):
            if current_display.feed_id == message.feed_id:
                current_display.view.handle_items_changed(message)
            else:
                logging.warn("wrong id for feed view (%s feed view: %s)",
                        message.feed_id, current_display.feed_id)
        else:
            logging.warn("got item list, but display is: %s", current_display)

    def handle_download_count_changed(self, message):
        static_tab_list = app.tab_list_manager.static_tab_list
        static_tab_list.update_download_count(message.count)

    def handle_new_count_changed(self, message):
        static_tab_list = app.tab_list_manager.static_tab_list
        static_tab_list.update_new_count(message.count)
