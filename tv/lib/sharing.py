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
from miro import eventloop
from miro import messages
from miro import playlist
from miro import feed
from miro import prefs
from miro import signals
from miro import filetypes
from miro import fileutil
from miro import util
from miro import transcode
from miro import metadata
from miro.item import Item
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

supported_filetypes = filetypes.VIDEO_EXTENSIONS + filetypes.AUDIO_EXTENSIONS

# Conversion factor between our local duration (10th of a second)
# vs daap which is millisecond.
DURATION_SCALE = 1000

MIRO_ITEMKIND_MOVIE = (1 << 0)
MIRO_ITEMKIND_PODCAST = (1 << 1)
MIRO_ITEMKIND_SHOW = (1 << 2)
MIRO_ITEMKIND_CLIP = (1 << 3)

miro_itemkind_mapping = {
    'movie': MIRO_ITEMKIND_MOVIE,
    'show': MIRO_ITEMKIND_SHOW,
    'clip': MIRO_ITEMKIND_CLIP,
    'podcast': MIRO_ITEMKIND_PODCAST
}

miro_itemkind_rmapping = {
    MIRO_ITEMKIND_MOVIE: 'movie',
    MIRO_ITEMKIND_SHOW: 'show',
    MIRO_ITEMKIND_CLIP: 'clip',
    MIRO_ITEMKIND_PODCAST: 'podcast'
}

# XXX The daap mapping from the daap to the attribute is different from the
# reverse mapping, because we use daap_mapping to import items from remote
# side and we use daap_rmapping to create an export list.  But, when
# we import and create SharingItem, the attribut needs to be 'title'.  But
# when we export, we receive ItemInfo(), which uses 'name'.
daap_mapping = {
    'daap.songformat': 'file_format',
    'com.apple.itunes.mediakind': 'file_type',
    'dmap.itemid': 'id',
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

daap_rmapping = {
    'file_format': 'daap.songformat',
    'file_type': 'com.apple.itunes.mediakind',
    'id': 'dmap.itemid',
    'name': 'dmap.itemname',
    'duration': 'daap.songtime',
    'size': 'daap.songsize',
    'artist': 'daap.songartist',
    'album_artist': 'daap.songalbumartist',
    'album': 'daap.songalbum',
    'year': 'daap.songyear',
    'genre': 'daap.songgenre',
    'track': 'daap.songtracknumber',
    'kind': 'org.participatoryculture.miro.itemkind',
    'show': 'com.apple.itunes.series-name',
    'season_number': 'com.apple.itunes.season-num',
    'episode_id': 'com.apple.itunes.episode-num-str',
    'episode_number': 'com.apple.itunes.episode-sort'
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

class SharingItem(object):
    """
    An item which lives on a remote share.
    """
    def __init__(self, **kwargs):
        for required in ('video_path', 'id', 'file_type', 'host', 'port'):
            if required not in kwargs:
                raise TypeError('SharingItem must be given a "%s" argument'
                                % required)
        self.file_format = self.size = None
        self.release_date = self.feed_name = self.feed_id = None
        self.keep = True
        self.isContainerItem = False
        self.url = self.payment_link = None
        self.comments_link = self.permalink = self.file_url = None
        self.license = self.downloader = None
        self.duration = self.screenshot = self.thumbnail_url = None
        self.resumeTime = 0
        self.description = u''
        self.subtitle_encoding = self.enclosure_type = None
        self.metadata_version = 0
        self.file_type = None
        self.creation_time = None

        for name in metadata.attribute_names:
            setattr(self, name, None)

        self.__dict__.update(kwargs)

        self.video_path = FilenameType(self.video_path)
        if self.title is None:
            self.title = _("Unknown")
        # Do we care about file_format?
        if self.file_format is None:
            pass
        if self.size is None:
            self.size = 0
        if self.release_date is None or self.creation_time is None:
            now = time.time()
            if self.release_date is None:
                self.release_date = now
            if self.creation_time is None:
                self.creation_time = now
        if self.duration is None: # -1 is unknown
            self.duration = 0

    @staticmethod
    def id_exists():
        return True

    def get_release_date(self):
        try:
            return datetime.fromtimestamp(self.release_date)
        except ValueError:
            logging.warn('SharingItem: release date time %s invalid' %
                          self.release_date)
            return datetime.now()

    def get_creation_time(self):
        try:
            return datetime.fromtimestamp(self.creation_time)
        except ValueError:
            logging.warn('SharingItem: creation time %s invalid' %
                          self.creation_time)
            return datetime.now()

    @returns_filename
    def get_filename(self):
        # For daap, sent it to be the same as http as it is basically
        # http with a different port.
        def daap_handler(path, host, port):
            return 'http://%s:%s%s' % (host, port, path)
        fn = FilenameType(self.video_path)
        fn.set_urlize_handler(daap_handler, [self.address, self.port])
        return fn

    def get_url(self):
        return self.url or u''

    @returns_filename
    def get_thumbnail(self):
        # What about cover art?
        if self.file_type == 'audio':
            return resources.path("images/thumb-default-audio.png")
        else:
            return resources.path("images/thumb-default-video.png")

    def _migrate_thumbnail(self):
        # This should not ever do anything useful.  We don't have a backing
        # database to safe this stuff.
        pass

    def drm_description(self):
        if self.has_drm:
            return _("Locked")
        else:
            return u""

    def remove(self, save=True):
        # This should never do anything useful, we don't have a backing
        # database. Yet.
        pass

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
        self.available_shares = dict()
        self.r, self.w = util.make_dummy_socket_pair()
        self.paused = True
        self.event = threading.Event()
        libdaap.register_meta('org.participatoryculture.miro.itemkind', 'miKD',
                              libdaap.DMAP_TYPE_UBYTE)

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
        if fullname == app.sharing_manager.name:
            return
        # Need to come up with a unique ID for the share.  We want to use the 
        # name only since that's supposed to be unique, but can't because
        # the name may change, and the id is used throughout to identify
        # the item tracker, and we don't want to change the id mid-way.
        # We can't use the hostname or port directly also because
        # on removal avahi can't do a name query so we have no hostname,
        # or port information!  So, we have a name to id map.
        if added:
            share_id = (host, port)
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
                info = messages.SharingInfo(share_id, share_id,
                                            fullname, host, port)
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
                # Only tell the frontend if the share's been tested because
                # otherwise the TabsChanged() message wouldn't have arrived.
                if victim.connect_uuid is None:
                    messages.SharingDisappeared(victim).send_to_frontend()
            else:
                # We don't know if the share's alive or not... what to do
                # here?  Let's add a timeout of 2 secs, if no added message
                # comes in, assume it's gone bye...
                share_info = self.available_shares[share_id]
                share = self.trackers[share_id]
                if share.share != share_info:
                    logging.error('Share disconn error: share info != share')
                dc = eventloop.add_timeout(2, self.remove_timeout_callback,
                                      "share tab removal timeout callback",
                                      args=(share_id, share_info))
                # Cancel pending callback is there is one.
                if share.share.stale_callback:
                    share.share.stale_callback.cancel()
                share.share.stale_callback = dc

    def remove_timeout_callback(self, share_id, share_info):
        del self.available_shares[share_id]
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

    def eject(self, share_id):
        try:
            tracker = self.trackers[share_id]
        except KeyError:
            pass
        else:
            del self.trackers[share_id]
            tracker.client_disconnect()

    def get_tracker(self, share_id):
        try:
            return self.trackers[share_id]
        except KeyError:
            logging.debug('sharing: creating new tracker')
            share = self.available_shares[share_id]
            self.trackers[share_id] = SharingItemTrackerImpl(share)
            return self.trackers[share_id]

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
class SharingItemTrackerImpl(signals.SignalEmitter):
    """This is the backend for the SharingItemTracker the messagehandler file.
    This backend class allows the item tracker to be persistent even as the
    user switches across different tabs in the sidebar, until the disconnect
    button is clicked.
    """
    type = u'sharing'
    fake_playlists = ('video', 'audio', 'playlist', 'podcast')

    def __init__(self, share):
        signals.SignalEmitter.__init__(self)
        for sig in 'added', 'changed', 'removed':
            self.create_signal(sig)
        self.client = None
        self.share = share
        self.items = dict()
        self.info_cache = dict()
        self.playlists = dict()
        self.base_playlist = None    # Temporary
        self.share.is_updating = True
        message = messages.TabsChanged('connect', [], [self.share], [])
        message.send_to_frontend()
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

    def runloop(self):
        success = self.run(self.client_connect, self.client_connect_callback,
                           self.client_connect_error_callback)
        # If server does not support update, then we short circuit since
        # the loop becomes useless.  There is nothing wait for being updated.
        logging.debug('UPDATE SUPPORTED = %s', self.client.supports_update)
        if not success or not self.client.supports_update:
            return
        while True:
            success = self.run(self.client_update, self.client_update_callback,
                               self.client_update_error_callback)
            if not success:
                break

    def sharing_item(self, rawitem):
        kwargs = dict()
        for k in rawitem.keys():
            try:
                key = daap_mapping[k]
            except KeyError:
                # Got something back we don't really care about.
                continue
            kwargs[key] = rawitem[k]
            if isinstance(rawitem[k], str):
                kwargs[key] = kwargs[key].decode('utf-8')

        try:
            kwargs['kind'] = miro_itemkind_rmapping[kwargs['kind']]
        except KeyError:
            pass

        # Fix this up.
        file_type = u'audio'    # fallback
        try:
            if kwargs['file_type'] == libdaap.DAAP_MEDIAKIND_AUDIO:
                file_type = u'audio'
            if kwargs['file_type'] in [libdaap.DAAP_MEDIAKIND_TV,
                                       libdaap.DAAP_MEDIAKIND_MOVIE,
                                       libdaap.DAAP_MEDIAKIND_VIDEO
                                      ]:
                file_type = u'video'
        except KeyError:
           # Whoups.  Server didn't send one over?  Assume default.
           pass

        kwargs['file_type'] = file_type
        kwargs['video_path'] = self.client.daap_get_file_request(
                                   kwargs['id'],
                                   kwargs['file_format'])
        kwargs['host'] = self.client.host
        kwargs['port'] = self.client.port
        kwargs['address'] = self.address
        kwargs['file_type'] = file_type

        # Duration: daap uses millisecond, so we need to scale it.
        if kwargs['duration'] is not None:
            kwargs['duration'] /= DURATION_SCALE

        sharing_item = SharingItem(**kwargs)
        return sharing_item

    def client_disconnect(self):
        client = self.client
        self.client = None
        eventloop.call_in_thread(self.client_disconnect_callback,
                                 self.client_disconnect_error_callback,
                                 client.disconnect,
                                 'DAAP client connect')

    def client_disconnect_error_callback(self, unused):
        self.client_disconnect_callback_common(unused)

    def client_disconnect_callback(self, unused):
        self.client_disconnect_callback_common(unused)

    def client_disconnect_callback_common(self, unused):
        tab_ids = [p.id for p in self.playlists.itervalues()
                        if self.items[p.playlist_id] or
                         p.playlist_id in SharingItemTrackerImpl.fake_playlists]
        message = messages.TabsChanged('connect', [], [], tab_ids)
        message.send_to_frontend()

    def client_connect(self):
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
        return self.setup_items()

    # See use of self.client in client_update().
    def setup_items(self, update=False):
        name = self.share.name
        host = self.share.host
        port = self.share.port
        try:
            client = self.client
        except AttributeError:
            # Doesn't matter what exception it is, just raise to call error
            # callback
            raise

        # From this point on ... if use of client is invalid (because socket
        # is closed or something it should raise an error and we can bail
        # out that way, and call the error callback.
        if not client.databases(update=update):
            raise IOError('Cannot get database')
        deleted_items = dict()
        playlists, deleted_playlists = client.playlists(update=update)
        if playlists is None:
            raise IOError('Cannot get playlist')
        returned_playlists = dict()
        video_tab_id = unicode(md5(repr((name,
                                         host,
                                         port, u'video'))).hexdigest())
        audio_tab_id = unicode(md5(repr((name,
                                         host,
                                         port, u'audio'))).hexdigest())
        playlist_tab_id = unicode(md5(repr((name,
                                            host,
                                            port, u'playlist'))).hexdigest())
        podcast_tab_id = unicode(md5(repr((name,
                                           host,
                                           port, u'podcast'))).hexdigest())
        for k in playlists.keys():
            # Clean the playlist: remove NUL characters.
            for k_ in playlists[k]:
                if isinstance(playlists[k][k_], str):
                    tmp = playlists[k][k_]
                    playlists[k][k_] = tmp.replace('\x00', '')

            is_base_playlist = None
            if playlists[k].has_key('daap.baseplaylist'):
                is_base_playlist = playlists[k]['daap.baseplaylist']
            if is_base_playlist:
                if not update and self.base_playlist:
                    logging.debug('WARNING: more than one base playlist found')
                if update and self.base_playlist != k:
                    logging.debug('WARNING: base playlistid changed in update')
                self.base_playlist = k
            # This isn't the playlist id of the remote share, this is the
            # playlist id we use internally.
            # XXX is there anything better we can do than repr()?
            if not is_base_playlist:
                # XXX only add playlist if it not base playlist.  We don't
                # explicitly show base playlist.
                tab_id = unicode(md5(repr((name,
                                           host,
                                           port, k))).hexdigest())
                try:
                    key = 'com.apple.itunes.is-podcast-playlist'
                    podcast = playlists[k][key]
                except KeyError:
                    podcast = False
                if podcast:
                    parent_id = podcast_tab_id
                else:
                    parent_id = playlist_tab_id
                info = messages.SharingInfo(tab_id,
                                            self.share.id,
                                            playlists[k]['dmap.itemname'],
                                            host,
                                            port,
                                            parent_id=parent_id,
                                            playlist_id=k,
                                            podcast=podcast)
                returned_playlists[k] = info
        # These are fake: so we only want to insert these once.
        if not update:
            video_info = messages.SharingInfo(video_tab_id,
                                              self.share.id,
                                              u'video',
                                              host,
                                              port,
                                              parent_id=self.share.id,
                                              playlist_id=u'video')
            audio_info = messages.SharingInfo(audio_tab_id,
                                              self.share.id,
                                              u'audio',
                                              host,
                                              port,
                                              parent_id=self.share.id,
                                              playlist_id=u'audio')
            playlist_folder_info = messages.SharingInfo(playlist_tab_id,
                                              self.share.id,
                                              u'playlist',
                                              host,
                                              port,
                                              parent_id=self.share.id,
                                              playlist_id=u'playlist',
                                              has_children=True)
            podcast_folder_info = messages.SharingInfo(podcast_tab_id,
                                              self.share.id,
                                              u'podcast',
                                              host,
                                              port,
                                              parent_id=self.share.id,
                                              playlist_id=u'podcast',
                                              has_children=True)
            returned_playlists['video'] = video_info
            returned_playlists['audio'] = audio_info
            returned_playlists['playlist'] = playlist_folder_info
            returned_playlists['podcast'] = podcast_folder_info

        # Maybe we have looped through here without a base playlist.  Then
        # the server is broken?
        if not self.base_playlist:
            raise ValueError('Cannot find base playlist')

        items, deleted = client.items(playlist_id=self.base_playlist,
                                  meta=DAAP_META, update=update)
        if items is None:
            raise ValueError('Cannot find items in base playlist')

        deleted_items[self.base_playlist] = deleted
        # Make sure that we ditch stuff from the in-house video, music,
        # playlist and podcast tabs too.
        #
        # The callback will filter out irrelevant items, so we can just
        # add these as we please, it's easier that way to than figure out
        # the exact set.
        for p in SharingItemTrackerImpl.fake_playlists:
            deleted_items[p] = deleted

        itemdict = dict()
        returned_playlist_items = dict()
        returned_items = dict()
        video_items = dict()
        audio_items = dict()
        sharing_item_meth = self.sharing_item
        for itemkey in items.keys():
            # Clean it of NUL
            for k in items[itemkey]:
                if isinstance(items[itemkey][k], str):
                    tmp = items[itemkey][k]
                    items[itemkey][k] = tmp.replace('\x00', '')
            item = sharing_item_meth(items[itemkey])
            itemdict[itemkey] = item
            returned_items[itemkey] = item
            if item.file_type == u'video':
                video_items[itemkey] = item
            elif item.file_type == u'audio':
                audio_items[itemkey] = item
            else:
                logging.warn('item file type unrecognized %s', item.file_type)
        returned_playlist_items[u'video'] = video_items
        returned_playlist_items[u'audio'] = audio_items
        returned_playlist_items[self.base_playlist] = returned_items

        # Have to save the items from the base playlist first, because
        # Rhythmbox will get lazy and only send the ids around (expecting
        # us to already to have the data, I guess). 
        playlist_items = dict()
        podcast_items = dict()
        for k in playlists.keys():
            if k == self.base_playlist:
                continue
            returned_items = dict()
            items, deleted = client.items(playlist_id=k, meta=DAAP_META,
                                               update=update)
            if items is None:
                raise ValueError('Cannot find items for playlist %d' % k)
            deleted_items[k] = deleted
            for itemkey in items.keys():
                item = itemdict[itemkey]
                returned_items[itemkey] = itemdict[itemkey]
                try:
                    key = 'com.apple.itunes.is-podcast-playlist'
                    if playlists[k].has_key(key) and playlists[k][key]:
                        podcast_items[itemkey] = item
                    else:
                        playlist_items[itemkey] = item
                except KeyError:
                    pass
            returned_playlist_items[k] = returned_items

        returned_playlist_items['podcast'] = podcast_items
        returned_playlist_items['playlist'] = playlist_items

        # We don't append these items directly to the object and let
        # the success callback to do it to prevent race.
        return (returned_playlist_items, returned_playlists,
                deleted_playlists, deleted_items)

    # If we are disconnecting, then, disconnect() sets the self.client
    # to None before actually running the client.disconnect() routine.
    # So, usage of self.client should be:
    #
    # try:
    #    client = self.client
    # except AttributeError:
    #    # Handle error here.
    #    pass
    # else:
    #     client.blah()
    def client_update(self):
        logging.debug('CLIENT UPDATE')
        try:
            client = self.client
        except AttributeError:
            # Doesn't matter what exception it is, just raise to call error
            # callback
            raise
        client.update()
        return self.setup_items(update=True)

    def client_update_callback(self, args):
        logging.debug('CLIENT UPDATE CALLBACK')
        deleted = []
        changed = []
        added = []
        (returned_items, returned_playlists,
         deleted_playlists, deleted_items) = args

        # First: delete old junk.  But only delete from sidebar if the
        # thing was there in the first place, which basically means if there
        # was a non-empty number of items in the list.
        for k in deleted_playlists:
            if k == self.base_playlist:
                logging.debug('client_update_callback: remote asked us to '
                              'delete base playlist, ignoring')
                continue
            try:
                playlist_id = self.playlists[k].id
                del self.playlists[k]
                if self.items[k]:
                    deleted.append(playlist_id)
            except KeyError:
                pass

        # Added/update changed playlist.  But not necessarily the added/changed
        # list to send, because we don't know whether this list is empty
        # at this point.  Defer until we process the items, we will fix up.
        for k, v in returned_playlists.iteritems():
            if self.playlists.has_key(k):
                changed.append(v)
            else:
                added.append(v)
                self.items[k] = dict()
            self.playlists[k] = v

        # Keep tabs on whether existing playlist is empty or not
        old_empty_playlists = set([k for k in self.items if not self.items[k]])
        old_valid_playlists = set([k for k in self.items if self.items[k]])

        # Process deleted items.
        for k, item_ids in deleted_items.iteritems():
            try:
                playlist_items = self.items[k]
            except KeyError:
                # Huh what?  Sent us something that we don't have anymore.
                logging.debug('Playlist %s already deleted', k)
                continue
            # Base playlist == None, so munge it up.  Could probably just
            # use the base playlist id and skip this trouble!
            playlist_id = None if k == self.base_playlist else k
            for item_id in item_ids:
                try:
                    item = playlist_items[item_id]
                    del playlist_items[item_id]
                    self.emit('removed', playlist_id, item)
                except KeyError:
                    pass

        # Now, process returned items, that have been added/changed. 
        for k, updated_playlist in returned_items.iteritems():
            try:
                playlist_items = self.items[k]
            except KeyError:
                # Huh?  We asked for a playlist that didn't exist?
                logging.debug('CANNOT ACCESS self.items[%s]', k)
                continue
            playlist_id = None if k == self.base_playlist else k
            for key, value in updated_playlist.iteritems():
                sig = 'changed' if playlist_items.has_key(key) else 'added'
                self.emit(sig, playlist_id, value)
                playlist_items[key] = value

        # Keep tabs on current state of playlists
        valid_playlists = set([k for k in self.items if self.items[k]])

        # Filter out empty stuff.  Re-add previously empty stuff that now
        # has stuff (in changed).
        #
        # Algorithm: check added.  If empty, filter out.
        # Check changed.  If empty, and previously not empty, append to
        # deleted.  If previously empty and now not empty, move from changed
        # to added.  If previously empty and now also empty, ditch it from the
        # changed lists.
        added = [a for a in added if self.items[a.playlist_id]]
        to_remove = []
        for c in changed:
            if (c.playlist_id == self.base_playlist or
              c.playlist_id in SharingItemTrackerImpl.fake_playlists):
                continue
            if not self.items[c.playlist_id]:
                # We need to remove it.
                if c.playlist_id in old_valid_playlists:
                    # Transitioned from valid to empty.  Append to deleted.
                    logging.debug('%s transitioned to empty', c.name)
                    deleted.append(c.id)
                    to_remove.append(c)
                elif c.playlist_id in old_empty_playlists:
                    # Was empty, is still empty.  Ditch from changed list.
                    logging.debug('%s was empty, still empty', c.name)
                    to_remove.append(c)

        # Ditch stuff in the changed list
        for r in to_remove:
            while True:
                try:
                    changed.remove(r)
                except ValueError:
                    break

        # Was empty and now not empty.  Intersection of previously empty
        # playlists and playlists are now not empty.  Add to added list,
        # and if it exists in the changed list, ditch it (because we should
        # use add as it did not exist before).
        added_ids = list(old_empty_playlists.intersection(valid_playlists))
        for added_id in added_ids:
            if added_id == self.base_playlist:
                continue
            if added_id in SharingItemTrackerImpl.fake_playlists:
                continue
            added.append(self.playlists[added_id])
            try:
                changed.remove(self.playlists[added_id])
            except ValueError:
                logging.debug('empty to non-empty transition playlist %s '
                              'not in changed list', added_id)

        # Finally, update the tabs.  Use set() to filter out the duplicates.
        message = messages.TabsChanged('connect', set(added), set(changed),
                                       set(deleted))
        message.send_to_frontend()

    def client_update_error_callback(self, unused):
        self.client_connect_update_error_callback(unused, update=True)

    # NB: this runs in the eventloop (backend) thread.
    def client_connect_callback(self, args):
        # Just ignore any deleted items on first connect - they shouldn't
        # be there.
        returned_items, returned_playlists, _, _ = args
        self.items = returned_items
        self.playlists = returned_playlists
        # Send a list of all the items to the main sharing tab.  Only add
        # those that are part of the base playlist.
        for item in self.items[self.base_playlist].itervalues():
            self.emit('added', None, item)
        # Once all the items are added then send display mounted and remove
        # the progress indicator.
        self.share.mount = True
        self.share.is_updating = False
        # Only show non-empty stuff, but make sure that we always display
        # the top level podcast tabs.  This filtering is a bit of work, but
        # even if we have hundreds of playlists, it won't be that bad, and
        # we only need to do this once.
        playlists = [p for p in self.playlists.itervalues()
                     if self.items[p.playlist_id] and
                     p.playlist_id not in SharingItemTrackerImpl.fake_playlists]
        # Append the ersatz playlists at the front.
        for i, v in enumerate(SharingItemTrackerImpl.fake_playlists):
            playlists.insert(i, self.playlists[v])
        message = messages.TabsChanged('connect', playlists,
                                       [self.share], [])
        message.send_to_frontend()

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
            self.share.is_updating = False
            message = messages.TabsChanged('connect', [], [self.share], [])
            message.send_to_frontend()
        if not self.share.stale_callback:
            app.sharing_tracker.eject(self.share.id)
        messages.SharingConnectFailed(self.share).send_to_frontend()

    def get_items(self, playlist_id=None):
        # NB: keep this in a try/except construct because this could be
        # called before the connection actually has succeeded.
        try:
            if playlist_id is None:
                return self.items[self.base_playlist].values()
            else:
                return self.items[playlist_id].values()
        except KeyError:
            logging.error('Cannot get playlist, was looking for %s',
                          playlist_id)
            return []

class SharingManagerBackend(object):
    """SharingManagerBackend is the bridge between pydaap and Miro.  It
    pushes Miro media items to pydaap so pydaap can serve them to the outside
    world."""

    type = u'sharing-backend'
    id = u'sharing-backend'

    SHARE_AUDIO = libdaap.DAAP_MEDIAKIND_AUDIO
    SHARE_VIDEO = libdaap.DAAP_MEDIAKIND_VIDEO
    SHARE_FEED  = 0x4    # XXX

    def __init__(self):
        self.revision = 1
        self.share_types = []
        if app.config.get(prefs.SHARE_AUDIO):
            self.share_types += [SharingManagerBackend.SHARE_AUDIO]
        if app.config.get(prefs.SHARE_VIDEO):
            self.share_types += [SharingManagerBackend.SHARE_VIDEO]
        if app.config.get(prefs.SHARE_FEED):
            self.share_types += [SharingManagerBackend.SHARE_FEED]
        
        self.item_lock = threading.Lock()
        self.revision_cv = threading.Condition(self.item_lock)
        self.transcode_lock = threading.Lock()
        self.transcode = dict()
        # XXX daapplaylist should be hidden from view. 
        self.daapitems = dict()         # DAAP format XXX - index via the items
        self.daap_playlists = dict()    # Playlist, in daap format
        self.playlist_item_map = dict() # Playlist -> item mapping
        self.deleted_item_map = dict()  # Playlist -> deleted item mapping
        self.in_shutdown = False
        self.config_handle = app.backend_config_watcher.connect('changed',
                             self.on_config_changed)

    # Reserved for future use: you can register new sharing protocols here.
    def register_protos(self, proto):
        pass

    # Note: this can be called more than once, if you change your podcast
    # configuration to show/hide podcast items!  What we do here is,
    # ditch the old list re-create new one with the updated information.
    # This is a complete list send and not a diff like handle_items_changed()
    # is.  But make sure at the same time that the old deleted stuff is marked
    # as such.
    def handle_item_list(self, message):
        with self.item_lock:
            self.update_revision()
            item_ids = [item.id for item in message.items]
            if message.id is not None:
                self.daap_playlists[message.id]['revision'] = self.revision
                self.playlist_item_map[message.id] = item_ids
                self.deleted_item_map[message.id] = []
                # Update the revision of these items, so they will match
                # when the playlist items are fetched.
                for item_id in item_ids:
                    try:
                        self.daapitems[item_id]['revision'] = self.revision
                    except KeyError:
                        # This non-downloaded podcast item?  I think what
                        # we want to do here is set it as a podcast item
                        # but disable the items that are not yet available.
                        #
                        # Requires work to update the watchable view to include
                        # stuff from the individual feeds.
                        pass
            else:
                deleted = [item_id for item_id in self.daapitems if
                           item_id not in item_ids]
                self.make_item_dict(message.items)
                for d in deleted:
                    self.daapitems[d] = self.deleted_item()

    def handle_items_changed(self, message):
        # If items are changed, overwrite with a recreated entry.  This
        # might not be necessary, as currently this change can be due to an 
        # item being moved out of, and then into, a playlist.  Also, based on 
        # message.id, change the playlists accordingly.
        with self.item_lock:
            self.update_revision()
            for itemid in message.removed:
                try:
                    if message.id is not None:
                        revision = self.revision
                        self.daap_playlists[message.id]['revision'] = revision
                        self.playlist_item_map[message.id].remove(itemid)
                        self.deleted_item_map[message.id].append(itemid)
                except KeyError:
                    pass
                try:
                    if message.id is None:
                        self.daapitems[itemid] = self.deleted_item()
                except KeyError:
                    pass
            if message.id is not None:
                item_ids = [item.id for item in message.added]
                self.daap_playlists[message.id]['revision'] = self.revision
                # If they have been previously removed, unmark deleted.
                for i in item_ids:
                    try:
                        self.deleted_item_map[message.id].remove(i)
                    except ValueError:
                        pass
                self.playlist_item_map[message.id] += item_ids

            # Only make or modify an item if it is for main library.
            # Otherwise, we just re-create an item when all that's changed
            # is the contents of the playlist.
            if message.id is None:
                self.make_item_dict(message.added)
                self.make_item_dict(message.changed)
            else:
                # Simply update the item's revision.
                # XXX Feed sharing: catch KeyError because item may not
                # be downloaded (and hence not in watchable list).
                # Catch changed as when feed items get added they
                # do not get added to the main list.  Catch added, when newly
                # available podcasts come into view.
                for x in message.added:
                    try:
                        self.daapitems[x.id]['revision'] = self.revision
                    except KeyError:
                        pass
                for x in message.changed:
                    try:
                        self.daapitems[x.id]['revision'] = self.revision
                    except KeyError: 
                        pass

    def deleted_item(self):
        return dict(revision=self.revision, valid=False)

    # At this point: item_lock acquired
    def update_revision(self, directed=None):
        self.revision += 1
        self.directed = directed
        self.revision_cv.notify_all()

    def make_daap_playlists(self, items, typ):
        for item in items:
            itemprop = dict()
            for attr in daap_rmapping.keys():
               daap_string = daap_rmapping[attr]
               itemprop[daap_string] = getattr(item, attr, None)
               # XXX Pants.  We use this for the initial population when
               # we pass in DB objects and then later on we also use this
               # when they are in fact tab infos.  In the raw DBObject we
               # use title, and in the tab infos we use name.  But in the
               # DBObject 'name' is valid too!
               # 
               # Blargh!
               if daap_string == 'dmap.itemname':
                   itemprop[daap_string] = getattr(item, 'title', None)
                   if itemprop[daap_string] is None:
                       itemprop[daap_string] = getattr(item, 'name', None)
               if isinstance(itemprop[daap_string], unicode):
                   itemprop[daap_string] = (
                     itemprop[daap_string].encode('utf-8'))
            daap_string = 'dmap.itemcount'
            if daap_string == 'dmap.itemcount':
                # At this point, the item list has not been fully populated 
                # yet.  Therefore, it may not be possible to run 
                # get_items() and getting the count attribute.  Instead we 
                # use the playlist_item_map.
                if typ == 'playlist':
                    tmp = [y for y in 
                           playlist.PlaylistItemMap.playlist_view(item.id)]
                elif typ == 'feed':
                    tmp = [y for y in Item.feed_view(item.id)]
                else:
                    # whoups, sorry mate!
                    raise ValueError('unknown playlist variant type %s' % typ)
                count = len(tmp)
                itemprop[daap_string] = count
            daap_string = 'dmap.parentcontainerid'
            if daap_string == 'dmap.parentcontainerid':
                itemprop[daap_string] = 0
                #attributes.append(('mpco', 0)) # Parent container ID
                #attributes.append(('mimc', count))    # Item count
                #self.daap_playlists[x.id] = attributes
            daap_string = 'dmap.persistentid'
            if daap_string == 'dmap.persistentid':
                itemprop[daap_string] = item.id

            itemprop['podcast'] = typ == 'feed'
            # XXX
            if itemprop['podcast']:
                itemprop['com.apple.itunes.is-podcast-playlist'] = True

            # piece de resistance
            itemprop['revision'] = self.revision
            itemprop['valid'] = True

            self.daap_playlists[item.id] = itemprop

    def handle_feed_added(self, obj, added):
        added = [a for a in added if not a.url or
                 (a.url and not a.url.startswith('dtv:'))]
        self.handle_playlist_added(obj, added, typ='feed')

    def handle_feed_changed(self, obj, changed):
        changed = [c for c in changed if not c.url or
                 (c.url and not c.url.startswith('dtv:'))]
        self.handle_playlist_changed(obj, changed, typ='feed')

    def handle_feed_removed(self, obj, removed):
        # Can't actually filter out removed - it is a list of ids.  But no
        # matter as we just ignore it if we can't find it in our tracked
        # playlists.
        self.handle_playlist_removed(obj, removed, typ='feed')

    def handle_playlist_added(self, obj, added, typ='playlist'):
        playlists = [x for x in added if not x.is_folder]

        def _handle_playlist_added():
            with self.item_lock:
                self.update_revision()
                self.make_daap_playlists(playlists, typ)
                for p in playlists:
                    # no need to update the revision here: already done in
                    # make_daap_playlists.
                    self.playlist_item_map[p.id] = []
                    self.deleted_item_map[p.id] = []
                    app.info_updater.item_list_callbacks.add(self.type,
                                                     p.id,
                                                     self.handle_item_list)
                    app.info_updater.item_changed_callbacks.add(self.type,
                                                     p.id,
                                                     self.handle_items_changed)
                    id_ = (p.id, typ == 'feed')
                    messages.TrackItems(self.type, id_).send_to_backend()

        eventloop.add_urgent_call(lambda: _handle_playlist_added(),
                                  "SharingManagerBackend: playlist added")

    def handle_playlist_changed(self, obj, changed, typ='playlist'):
        def _handle_playlist_changed():
            with self.item_lock:
                self.update_revision()
                # We could just overwrite everything without actually deleting
                # the object.  A missing key means it's a folder, and we skip
                # over it.
                playlist = []
                for x in changed:
                    if self.daap_playlists.has_key(x.id):
                        #self.daap_playlists[x.id] = self.deleted_item()
                        del self.daap_playlists[x.id]
                        playlist.append(x)
                self.make_daap_playlists(playlist, typ)

        eventloop.add_urgent_call(lambda: _handle_playlist_changed(),
                                  "SharingManagerBackend: playlist changed")


    def handle_playlist_removed(self, obj, removed, typ='playlist'):
        def _handle_playlist_removed():
            with self.item_lock:
                self.update_revision()
                for x in removed:
                    # Missing key means it's a folder and we skip over it.
                    if self.daap_playlists.has_key(x):
                        self.daap_playlists[x] = self.deleted_item()
                        #del self.daap_playlists[x]
                        try:
                            del self.playlist_item_map[x]
                        except KeyError:
                            logging.debug('sharing: cannot delete '
                                          'playlist_item_map id = %d', x)
                        try:
                            del self.deleted_item_map[x]
                        except KeyError:
                            logging.debug('sharing: cannot delete '
                                          'deleted_item_map id = %d', x)
                        messages.StopTrackingItems(self.type,
                                                   x).send_to_backend()
                        app.info_updater.item_list_callbacks.remove(self.type,
                                                    x,
                                                    self.handle_item_list)
                        app.info_updater.item_changed_callbacks.remove(
                                                    self.type,
                                                    x,
                                                    self.handle_items_changed)

        eventloop.add_urgent_call(lambda: _handle_playlist_removed(),
                                  "SharingManagerBackend: playlist removed")

    # Can't do away with this one.  Info_updater callbacks only notifies us
    # on the fly when something is added/changed/removed, but not the initial
    # state that should be in place on startup.
    def populate_playlists(self):
        with self.item_lock:
            self.update_revision()
            # First, playlists.
            playlists = playlist.SavedPlaylist.make_view()
            # Grab feeds.  We like the feeds, but don't grab fake ersatz stuff. 
            feeds = [f for f in feed.Feed.make_view() if not f.origURL or
                     (f.origURL and not f.origURL.startswith('dtv:'))]
            playlist_ids = [p.id for p in playlists]
            feed_ids = [f.id for f in feeds]
            self.make_daap_playlists(playlist.SavedPlaylist.make_view(),
                                     'playlist')
            # et tu, feed.  But we basically handle it the same way.
            self.make_daap_playlists(feeds, 'feed')
            # Now, build the playlists.
            for playlist_id in self.daap_playlists.keys():
                # revision for playlist already created in make_daap_playlist
                if playlist_id in playlist_ids:
                    self.playlist_item_map[playlist_id] = [x.item_id
                      for x in playlist.PlaylistItemMap.playlist_view(
                      playlist_id)]
                elif playlist_id in feed_ids:
                    self.playlist_item_map[playlist_id] = [x.id
                      for x in Item.feed_view(playlist_id)]
                else:
                    logging.error('playlist id %s not valid', playlist_id)
                    continue
                self.deleted_item_map[playlist_id] = []

    def start_tracking(self):
        self.populate_playlists()
        # Track items that do not belong in any playlist.  Do this first
        # so we pick up all items in the media library.
        app.info_updater.item_list_callbacks.add(self.type, None,
                                                 self.handle_item_list)
        app.info_updater.item_changed_callbacks.add(self.type, None,
                                                 self.handle_items_changed)
        messages.TrackItems(self.type, None).send_to_backend()

        # Now, for the specific playlists.
        for playlist_id in self.daap_playlists:
            app.info_updater.item_list_callbacks.add(self.type, playlist_id,
                                                 self.handle_item_list)
            app.info_updater.item_changed_callbacks.add(self.type, playlist_id,
                                                 self.handle_items_changed)
            id_ = (playlist_id, self.daap_playlists[playlist_id]['podcast'])
            messages.TrackItems(self.type, id_).send_to_backend()

        app.info_updater.connect('playlists-added',
                                 self.handle_playlist_added)
        app.info_updater.connect('playlists-changed',
                                 self.handle_playlist_changed)
        app.info_updater.connect('playlists-removed',
                                 self.handle_playlist_removed)

        app.info_updater.connect('feeds-added',
                                 self.handle_feed_added)
        app.info_updater.connect('feeds-changed',
                                 self.handle_feed_changed)
        app.info_updater.connect('feeds-removed',
                                 self.handle_feed_removed)

    def stop_tracking(self):
        for playlist_id in self.daap_playlists:
            messages.StopTrackingItems(self.type,
                                       playlist_id).send_to_backend()
            app.info_updater.item_list_callbacks.remove(self.type, playlist_id,
                                                    self.handle_item_list)
            app.info_updater.item_changed_callbacks.remove(self.type,
                                                    playlist_id,
                                                    self.handle_items_changed)
        messages.StopTrackingItems(self.type, self.id).send_to_backend()
        app.info_updater.item_list_callbacks.remove(self.type, None,
                                                    self.handle_item_list)
        app.info_updater.item_changed_callbacks.remove(self.type, None,
                                                    self.handle_items_changed)

        app.info_updater.disconnect(self.handle_playlist_added)
        app.info_updater.disconnect(self.handle_playlist_changed)
        app.info_updater.disconnect(self.handle_playlist_removed)

        app.info_updater.disconnect(self.handle_feed_added)
        app.info_updater.disconnect(self.handle_feed_changed)
        app.info_updater.disconnect(self.handle_feed_removed)

    def watcher(self, session, request):
        while True:
            try:
                r, w, x = select.select([request], [], [])
                # Unlock the revision by bumping it
                with self.item_lock:
                    logging.debug('WAKEUP %s', session)
                    self.update_revision(directed=session)
                break
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue
            except StandardError, err:
                raise ValueError('watcher: unknown error during select')

    def get_revision(self, session, old_revision, request):
        self.revision_cv.acquire()
        while self.revision == old_revision:
            t = threading.Thread(target=self.watcher, args=(session, request))
            t.daemon = True
            t.start()
            self.revision_cv.wait()
            # If we really did a update or if the wakeup was directed at us
            # (because we are quitting or something) then release the lock
            # and return the revision
            if self.directed is None or self.directed == session:
                break
            # update revision and then wait again
            old_revision = self.revision
        self.revision_cv.release()
        return self.revision

    def get_file(self, itemid, generation, ext, session, request_path_func,
                 offset=0, chunk=None):
        file_obj = None
        no_file = (None, None)
        # Get a copy of the item under the lock ... if the underlying item
        # is going away then we'll deal with it later on.  only care about
        # the reference being valid (?)
        with self.item_lock:
            try:
                daapitem = self.daapitems[itemid]
            except KeyError:
                return no_file
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
        returned = dict()
        with self.item_lock:
            for p in self.daap_playlists:
                pl = self.daap_playlists[p]
                send_podcast = (
                  SharingManagerBackend.SHARE_FEED in self.share_types)
                if (not pl['valid'] or not pl['podcast'] or
                  (pl['podcast'] and send_podcast)):
                    returned[p] = pl
                else:
                    returned[p] = self.deleted_item()
        return returned

    def on_config_changed(self, obj, key, value):
        keys = [prefs.SHARE_AUDIO.key, prefs.SHARE_VIDEO.key,
                prefs.SHARE_FEED.key]
        if key in keys:
            with self.item_lock:
                share_types_orig = self.share_types
                self.share_types = []
                if app.config.get(prefs.SHARE_AUDIO):
                    self.share_types += [SharingManagerBackend.SHARE_AUDIO]
                if app.config.get(prefs.SHARE_VIDEO):
                    self.share_types += [SharingManagerBackend.SHARE_VIDEO]
                if app.config.get(prefs.SHARE_FEED):
                    self.share_types += [SharingManagerBackend.SHARE_FEED]
                # Just by enabling and disabing this, the selection of items
                # available to a user could have changed.  We are a bit lazy
                # here and just use a hammer to update everything without
                # working out what needs to be updated.
                if share_types_orig != self.share_types:
                    self.update_revision()
                for p in self.daap_playlists:
                    self.daap_playlists[p]['revision'] = self.revision
                for i in self.daapitems:
                    self.daapitems[i]['revision'] = self.revision

    # XXX TEMPORARY: should this item be podcast?  We won't need this when
    # the item type's metadata is completely accurate and won't lie to us.
    def item_from_podcast(self, item):
        feed_url = item.feed_url
        ersatz_feeds = ['dtv:manualFeed', 'dtv:searchDownloads', 'dtv:search']
        is_feed = not any([feed_url.startswith(x) for x in ersatz_feeds])
        return item.feed_id and is_feed and not item.is_file_item

    def get_items(self, playlist_id=None):
        # Easy: just return
        with self.item_lock:
            items = dict()
            if not playlist_id:
                for k in self.daapitems.keys():
                    item = self.daapitems[k]
                    valid = item['valid']
                    if valid:
                        mk = item['com.apple.itunes.mediakind']
                        ik = item['org.participatoryculture.miro.itemkind']
                        podcast = ik and (ik & MIRO_ITEMKIND_PODCAST)
                        include_if_podcast = (podcast and
                          SharingManagerBackend.SHARE_FEED in self.share_types)
                    if (not valid or
                      mk in self.share_types and 
                      (not podcast or include_if_podcast)):
                        items[k] = item
                    else:
                        items[k] = self.deleted_item()
                return items
            # XXX Somehow cache this?
            playlist = dict()
            if self.playlist_item_map.has_key(playlist_id):
                for x in self.daapitems.keys():
                    item = self.daapitems[x]
                    valid = item['valid']
                    if valid:
                        mk = item['com.apple.itunes.mediakind']
                        ik = item['org.participatoryculture.miro.itemkind']
                        podcast = ik and (ik & MIRO_ITEMKIND_PODCAST)
                        include_if_podcast = (podcast and
                          SharingManagerBackend.SHARE_FEED in self.share_types)
                    if (x in self.playlist_item_map[playlist_id] and
                      (not valid or
                       mk in self.share_types and
                       (not podcast or include_if_podcast))):
                        playlist[x] = item
                    else:
                        playlist[x] = self.deleted_item()
            return playlist

    def make_item_dict(self, items):
        # See the daap_rmapping/daap_mapping for a list of mappings that
        # we do.
        for item in items:
            itemprop = dict()
            for attr in daap_rmapping.keys():
                daap_string = daap_rmapping[attr]
                itemprop[daap_string] = getattr(item, attr, None)
                if isinstance(itemprop[daap_string], unicode):
                    itemprop[daap_string] = (
                      itemprop[daap_string].encode('utf-8'))
                # Fixup the year, etc being -1.  XXX should read the daap
                # type then determine what to do.
                if itemprop[daap_string] == -1:
                    itemprop[daap_string] = 0
                # Fixup: these are stored as string?
                if daap_string in ('daap.songtracknumber',
                                   'daap.songyear'):
                    if itemprop[daap_string] is not None:
                        itemprop[daap_string] = int(itemprop[daap_string])
                # Fixup the duration: need to convert to millisecond.
                if daap_string == 'daap.songtime':
                    if itemprop[daap_string]:
                        itemprop[daap_string] *= DURATION_SCALE
                    else:
                        itemprop[daap_string] = 0
            # Fixup the enclosure format.  This is hardcoded to mp4, 
            # as iTunes requires this.  Other clients seem to be able to sniff
            # out the container.  We can change it if that's no longer true.
            # Fixup the media kind: XXX what about u'other'?
            enclosure = item.file_format
            if enclosure not in supported_filetypes:
                nam, ext = os.path.splitext(item.video_path)
                if ext in supported_filetypes:
                    enclosure = ext

            # If this should be considered an item from a podcast feed then
            # mark it as such.  But allow for manual overriding by the user,
            # as per what was set in the metadata.
            if self.item_from_podcast(item):
                key = 'org.participatoryculture.miro.itemkind'
                itemprop[key] = MIRO_ITEMKIND_PODCAST
            try:
                key = 'org.participatoryculture.miro.itemkind'
                kind = itemprop[key]
                if kind:
                    itemprop[key] = miro_itemkind_mapping[kind]
            except KeyError:
                pass
            if itemprop['com.apple.itunes.mediakind'] == u'video':
                itemprop['com.apple.itunes.mediakind'] = (
                  libdaap.DAAP_MEDIAKIND_VIDEO)
                if not enclosure:
                    enclosure = '.mp4'
                enclosure = enclosure[1:]
                itemprop['daap.songformat'] = enclosure
            else:
                itemprop['com.apple.itunes.mediakind'] = (
                  libdaap.DAAP_MEDIAKIND_AUDIO)
                if not enclosure:
                    enclosure = '.mp3'
                enclosure = enclosure[1:]
                itemprop['daap.songformat'] = enclosure
            # Normally our strings are fixed up above, but then we re-pull
            # this out of the input data structure, so have to re-convert.
            if isinstance(itemprop['daap.songformat'], unicode):
                tmp = itemprop['daap.songformat'].encode('utf-8')
                itemprop['daap.songformat'] = tmp

            # don't forget to set the path..
            # ok: it is ignored since this is not valid dmap/daap const.
            itemprop['path'] = item.video_path
            defaults = (resources.path('images/thumb-default-audio.png'),
                        resources.path('images/thumb-default-video.png'))
            if item.thumbnail not in defaults:
                itemprop['cover_art'] = item.thumbnail
            else:
                itemprop['cover_art'] = ''

            # HACK: the rmapping dict doesn't work because we can't
            # double up the key.
            itemprop['dmap.containeritemid'] = itemprop['dmap.itemid']

            # piece de resistance: tack on the revision.
            itemprop['revision'] = self.revision
            itemprop['valid'] = True

            self.daapitems[item.id] = itemprop

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
        self.mdns_present = libdaap.mdns_init()
        self.reload_done_event = threading.Event()
        self.mdns_callback = None
        self.sharing_frontend_volatile = False
        self.sharing_frontend_callbacks = dict()
        self.callback_handle = app.backend_config_watcher.connect('changed',
                               self.on_config_changed)
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
