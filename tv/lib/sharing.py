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
import os
import socket
import select
import threading

from miro import app
from miro import config
from miro import eventloop
from miro import item
from miro import messages
from miro import playlist
from miro import prefs

from miro.plat.utils import thread_body

import libdaap

# Helper utilities
# Translate neutral constants to native protocol constants with this, or
# fixup strings if necessary.
def daap_item_fixup(item_id, entry):
    daapitem = []

    # Easy ones - can do a direct translation
    mapping = [('name', 'minm'), ('enclosure_format', 'asfm'),
               ('size', 'assz')]
    for p, q in mapping:
        if isinstance(entry[p], unicode):
            attribute = (q, entry[p].encode('utf-8'))
        else:
            attribute = (q, entry[p])
        daapitem.append(attribute)

    # Manual ones

    # Tack on the ID.
    daapitem.append(('miid', item_id))
    # Convert the duration to milliseconds, as expected.
    daapitem.append(('astm', entry['duration'] * 1000))
    # Also has movie or tv shows but Miro doesn't support it so make it
    # a generic video.
    if entry['file_type'] == 'video':
        daapitem.append(('aeMK', libdaap.DAAP_MEDIAKIND_VIDEO))
    else:
        daapitem.append(('aeMK', libdaap.DAAP_MEDIAKIND_AUDIO))

    return daapitem

class SharingTracker(object):
    type = 'sharing'
    def __init__(self):
        self.trackers = dict()
        self.available_shares = []
        self.r, self.w = os.pipe()

    def mdns_callback(self, added, fullname, host, ips, port):
        added_list = []
        removed_list = []
        # First check to see if it's myself.
        local_address, local_port = app.sharing_manager.mdns_myself()
        ip_values = [socket.inet_ntop(k, ips[k]) for k in ips.keys()]
        if set(local_address + ip_values) and local_port == port:
            return
        # Need to come up with a unique ID for the share.  Use 
        # (name, host, port)
        share_id = (fullname, host, port)
        # Do we have this share on record?  If so then just ignore.
        # In particular work around a problem with Avahi apparently sending
        # duplicate messages.
        if added and share_id in self.available_shares:
            return
        if not added and not share_id in self.available_shares:
            return 

        info = messages.SharingInfo(share_id, fullname, host, port)
        if added:
            added_list.append(info)
            self.available_shares.append(share_id)
        else:
            removed_list.append(share_id)
            self.available_shares.append(share_id)
            # XXX we should not be simply stopping because the mDNS share
            # disappears.  AND we should not be calling this from backend
            # due to RACE!
            item = app.playback_manager.get_playing_item()
            remote_item = False
            if item and item.remote:
                remote_item = True
            if remote_item and item.host == host and item.port == port:
                app.playback_manager.stop(save_resume_time=False)
        # XXX should not remove this tab if it is currently mounted.  The
        # mDNS going away just means it is no longer published, doesn't
        # mean it's not available.
        message = messages.TabsChanged('sharing', added_list, [], removed_list) 
        message.send_to_frontend()

    def server_thread(self):
        callback = libdaap.browse_mdns(self.mdns_callback)
        while True:
            refs = callback.get_refs()
            try:
                r, w, x = select.select(refs + [self.r], [], [])
                for i in r:
                    if i in refs:
                        callback(i)
                        continue
                    if i == self.r:
                        return
            # XXX what to do in case of error?  How to pass back to user?
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue
                else:
                    pass
            except:
                pass

    def start_tracking(self):
        # sigh.  New thread.  Unfortunately it's kind of hard to integrate
        # it into the application runloop at this moment ...
        self.thread = threading.Thread(target=thread_body,
                                       args=[self.server_thread],
                                       name='mDNS Browser Thread')
        self.thread.start()

    def eject(self, share_id):
        tracker = self.trackers[share_id]
        del self.trackers[share_id]
        tracker.disconnect()

    def get_tracker(self, tab, share_id):
        try:
            return self.trackers[share_id]
        except KeyError:
            print 'CREATING NEW TRACKER'
            self.trackers[share_id] = SharingItemTrackerImpl(tab, share_id)
            return self.trackers[share_id]

    def stop_tracking(self):
        os.write(self.w, "b")

# Synchronization issues: The messagehandler.SharingItemTracker() creates
# one of these for each share it connects to.  If this is an initial connection
# the send_initial_list() will be empty and it will send the actual list
# after connected, which must happen strictly after send_initial_list() as
# both are scheduled to run on the backend thread.  If this is not an initial
# connection then send_initial_list() would already have been populated so
# we are fine there.
class SharingItemTrackerImpl(object):
    type = 'sharing'
    def __init__(self, tab, share_id):
        self.tab = tab
        self.id = share_id
        self.items = []
        eventloop.call_in_thread(self.client_connect_callback,
                                 self.client_connect_error_callback,
                                 self.client_connect,
                                 'DAAP client connect')

    def sharing_item(self, rawitem):
        file_type = u'audio'    # fallback
        if rawitem['file_type'] == libdaap.DAAP_MEDIAKIND_AUDIO:
            file_type = u'audio'
        if rawitem['file_type'] in [libdaap.DAAP_MEDIAKIND_TV,
                                    libdaap.DAAP_MEDIAKIND_MOVIE,
                                    libdaap.DAAP_MEDIAKIND_VIDEO
                                   ]:
            file_type = u'video'
        sharing_item = item.SharingItem(
            id=rawitem['id'],
            duration=rawitem['duration'],
            size=rawitem['size'],
            name=rawitem['name'].decode('utf-8'),
            file_type=file_type,
            host=self.client.host,
            port=self.client.port,
            video_path=self.client.daap_get_file_request(rawitem['id'])
        )
        return sharing_item

    def disconnect(self):
        ids = [item.id for item in self.get_items()]
        message = messages.ItemsChanged(self.type, self.tab, [], [], ids)
        print 'SENDING removed message'
        message.send_to_frontend()
        # No need to clean out our list of items as we are going away anyway.
        # As close() can block, run in separate thread.
        eventloop.call_in_thread(self.client_disconnect_callback,
                                 self.client_disconnect_error_callback,
                                 lambda: self.client.disconnect(),
                                 'DAAP client disconnect')

    def client_disconnect_error_callback(self, unused):
        pass

    def client_disconnect_callback(self, unused):
        pass

    def client_connect(self):
        print 'client_thread: running'
        # The id actually encodes (name, host, port).
        name, host, port = self.id
        self.client = libdaap.make_daap_client(host, port)
        if not self.client.connect():
            # XXX API does not allow us to send more detailed results
            # back to the poor user.
            raise IOError('Cannot connect')
        # XXX no API for this?  And what about playlists?
        # XXX dodgy - shouldn't do this directly
        # Find the base playlist, then suck all data out of it and then
        # return as a ItemsChanged message
        for k in self.client.playlists.keys():
            if self.client.playlists[k]['base']:
                break
        # Maybe we have looped through here without a base playlist.  Then
        # the server is broken.
        if not self.client.playlists[k]['base']:
            print 'no base list?'
            return
        items = self.client.items[k]
        for k in items.keys():
            item = messages.ItemInfo(self.sharing_item(items[k]))
            self.items.append(item)

    def client_connect_callback(self, unused):
        self.connected = True
        message = messages.ItemsChanged(self.type, self.tab, self.items, [], [])
        print 'SENDING changed message %d items' % len(message.added)
        message.send_to_frontend()

    def client_connect_error_callback(self, unused):
        # If it didn't work, immediately disconnect ourselves.
        app.sharing_tracker.eject(self.id)
        messages.SharingConnectFailed(self.tab, self.id).send_to_frontend()

    def get_items(self):
        return self.items

class SharingManagerBackend(object):
    types = ['videos', 'music']
    id    = None                # Must be None
    items = dict()              # Neutral format - not really needed.
    daapitems = dict()          # DAAP format XXX - index via the items
    # XXX daapplaylist should be hidden from view. 
    daap_playlists = dict()     # Playlist, in daap format
    playlist_item_map = dict()  # Playlist -> item mapping
    my_mdns = (None, None)      # No entry

    def register_protos(self, proto):
        pass

    def handle_item_list(self, message):
        self.make_item_dict(message.items)

    def handle_items_changed(self, message):
        # If items are changed, just redelete and recreate the entry.
        for x in message.removed:
            del self.items[x]
            del self.daapitems[x]
        self.make_item_dict(message.added)
        self.make_item_dict(message.changed)

    # Note: this should really be a util function and be separated
    def make_daap_playlists(self, items):
        # Pants.  We reuse the function but the view from the database is
        # different to the message the frontend sends to us!  So, minm is
        # duplicated.
        mappings = [('name', 'minm'), ('title', 'minm'), ('id', 'miid'),
                    ('id', 'mper')]
        for x in items:
            attributes = []
            for p, q in mappings:
                try:
                    if isinstance(getattr(x, p), unicode):
                        attributes.append((q, getattr(x, p).encode('utf-8')))
                    else:
                        attributes.append((q, getattr(x, p)))
                except AttributeError:
                    # Didn't work.  Oh well, get the next one.
                    continue
            # At this point, the item list has not been fully populated yet.
            # Therefore, it may not be possible to run get_items() and getting
            # the count attribute.  Instead we use the playlist_item_map.
            tmp = [y for y in playlist.PlaylistItemMap.playlist_view(x.id)]
            count = len(tmp)
            attributes.append(('mpco', 0))        # Parent container ID
            attributes.append(('mimc', count))    # Item count
            self.daap_playlists[x.id] = attributes

    def handle_playlist_added(self, obj, added):
        self.make_daap_playlists(added)

    def handle_playlist_changed(self, obj, changed):
        for x in changed:
            del self.daap_playlists[x.id]
        self.make_daap_playlists(changed)

    def handle_playlist_removed(self, obj, removed):
        for x in removed:
            del self.daap_playlists[x]

    def populate_playlists(self):
        self.make_daap_playlists(playlist.SavedPlaylist.make_view())
        for playlist_id in self.daap_playlists.keys():
            self.playlist_item_map[playlist_id] = [x.item_id
              for x in playlist.PlaylistItemMap.playlist_view(playlist_id)]

    def start_tracking(self):
        for t in self.types:
            app.info_updater.item_list_callbacks.add(t, self.id,
                                                self.handle_item_list)
            app.info_updater.item_changed_callbacks.add(t, self.id,
                                                self.handle_items_changed)

        self.populate_playlists()

        app.info_updater.connect('playlists-added',
                                 self.handle_playlist_added)
        app.info_updater.connect('playlists-changed',
                                 self.handle_playlist_changed)
        app.info_updater.connect('playlists-removed',
                                 self.handle_playlist_removed)

    def stop_tracking(self):
        for t in self.types:
            app.info_updater.item_list_callbacks.remove(t, self.id,
                                                self.handle_item_list)
            app.info_updater.item_changed_callbacks.remove(t, self.id,
                                                self.handle_items_changed)

        app.info_updater.disconnect(self.handle_playlist_added)
        app.info_updater.disconnect(self.handle_playlist_changed)
        app.info_updater.disconnect(self.handle_playlist_removed)

    def get_filepath(self, itemid):
        return self.items[itemid]['path']

    def get_playlists(self):
        playlists = []
        for k in self.daap_playlists.keys():
            playlists.append(('mlit', self.daap_playlists[k]))
        return playlists

    def get_items(self, playlist_id=None):
        # FIXME Guard against handle_item_list not having been run yet?
        # But if it hasn't been run, it really means at there are no items
        # (at least, in the eyes of Miro at this stage).
        # XXX cache me.  Ideally we cache this per-protocol then we create
        # this eagerly, then the self.items becomes a mapping from proto
        # to a list of items.

        # Easy: just return
        if not playlist_id:
            return self.daapitems
        # XXX Somehow cache this?
        playlist = dict()
        for x in self.daapitems.keys():
            if x in self.playlist_item_map[playlist_id]:
                playlist[x] = self.daapitems[x]
        return playlist

    def make_item_dict(self, items):
        # See lib/messages.py for a list of full fields that can be obtained
        # from an ItemInfo.  Note that, this only contains partial information
        # as it does not contain metadata about the item.  We do make one or
        # two assumptions here, in particular the file_type will always either
        # be video or audio.  For the actual file extension we strip it off
        # from the actual file path.  We create a dict object for this,
        # which is not very economical.  Is it possible to just keep a 
        # reference to the ItemInfo object?
        interested_fields = ['id', 'name', 'size', 'file_type', 'file_format',
                             'video_path', 'duration']
        for x in items:
            name = x.name
            size = x.size
            duration = x.duration
            file_type = x.file_type
            path = x.video_path
            f, e = os.path.splitext(path)
            # Note! sometimes this doesn't work because the file has no
            # extension!
            if e:
                e = e[1:]
            self.items[x.id] = dict(name=name, size=size, duration=duration,
                                  file_type=file_type, path=path,
                                  enclosure_format=e)
            self.daapitems[x.id] = daap_item_fixup(x.id, self.items[x.id])

class SharingManager(object):
    def __init__(self):
        self.r, self.w = os.pipe()
        self.sharing = False
        self.discoverable = False
        self.my_mdns = (None, None)
        self.config_watcher = config.ConfigWatcher(
            lambda func, *args: eventloop.add_idle(func, 'config watcher',
                 args=args))
        self.callback_handle = self.config_watcher.connect('changed',
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

    def mdns_myself(self):
        return self.my_mdns

    def on_config_changed(self, obj, key, value):
        # We actually know what's changed but it's so simple let's not bother.
        self.twiddle_sharing()

    def twiddle_sharing(self):
        sharing = app.config.get(prefs.SHARE_MEDIA)
        discoverable = app.config.get(prefs.SHARE_DISCOVERABLE)

        if sharing != self.sharing:
            if sharing:
                # TODO: if this didn't work, should we set a timer to retry
                # at some point in the future?
                if not self.enable_sharing():
                    return
            else:
                self.disable_discover()
                self.disable_sharing()

        # Short-circuit: if we have just disabled the share, then we don't
        # need to check the discoverable bits since it is not relevant, and
        # would already have been disabled anyway.
        if not self.sharing:
            return

        if discoverable != self.discoverable:
            if discoverable:
                self.enable_discover()
            else:
                self.disable_discover()

    def enable_discover(self):
        name = app.config.get(prefs.SHARE_NAME)
        address, port = self.server.server_address
        # XXX need to call asynchronously
        hostname = socket.gethostname()
        addrinfo = socket.getaddrinfo(hostname, port, 0, 0, socket.SOL_TCP)
        addresses = []
        for family, socktype, proto, canonname, sockaddr in addrinfo:
            addresses.append(canonname) 
        self.my_mdns = addresses, port
        self.mdns_callback = libdaap.install_mdns(name, port=port)
        # not exactly but close enough: it's not actually until the
        # processing function gets called.
        self.discoverable = True

    def disable_discover(self):
        self.discoverable = False
        libdaap.uninstall_mdns(self.mdns_callback)
        self.my_mdns = (None, None)

    def server_thread(self):
        server_fileno = self.server.fileno()
        kill_thread = False
        while True:
            try:
                rset = [server_fileno, self.r]
                refs = self.mdns_callback.get_refs()
                rset += refs
                r, w, x = select.select(rset, [], [])
                for i in r:
                    if i in refs:
                        self.mdns_callback(i)
                        continue
                    if server_fileno == i:
                        self.server.handle_request()
                        continue
                    if self.r == i:
                        return
            except select.error, (err, errstring):
                if err == errno.EINTR:
                    continue 
                else:
                    pass
            # XXX How to pass error, send message to the backend/frontend?
            except:
                pass

    def enable_sharing(self):
        name = app.config.get(prefs.SHARE_NAME)
        self.server = libdaap.make_daap_server(self.backend, name=name)
        if not self.server:
            self.sharing = False
            return
        self.thread = threading.Thread(target=thread_body,
                                       args=[self.server_thread],
                                       name='DAAP Server Thread')
        self.thread.start()
        self.sharing = True

        return self.sharing

    def disable_sharing(self):
        self.sharing = False
        os.write(self.w, "b")
        del self.thread
        del self.server

    def shutdown(self):
        if self.sharing:
            self.disable_sharing()
