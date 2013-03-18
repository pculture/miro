# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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

import errno
import logging
import os
import sys
import socket
import select
import struct
import threading
import time
import traceback
import uuid

from datetime import datetime
from hashlib import md5

from miro.gtcache import gettext as _
from miro import app
from miro import database
from miro import eventloop
from miro import messages
from miro import models
from miro import prefs
from miro import signals
from miro import filetypes
from miro import fileutil
from miro import util
from miro import schema
from miro import storedatabase
from miro import transcode
from miro import metadata
from miro.data import mappings
from miro.data import itemtrack
from miro.item import Item, SharingItem
from miro.fileobject import FilenameType
from miro.util import returns_filename

from miro.plat import resources
from miro.plat.utils import thread_body
from miro.plat.frontends.widgets.threads import call_on_ui_thread

try:
    import libdaap
except ImportError:
    from miro import libdaap

DAAP_META = ('dmap.itemkind,dmap.itemid,dmap.itemname,' +
             'dmap.containeritemid,dmap.parentcontainerid,' +
             'daap.songtime,daap.songsize,daap.songformat,' +
             'daap.songartist,daap.songalbum,daap.songgenre,' +
             'daap.songyear,daap.songtracknumber,daap.songuserrating,' +
             'org.participatoryculture.miro.itemkind,' +
             'com.apple.itunes.mediakind')

DAAP_PODCAST_KEY = 'com.apple.itunes.is-podcast-playlist'

supported_filetypes = filetypes.VIDEO_EXTENSIONS + filetypes.AUDIO_EXTENSIONS

# Conversion factor between our local duration (10th of a second)
# vs daap which is millisecond.
DURATION_SCALE = 1000

MIRO_ITEMKIND_MOVIE = (1 << 0)
MIRO_ITEMKIND_PODCAST = (1 << 1)
MIRO_ITEMKIND_SHOW = (1 << 2)
MIRO_ITEMKIND_CLIP = (1 << 3)

miro_itemkind_rmapping = {
    MIRO_ITEMKIND_MOVIE: u'movie',
    MIRO_ITEMKIND_SHOW: u'show',
    MIRO_ITEMKIND_CLIP: u'clip',
    MIRO_ITEMKIND_PODCAST: u'podcast'
}

# Windows Python does not have inet_ntop().  Sigh.  Fallback to this one,
# which isn't as good, if we do not have access to it.
def inet_ntop(af, ip):
    try:
        return socket.inet_ntop(af, ip)
    except AttributeError:
        if af == socket.AF_INET:
            return socket.inet_ntoa(ip)
        if af == socket.AF_INET6:
            return ':'.join('%x' % bit for bit in struct.unpack('!' + 'H' * 8,
                                                                ip))
        raise ValueError('unknown address family %d' % af)

class Share(object):
    """Backend object that tracks data for an active DAAP share."""
    _used_db_paths = set()

    def __init__(self, share_id, name, host, port):
        self.id = share_id
        self.name = name
        self.host = host
        self.port = port
        self.db_path, self.db = self.find_unused_db()
        self.db_info = database.DBInfo(self.db)
        self.__class__._used_db_paths.add(self.db_path)
        self.tracker = None
        # SharingInfo object for this share.  We use this to send updates to
        # the frontend when things change.
        self.info = None

    def destroy(self):
        if self.db is not None:
            self.db.close()
        if self.db_path:
            fileutil.delete(self.db_path)
        self.db = self.db_info = self.db_path = None

    def is_closed(self):
        return self.db is None

    def find_unused_db(self):
        """Find a DB path for our share that's not being used.

        This method will ensure that no 2 Share objects share the same DB
        path, but it will try delete and then reuse paths that were created by
        previous miro instances.
        """
        for candidate in self.generate_db_paths():
            if os.path.exists(candidate):
                try:
                    os.remove(candidate)
                except EnvironmentError, e:
                    logging.warn("Share.find_unused_db "
                                 "error removing %s (%s)" % (candidate, e))
                    continue
            return candidate, self.make_new_database(candidate)
        raise AssertionError("Couldn't find an unused path "
                             "for Share")

    @classmethod
    def generate_db_paths(cls):
        """Iterate through potential paths for a sharing db.
        """
        support_dir = app.config.get(prefs.SUPPORT_DIRECTORY)
        for i in xrange(300):
            candidate = os.path.join(support_dir, 'sharing-db-%s' % i)
            if candidate in cls._used_db_paths:
                continue
            yield candidate

    @classmethod
    def cleanup_old_databases(cls):
        """Remove any databases left by old miro processes."""
        for path in cls.generate_db_paths():
            if os.path.exists(path):
                try:
                    os.remove(path)
                except EnvironmentError:
                    logging.warn("Share.cleanup_old_databases(): error "
                                 "removing %s" % path)

    def make_new_database(self, path):
        return storedatabase.SharingLiveStorage(
            path, self.name, schema.sharing_object_schemas)

    def start_tracking(self):
        """Start tracking items on this share.

        This will create a SharingItemTrackerImpl that connects to the share
        using a separate thread.  Call stop_tracking() to end the tracking.
        """
        if self.tracker is None:
            self.tracker = SharingItemTrackerImpl(self)

    def stop_tracking(self):
        if self.tracker is not None:
            self.tracker.client_disconnect()
            self.tracker = None
            self.reset_database()
            if self.info:
                self.info.is_updating = False
                self.info.mount = False
                self.send_tabs_changed()

    def reset_database(self):
        SharingItem.delete(db_info=self.db_info)
        self.db.forget_all_objects()
        self.db.cache.clear_all()

    def set_info(self, info):
        """Set the SharingInfo to use to send updates for."""
        # FIXME: we probably shouldn't be modifying the SharingInfo directly
        # here (#19689)
        self.info = info

    def update_started(self):
        # FIXME: we probably shouldn't be modifying the SharingInfo directly
        # here (#19689)
        if self.info:
            self.info.is_updating = True
            self.send_tabs_changed()

    def update_finished(self, success=True):
        # FIXME: we probably shouldn't be modifying the SharingInfo directly
        # here (#19689)
        if self.info:
            self.info.mount = success
            self.info.is_updating = False
            self.send_tabs_changed()

    def send_tabs_changed(self):
        message = messages.TabsChanged('connect', [], [self.info], [])
        message.send_to_frontend()

class SharingTracker(object):
    """The sharing tracker is responsible for listening for available music
    shares and the main client connection code.  For each connected share,
    there is a separate SharingItemTrackerImpl() instance which is basically
    a backend for messagehandler.SharingItemTracker().
    """
    type = u'sharing'
    # These need to be the same size.
    CMD_QUIT = 'quit'
    CMD_PAUSE = 'paus'
    CMD_RESUME = 'resm'

    def __init__(self):
        self.name_to_id_map = dict()
        self.trackers = dict()
        self.shares = dict()
        # FIXME: we probably can remove this dict as part of #19689.  At the
        # last, we should give it a name that better distinguishes it from
        # shares
        self.available_shares = dict()
        self.r, self.w = util.make_dummy_socket_pair()
        self.paused = True
        self.event = threading.Event()
        libdaap.register_meta('org.participatoryculture.miro.itemkind', 'miKD',
                              libdaap.DMAP_TYPE_UBYTE)
        Share.cleanup_old_databases()

    def mdns_callback(self, added, fullname, host, port):
        eventloop.add_urgent_call(self.mdns_callback_backend, "mdns callback",
                                  args=[added, fullname, host, port])

    def try_to_add(self, share_id, fullname, host, port, uuid):
        def success(unused):
            logging.debug('SUCCESS!!')
            if self.available_shares.has_key(share_id):
                info = self.available_shares[share_id]
            else:
                info = None
            # It's been deleted or worse, deleted and recreated!
            if not info or info.connect_uuid != uuid:
                return
            info.connect_uuid = None
            info.share_available = True
            messages.TabsChanged('connect', [info], [], []).send_to_frontend()

        def failure(unused):
            logging.debug('FAILURE')
            if self.available_shares.has_key(share_id):
                info = self.available_shares[share_id]
            else:
                info = None
            if not info or info.connect_uuid != uuid:
                return
            info.connect_uuid = None

        def testconnect():
            client = libdaap.make_daap_client(host, port)
            if not client.connect() or client.databases() is None:
                raise IOError('test connect failed')
            client.disconnect()

        eventloop.call_in_thread(success,
                                 failure,
                                 testconnect,
                                 'DAAP test connect')

    def mdns_callback_backend(self, added, fullname, host, port):
        # SAFE: the shared name should be unique.  (Or else you could not
        # identify the resource).
        if fullname == app.sharing_manager.name:
            return
        # Need to come up with a unique ID for the share and that's a bit
        # tricky.  We need the id to:
        #   - Be uniquly determined by the host/port which is the one thing
        #   that stays the same throughout the share.  The fullname can
        #   change.
        #   - By accesible by the current name of the share, this is the only
        #   info we during avahi removal
        #
        # We take the hash of the host and the port to get the id, then map
        # the last-known name it.  We force the hash to be positive, since
        # other ids are always positive.
        if added:
            share_id = abs(hash((host, port)))
            self.name_to_id_map[fullname] = share_id
        else:
            try:
                share_id = self.name_to_id_map[fullname]
                del self.name_to_id_map[fullname]
                if share_id in self.name_to_id_map.values():
                    logging.debug('sharing: out of order add/remove during '
                                  'rename?')
                    return
            except KeyError:
                # If it doesn't exist then it's been taken care of so return.
                logging.debug('KeyError: name %s', fullname)
                return

        logging.debug(('gotten mdns callback share_id, added = %s '
                       ' fullname = %s host = %s port = %s'),
                      added, fullname, host, port)

        if added:
            # This added message could be just because the share name got
            # changed.  And if that's the case, see if the share's connected.
            # If it is not connected, it must have been removed from the
            # sidebar so we can add as normal.  If it was connected, make
            # sure we change the name of it, and just skip over adding the 
            # tab..  We don't do this if the share's not a connected one
            # because the remove/add sequence, there's no way to tell if the
            # share's just going away or not.
            #
            # Else, create the SharingInfo eagerly, so that duplicate messages
            # can use it to filter out.  We also create a unique stamp on it,
            # in case of errant implementations that try to register, delete,
            # and re-register the share.  The try_to_add() success/failure
            # callback can check whether info is still valid and if so, if it
            # is this particular info (if not, the uuid will be different and
            # and so should ignore).
            has_key = False
            for info in self.available_shares.values():
                if info.mount and info.host == host and info.port == port:
                    has_key = True
                    break
            if has_key:
                if info.stale_callback:
                    info.stale_callback.cancel()
                    info.stale_callback = None
                info.name = fullname
                message = messages.TabsChanged('connect', [], [info], [])
                message.send_to_frontend()
            else:
                # If the share has already been previously added, update the
                # fullname, and ensure it is not stale.  Furthermore, if
                # this share is actually displayed, then change the tab.
                if share_id in self.available_shares.keys():
                    info = self.available_shares[share_id]
                    info.name = fullname
                    if info.share_available:
                        logging.debug('Share already registered and '
                                      'available, sending TabsChanged only')
                        if info.stale_callback:
                            info.stale_callback.cancel()
                            info.stale_callback = None
                        message = messages.TabsChanged('connect', [],
                                                       [info], [])
                        message.send_to_frontend()
                    return
                share = Share(share_id, fullname, host, port)
                info = messages.SharingInfo(share)
                share.set_info(info)
                self.shares[share_id] = share
                # FIXME: We should probably only store the Share object and
                # create new SharingInfo objects when we want to send updates
                # to the frontend (see #19689)
                info.connect_uuid = uuid.uuid4()
                self.available_shares[share_id] = info
                self.try_to_add(share_id, fullname, host, port,
                                    info.connect_uuid)
        else:
            # The mDNS publish is going away.  Are we connected?  If we
            # are connected, keep it around.  If not, make it disappear.
            # SharingDisappeared() kicks off the necessary bits in the 
            # frontend for us.
            if not share_id in self.trackers.keys():
                victim = self.available_shares[share_id]
                del self.available_shares[share_id]
                self.destroy_share(share_id)
                # Only tell the frontend if the share's been tested because
                # otherwise the TabsChanged() message wouldn't have arrived.
                if victim.connect_uuid is None:
                    messages.SharingDisappeared(victim).send_to_frontend()
            else:
                # We don't know if the share's alive or not... what to do
                # here?  Let's add a timeout of 2 secs, if no added message
                # comes in, assume it's gone bye...
                share_info = self.available_shares[share_id]
                tracker_share_info = self.trackers[share_id].share.info
                if tracker_share_info != share_info:
                    logging.error('Share disconn error: share info != share')
                dc = eventloop.add_timeout(2, self.remove_timeout_callback,
                                      "share tab removal timeout callback",
                                      args=(share_id, share_info))
                # Cancel pending callback is there is one.
                if tracker_share_info.stale_callback:
                    tracker_share_info.stale_callback.cancel()
                tracker_share_info.stale_callback = dc

    def destroy_share(self, share_id):
        self.shares[share_id].destroy()
        del self.shares[share_id]

    def remove_timeout_callback(self, share_id, share_info):
        del self.available_shares[share_id]
        self.destroy_share(share_id)
        messages.SharingDisappeared(share_info).send_to_frontend()

    def server_thread(self):
        # Wait for the resume message from the sharing manager as 
        # startup protocol of this thread.
        while True:
            try:
                r, w, x = select.select([self.r], [], [])
                if self.r in r:
                    cmd = self.r.recv(4)
                    if cmd == SharingTracker.CMD_RESUME:
                        self.paused = False
                        break
                    # User quit very quickly.
                    elif cmd == SharingTracker.CMD_QUIT:
                        return
                    raise ValueError('bad startup message received')
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue
            except StandardError, err:
                raise ValueError('unknown error during select %s' % str(err))

        if app.sharing_manager.mdns_present:
            callback = libdaap.mdns_browse(self.mdns_callback)
        else:
            callback = None
        while True:
            refs = []
            if callback is not None and not self.paused:
                refs = callback.get_refs()
            try:
                # Once we get a shutdown signal (from self.r/self.w socketpair)
                # we return immediately.  I think this is okay since we are 
                # passive listener and we only stop tracking on shutdown,
                #  OS will help us close all outstanding sockets including that
                # for this listener when this process terminates.
                r, w, x = select.select(refs + [self.r], [], [])
                if self.r in r:
                    cmd = self.r.recv(4)
                    if cmd == SharingTracker.CMD_QUIT:
                        return
                    if cmd == SharingTracker.CMD_PAUSE:
                        self.paused = True
                        self.event.set()
                        continue
                    if cmd == SharingTracker.CMD_RESUME:
                        self.paused = False
                        continue
                    raise
                for i in r:
                    if i in refs:
                        callback(i)
            # XXX what to do in case of error?  How to pass back to user?
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue
                else:
                    pass
            except StandardError:
                pass

    def start_tracking(self):
        # sigh.  New thread.  Unfortunately it's kind of hard to integrate
        # it into the application runloop at this moment ...
        self.thread = threading.Thread(target=thread_body,
                                       args=[self.server_thread],
                                       name='mDNS Browser Thread')
        self.thread.start()

    def track_share(self, share_id):
        try:
            self.shares[share_id].start_tracking()
        except KeyError:
            logging.warn("SharingTracker.stop_tracking_share: "
                         "Unknown share_id: %s", share_id)

    def stop_tracking_share(self, share_id):
        try:
            self.shares[share_id].stop_tracking()
        except KeyError:
            logging.warn("SharingTracker.stop_tracking_share: "
                         "Unknown share_id: %s", share_id)
    def stop_tracking(self):
        # What to do in case of socket error here?
        self.w.send(SharingTracker.CMD_QUIT)

    # pause/resume is only meant to be used by the sharing manager.
    # Pause needs to be synchronous because we want to make sure this module
    # is in a quiescent state.
    def pause(self):
        # What to do in case of socket error here?
        self.w.send(SharingTracker.CMD_PAUSE)
        self.event.wait()
        self.event.clear()

    def resume(self):
        # What to do in case of socket error here?
        self.w.send(SharingTracker.CMD_RESUME)

class _ClientUpdateResult(object):
    """Stores the results of a client update.

    One issue we must deal with is that we only want to access the daap client
    in the thread maid for it.  However, we want to create SharingItems in the
    backend thread.

    This class helps that by calling all the daap client methods that we need
    to inside the daap client thread, then allows us to access the data from
    the backend thread.

    Attributes:
        items - dictionary tracking items that have been added/updated.  Maps
                item ids to dicts of item data
        item_paths - dictionary mapping item ids to their paths for
                added/updated items
        deleted_items - list of item ids for deleted items
        playlists - dictionary tracking the playlists that have been
                    added/updated.  Maps playlist ids to dicts of playlist
                    data deleted_playlist - list of playlist ids for deleted
                    playlist
        deleted_playlist - list of playlist ids for deleted playlists
        playlist_items - dictionary tracking items added/updated in playlists.
                         Maps playlist ids to list of item ids
        playlist_deleted_items - dictionary tracking items deleted from
                                 playlists.  Maps playlist ids to a list of
                                 item ids.
    """
    def __init__(self, client, update=False):
        self.update = update
        self.items = {}
        self.item_paths = {}
        self.deleted_items = []
        self.playlists = {}
        self.deleted_playlists = []
        self.playlist_items = {}
        self.playlist_deleted_items = {}

        self.fetch_from_client(client)

    def strip_nuls_from_data(self, data_list):
        """Strip nul characters from items/playlist data

        :param data_list: list of dicts containing playlist/item data.  For
        each string value of each dict nuls will be removed
        """
        for data in data_list:
            for key, value in data.items():
                if isinstance(value, str):
                    data[key] = value.replace('\x00', '')

    def fetch_from_client(self, client):
        if not self.update:
            self.check_database_exists(client)
        self.fetch_playlists(client)
        self.fetch_items(client)
        for daap_id in self.playlists.keys():
            self.fetch_playlist_items(client, daap_id)

    def check_database_exists(self, client):
        if not client.databases(update=self.update):
            raise IOError('Cannot get database')

    def fetch_playlists(self, client):
        self.playlists, self.deleted_playlists = client.playlists(
            update=self.update)
        if self.playlists is None:
            raise IOError('Cannot get playlist')
        # Clean the playlist: remove NUL characters.
        self.strip_nuls_from_data(self.playlists.values())
        # Only return playlist that are not the base playlist.  We don't
        # explicitly show base playlist.
        for daap_id, data in self.playlists.items():
            if data.get('daap.baseplaylist', False):
                del self.playlists[daap_id]

    def fetch_items(self, client):
        self.items, self.deleted_items = client.items(
            meta=DAAP_META,
            update=self.update)
        if self.items is None:
            raise ValueError('Cannot find items in base playlist')

        self.strip_nuls_from_data(self.items.values())
        for daap_id, item_data in self.items.items():
            self.item_paths[daap_id] = client.daap_get_file_request(
                daap_id, item_data['daap.songformat'])

    def fetch_playlist_items(self, client, playlist_key):
        items, deleted = client.items(playlist_id=playlist_key,
                                      meta=DAAP_META, update=self.update)
        if items is None:
            raise ValueError('Cannot find items for playlist %d' % k)
        self.playlist_items[playlist_key] = items.keys()
        self.playlist_deleted_items[playlist_key] = deleted

class _ClientPlaylistTracker(object):
    """Tracks playlist data from the DAAP client for SharingItemTrackerImpl

    Attributes:
        playlist_data - maps DAAP ids to the latest playlist data for them
        playlist_items - maps DAAP playlist ids to sets of DAAP item ids
    """
    def __init__(self):
        self.playlist_data = {}
        self.playlist_items = {}

    def update(self, result):
        """Update data
        
        :param result: _ClientUpdateResult
        """
        for playlist_id, playlist_data in result.playlists.items():
            if playlist_id not in self.playlist_data:
                self.playlist_items[playlist_id] = set()
            self.playlist_data[playlist_id] = playlist_data
        for playlist_id in result.deleted_playlists:
            del self.playlist_data[playlist_id]
            del self.playlist_items[playlist_id]
        for playlist_id, item_ids in result.playlist_items.items():
            self.playlist_items[playlist_id].update(item_ids)
        for playlist_id, item_ids in result.playlist_deleted_items.items():
            self.playlist_items[playlist_id].difference_update(item_ids)

    def current_playlists(self):
        """Get a the playlists that should be visible.  """
        return dict((id_, data)
                    for id_, data in self.playlist_data.items()
                    if self.playlist_items.get(id_) and
                    self.playlist_data_valid(data))

    def playlist_data_valid(self, playlist_data):
        return (playlist_data.get('dmap.itemid') and
                playlist_data.get('dmap.itemname'))

    def items_in_podcasts(self):
        """Get the set of item ids in any podcast playlist."""
        rv = set()
        for daap_id, playlist_data in self.playlist_data.items():
            if playlist_data.get(DAAP_PODCAST_KEY):
                rv.update(self.playlist_items[daap_id])
        return rv

    def items_in_playlists(self):
        """Get the set of item ids in any non-podcast playlist."""
        rv = set()
        for daap_id, playlist_data in self.playlist_data.items():
            if not playlist_data.get(DAAP_PODCAST_KEY):
                rv.update(self.playlist_items[daap_id])
        return rv

# Synchronization issues: this code is a bit sneaky, so here is an explanation
# of how it works.  When you click on a share tab in the frontend, the 
# display (the item list controller) starts tracking the items.  It does
# so by sending a message to the backend.  If it was previously unconnected
# a new SharingItemTrackerImpl() will be created, and connect() is called,
# which may take an indeterminate period of time, so this is farmed off
# to an external thread.  When the connection is successful, a callback will
# be called which is run on the backend (eventloop) thread which adds the
# items and playlists to the SharingItemTrackerImpl tracker object. 
# At the same time, handle_item_list() is called after the tracker is created
# which will be empty at this time, because the items have not yet been added.
# (recall that the callback runs in the eventloop, we are already in the 
# eventloop so this could not have happened prior to handle_item_list()
# being called).
#
# The SharingItemTrackerImpl() object is designed to be persistent until
# disconnection happens.  If you click on a tab that's already connected,
# it finds the appropriate tracker and calls handle_item_list.  Either it is
# already populated, or if connection is still in process will return empty
# list until the connection success callback is called.
class SharingItemTrackerImpl(object):
    """Handle the backend work to track a single share

    SharingItemTrackerImpl creates a thread to connect and monitor the DAAP
    client.  As we get changes from the DAAP server, we update the database in
    the backend thread.

    This backend is persistent as the user switches across different tabs in
    the sidebar, until the disconnect button is clicked.
    """

    # Maps DAAP keys to DeviceItem attribute names
    daap_mapping = {
        'daap.songformat': 'file_format',
        'com.apple.itunes.mediakind': 'file_type',
        'dmap.itemid': 'daap_id',
        'dmap.itemname': 'title',
        'daap.songtime': 'duration',
        'daap.songsize': 'size',
        'daap.songartist': 'artist',
        'daap.songalbumartist': 'album_artist',
        'daap.songalbum': 'album',
        'daap.songyear': 'year',
        'daap.songgenre': 'genre',
        'daap.songtracknumber': 'track',
        'org.participatoryculture.miro.itemkind': 'kind',
        'com.apple.itunes.series-name': 'show',
        'com.apple.itunes.season-num': 'season_number',
        'com.apple.itunes.episode-num-str': 'episode_id',
        'com.apple.itunes.episode-sort': 'episode_number'
    }

    def __init__(self, share):
        self.client = None
        self.share = share
        self.playlist_item_map = mappings.SharingItemPlaylistMap(
            share.db_info.db.connection)
        self.current_item_ids = set()
        self.current_playlist_ids = set()
        self.playlist_tracker = _ClientPlaylistTracker()
        self.info_cache = dict()
        self.share.update_started()
        self.start_thread()

    def start_thread(self):
        name = self.share.name
        host = self.share.host
        port = self.share.port
        title = 'Sharing Client %s @ (%s, %s)' % (name, host, port)
        self.thread = threading.Thread(target=self.runloop,
                                       name=title)
        self.thread.daemon = True
        self.thread.start()

    def run(self, func, success, failure):
        succeeded = False
        try:
            result = func()
        except KeyboardInterrupt:
            raise
        except Exception, e:
                logging.debug('>>> Exception %s %s', self.thread.name,
                              ''.join(traceback.format_exc()))
                func = failure
                name = 'error callback (%s)' % self.thread.name
                args = (e,)
        else:
                func = success
                name = 'result callback (%s)' % self.thread.name
                args = (result,)
                succeeded = True
        eventloop.add_idle(func, name, args=args)
        return succeeded

    def run_client_connect(self):
        return self.run(self.client_connect, self.client_connect_callback,
                        self.client_connect_error_callback)

    def run_client_update(self):
        return self.run(self.client_update, self.client_update_callback,
                        self.client_update_error_callback)

    def runloop(self):
        success = self.run_client_connect()
        # If server does not support update, then we short circuit since
        # the loop becomes useless.  There is nothing wait for being updated.
        logging.debug('UPDATE SUPPORTED = %s', self.client.supports_update)
        if not success or not self.client.supports_update:
            return
        while True:
            success = self.run_client_update()
            if not success:
                break

    def convert_raw_sharing_item(self, rawitem, result):
        """Convert raw data from libdaap to the attributes of SharingItem
        """
        item_data = dict()
        for k in rawitem.keys():
            try:
                key = self.daap_mapping[k]
            except KeyError:
                # Got something back we don't really care about.
                continue
            item_data[key] = rawitem[k]
            if isinstance(rawitem[k], str):
                item_data[key] = item_data[key].decode('utf-8')

        try:
            item_data['kind'] = miro_itemkind_rmapping[item_data['kind']]
        except KeyError:
            pass

        # Fix this up.
        file_type = u'audio'    # fallback
        try:
            if item_data['file_type'] == libdaap.DAAP_MEDIAKIND_AUDIO:
                file_type = u'audio'
            if item_data['file_type'] in [libdaap.DAAP_MEDIAKIND_TV,
                                          libdaap.DAAP_MEDIAKIND_MOVIE,
                                          libdaap.DAAP_MEDIAKIND_VIDEO
                                         ]:
                file_type = u'video'
        except KeyError:
           # Whoups.  Server didn't send one over?  Assume default.
           pass

        item_data['file_type'] = file_type
        item_data['video_path'] = self.get_item_path(result,
                                                     item_data['daap_id'])
        item_data['file_type'] = file_type
        return item_data

    def get_item_path(self, result, daap_id):
        return unicode(result.item_paths[daap_id])

    def make_sharing_item(self, rawitem, result):
        kwargs = self.convert_raw_sharing_item(rawitem, result)
        kwargs['host'] = unicode(self.client.host)
        kwargs['port'] = self.client.port
        kwargs['address'] = unicode(self.address)
        return SharingItem(self.share, **kwargs)

    def get_sharing_item(self, daap_id):
        return SharingItem.get_by_daap_id(daap_id, db_info=self.share.db_info)

    def make_playlist_sharing_info(self, daap_id, playlist_data):
        return messages.SharingPlaylistInfo(
            self.share.id,
            playlist_data['dmap.itemname'],
            daap_id,
            playlist_data.get(DAAP_PODCAST_KEY, False))

    def client_disconnect(self):
        client = self.client
        self.client = None
        eventloop.call_in_thread(self.client_disconnect_callback,
                                 self.client_disconnect_error_callback,
                                 client.disconnect,
                                 'DAAP client connect')

    def client_disconnect_error_callback(self, unused):
        self.client_disconnect_callback_common()

    def client_disconnect_callback(self, unused):
        self.client_disconnect_callback_common()

    def client_disconnect_callback_common(self):
        message = messages.TabsChanged('connect', [], [],
                                       list(self.current_playlist_ids))
        message.send_to_frontend()

    def client_connect(self):
        self.make_client()
        result = _ClientUpdateResult(self.client)
        return result

    def make_client(self):
        name = self.share.name
        host = self.share.host
        port = self.share.port
        self.client = libdaap.make_daap_client(host, port)
        if not self.client.connect():
            # XXX API does not allow us to send more detailed results
            # back to the poor user.
            raise IOError('Cannot connect')
        # XXX Dodgy: Windows name resolution sucks so we get a free ride
        # off the main connection with getpeername(), so we can use the IP
        # value to connect subsequently.   But we have to poke into the 
        # semi private data structure to get the socket structure.  
        # Lousy Windows and Python API.
        address, port = self.client.conn.sock.getpeername()
        self.address = address

    def client_update(self):
        logging.debug('CLIENT UPDATE')
        self.client.update()
        result = _ClientUpdateResult(self.client, update=True)
        return result

    def client_update_callback(self, result):
        logging.debug('CLIENT UPDATE CALLBACK')
        if self.share.is_closed():
            logging.warn("client_update_callback: database is closed")
            return
        self.update_sharing_items(result)
        self.update_playlists(result)

    def client_update_error_callback(self, unused):
        if self.share.is_closed():
            logging.stacktrace("client_update_error_callback: "
                               "database is closed")
            return
        self.client_connect_update_error_callback(unused, update=True)

    # NB: this runs in the eventloop (backend) thread.
    def client_connect_callback(self, result):
        # ignore deleted items for the first run
        if self.share.is_closed():
            logging.warn("client_connect_callback: database is closed")
            return
        result.deleted_items = []
        result.deleted_playlists = []
        result.playlist_deleted_items = {}
        self.update_sharing_items(result)
        self.update_playlists(result)
        self.share.update_finished()

    def update_sharing_items(self, result):
        """Create or update SharingItems on the database.

        :param new_item_data: _ClientUpdateResult
        """
        for daap_id, item_data in result.items.items():
            if daap_id not in self.current_item_ids:
                self.make_sharing_item(item_data, result)
                self.current_item_ids.add(daap_id)
            else:
                sharing_item = self.get_sharing_item(daap_id)
                new_data = self.convert_raw_sharing_item(item_data, result)
                for key, value in new_data.items():
                    setattr(sharing_item, key, value)
                sharing_item.signal_change()
        for item_id in result.deleted_items:
            try:
                sharing_item = SharingItem.get_by_daap_id(
                    item_id, db_info=self.share.db_info)
            except database.ObjectNotFoundError:
                logging.warn("SharingItemTrackerImpl.update_sharing_items: "
                             "deleted item not found: %s", item_id)
            sharing_item.remove()

    def update_playlists(self, result):
        added = []
        # We always send the share as changed since we're updating its
        # contents.
        changed = []
        removed = []

        old_playlist_items = {}
        for daap_id, item_ids in self.playlist_tracker.playlist_items.items():
            old_playlist_items[daap_id] = item_ids.copy()

        self.playlist_tracker.update(result)
        # update the playlist item map
        playlist_items_changed = False
        new_playlist_items = self.playlist_tracker.playlist_items
        for playlist_id in old_playlist_items:
            if playlist_id not in new_playlist_items:
                self.playlist_item_map.remove_playlist(playlist_id)
                playlist_items_changed = True
        for playlist_id, item_ids in new_playlist_items.items():
            if item_ids != old_playlist_items.get(playlist_id):
                self.playlist_item_map.set_playlist_items(playlist_id,
                                                          item_ids)
                playlist_items_changed = True

        current_playlists = self.playlist_tracker.current_playlists()
        # check for added/changed playlists
        for daap_id, playlist_data in current_playlists.items():
            if daap_id not in self.current_playlist_ids:
                added.append(
                    self.make_playlist_sharing_info(daap_id, playlist_data))
                self.current_playlist_ids.add(daap_id)
            elif daap_id in result.playlists:
                changed.append(
                    self.make_playlist_sharing_info(daap_id, playlist_data))
        # check for removed playlists
        removed.extend(self.current_playlist_ids -
                       set(current_playlists.keys()))
        self.current_playlist_ids = set(current_playlists.keys())
        if playlist_items_changed or added or changed or removed:
            SharingItem.change_tracker.playlist_changed(self.share.id)
            self.update_fake_playlists()

        message = messages.TabsChanged('connect', added, changed, removed)
        message.send_to_frontend()

    def update_fake_playlists(self):
        self.playlist_item_map.set_playlist_items(
            u'podcast', self.playlist_tracker.items_in_podcasts())
        self.playlist_item_map.set_playlist_items(
            u'playlist', self.playlist_tracker.items_in_playlists())

    def client_connect_error_callback(self, unused):
        self.client_connect_update_error_callback(unused)

    def client_connect_update_error_callback(self, unused, update=False):
        # If it didn't work, immediately disconnect ourselves.
        # Non atomic test-and-do check ok - always in eventloop.
        if self.client is None:
            # someone already did handy-work for us - probably a disconnect
            # happened while we were in the middle of an update().
            return
        if not update:
            self.share.update_finished(success=False)
        if not self.share.info.stale_callback:
            app.sharing_tracker.stop_tracking_share(self.share.id)
        messages.SharingConnectFailed(self.share).send_to_frontend()

class _SharedDataSet(object):
    """Tracks the items/playlist/feeds we're sharing to others.

    This object is used by SharingManagerBackend to track the database objects
    its sharing.  It needs to be thread-safe since it gets updated in the
    backend thread and accessed in the server thread for our share.
    """
    SHARE_AUDIO = libdaap.DAAP_MEDIAKIND_AUDIO
    SHARE_VIDEO = libdaap.DAAP_MEDIAKIND_VIDEO
    SHARE_FEED  = 0x4    # XXX

    # Maps ItemInfo attribute names to DAAP keys.
    daap_mapping = {
        'id': 'dmap.itemid',
        'title': 'dmap.itemname',
        'duration': 'daap.songtime',
        'size': 'daap.songsize',
        'artist': 'daap.songartist',
        'album_artist': 'daap.songalbumartist',
        'album': 'daap.songalbum',
        'year': 'daap.songyear',
        'genre': 'daap.songgenre',
        'track': 'daap.songtracknumber',
        'show': 'com.apple.itunes.series-name',
        'season_number': 'com.apple.itunes.season-num',
        'episode_id': 'com.apple.itunes.episode-num-str',
        'episode_number': 'com.apple.itunes.episode-sort'
    }

    # Map values for ItemInfo.kind to DAAP values
    miro_itemkind_mapping = {
        'movie': MIRO_ITEMKIND_MOVIE,
        'show': MIRO_ITEMKIND_SHOW,
        'clip': MIRO_ITEMKIND_CLIP,
        'podcast': MIRO_ITEMKIND_PODCAST
    }

    def __init__(self):
        # our lock must be acquired before acsessing any of our data.  Our
        # condition gets signaled when changes occur.
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        # current revision number
        self.revision = 1
        # map DAAP ids to dicts of item data
        self.daap_items = dict()
        # map DAAP ids to dicts of playlist data
        self.daap_playlists = dict()
        # map DAAP playlist ids to sets of items in that playlist
        self.playlist_item_map = dict() # Playlist -> item mapping
        # map DAAP playlist ids to sets of items that have been removed from
        # that playlist.
        self.deleted_item_map = dict()  # Playlist -> deleted item mapping
        # signal handle and trackers that we create in start_tracking()
        self.config_handle = None
        self.item_tracker = None
        self.playlist_tracker = None
        self.feed_tracker = None
        self.after_event_finished_handle = None
        self.item_changes_handle = None
        # store SavedPlaylist/Feed objects that have been
        # added/changed/removed.  We save up the changes, then process them
        # all at once when the eventloop emits "event-finished".
        self.playlists_changed = set()
        self.playlists_removed = set()

    def _deleted_item(self, daap_id):
        """Make a dict for a delete playlist or item."""
        return {
            'revision': self.revision,
            'valid': False,
            'dmap.itemid': daap_id,
        }

    def start_tracking(self):
        with self.lock:
            # make trackers
            self.calc_share_types()
            self.config_handle = app.backend_config_watcher.connect('changed',
                                 self.on_config_changed)
            # setup initial data
            self.start_tracking_items()
            self.start_tracking_playlists()
            if _SharedDataSet.SHARE_FEED in self.share_types:
                self.start_tracking_feeds()
            self.after_event_finished_handle = eventloop.connect_after(
                'event-finished', self.after_event_finished)
            self.item_changes_handle = models.Item.change_tracker.connect(
                'item-changes', self.on_item_changes)

    def stop_tracking(self):
        if self.config_handle is not None:
            backend_config_watcher.disconnect(self.config_handle)
            self.config_handle = None
        if self.item_tracker is not None:
            self.item_tracker.destroy()
            self.item_tracker = None
        if self.playlist_tracker is not None:
            self.playlist_tracker.unlink()
            self.playlist_tracker = None
        if self.feed_tracker is not None:
            self.feed_tracker.unlink()
            self.feed_tracker = None
        if self.after_event_finished_handle:
            eventloop.disconnect(self.after_event_finished_handle)
            self.after_event_finished_handle = None
        if self.item_changes_handle:
            models.Item.changes.disconnect(self.item_changes_handle)
            self.item_changes_handle = None

    def calc_share_types(self):
        self.share_types = set()
        if app.config.get(prefs.SHARE_AUDIO):
            self.share_types.add(_SharedDataSet.SHARE_AUDIO)
        if app.config.get(prefs.SHARE_VIDEO):
            self.share_types.add(_SharedDataSet.SHARE_VIDEO)
        if app.config.get(prefs.SHARE_FEED):
            self.share_types.add(_SharedDataSet.SHARE_FEED)

    def start_tracking_items(self):
        query = self._make_item_tracker_query()
        self.item_tracker = itemtrack.BackendItemTracker(query)
        for item_info in self.item_tracker.get_items():
            self.make_daap_item(item_info)
        self.item_tracker.connect('items-changed', self.on_items_changed)

    def start_tracking_playlists(self):
        view = models.SavedPlaylist.make_view()
        for playlist in view:
            self.make_daap_playlist(playlist)
        self.playlist_tracker = view.make_tracker()
        self.playlist_tracker.connect('added', self.on_playlist_added)
        self.playlist_tracker.connect('changed', self.on_playlist_changed)
        self.playlist_tracker.connect('removed', self.on_playlist_removed)

    def start_tracking_feeds(self):
        if self.feed_tracker is None:
            view = models.Feed.visible_view()
            for feed in view:
                self.make_daap_playlist(feed)
            self.feed_tracker = view.make_tracker()
            self.feed_tracker.connect('added', self.on_playlist_added)
            self.feed_tracker.connect('changed', self.on_playlist_changed)
            self.feed_tracker.connect('removed', self.on_playlist_removed)

    def stop_tracking_feeds(self):
        if self.feed_tracker is not None:
            self.feed_tracker.unlink()
            self.feed_tracker = None
            # Remove all feeds from our lists
            for feed in models.Feed.visible_view():
                self.daap_playlists[feed.id] = self._deleted_item(feed.id)

    def on_items_changed(self, tracker, added, changed, removed):
        with self.lock:
            self.revision += 1
            for item_info in added + changed:
                self.make_daap_item(item_info)
            for item_id in removed:
                self.daap_items[item_id] = self._deleted_item(item_id)
            self.condition.notify_all()

    def on_playlist_added(self, tracker, playlist_or_feed):
        self.playlists_changed.add(playlist_or_feed)

    def on_playlist_changed(self, tracker, playlist_or_feed):
        self.playlists_changed.add(playlist_or_feed)

    def on_playlist_removed(self, tracker, playlist_or_feed):
        self.playlists_removed.add(playlist_or_feed)

    def after_event_finished(self, eventloop, success):
        if not (self.playlists_changed or self.playlists_removed):
            return
        with self.lock:
            self.revision += 1
            for obj in self.playlists_changed:
                self.make_daap_playlist(obj)
            for obj in self.playlists_removed:
                self.daap_playlists[obj.id] = self._deleted_item(obj.id)
            self.playlists_changed = set()
            self.playlists_removed = set()
            self.condition.notify_all()

    def on_item_changes(self, tracker, message):
        if 'feed_id' in message.changed_columns:
            # items have changed feeds, regenerate the item lists
            for feed in models.Feed.visible_view():
                self.make_daap_playlist(feed)
        if message.playlists_changed:
            # items have been added/removed from playlists,
            # regenerate the item lists
            for playlist in models.SavedPlaylist.make_view():
                self.make_daap_playlist(playlist)

    def _make_item_tracker_query(self):
        query = itemtrack.ItemTrackerQuery()
        # we can do this simply when SHARE_AUDIO and SHARE_VIDEO are selected
        if (_SharedDataSet.SHARE_AUDIO in self.share_types and
            _SharedDataSet.SHARE_VIDEO in self.share_types):
            query.add_complex_condition(
                ['file_type'], 'item.file_type IN ("audio", "video")')
            return query

        # No matter what, we only care about audio/video items
        query.add_complex_condition(['file_type'],
                                    'item.file_type IN ("audio", "video")')

        # Based on the preferences, we OR together various other conditions
        extra_sql_parts = []
        extra_sql_columns = set()
        if _SharedDataSet.SHARE_AUDIO in self.share_types:
            extra_sql_parts.append('file_type = "audio"')
            extra_sql_columns.add('file_type')
        if _SharedDataSet.SHARE_VIDEO in self.share_types:
            extra_sql_parts.append('file_type = "video"')
            extra_sql_columns.add('file_type')
        if _SharedDataSet.SHARE_FEED in self.share_types:
            extra_sql_parts.append('feed.visible')
            extra_sql_columns.add('feed.visible')
        # items in playlists are always included
        extra_sql_parts.append('playlist_item_map.playlist_id IS NOT NULL')
        extra_sql_columns.add('playlist_item_map.playlist_id')
        # OR together all the parts into a complex condition
        sql = ' OR '.join('(%s)' % part for part in extra_sql_parts)
        query.add_complex_condition(extra_sql_columns, sql)
        return query

    def make_daap_item(self, item_info):
        daap_item = dict()
        # Set attributes in daap_mapping
        for attr_name, key_name in self.daap_mapping.items():
            value = getattr(item_info, attr_name)
            # Fixup the year, etc being -1.  XXX should read the daap
            # type then determine what to do.
            if value == -1:
                value = 0
            # Fixup: these are stored as string?
            if key_name in ('daap.songtracknumber',
                               'daap.songyear'):
                if value is not None:
                    value = int(value)
            # Fixup the duration: need to convert to millisecond.
            elif key_name == 'daap.songtime':
                if value:
                    value *= DURATION_SCALE
                else:
                    value = 0
            daap_item[key_name] = value
        # add attributes that need to be calculated
        self._calc_item_kind(item_info, daap_item)
        self._calc_item_format_mediakind(item_info, daap_item)
        self._calc_item_paths(item_info, daap_item)
        # add attributes for keys needed by libdaap, but aren't part of DAAP
        # itself
        daap_item['dmap.containeritemid'] = item_info.id
        daap_item['revision'] = self.revision
        daap_item['valid'] = True
        # Convert unicode to utf-8
        for key, value in daap_item.items():
            if isinstance(value, unicode):
                daap_item[key] = value.encode('utf-8')
        # store the data
        self.daap_items[item_info.id] = daap_item

    # XXX TEMPORARY: should this item be podcast?  We won't need this when
    # the item type's metadata is completely accurate and won't lie to us.
    def _item_from_podcast(self, item_info):
        feed_url = item_info.feed_url
        if feed_url is None:
            logging.warn("_item_from_podcast: feed_url is None for %s",
                         item_info.title)
            return False
        ersatz_feeds = ['dtv:manualFeed', 'dtv:searchDownloads', 'dtv:search']
        is_feed = not any([feed_url.startswith(x) for x in ersatz_feeds])
        return item_info.feed_id and is_feed and not item_info.is_file_item

    def _calc_item_kind(self, item_info, daap_item):
        """Calculate the value for org.participatoryculture.miro.itemkind

        :param item_info: ItemInfo to get the value from
        :param daap_item: dict of DAAP data to set the value for
        """
        key = 'org.participatoryculture.miro.itemkind'
        if self._item_from_podcast(item_info):
            daap_item[key] = MIRO_ITEMKIND_PODCAST
        if item_info.kind:
            try:
                daap_item[key] = self.miro_itemkind_mapping[item_info.kind]
            except KeyError:
                logging.warn("Error looking up item kind: %s", item_info.kind)

    def _calc_item_format_mediakind(self, item_info, daap_item):
        """Calculate the DAAP values for com.apple.itunes.mediakind and
        daap.songformat

        :param item_info: ItemInfo to get the values from
        :param daap_item: dict of DAAP data to set the values for
        """

        mediakind_key = 'com.apple.itunes.mediakind'
        songformat_key = 'daap.songformat'

        # Fixup the enclosure format.  This is hardcoded to mp4, 
        # as iTunes requires this.  Other clients seem to be able to sniff
        # out the container.  We can change it if that's no longer true.
        # Fixup the media kind: XXX what about u'other'?
        enclosure = item_info.file_format
        if enclosure not in supported_filetypes:
            nam, ext = os.path.splitext(item_info.filename)
            if ext in supported_filetypes:
                enclosure = ext
        if enclosure:
            songformat = enclosure[1:]
        else:
            songformat = None

        if item_info.file_type == u'video':
            daap_item[mediakind_key] = libdaap.DAAP_MEDIAKIND_VIDEO
            if not songformat:
                songformat = 'mp4'
            daap_item[songformat_key] = songformat
        else:
            daap_item[mediakind_key] = libdaap.DAAP_MEDIAKIND_AUDIO
            if not songformat:
                songformat = 'mp3'
            daap_item[songformat_key] = enclosure

    def _calc_item_paths(self, item_info, daap_item):
        """Calculate the DAAP values for path and cover_art

        :param item_info: ItemInfo to get the values from
        :param daap_item: dict of DAAP data to set the values for
        """
        daap_item['path'] = item_info.filename
        defaults = (resources.path('images/thumb-default-audio.png'),
                    resources.path('images/thumb-default-video.png'))
        if item_info.thumbnail not in defaults:
            daap_item['cover_art'] = item_info.thumbnail
        else:
            daap_item['cover_art'] = ''

    def make_daap_playlist(self, playlist_or_feed):
        if isinstance(playlist_or_feed, models.SavedPlaylist):
            view = models.PlaylistItemMap.playlist_view(playlist_or_feed.id)
            item_ids = set(pim.item_id for pim in view)
            is_podcast = False
        else:
            item_ids = set(i.id for i in playlist_or_feed.downloaded_items)
            is_podcast = True

        daap_item = {
            'dmap.itemid': playlist_or_feed.id,
            'dmap.persistentid': playlist_or_feed.id,
            'dmap.itemname': playlist_or_feed.get_title(),
            'dmap.itemcount': len(item_ids),
            'dmap.parentcontainerid': 0,
            'revision': self.revision,
            'valid': True,
        }
        if is_podcast:
            daap_item[DAAP_PODCAST_KEY] = 1
        self.daap_playlists[playlist_or_feed.id] = daap_item
        self.playlist_item_map[playlist_or_feed.id] = item_ids

    def on_config_changed(self, obj, key, value):
        watched_keys = [prefs.SHARE_AUDIO.key, prefs.SHARE_VIDEO.key,
                prefs.SHARE_FEED.key]
        if key not in watched_keys:
            return
        with self.lock:
            old_share_types = self.share_types
            self.calc_share_types()
            changed = self.share_types.symmetric_difference(old_share_types)
            if changed:
                self.revision += 1
                # If SHARE_FEED changes, we need to start/stop tracking feeds
                if self.SHARE_FEED in changed:
                    if self.SHARE_FEED in self.share_types:
                        self.start_tracking_feeds()
                    else:
                        self.stop_tracking_feeds()
                # If SHARE_AUDIO/SHARE_VIDEO changes we need to recalculate
                # which items are in the main list
                if changed.intersection([self.SHARE_AUDIO, self.SHARE_VIDEO]):
                    query = self._make_item_tracker_query()
                    self.item_tracker.change_query(query)
                self.condition.notify_all()

    def get_item(self, item_id):
        with self.lock:
            return self.daap_items[item_id]

    def get_items(self, playlist_id):
        with self.lock:
            if playlist_id is None:
                return self.daap_items.copy()
            else:
                items_dict = dict()
                for id_ in self.playlist_item_map[playlist_id]:
                    try:
                        items_dict[id_] = self.daap_items[id_]
                    except KeyError:
                        logging.warn("Error looking up DAAP item: %s", id_)
                return items_dict

    def get_playlists(self):
        with self.lock:
            return self.daap_playlists.copy()

    def get_revision(self, old_revision, request_socket):
        with self.lock:
            while self.revision == old_revision:
                # releause our lock and wait for some changes.
                self.condition.wait(1.0)
                # If we reached the timeout, check if request_socket is
                # closed.
                if self.revision == old_revision:
                    # we aren't expecting any data from the other side, so if
                    # the socket is available for reading, that means that
                    # either a) it's been closed, or b) the other side is
                    # sending us some garbage.  Either way, don't wait on our
                    # condition for longer
                    r, w, x = select.select([request_socket], [], [], 0)
                    if r:
                        break
            return self.revision

class SharingManagerBackend(object):
    """Implement a DAAP server using pydaap

    SharingManagerBackend pushes Miro media items to pydaap so pydaap can
    serve them to the outside world.
    """

    type = u'sharing-backend'
    id = u'sharing-backend'

    def __init__(self):
        self.data_set = _SharedDataSet()
        self.transcode_lock = threading.Lock()
        self.transcode = dict()
        self.in_shutdown = False

    # Reserved for future use: you can register new sharing protocols here.
    def register_protos(self, proto):
        pass

    def start_tracking(self):
        self.data_set.start_tracking()

    def stop_tracking(self):
        self.data_set.stop_tracking()

    def get_revision(self, session, old_revision, request):
        """Block until the there is a new revision.

        If the request socket is closed while we are waiting for a new
        revision, then this method should return the old revision.

        :param session_id: session id
        :param old_revision: old revision id.  Return when we get an
        item/playlist update with a newer revision than this.
        :param request: socket handle to the client

        :returns: newest revision number
        """
        return self.data_set.get_revision(old_revision, request)

    def get_file(self, itemid, generation, ext, session, request_path_func,
                 offset=0, chunk=None):
        """Get a file to serve

        :returns (fileobj, filename_hint) tuple:
        """
        # FIXME: the above docstring could realy use some more details.

        file_obj = None
        no_file = (None, None)
        # Get a copy of the item and use that.  If the item gets deleted in a
        # different thread while we're running the code below, then we'll deal
        # with it later on.
        daapitem = self.data_set.get_item(itemid)
        path = daapitem['path']
        if ext in ('ts', 'm3u8'):
            # If we are requesting a playlist, this basically means that
            # transcode is required.
            old_transcode_obj = None
            need_create = False
            with self.transcode_lock:
                if self.in_shutdown:
                    return no_file
                try:
                    transcode_obj = self.transcode[session]
                    if transcode_obj.itemid != itemid:
                        need_create = True
                        old_transcode_obj = transcode_obj
                    else:
                        # This request has already been satisfied by a more
                        # recent request.  Bye ...
                        if generation < transcode_obj.generation:
                            logging.debug('item %s transcode out of order',
                                          itemid)
                            return no_file
                        if chunk is not None and transcode_obj.isseek(chunk):
                            need_create = True
                            old_transcode_obj = transcode_obj
                except KeyError:
                    need_create = True
                if need_create:
                    yes, info = transcode.needs_transcode(path)
                    transcode_obj = transcode.TranscodeObject(
                                                          path,
                                                          itemid,
                                                          generation,
                                                          chunk,
                                                          info,
                                                          request_path_func)
                self.transcode[session] = transcode_obj

            # If there was an old object, shut it down.  Do it outside the
            # loop so that we don't hold onto the transcode lock for excessive
            # time
            if old_transcode_obj:
                old_transcode_obj.shutdown()
            if need_create:
                transcode_obj.transcode()

            if ext == 'm3u8':
                file_obj = transcode_obj.get_playlist()
                file_obj.seek(offset, os.SEEK_SET)
            elif ext == 'ts':
                file_obj = transcode_obj.get_chunk()
            else:
                # Should this be a ValueError instead?  But returning -1
                # will make the caller return 404.
                logging.warning('error: transcode should be one of ts or m3u8')
        elif ext == 'coverart':
            try:
                cover_art = daapitem['cover_art']
                if cover_art:
                    file_obj = open(cover_art, 'rb')
                    file_obj.seek(offset, os.SEEK_SET)
            except OSError:
                if file_obj:
                    file_obj.close()
        else:
            # If there is an outstanding job delete it first.
            try:
                del self.transcode[session]
            except KeyError:
                pass
            try:
                file_obj = open(path, 'rb')
                file_obj.seek(offset, os.SEEK_SET)
            except OSError:
                if file_obj:
                    file_obj.close()
        return file_obj, os.path.basename(path)

    def get_playlists(self):
        """Get the current list of playlists

        This should return a dict mapping DAAP playlist ids to dicts of
        playlist data.  Each dict should contain:
            - dmap.itemid -> DAAP id
            - dmap.persistentid -> DAAP id
            - dmap.itemname -> title
            - dmap.itemcount -> number of items in the playlist
            - dmap.parentcontainerid -> DAAP id of the parent playlist
            (currently always 0)
            - revision -> revision this item was last updated
            - valid -> False if the item has been deleted
        """
        return self.data_set.get_playlists()

    def get_items(self, playlist_id=None):
        """Get the current list of items

        This should return a dict mapping DAAP item ids to dicts of item data.
        Each dict should contain:
            - A value for each key in daap_mapping
            - path -> file path of the item
            - cover_path -> thumbnail path for the item
            - revision -> revision this item was last updated
            - valid -> False if the item has been deleted

        :param playlist_id: playlist to fetch items from, or None to fetch all
        items.
        """
        return self.data_set.get_items(playlist_id)

    def finished_callback(self, session):
        # Like shutdown but only shuts down one of the sessions.  No need to
        # set shutdown.   XXX - could race - if we terminate control connection
        # and and reach here, before a transcode job arrives.  Then the
        # transcode job gets created anyway.
        with self.transcode_lock:
            try:
                self.transcode[session].shutdown()
            except KeyError:
                pass

    def shutdown(self):
        # Set the in_shutdown flag inside the transcode lock to ensure that
        # the transcode object synchronization gate in get_file() does not
        # waste time creating any more objects after this flag is set.
        with self.transcode_lock:
            self.in_shutdown = True
            for key in self.transcode.keys():
                self.transcode[key].shutdown()

class SharingManager(object):
    """SharingManager is the sharing server.  It publishes Miro media items
    to the outside world.  One part is the server instance and the other
    part is the service publishing, both are handled here.

    Important note: mdns_present only indicates the ability to interact with
    the mdns libraries, does not mean that mdns functionality is present
    on the system (e.g. server may be disabled).

    You may not call normally call anything here from the frontend EXCEPT
    for sharing_set_enable() and register_interest(), and
    unregister_interest().

    How to turn on sharing from frontend:

    (1) call register_interest().  This will notify you when the share on/off
        settings change.  You will need to supply a tag, by convention this is
        the object instance you are calling it from.  You will also need to
        supply 2 callbacks the start and end callback.  The start callback
        is called just before the share on/off settings gets written. The 
        end callback is called just after twiddle_sharing() finishs its work.
        You can safely assume that both callbacks will be run from the
        frontend.

    (2) When you change a on/off setting, call sharing_set_enable() with the
        new value and your tag.  You should check the return value.  A return
        value of False indicates that a sharing on/off change is in progress
        and if so you restore the orgiinal value of on/off widget that was
        activated by the user and not proceed any further.

    (3) If sharing_set_enable() returned True, your configuration change
        has been queued and at some point your callbacks should be called.
        You can identify whether it is a particular class of widget 
        that activated the configuration change by looking at the tag in 
        your callback.

    (4) In your start callback, typically you would disable the on/off toggle
        and other dependent widgets.  In your end callback, typically you
        would re-enable the on/off toggle unconditionally, while for dependent
        widgets you would enable if sharing is enabled (and hence dependents
        should be active).

    (4) When you are done with a paritcular set of widgets, call 
        unregister_interest() with the tag to tell who you are.

    In no event do you have to call app.config.set() to toggle the sharing
    on/off state, it is done for you.  These steps are required because
    there is more than one place for you to disable/enable sharing and it is
    needed to make sure that these widgets are always in sync.  This is made
    further difficult because sharing is not just a configuration change: it
    requires startup/shutdown of extra services and takes an indeterminate
    amount of time.  This scheme should solve it satisfactorily.
    """
    # These commands should all be of the same size.
    CMD_QUIT = 'quit'
    CMD_NOP  = 'noop'
    def __init__(self):
        self.r, self.w = util.make_dummy_socket_pair()
        self.sharing = False
        self.discoverable = False
        self.name = ''
        self.mdns_init_result = None
        self.reload_done_event = threading.Event()
        self.mdns_callback = None
        self.sharing_frontend_volatile = False
        self.sharing_frontend_callbacks = dict()
        self.callback_handle = app.backend_config_watcher.connect('changed',
                               self.on_config_changed)

    def init_mdns(self):
        if self.mdns_init_result is None:
            self.mdns_init_result = libdaap.mdns_init()

    @property
    def mdns_present(self):
        self.init_mdns()
        return self.mdns_init_result

    def startup(self):
        self.init_mdns()
        # Create the sharing server backend that keeps track of all the list
        # of items available.  Don't know whether we can just query it on the
        # fly, maybe that's a better idea.
        self.backend = SharingManagerBackend()
        # We can turn it on dynamically but if it's not too much work we'd
        # like to get these before so that turning it on and off is not too
        # onerous?
        self.backend.start_tracking()
        # Enable sharing if necessary.
        self.twiddle_sharing()
        # Normally, if mDNS discovery is enabled, we call resume() in the
        # in the registration callback, we need to do this because the
        # sharing tracker needs to know what name we actually got registered
        # with (instead of what we requested).   But alas, it won't be 
        # called if sharing's off.  So we have to do it manually here.
        if not self.mdns_present or not self.discoverable:
            app.sharing_tracker.resume()

    def session_count(self):
        if self.sharing:
            return self.server.session_count()
        else:
            return 0

    def on_config_changed(self, obj, key, value):
        listen_keys = [prefs.SHARE_MEDIA.key,
                       prefs.SHARE_DISCOVERABLE.key,
                       prefs.SHARE_NAME.key]
        if not key in listen_keys:
            return
        logging.debug('twiddle_sharing: invoked due to configuration change.')
        self.twiddle_sharing()

    def twiddle_sharing(self):
        sharing = app.config.get(prefs.SHARE_MEDIA)
        discoverable = app.config.get(prefs.SHARE_DISCOVERABLE)
        name = app.config.get(prefs.SHARE_NAME).encode('utf-8')
        name_changed = name != self.name
        if sharing != self.sharing:
            if sharing:
                # TODO: if this didn't work, should we set a timer to retry
                # at some point in the future?
                if not self.enable_sharing():
                    # if it didn't work then it must be false regardless.
                    self.discoverable = False
                    self.sharing_set_complete(sharing)
                    return
            else:
                if self.discoverable:
                    self.disable_discover()
                self.disable_sharing()

        # Short-circuit: if we have just disabled the share, then we don't
        # need to check the discoverable bits since it is not relevant, and
        # would already have been disabled anyway.
        if not self.sharing:
            self.sharing_set_complete(sharing)
            return

        # Did we change the name?  If we have, then disable the share publish
        # first, and update what's kept in the server.
        if name_changed and self.discoverable:
            self.disable_discover()
            app.sharing_tracker.pause()
            self.server.set_name(name)

        if discoverable != self.discoverable:
            if discoverable:
                self.enable_discover()
            else:
                self.disable_discover()

        self.sharing_set_complete(sharing)
 
    def finished_callback(self, session):
        eventloop.add_idle(lambda: self.backend.finished_callback(session),
                           'daap logout notification')

    def get_address(self):
        server_address = (None, None)
        try:
            server_address = self.server.server_address
        except AttributeError:
            pass
        return server_address

    def mdns_register_callback(self, name):
        self.name = name
        app.sharing_tracker.resume()

    def enable_discover(self):
        name = app.config.get(prefs.SHARE_NAME).encode('utf-8')
        # At this point the server must be available, because we'd otherwise
        # have no clue what port to register for with Bonjour.
        address, port = self.server.server_address
        self.mdns_callback = libdaap.mdns_register_service(name,
                                                  self.mdns_register_callback,
                                                  port=port)
        # not exactly but close enough: it's not actually until the
        # processing function gets called.
        self.discoverable = True
        # Reload the server thread: if we are only toggling between it
        # being advertised, then the server loop is already running in
        # the select() loop and won't know that we need to process the
        # registration.
        logging.debug('enabling discover ...')
        self.w.send(SharingManager.CMD_NOP)
        # Wait for the reload to finish.
        self.reload_done_event.wait()
        self.reload_done_event.clear()
        logging.debug('discover enabled.')

    def disable_discover(self):
        self.discoverable = False
        # Wait for the mdns unregistration to finish.
        logging.debug('disabling discover ...')
        self.w.send(SharingManager.CMD_NOP)
        self.reload_done_event.wait()
        self.reload_done_event.clear()
        # If we were trying to register a name change but disabled mdns
        # discovery in between make sure we do not wedge the sharing tracker.
        app.sharing_tracker.resume()
        logging.debug('discover disabled.')

    def server_thread(self):
        # Let caller know that we have started.
        self.reload_done_event.set()
        server_fileno = self.server.fileno()
        while True:
            try:
                rset = [server_fileno, self.r]
                refs = []
                if self.discoverable and self.mdns_callback:
                    refs += self.mdns_callback.get_refs()
                rset += refs
                r, w, x = select.select(rset, [], [])
                for i in r:
                    if i in refs:
                        # Possible that mdns_callback is not valid at this
                        # point, because the this wakeup was a result of
                        # closing of the socket (e.g. during name change
                        # when we unpublish and republish our name).
                        if self.mdns_callback:
                            self.mdns_callback(i)
                        continue
                    if server_fileno == i:
                        self.server.handle_request()
                        continue
                    if self.r == i:
                        cmd = self.r.recv(4)
                        logging.debug('sharing: CMD %s' % cmd)
                        if cmd == SharingManager.CMD_QUIT:
                            del self.thread
                            del self.server
                            self.reload_done_event.set()
                            return
                        elif cmd == SharingManager.CMD_NOP:
                            logging.debug('sharing: reload')
                            if not self.discoverable and self.mdns_callback:
                                old_callback = self.mdns_callback
                                self.mdns_callback = None
                                libdaap.mdns_unregister_service(old_callback)
                            self.reload_done_event.set()
                            continue
                        else:
                            raise 
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue 
                # If we end up here, it could mean that the mdns has
                # been closed.  Alternatively the server fileno has been 
                # closed or the command pipe has been closed (not likely).
                if err == errno.EBADF:
                    continue
                typ, value, tb = sys.exc_info()
                logging.error('sharing:server_thread: err %d reason = %s',
                              err, errstring)
                for line in traceback.format_tb(tb):
                    logging.error('%s', line) 
            # XXX How to pass error, send message to the backend/frontend?
            except StandardError:
                typ, value, tb = sys.exc_info()
                logging.error('sharing:server_thread: type %s exception %s',
                       typ, value)
                for line in traceback.format_tb(tb):
                    logging.error('%s', line) 

    def enable_sharing(self):
        # Can we actually enable sharing.  The Bonjour client-side libraries
        # might not be installed.  This could happen if the user previously
        # have the libraries installed and has it enabled, but then uninstalled
        # it in the meantime, so handle this case as fail-safe.
        if not self.mdns_present:
            self.sharing = False
            return

        name = app.config.get(prefs.SHARE_NAME).encode('utf-8')
        self.server = libdaap.make_daap_server(self.backend, debug=True,
                                               name=name)
        if not self.server:
            self.sharing = False
            return

        self.server.set_finished_callback(self.finished_callback)
        self.server.set_log_message_callback(
            lambda format, *args: logging.info(format, *args))

        self.thread = threading.Thread(target=thread_body,
                                       args=[self.server_thread],
                                       name='DAAP Server Thread')
        self.thread.daemon = True
        self.thread.start()
        logging.debug('waiting for server to start ...')
        self.reload_done_event.wait()
        self.reload_done_event.clear()
        logging.debug('server started.')
        self.sharing = True

        return self.sharing

    def disable_sharing(self):
        self.sharing = False
        # What to do in case of socket error here?
        logging.debug('waiting for server to stop ...')
        self.w.send(SharingManager.CMD_QUIT)
        self.reload_done_event.wait()
        self.reload_done_event.clear()
        logging.debug('server stopped.')

    def shutdown(self):
        eventloop.add_urgent_call(self.shutdown_callback,
                                  'sharing shutdown backend call')

    def shutdown_callback(self):
        if self.sharing:
            if self.discoverable:
                self.disable_discover()
            # XXX: need to break off existing connections
            self.disable_sharing()
        self.backend.shutdown()

    def unregister_interest(self, tag):
        del self.sharing_frontend_callbacks[tag]

    def register_interest(self, tag, callbacks, args):
        self.sharing_frontend_callbacks[tag] = (callbacks, args)
        
    def sharing_set_enable(self, tag, value):
        if self.sharing_frontend_volatile:
            logging.debug('Refusing to set sharing to %s while sharing '
                          'set/unset is volatile.', value)
            return False
        self.sharing_frontend_volatile = True
        for t in self.sharing_frontend_callbacks:
            callbacks, args = self.sharing_frontend_callbacks[t]
            (start, _) = callbacks
            start(value, t, args)
        app.config.set(prefs.SHARE_MEDIA, value)
        return True

    def sharing_set_complete(self, value):
        def func():
            if not self.sharing_frontend_volatile:
                return
            for t in self.sharing_frontend_callbacks:
                callbacks, args = self.sharing_frontend_callbacks[t]
                (_, end) = callbacks
                end(value, t, args)
            self.sharing_frontend_volatile = False
        call_on_ui_thread(func)
