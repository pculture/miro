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

"""messages.py -- Message passing between the frontend thread and the backend
thread.

The backend thread is the eventloop, which processes things like feed updates
and handles reading and writing to the database.  The frontend thread is the
thread of the UI toolkit we're using.  Communication between the two threads
is handled by passing messages between the two.  These messages are handled
asynchronously.

This module defines the messages that are passed between the two threads.
"""

import re

from folder import ChannelFolder, PlaylistFolder

class MessageHandler(object):
    def __init__(self):
        self.message_map = {} # maps message classes to method names

    def call_handler(self, method, message):
        """Arrange for a message handler method to be called in the correct
        thread.  Must be implemented by subclasses.
        """
        raise NotImplementedError()

    def handle(self, message):
        handler_name = self.get_message_handler_name(message)
        try:
            handler = getattr(self, handler_name)
        except AttributeError:
            pass
        else:
            self.call_handler(handler, message)

    def get_message_handler_name(self, message):
        try:
            return self.message_map[message.__class__]
        except KeyError:
            self.message_map[message.__class__] = \
                    self.calc_message_handler_name(message.__class__)
            return self.message_map[message.__class__]

    def calc_message_handler_name(self, message_class):
        def replace(match):
            return '%s_%s' % (match.group(1), match.group(2).lower())
        underscores = re.sub(r'([a-z])([A-Z])', replace,
                message_class.__name__)
        return 'handle_' + underscores.lower()


class Message(object):
    """Base class for all Messages."""

    @classmethod
    def install_handler(cls, handler):
        """Install a new message handler for this class.  When
        send_to_frontend() or send_to_backend() is called, this handler will
        be invoked.
        """
        cls.handler = handler

class BackendMessage(Message):
    """Base class for Messages that get sent to the backend."""

    def send_to_backend(self):
        self.handler.handle(self)


class FrontendMessage(Message):
    """Base class for Messages that get sent to the frontend."""

    def send_to_frontend(self):
        self.handler.handle(self)

# Backend Messages

class TrackChannels(BackendMessage):
    """Begin tracking channels.

    After this message is sent, the backend will send back a ChannelList
    message, then it will send ChannelAdded, ChannelRemoved and ChannelChanged
    messages whenever the channel list changes.
    """

class StopTrackingChannels(BackendMessage):
    """Stop tracking channels."""

class TrackPlaylists(BackendMessage):
    """Begin tracking playlists.

    After this message is sent, the backend will send back a PlaylistList
    message, then it will send PlaylistAdded, PlaylistRemoved and
    PlaylistChanged messages whenever the list of playlists changes.
    """

class StopTrackingPlaylists(BackendMessage):
    """Stop tracking playlists."""

# Frontend Messages
class ChannelInfo(object):
    """Tracks the state of a channel

    Attributes:

    name -- channel name
    id -- object id
    unwatched -- number of unwatched videos
    available -- number of newly downloaded videos
    children -- Child channels or None if this is not a folder
    """

    def __init__(self, channel_obj):
        self.name = channel_obj.getTitle()
        self.id = channel_obj.id
        self.unwatched = channel_obj.numUnwatched()
        self.available = channel_obj.numAvailable()
        if isinstance(channel_obj, ChannelFolder):
            self.children = []
        else:
            self.children = None

    def is_folder(self):
        return children is not None

class ChannelList(FrontendMessage):
    """Informs the frontend of the current channel list.

    Attributes:
    channels -- the current list of ChannelInfo objects.
    """

    def __init__(self):
        self.channels = []

    def append(self, info):
        self.channels.append(info)

class ChannelAdded(FrontendMessage):
    """Informs the frontend that a new channel has been added.

    Attributes:
    channel -- ChannelInfo object for the added channel
    added_after -- id of the previous channel in the channel list
    """

    def __init__(self, channel, added_after):
        self.channel = channel
        self.added_after = added_after

class ChannelRemoved(FrontendMessage):
    """Informs the frontend that a channel has been removed

    Attributes:
    channel -- ChannelInfo object for the removed channel
    """

    def __init__(self, channel):
        self.channel = channel

class ChannelChanged(FrontendMessage):
    """Informs the frontend that a channel has been changed

    Attributes:
    channel -- ChannelInfo object for the changed channel
    """

    def __init__(self, channel):
        self.channel = channel

class PlaylistInfo(object):
    """Tracks the state of a playlist

    Attributes:

    name -- playlist name
    id -- object id
    children -- Child playlists or None if this is not a folder
    """

    def __init__(self, playlist_obj):
        self.name = playlist_obj.getTitle()
        self.id = playlist_obj.id
        if isinstance(playlist_obj, PlaylistFolder):
            self.children = []
        else:
            self.children = None

    def is_folder(self):
        return children is not None

class PlaylistList(FrontendMessage):
    """Informs the frontend of the current list of playlists.

    Attributes:
    playlists -- the current list of PlaylistInfo objects.
    """

    def __init__(self):
        self.playlists = []

    def append(self, info):
        self.playlists.append(info)

class PlaylistAdded(FrontendMessage):
    """Informs the frontend that a new playlist has been added.

    Attributes:
    playlist -- PlaylistInfo object for the added playlist
    added_after -- id of the previous playlist in the list of playlists
    """

    def __init__(self, playlist, added_after):
        self.playlist = playlist
        self.added_after = added_after

class PlaylistRemoved(FrontendMessage):
    """Informs the frontend that a playlist has been removed

    Attributes:
    playlist -- PlaylistInfo object for the removed playlist
    """

    def __init__(self, playlist):
        self.playlist = playlist

class PlaylistChanged(FrontendMessage):
    """Informs the frontend that a playlist has been changed

    Attributes:
    playlist -- PlaylistInfo object for the changed playlist
    """

    def __init__(self, playlist):
        self.playlist = playlist
