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

import logging
import traceback

from miro import app
from miro import startup
from miro import signals
from miro import messages
from miro.gtcache import gettext as _
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import displays
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
        messages.FrontendMessage.install_handler(self.message_handler)

    def startup(self):
        self.connect_to_signals()
        startup.startup()

    def buildUI(self):
        app.tab_list_manager = tablistmanager.TabListManager()
        app.display_manager = displays.DisplayManager()
        self.window = MiroWindow(_("Miro"), Rect(100, 300, 800, 600))
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

    def on_video_time_change(self, slider, time):
        print 'seek to: ', time

    def on_volume_change(self, slider, volume):
        print 'volume change: ', volume

    def on_play_clicked(self, button):
        type, selected = app.tab_list_manager.get_selection()
        if len(selected) == 1:
            if type == 'feed':
                title = _("Rename Channel")
                text = _("Enter a new name for the channel %s" %
                        selected[0].name)
            elif type == 'playlist':
                title = _("Rename Playlist")
                text = _("Enter a new name for the playlist %s" %
                        selected[0].name)
            elif type == 'static':
                print 'cant rename static tabs: ', selected[0].name
                return
            else:
                raise ValueError("unknown type: %s" % type)
            response = dialogs.ask_for_string(title, text, selected[0].name)
            if response:
                if selected[0].is_folder:
                    type = '%s-folder' % type
                id = selected[0].id
                messages.RenameObject(type, id, response).send_to_backend()

    def on_stop_clicked(self, button):
        type, selected = app.tab_list_manager.get_selection()
        for tab in selected:
            if type == 'feed':
                message = messages.DeleteChannel(tab.id, tab.is_folder, False)
            elif type == 'playlist':
                message = messages.DeletePlaylist(tab.id, tab.is_folder)
            elif type == 'static':
                print 'cant delete static tab: ', tab.name
                return
            else:
                raise ValueError("unknown type: %s" % type)
            message.send_to_backend()

    def on_forward_clicked(self, button):
        title = _("New Channel Folder")
        text = _("Enter the new name for the new channel folder")
        response = dialogs.ask_for_string(title, text)
        if response:
            messages.NewChannelFolder(response).send_to_backend()

    def on_previous_clicked(self, button):
        title = _("New Playlist Folder")
        text = _("Enter the new name for the new playlist folder")
        response = dialogs.ask_for_string(title, text)
        if response:
            messages.NewPlaylistFolder(response).send_to_backend()

    def quit_ui(self):
        """Quit  out of the UI event loop."""
        raise NotImplementedError()

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
        call_on_ui_thread(self.buildUI)

    def handleDownloadComplete(self, obj, item):
        print "DOWLOAD COMPLETE"

    def handleError(self, obj, report):
        # I don't want to write the code in dialogs.py yet
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
        print 'Shutting down...'

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

    def handle_tabs_changed(self, message):
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
