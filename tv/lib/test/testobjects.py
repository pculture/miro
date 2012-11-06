"""miro.test.testobjs -- Create test objects.

This module is a collection of functions to make objects to use for testing.
"""

import collections
import datetime
import itertools
import random
import os

from miro import app
from miro import database
from miro import devices
from miro import item
from miro import libdaap
from miro import models
from miro import messages
from miro import sharing
from miro import util
from miro.data.item import fetch_item_infos
from miro.plat.utils import filename_to_unicode, unicode_to_filename
from miro.test import mock

feed_counter = itertools.count()

def test_started(current_test_case):
    """Reset the test object data"""
    global feed_counter, current_test
    feed_counter = itertools.count()
    current_test = current_test_case

def make_item_info(itemobj):
    return fetch_item_infos(app.db.connection, [itemobj.id])[0]

def make_feed():
    url = u'http://feed%d.com/feed.rss' % feed_counter.next()
    return models.Feed(url)

def make_manual_feed():
    return models.Feed(u'dtv:manualFeed', initiallyAutoDownloadable=False)

def make_feed_for_file(path):
    """Create a feed with a file:// URL that points to a file """
    url = u'file://%s' % path
    return models.Feed(url)

def make_item(feed, title):
    """Make a new item."""
    fp_values = item.FeedParserValues({})
    fp_values.data['entry_title'] = title
    fp_values.data['url'] = u'http://example.com/%s.mkv' % title
    # pick a random recent date for the release date
    seconds_ago = random.randint(0, 60 * 60 * 24 * 7)
    release_date = (datetime.datetime.now() -
                    datetime.timedelta(seconds=seconds_ago))
    fp_values.data['release_date'] = release_date
    return models.Item(fp_values, feed_id=feed.id)

def make_file_item(feed, title=None, path=None):
    if path is None:
        path = current_test.make_temp_path('.avi')
    ensure_file_exists(path)
    return models.FileItem(path, feed.id,
                           fp_values=item.fp_values_for_file(path, title))

def make_feed_with_items(item_count, file_items=False, prefix=None):
    feed = make_feed()
    items = add_items_to_feed(feed, item_count, file_items, prefix)
    return feed, items

def add_items_to_feed(feed, item_count, file_items=False, prefix=None):
    items = []
    for i in xrange(item_count):
        if prefix is None:
            name = u"%s-item%d" % (feed.get_title(), i)
        else:
            name = u"%s-item%d" % (prefix, i)
        if file_items:
            items.append(make_file_item(feed, name))
        else:
            items.append(make_item(feed, name))
    return items

def ensure_file_exists(path):
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write("test-data")
            f.close()

def make_devices_device_info():
    return devices.DeviceInfo(
        u'Test Device',
        video_conversion='copy',
        audio_conversion='copy',
        video_path=u'Video',
        audio_path=u'Music',
        vendor_id=123,
        product_id=123,
        container_types='mp3 wav asf isom ogg mpeg avi'.split(),
        audio_types='mp* wmav* aac pcm* vorbis'.split(),
        video_types='theora h264 mpeg* wmv*'.split(),
        mount_instructions='')

def make_mock_device(no_database=False):
    mount = current_test.make_temp_dir_path()
    os.makedirs(os.path.join(mount, '.miro'))
    os.makedirs(os.path.join(mount, 'cover-art'))
    device = messages.DeviceInfo(123, make_devices_device_info(), mount,
                                 devices.sqlite_database_path(mount),
                                 devices.DeviceDatabase(), None, None,
                                 1024000, 512000, False)
    if not no_database:
        setup_mock_device_database(device)
    return device

def setup_mock_device_database(device):
    device.database = devices.DeviceDatabase()
    device.database[u'settings'] = {
        u'audio_path': os.path.join(device.mount, 'audio_path'),
        u'video_path': os.path.join(device.mount, 'video_path'),
    }
    sqlite_db = devices.load_sqlite_database(device.mount,
                                             device.size)
    db_info = database.DeviceDBInfo(sqlite_db, device.id)
    metadata_manager = devices.make_metadata_manager(device.mount,
                                                     db_info,
                                                     device.id)
    device.db_info = db_info
    device.metadata_manager = metadata_manager
    return device

def make_device_items(device, *filenames):
    return [make_device_item(device, filename) for filename in filenames]

def make_device_item(device, filename):
    # ensure that filename is the correct type for our platform
    filename = unicode_to_filename(unicode(filename))
    ensure_file_exists(os.path.join(device.mount, filename))
    return item.DeviceItem(device, filename)

class MockDAAPClientLibrary(object):
    """Tracks items in the library for MockDAAPClient
    """

    def __init__(self):
        self.base_playlist_id = 123
        # maps item ids to item data for all items
        self.all_items = {}
        # maps playlist id to playlist data
        self.playlists = {
            self.base_playlist_id: { 'daap.baseplaylist': 1, },
        }
        # maps playlist id to dict mapping item ids to item data for that
        # playlist
        self.playlist_items = {
            self.base_playlist_id: {}
        }

    def set_items(self, new_items):
        self.all_items = dict((i['dmap.itemid'], i) for i in new_items)
        self.set_playlist_items(self.base_playlist_id, self.all_items.keys())

    def add_playlist(self, new_playlist):
        daap_id = new_playlist['dmap.itemid']
        if daap_id not in self.playlists:
            self.playlist_items[daap_id] = {}
        self.playlists[daap_id] = new_playlist.copy()

    def remove_playlist(self, daap_id):
        del self.playlists[daap_id]
        del self.playlist_items[daap_id]

    def set_playlist_items(self, playlist_id, item_ids):
        self.playlist_items[playlist_id] = dict(
            (daap_id, self.all_items[daap_id])
            for daap_id in item_ids)

    def copy(self):
        """Get a copy of this library."""
        rv = MockDAAPClientLibrary()
        rv.set_items(self.all_items.values())
        for k, playlist in self.playlists.items():
            if k != self.base_playlist_id:
                rv.add_playlist(playlist)
                rv.set_playlist_items(k, self.playlist_items[k])
        return rv

class MockDAAPClient(mock.Mock):
    """Mock up a DAAP client.

    Call set_items(), set_playlists(), and set_playlist_items() to change the
    data the client returns.  MockDAAPClient is smart enough to understand the
    upgrade=True flag and only return items that have changed since the last
    call


    """
    def __init__(self, *args, **kwargs):
        mock.Mock.__init__(self)
        self.host = '127.0.0.1'
        self.port = 8000
        self.conn.sock.getpeername.return_value = ('127.0.0.1', 8000)
        self.library = MockDAAPClientLibrary()
        # maps playlist ids to the last library we used to send items for that
        # playlist.  We use this to calculate which items we need to send when
        # update=True
        self.last_sent_library = {}
        # last sent library used for the playlists() method
        self.last_sent_library_for_playlists = None

    def set_items(self, new_items):
        """Change the current set of items.

        :param new_items: dict mapping DAAP ids to dicts of item data
        """
        self.library.set_items(new_items)

    def add_playlist(self, new_playlist):
        """Add a new playlist to the client."""
        self.library.add_playlist(new_playlist)

    def remove_playlist(self, playlist_id):
        """Remove a playlisst from the client."""
        self.library.remove_playlist(playlist_id)

    def set_playlist_items(self, playlist_id, new_playlist_items):
        """Change the current set of playlists.

        :param playlist_id: DAAP id of the playlist
        :param new_items: dict mapping DAAP ids for playlists to lists of DAAP
        ids for items in that playlist
        """
        self.library.set_playlist_items(playlist_id, new_playlist_items)

    def dict_diff(self, new_items, old_items):
        """Calculate the difference of 2 dicts.

        This method is used in items() and playlists() to when the update=True
        flag is used.

        :returns: (changed_items, deleted_ids) tuple.  changed_items is a dict
        mapping daap_ids to item data for new or updated items.  deleted_ids
        is a list of ids for deleted items.
        """
        items = {}
        deleted_items = []
        for k, item_data in new_items.items():
            if k not in old_items or old_items[k] != item_data:
                items[k] = item_data
        for k in old_items:
            if k not in new_items:
                deleted_items.append(k)
        return items, deleted_items

    def current_items(self, playlist_id=None):
        """Get current set of items."""
        if playlist_id is None:
            return self.library.all_items.copy()
        else:
            return self.library.playlist_items[playlist_id].copy()

    def current_playlists(self):
        """Get current set of playlists."""
        return self.library.playlists.copy()

    def current_playlist_item_map(self):
        """Get the current playlist item map

        :returns: dict mapping playlist id to item id lists.  This will only
        contain entries for playlists that actually have items in them.
        """
        rv = {}
        for playlist_id, items in self.library.playlist_items.items():
            if playlist_id != self.library.base_playlist_id and items:
                rv[playlist_id] = [i['dmap.itemid'] for i in items.values()]
        return rv

    def items(self, playlist_id=None, meta=None, update=False):
        last_library = self.last_sent_library.get(playlist_id)
        if not update or last_library is None:
            items = self.library.playlist_items[playlist_id].copy()
            deleted_items = []
        else:
            items, deleted_items = self.dict_diff(
                self.library.playlist_items[playlist_id],
                last_library.playlist_items[playlist_id])
        self.last_sent_library[playlist_id] = self.library.copy()
        return items, deleted_items

    def playlists(self, meta=None, update=False):
        if not update or self.last_sent_library_for_playlists is None:
            playlists = self.library.playlists.copy()
            deleted_playlists = []
        else:
            playlists, deleted_playlists = self.dict_diff(
                self.library.playlists,
                self.last_sent_library_for_playlists.playlists)
            # add playlists that have had their items changed
            for playlist_id, item_set in self.library.playlist_items.items():
                try:
                    last_library = self.last_sent_library[playlist_id]
                except KeyError:
                    continue
                last_item_set = last_library.playlist_items[playlist_id]
                if last_item_set != item_set:
                    playlist_data = self.library.playlists[playlist_id]
                    playlists[playlist_id] = playlist_data

        self.last_sent_library_for_playlists = self.library.copy()
        return playlists, deleted_playlists

    def databases(self, update):
        return True

    def daap_get_file_request(self, daap_id, file_format):
        return '/item-%s' % daap_id

    def _get_child_mock(self, parent, name, wraps):
        return mock.Mock()

    def returnself(self, *args):
        """Return a references to ourselves.

        This method can be used to patch the miro.libdaap.make_daap_client()
        """
        return self

def make_mock_daap_item(item_id, title, file_type='audio'):
    if file_type == 'audio':
        daap_file_type = libdaap.DAAP_MEDIAKIND_AUDIO
    elif file_type == 'video':
        daap_file_type = libdaap.DAAP_MEDIAKIND_VIDEO
    else:
        raise ValueError("Unknown file type %s" % file_type)
    return {
        'com.apple.itunes.mediakind': daap_file_type,
        'daap.songformat': 'mpeg',
        'dmap.itemid': item_id,
        'dmap.itemname': title,
        'daap.songtime': 123,
    }

def make_mock_daap_playlist(playlist_id, title, is_podcast=False):
    playlist_data = {
        'dmap.itemid': playlist_id,
        'dmap.itemname': title,
    }
    if is_podcast:
        playlist_data['com.apple.itunes.is-podcast-playlist'] = True
    return playlist_data

def make_share(name='TestShare'):
    return sharing.Share('testshareid', name, u'127.0.0.1', 1234)

def make_sharing_items(share, *titles):
    return [make_sharing_item(share, i, "/item-%s" % i, title)
            for i, title in enumerate(titles)]

def make_sharing_item(share, daap_id, path, title, file_type=u'video'):
    kwargs = {
        'video_path': path,
        'host': share.host,
        'port': share.port,
        'title': title,
        'file_type': file_type,
        'db_info': share.db_info,
    }
    return item.SharingItem(daap_id, **kwargs)
