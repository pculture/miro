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

"""messagehandler.py -- Backend message handler"""

from miro import eventloop
from miro import messages
from miro import views
from miro.folder import FolderBase
from miro.util import getSingletonDDBObject

class ViewTracker(object):
    """Handles tracking views for TrackChannels, TrackPlaylist and TrackFeed."""

    def __init__(self):
        self.view = self.get_view()
        self.view.addAddCallback(self.on_object_added)
        self.view.addRemoveCallback(self.on_object_removed)
        self.view.addChangeCallback(self.on_object_changed)
        self.reset_changes()

    def reset_changes(self):
        self.changed = set()
        self.added = set()
        self.removed = set()
        self.changes_pending = False

    def send_messages(self):
        # Try to reduce the number of messages we're sending out.
        self.added -= self.removed
        self.changed -= self.removed
        self.changed -= self.added

        for obj in self.added:
            self.make_added_message(obj).send_to_frontend()
        for obj in self.removed:
            self.make_removed_message(obj).send_to_frontend()
        for obj in self.changed:
            self.make_changed_message(obj).send_to_frontend()
        self.reset_changes()

    def schedule_send_messages(self):
        # We don't send messages immediately so that if an object gets changed
        # multiple times, only one callback gets sent.
        if not self.changes_pending:
            eventloop.addUrgentCall(self.send_messages, 'view tracker update' )
            self.changes_pending = True

    def on_object_added(self, obj, id):
        if obj in self.removed:
            # object was already removed, we need to send that message out
            # before we send the add message.
            self.send_messages()
        self.added.add(obj)
        self.schedule_send_messages()

    def on_object_removed(self, obj, id):
        self.removed.add(obj)
        self.schedule_send_messages()

    def on_object_changed(self, obj, id):
        self.changed.add(obj)
        self.schedule_send_messages()

    def unlink(self):
        self.view.removeAddCallback(self.on_object_added)
        self.view.removeRemoveCallback(self.on_object_removed)
        self.view.removeChangeCallback(self.on_object_changed)

class TabTracker(ViewTracker):
    def make_added_message(self, tab):
        added_after = self.view.getPrevID(tab.objID())
        if added_after == tab.objID(): # We are on the first object
            added_after =  None
        return self.AddedClass(self.InfoClass(tab.obj), added_after)

    def make_removed_message(self, tab):
        return self.RemovedClass(self.InfoClass(tab.obj))

    def make_changed_message(self, tab):
        return self.ChangedClass(self.InfoClass(tab.obj))

    def send_initial_list(self):
        response = self.ListClass()
        current_folder_info = None
        for tab in self.view:
            info = self.InfoClass(tab.obj)
            if tab.obj.getFolder() is None:
                response.append(info)
                if isinstance(tab.obj, FolderBase):
                    current_folder_info = info
                else:
                    current_folder_info = None
            else:
                if (current_folder_info is None or 
                        tab.obj.getFolder().id != current_folder_info.id):
                    raise AssertionError("Tab ordering is wrong")
                current_folder_info.children.append(info)
        response.send_to_frontend()

class ChannelTracker(TabTracker):
    ListClass = messages.ChannelList
    AddedClass = messages.ChannelAdded
    RemovedClass = messages.ChannelRemoved
    ChangedClass = messages.ChannelChanged
    InfoClass = messages.ChannelInfo

    def get_view(self):
        return getSingletonDDBObject(views.channelTabOrder).getView()

class PlaylistTracker(TabTracker):
    ListClass = messages.PlaylistList
    AddedClass = messages.PlaylistAdded
    RemovedClass = messages.PlaylistRemoved
    ChangedClass = messages.PlaylistChanged
    InfoClass = messages.PlaylistInfo

    def get_view(self):
        return getSingletonDDBObject(views.playlistTabOrder).getView()

class BackendMessageHandler(messages.MessageHandler):
    def __init__(self):
        messages.MessageHandler.__init__(self)
        self.channel_tracker = None
        self.playlist_tracker = None

    def call_handler(self, method, message):
        name = 'handling backend message: %s' % message
        eventloop.addUrgentCall(method, name, args=(message,))

    def handle_track_channels(self, message):
        if not self.channel_tracker:
            self.channel_tracker = ChannelTracker()
        self.channel_tracker.send_initial_list()

    def handle_stop_tracking_channels(self, message):
        if self.channel_tracker:
            self.channel_tracker.unlink()
            self.channel_tracker = None

    def handle_track_playlists(self, message):
        if not self.playlist_tracker:
            self.playlist_tracker = PlaylistTracker()
        self.playlist_tracker.send_initial_list()

    def handle_stop_tracking_playlists(self, message):
        if self.playlist_tracker:
            self.playlist_tracker.unlink()
            self.playlist_tracker = None

