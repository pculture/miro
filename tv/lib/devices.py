# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
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

from glob import glob
import fnmatch
try:
    import simplejson as json
except ImportError:
    import json
import codecs
import logging
import os, os.path
import re
import time
import bisect
import tempfile
try:
    from collections import Counter
except ImportError:
    from collections import defaultdict
    class Counter(defaultdict):
        def __init__(self, *args, **kwargs):
            super(Counter, self).__init__(int, *args, **kwargs)

from miro import app
from miro import database
from miro import devicedatabaseupgrade
from miro import eventloop
from miro import item
from miro import itemsource
from miro import feed
from miro import fileutil
from miro import filetypes
from miro import metadata
from miro import prefs
from miro import playlist
from miro.gtcache import gettext as _
from miro import messages
from miro import schema
from miro import signals
from miro import storedatabase
from miro import threadcheck
from miro import conversions
from miro.util import check_u

from miro.download_utils import next_free_filename

from miro.plat import resources
from miro.plat.utils import (filename_to_unicode, unicode_to_filename,
                             utf8_to_filename)


# how much slower converting a file is, compared to copying
CONVERSION_SCALE = 500
# schema version for device databases
DB_VERSION = 198

def unicode_to_path(path):
    """
    Convert a Unicode string into a file path.  We don't do any of the string
    replace nonsense that unicode_to_filename does.  We also convert separators
    into the appropriate type for the platform.
    """
    return utf8_to_filename(path.encode('utf8')).replace('/', os.path.sep)

class GlobSet(object):
    """
    A set()like object which allows some of its values to be glob-style pattern
    matches.
    """
    def __init__(self, values):
        self.frozenset = frozenset(v.lower() for v in values
                                   if v and '*' not in v)
        patterns = [v.lower() for v in values if '*' in v]
        self.repr = repr([v.lower() for v in values])
        if patterns:
            self.regex = re.compile('|'.join(fnmatch.translate(v)
                                             for v in patterns))
        else:
            self.regex = None

    def __repr__(self):
        return "GlobSet(%s)" % (self.repr,)

    def __contains__(self, value):
        if not value:
            return False
        value = value.lower()
        if value in self.frozenset:
            return True
        elif self.regex:
            return bool(self.regex.match(value))
        return False

    def __iter__(self):
        return iter(self.frozenset)

    def __eq__(self, other):
        return self.frozenset == frozenset(other)

    def __and__(self, other):
        if isinstance(other, GlobSet):
            return NotImplemented
        other = set(other)
        if self.frozenset & other:
            return True
        if not self.regex:
            return False
        return any(v for v in other if self.regex.match(v))

class BaseDeviceInfo(object):
    """
    Base class for device information.
    """
    # NB: We don't really need to be using __slots__ here; it's not using that
    # much memory.  But, since we need a list of the attributes anyways, we
    # might as well save a bit of memory anyways.
    __slots__ = ['name', 'device_name', 'vendor_id', 'product_id',
                 'video_conversion', 'video_path',
                 'audio_conversion', 'audio_path',
                 'container_types', 'audio_types', 'video_types',
                 'mount_instructions']
    def update(self, kwargs):
        for key, value in kwargs.items():
            if key == 'audio_path':
                self.audio_path = unicode_to_path(value)
            elif key == 'video_path':
                self.video_path = unicode_to_path(value)
            elif key.endswith('_types'):
                setattr(self, key, GlobSet(value))
            else:
                setattr(self, key, value)

    def __getattr__(self, key):
        try:
            return super(BaseDeviceInfo, self).__getattr_(key)
        except (AttributeError, KeyError):
            if key == 'parent' or not hasattr(self, 'parent'):
                raise AttributeError(key)
            else:
                return getattr(self.parent, key)

    def validate(self):
        for key in BaseDeviceInfo.__slots__:
            getattr(self, key)

class DeviceInfo(BaseDeviceInfo):
    """
    Object which contains various information about a specific supported
    device.

    name: User-visible name of the device
    device_name: the name of the device as reported through USB
    vendor_id: integer version of the device's USB vendor ID
    product_id: integer version of the device's USB product ID
    video_conversion: the Miro conversion name for video to this device
    video_path: mount-relative path to where the videos should be placed
    audio_conversion: the Miro conversion name for audio to this device
    audio_path: mount-relative path to where audio files should be placed
    container_types: FFmpeg container formats this device supports
    audio_types: FFmpeg audio codecs this device supports
    video_types: FFmpeg video codecs this device supports
    mount_instructions: text to show the user about how to mount their device
    parent (optional): a MultipleDeviceInfo instance which has this device's
                       info
    """
    has_multiple_devices = False
    __slots__ = BaseDeviceInfo.__slots__ + ['parent']

    def __init__(self, name, **kwargs):
        self.name = name
        self.update(kwargs)

    def __repr__(self):
        return "<DeviceInfo %r %r %x %x>" % (
            getattr(self, "name", None),
            getattr(self, "device_name", None),
            getattr(self, "vendor_id", None) or 0,
            getattr(self, "product_id", None) or 0)

class MultipleDeviceInfo(BaseDeviceInfo):
    """
    Like DeviceInfo, but represents a device we can't figure out just from the
    USB information.
    """
    has_multiple_devices = True
    __slots__ = BaseDeviceInfo.__slots__ + ['devices']
    def __init__(self, device_name, children, **kwargs):
        self.device_name = self.name = device_name
        self.update(kwargs)
        self.devices = {}
        for info in children:
            self.add_device(info)

    def add_device(self, info):
        self.devices[info.name] = info
        info.parent = self
        for key in BaseDeviceInfo.__slots__:
            try:
                getattr(self, key)
            except (AttributeError, KeyError):
                setattr(self, key, getattr(info, key))

    def get_device(self, name):
        """
        Get a given device by the user-visible name.

        Returns a DeviceInfo object.
        """
        return self.devices[name]

    def validate(self):
        for child in self.devices.values():
            child.validate()

class USBMassStorageDeviceInfo(DeviceInfo):
    """
    DeviceInfo object used for generic USB Mass Storage devices.
    """
    def __init__(self, name):
        self.name = self.device_name = name
        self.update({
                'generic': True,
                'mount_instructions': _("Your drive must be mounted."),
                'audio_conversion': 'copy',
                'audio_types': frozenset(),
                'audio_path': u'Miro',
                'video_types': frozenset(),
                'video_conversion': 'copy',
                'video_path': u'Miro',
                'container_types': frozenset(),
                })

class DeviceManager(object):
    """
    Manages the list of devices that Miro knows about, as well as managing the
    current syncs for devices.
    """
    def __init__(self):
        self.device_by_name = {}
        self.device_by_id = {}
        self.generic_devices = []
        self.generic_devices_by_id = {}
        self.connected = {}
        self.info_cache = {} # device mount > dict
        self.syncs_in_progress = {}
        self.running = False
        self.startup()
        self.show_unknown = app.config.get(prefs.SHOW_UNKNOWN_DEVICES)

    def _merge(self, one, two):
        """
        Merge two devices into one MultipleDeviceInfo.
        """
        if isinstance(one, MultipleDeviceInfo):
            if isinstance(two, MultipleDeviceInfo):
                for child in two.devices.values():
                    one.add_device(child)
            else:
                one.add_device(two)
            return one
        elif isinstance(two, MultipleDeviceInfo):
            two.add_device(one)
            return two
        else: # new MDI
            return MultipleDeviceInfo(one.device_name, [one, two])

    def add_device(self, info):
        try:
            info.validate()
        except AttributeError:
            logging.exception('error validating device %s', info.name)
        else:
            if info.product_id is None or '*' in info.device_name:
                # generic device
                if info.product_id is not None or '*' not in info.device_name:
                    logging.debug('invalid generic device %s', info.name)
                else:
                    self.generic_devices.append(info)
                    self.generic_devices_by_id[info.vendor_id] = info
            else:
                if info.device_name not in self.device_by_name:
                    self.device_by_name[info.device_name] = info
                else:
                    existing = self.device_by_name[info.device_name]
                    self.device_by_name[info.device_name] = self._merge(
                        existing, info)
                if (info.vendor_id, info.product_id) not in self.device_by_id:
                    self.device_by_id[(info.vendor_id, info.product_id)] = info
                else:
                    key = (info.vendor_id, info.product_id)
                    existing = self.device_by_id[key]
                    self.device_by_id[key] = self._merge(existing, info)

    def remove_device(self, info):
        # FIXME - need this
        pass

    def force_db_save_error(self, device_info):
        if device_info.db_info is None:
            logging.warn("force_db_save_error: db_info is None "
                         "is the device connected?")
            return
        device_info.db_info.db.simulate_db_save_error()

    def startup(self):
        # load devices
        self.load_devices(resources.path('devices/*.py'))
        self.running = True

    def shutdown(self):
        self.running = False
        for device in self.connected.values():
            if (device.mount and not device.read_only):
                device.metadata_manager.run_updates()
                device.database.shutdown()

    def load_devices(self, path):
        devices = glob(path)
        for device_desc in devices:
            global_dict = {}
            # XXX bz:17989 execfile() can't handle unicode paths!
            if isinstance(device_desc, unicode):
               device_desc = device_desc.encode('utf-8')
            execfile(device_desc, global_dict)
            if 'devices' in global_dict:
                for info in global_dict['devices']:
                    self.add_device(info)

    @staticmethod
    def _get_device_from_info(info, device_type):
        if not info.has_multiple_devices:
            return info
        if device_type is not None and device_type in info.devices:
            return info.devices[device_type]
        if len(info.devices) == 1: # only one device
            return info.devices.values()[0]
        return info

    def get_device(self, device_name, device_type=None):
        """
        Get a DeviceInfo (or MultipleDeviceInfo) object given the device's USB
        name.
        """
        try:
            info = self.device_by_name[device_name]
        except KeyError:
            for info in self.generic_devices:
                if fnmatch.fnmatch(device_name, info.device_name):
                    break
            else:
                raise
        return self._get_device_from_info(info, device_type)

    def get_device_by_id(self, vendor_id, product_id, device_type=None):
        """
        Get a DeviceInfo (or MultipleDeviceInfo) object give the device's USB
        vendor and product IDs.
        """
        try:
            info = self.device_by_id[(vendor_id, product_id)]
        except KeyError:
            if vendor_id in self.generic_devices_by_id:
                info = self.generic_devices_by_id[vendor_id]
            else:
                raise
        return self._get_device_from_info(info, device_type)

    def set_show_unknown(self, show):
        """
        Set the value of the show_unknown flag, and, if necessary, send some
        connected/disconnected messages.
        """
        if self.show_unknown == show:
            return # no change
        unknown_devices = [info for info in self.connected.values()
                           if self._is_unknown(info) and not info.read_only]
        if show: # now we're showing them
            for info in unknown_devices:
                if (info.db_info is not None and
                    info.db_info.db.temp_mode):
                    info.db_info.db.force_directory_creation = True
                    eventloop.add_idle(
                        info.db_info.db._try_save_temp_to_disk,
                        'writing device SQLite DB on show: %r' % info.mount)
                self._send_connect(info)
        else: # now we're hiding them
            for info in unknown_devices:
                self._send_disconnect(info)
        self.show_unknown = show
        app.config.set(prefs.SHOW_UNKNOWN_DEVICES, show)

    def change_setting(self, device, setting, value):
        """Change the value 
        """
        device.database.setdefault(u'settings', {})
        device.database[u'settings'][setting] = value
        if setting == 'name':
            device.name = value
            # need to send a changed message
            message = messages.TabsChanged('connect', [], [device], [])
            message.send_to_frontend()
            message = messages.DeviceChanged(device)
            message.send_to_frontend()
        elif setting == 'always_show' and not self.show_unknown:
            if value:
                self._send_connect(device)
            else:
                self._send_disconnect(device)

    def eject_device(self, device):
        worker_task_count = device.metadata_manager.worker_task_count()
        device.metadata_manager.close()
        if worker_task_count > 0:
            self._call_eject_later(device, 5)
            return

        write_database(device.database, device.mount)
        if device.db_info is not None:
            device.db_info.db.close()
        app.device_tracker.eject(device)

    def _call_eject_later(self, device, timeout):
        """Call eject_device after a short delay.  """
        eventloop.add_timeout(timeout, self.eject_device,
                              'ejecting device',
                              args=(device,))

    @staticmethod
    def _is_unknown(info_or_tuple):
        if isinstance(info_or_tuple, messages.DeviceInfo):
            mount, info, db = (info_or_tuple.mount, info_or_tuple.info,
                               info_or_tuple.database)
        else:
            mount, info, db = info_or_tuple
        if not getattr(info, 'generic', False):
            # not a generic device
            return False
        if mount and db.get(u'settings', {}).get(
            'always_show', False):
            # we want to show this device all the time
            return False
        return True

    @staticmethod
    def _is_read_only(mount):
        if not mount:
            return True
        try:
            f = tempfile.TemporaryFile(dir=mount)
        except EnvironmentError:
            return True
        else:
            f.close()
            return False

    def _is_hidden(self, info):
        # like _is_unknown(), but takes the self.show_unknown flag into account
        if self.show_unknown:
            return False
        else:
            return self._is_unknown(info)

    def _set_connected(self, id_, kwargs):
        mount = kwargs.get('mount')
        if mount:
            db = load_database(mount)
            device_name = db.get(u'device_name', kwargs.get('device_name'))
        else:
            device_name = None
            db = DeviceDatabase()
        if 'name' in kwargs:
            try:
                info = self.get_device(kwargs['name'],
                                       device_name)
            except KeyError:
                info = USBMassStorageDeviceInfo(kwargs.get('visible_name',
                                                   kwargs['name']))
        elif 'vendor_id' in kwargs and 'product_id' in kwargs:
            try:
                info = self.get_device_by_id(kwargs['vendor_id'],
                                             kwargs['product_id'],
                                             device_name)
            except KeyError:
                info = USBMassStorageDeviceInfo(_('USB Device'))
        else:
            raise RuntimeError('connect_device() requires either the device '
                               'name or vendor/product IDs')

        kwargs.update({
                'database': db,
                'device_name': device_name,
                'info': info})
        if mount:
            is_hidden = self._is_hidden((mount, info, db))
            read_only = self._is_read_only(mount)
            if (id_ in self.connected and
                self.connected[id_].db_info is not None):
                # reuse old database
                db_info = self.connected[id_].db_info
                metadata_manager = self.connected[id_].metadata_manager
                if is_hidden:
                    # device became hidden, close the existing objects
                    db_info.db.close()
                    metadata_manager.close()
                    db_info = metadata_manager = None
            elif not read_only:
                sqlite_db = load_sqlite_database(mount, kwargs.get('size'),
                                                 is_hidden=is_hidden)
                db_info = database.DeviceDBInfo(sqlite_db, id_)
                importer = devicedatabaseupgrade.OldItemImporter(sqlite_db,
                                                                 mount,
                                                                 db)
                importer.import_metadata()
                metadata_manager = make_metadata_manager(mount, db_info, id_)
                importer.import_device_items(metadata_manager)
                db.check_old_key_usage = True
            else:
                db_info = metadata_manager = None
        else:
            db_info = None
            metadata_manager = None
            read_only = False
        if db_info is not None:
            sqlite_path = sqlite_database_path(mount)
        else:
            sqlite_path = None

        info = self.connected[id_] = messages.DeviceInfo(
            id_, info, mount, sqlite_path, db, db_info,
            metadata_manager, kwargs.get('size'), kwargs.get('remaining'),
            read_only)

        return info

    @eventloop.as_idle
    def device_connected(self, id_, **kwargs):
        if id_ in self.connected:
            # backend got confused
            self.device_changed(id_, **kwargs)
            return

        info = self._set_connected(id_, kwargs)

        if not self._is_hidden(info) and not info.read_only:
            self._send_connect(info)
        else:
            logging.debug('ignoring %r', info)

    def _send_connect(self, info):
        if info.mount:
            self.info_cache.setdefault(info.mount, {})
            on_mount(info)
        messages.TabsChanged('connect', [info], [], []).send_to_frontend()

    @eventloop.as_idle
    def device_changed(self, id_, **kwargs):
        if id_ not in self.connected:
            # backend didn't send a connected message
            self.device_connected(id_, **kwargs)
            return

        info = self.connected[id_]

        if info.mount:
            # turn off the autosaving on the old database
            info.database.disconnect_all()
            eventloop.add_idle(write_database, 'writing database on change',
                               (info.database, info.mount))

        info = self._set_connected(id_, kwargs)

        if self._is_hidden(info) or info.read_only:
            # don't bother with change message on devices we're not showing
            return

        if info.mount:
            self.info_cache.setdefault(info.mount, {})
            on_mount(info)
        else:
            sync_manager = app.device_manager.get_sync_for_device(info,
                                                                  create=False)
            if sync_manager:
                sync_manager.cancel()
        messages.TabsChanged('connect', [], [info], []).send_to_frontend()
        messages.DeviceChanged(info).send_to_frontend()

    @eventloop.as_idle
    def device_disconnected(self, id_):
        if id_ not in self.connected:
            return # don't bother with sending messages

        info = self.connected.pop(id_)
        if not self._is_hidden(info) and not info.read_only:
            self._send_disconnect(info)

    def _send_disconnect(self, info):
        sync_manager = app.device_manager.get_sync_for_device(info,
                                                              create=False)
        if sync_manager and not sync_manager.is_finished():
            messages.ShowWarning(
                _('Device removed during sync'),
                _('%(name)s was removed while a sync was in progress.  '
                  'Not all items may have been copied.',
                  {'name': info.name})).send_to_frontend()
            sync_manager.cancel()

        if info.mount:
            del self.info_cache[info.mount]
        messages.TabsChanged('connect', [], [], [info.id]).send_to_frontend()

    def get_sync_for_device(self, device, create=True):
        """
        Returns a DeviceSyncManager for the given device.  If one exists,
        return that one, otherwise build a new one and return that.

        If create is False, return None instead of creating a new sync manager.
        """
        if device.id not in self.syncs_in_progress:
            if not create:
                return None
            dsm = DeviceSyncManager(device)
            self.syncs_in_progress[device.id] = dsm
            return dsm
        else:
            dsm = self.syncs_in_progress[device.id]
            dsm.set_device(device)
            return dsm

class DeviceSyncManager(object):
    """
    Represents a sync to a given device.
    """
    def __init__(self, device):
        self.device = device
        self.device_info = self.device.info
        self.device_settings = self.device.database.setdefault(u'settings',
                                                               {})
        self.start_time = time.time()
        self.signal_handles = []
        self.finished = 0
        self.total = 0
        self.progress_size = Counter()
        self.total_size = Counter()
        self.copying = {}
        self.waiting = set()
        self.auto_syncs = set()
        self.stopping = False
        self._change_timeout = None
        self._copy_iter_running = False
        self._info_to_conversion = {}
        self.started = False

    def get_sync_items(self, max_size=None):
        """Calculate information for syncing

        :returns: (sync_info, expired_items) where sync_info is ItemInfos that
        we need to sync and expired_items is DeviceItems for expired items.
        """
        # sync settings for the database
        sync = self.device.database.get(u'sync', {})
        # list of views with items to sync
        views = []
        # maps feed_urls -> set of URLs for items in that feed
        item_urls = {}
        # ItemInfos that we can sync
        infos = set()
        # DeviceItems whose original item is expired
        expired = set()

        # Iterate through synced podcasts
        if sync.setdefault(u'podcasts', {}).get(u'enabled', False):
            for url in sync[u'podcasts'].setdefault(u'items', []):
                feed_ = feed.lookup_feed(url)
                if feed_ is not None:
                    if sync[u'podcasts'].get(u'all', True):
                        view = feed_.downloaded_items
                    else:
                        view = feed_.unwatched_items
                    views.append(view)
                    item_urls[url] = set(i.url for i in view)

        # Iterate through synced playlist
        if sync.setdefault(u'playlists', {}).get(u'enabled', False):
            for name in sync[u'playlists'].setdefault(u'items', []):
                try:
                    playlist_ = playlist.SavedPlaylist.get_by_title(name)
                except database.ObjectNotFoundError:
                    continue
                views.append(item.Item.playlist_view(playlist_.id))


        # For each podcast/playlist view, check if there are new items.
        for view in views:
            item_infos = app.db.fetch_item_infos(view.id_list())
            infos.update(info for info in item_infos
                         if not self._item_exists(info))

        # check for expired items
        if sync[u'podcasts'].get(u'expire', True):
            for device_item in item.DeviceItem.make_view(
                db_info=self.device.db_info):
                if (device_item.feed_url in item_urls and
                    device_item.url not in item_urls[device_item.feed_url]):
                    expired.add(device_item)

        # check if our size will overflow max_size.  If so, remove items from
        # infos until they will fit
        if max_size is not None and infos:
            for info in expired:
                max_size += sum(i.size for i in expired)
            sync_size = self.get_sync_size(infos)[1]
            if sync_size > max_size:
                sizes_and_items = [
                    (self.get_sync_size([i])[1], i) for i in infos]
                for i in self.yield_items_to_get_to(sync_size - max_size,
                                                       sizes_and_items):
                    sync_size -= i.size
                    infos.remove(i)
        return infos, expired

    def get_auto_items(self, size):
        """
        Returns a list of ItemInfos to be automatically synced to the device.
        The items should be roughly 'size' bytes.
        """
        sync = self.device.database.get(u'sync', {})
        if not sync.get(u'auto_fill', False):
            return set()

        name_to_view = {
            u'recent_music': item.Item.watchable_audio_view(),
            u'random_music': item.Item.watchable_audio_view(),
            u'most_played_music': item.Item.watchable_audio_view(),
            u'new_playlists': playlist.SavedPlaylist.make_view(),
            u'recent_podcasts': item.Item.toplevel_view()
            }

        name_to_view[u'recent_music'].order_by = 'item.id DESC'
        name_to_view[u'random_music'].order_by = 'RANDOM()'
        name_to_view[u'most_played_music'].order_by = 'item.play_count DESC'
        name_to_view[u'new_playlists'].order_by = 'playlist.id DESC'
        name_to_view[u'recent_podcasts'].where = (
            '%s AND item.filename IS NOT NULL' % (
                name_to_view[u'recent_podcasts'].where,))
        name_to_view[u'recent_podcasts'].order_by = 'item.id DESC'

        scores = sync.get(u'auto_fill_settings', {})
        total = float(sum(scores.setdefault(name, 0.5)
                          for name in name_to_view))

        sizes = dict((name, int(size * scores[name] / total))
                     for name in name_to_view)

        auto_syncs = {}
        for name, view in name_to_view.items():
            auto_syncs[name] = syncs = set()
            remaining = sizes[name]
            if name == u'new_playlists':
                for playlist_ in view:
                    # FIXME: need to make sure this works now that ItemInfo
                    # has changed a bit
                    playlist_view = item.Item.playlist_view(playlist_.id)
                    playlist_ids = [i.id for i in playlist_view]
                    infos = app.db.fetch_item_infos(playlist_ids)
                    size = self.get_sync_size(infos)[1]
                    if size and size <= remaining:
                        syncs.update(infos)
                        remaining -= size
            else:
                # FIXME: need to make sure this works now that ItemInfo
                # has changed a bit
                for info in app.db.fetch_item_infos(i.id for i in view):
                    size = self.get_sync_size([info])[1]
                    if size and size <= remaining:
                        syncs.add(info)
                        remaining -= size

        return set().union(*auto_syncs.values())

    def get_sync_size(self, items, expired=None):
        """
        Returns the number of items that will be synced, and the size that sync
        will take.

        The count includes items that will be removed, but their size counts
        against the total sync size.
        """
        if not items and not expired:
            return 0, 0
        count = size = 0
        items_for_converter = {}
        for info in items:
            converter = self.conversion_for_info(info)
            if converter is not None:
                items_for_converter.setdefault(converter, set()).add(info)
        if 'copy' in items_for_converter:
            items = items_for_converter.pop('copy')
            count += len(items)
            size += sum(info.size for info in items)
        for converter, items in items_for_converter.items():
            for info in items:
                task = conversions.conversion_manager._make_conversion_task(
                    converter, info,
                    target_folder=None,
                    create_item=False)
                if task:
                    count += 1
                    size += task.get_output_size_guess()
        if expired:
            count += len(expired)
            size -= sum(i.size for i in expired)
        return count, size

    def max_sync_size(self, include_auto=True):
        """
        Returns the largest sync (in bytes) that we can perform on this device.
        """
        if not self.device.mount:
            return 0
        sync = self.device.database.get(u'sync', {})
        if include_auto:
            auto_fill_size = self._calc_auto_fill_size()
        else:
            auto_fill_size = 0
        if not sync.get(u'max_fill', False):
            return self.device.remaining + auto_fill_size
        else:
            try:
                percent = int(sync.get(u'max_fill_percent', 90)) * 0.01
            except ValueError:
                return self.device.remaining + auto_fill_size
            else:
                min_remaining = self.device.size * (1 - percent)
                return self.device.remaining - min_remaining + auto_fill_size

    def _calc_auto_fill_size(self):
        """
        Returns the total size of auto-filled files.
        """
        sync = self.device.database.get(u'sync')
        if not sync:
            return 0
        if not sync.get(u'auto_fill', False):
            return 0
        return sum(i.size for i in 
                   item.DeviceItem.auto_sync_view(self.device.db_info))

    def start(self):
        if self.started:
            return
        self.started = True
        self.audio_target_folder = os.path.join(
            self.device.mount,
            self._get_path_from_setting('audio_path'))
        if not os.path.exists(self.audio_target_folder):
            os.makedirs(self.audio_target_folder)

        self.video_target_folder = os.path.join(
            self.device.mount,
            self._get_path_from_setting('video_path'))
        if not os.path.exists(self.video_target_folder):
            os.makedirs(self.video_target_folder)

        self.device.is_updating = True # start the spinner
        messages.TabsChanged('connect', [], [self.device],
                             []).send_to_frontend()

    def _get_path_from_setting(self, setting):
        device_settings = self.device.database.setdefault(u'settings', {})
        device_path = device_settings.get(setting)
        if device_path is None:
            return getattr(self.device.info, setting)
        else:
            return unicode_to_path(device_path)

    def set_device(self, device):
        self.device = device

    def expire_items(self, item_infos):
        for info in item_infos:
            try:
                device_item = item.DeviceItem.get_by_id(
                    info.id, db_info=self.device.db_info)
            except database.ObjectNotFoundError:
                logging.warn("expire_items: Got ObjectNotFoundError for %s",
                             info.id)
            else:
                self._expire_item(device_item)
        self._check_finished()

    def _item_exists(self, item_info):
        return item.DeviceItem.item_exists(item_info,
                                           db_info=self.device.db_info)

    @staticmethod
    def yield_items_to_get_to(size, sizes_and_items):
        """
        This algorithm lets us filter a set of items to get to a given size.
        ``size`` is the total size we're trying to get below.
        ``sizes_and_items`` is a list of (size, item) tuples.  This function
        yields the items that need to be removed.

        The algorithm we use is:
        * Sort all the auto items by their size
        * While we need more space:
            * bisect the sorted sizes with the size we've got left
            * If there's an exact match, remove it and we're done
            * Otherwise, remove the item around the insertion point which is
              closest and try again with the new remaining size
        """
        sizes_and_items.sort()
        keys = [i[0] for i in sizes_and_items]
        def remove_(index):
            keys.pop(index)
            return sizes_and_items.pop(index)

        while size >= 0 and keys:
            left = bisect.bisect_left(keys, size)
            if left == size: # perfect fit!
                s, i = remove_(left)
                yield i
                break
            right = bisect.bisect_right(keys, size)
            if left == right == len(keys):
                s, i = remove_(len(keys) - 1)
                size -= s
                yield i
                continue
            if (abs(left - size) < abs(right - size)): # left is closer
                s, i = remove_(left)
                size -= s
                yield i
            else:
                s, i = remove_(right)
                size -= s
                yield i
        
    def expire_auto_items(self, size):
        """
        Expires automatically synced items.
        """
        sizes_and_items = [(i.size, i) for i in
                           item.DeviceItem.auto_sync_view(self.device.db_info)]
        for size, device_item in self.yield_items_to_get_to(size,
                                                            sizes_and_items):
            self._expire_item(device_item)

    def _expire_item(self, device_item):
        device_item.delete_and_remove(self.device)
        self.device.remaining += device_item.size

    def add_items(self, item_infos, auto_sync=False):
        for info in item_infos:
            if self.stopping:
                self._check_finished()
                return
            if self._item_exists(info):
                continue # don't recopy stuff
            conversion = self.conversion_for_info(info)
            if not conversion:
                continue
            if info.file_type == 'audio':
                target_folder = self.audio_target_folder
            elif info.file_type == 'video':
                target_folder = self.video_target_folder
            else:
                continue
            if auto_sync:
                self.auto_syncs.add(info.id)
            self.total += 1
            if conversion == 'copy':
                final_path = os.path.join(target_folder,
                                          os.path.basename(
                        info.filename))
                if os.path.exists(final_path):
                    logging.debug('%r exists, getting a new one precopy',
                                  final_path)
                    try:
                        final_path, fp = next_free_filename(final_path)
                        # XXX we should be passing in the file handle not
                        # path.
                        fp.close()
                    except ValueError:
                        logging.warn('add_items: next_free_filename failed. '
                                     'candidate = %r', final_path)
                        continue
                self.copy_file(info, final_path)
            else:
                self.start_conversion(conversion,
                                      info,
                                      target_folder)

        self._check_finished()


    def cache_conversion(meth):
        def wrapper(self, info):
            if info not in self._info_to_conversion:
                self._info_to_conversion[info] = meth(self, info)
            return self._info_to_conversion[info]
        return wrapper

    @cache_conversion
    def conversion_for_info(self, info):
        if not info.filename:
            app.controller.failed_soft("device conversion",
                                       "got video %r without filename" % (
                    info.title,))
            return None

        if info.file_type not in ('audio', 'video'):
            logging.debug("got item %r that's not audio or video", info.title)
            return None

        # shortcut, if we're just going to copy the file
        if self.device_settings.get(
            u'%s_conversion' % info.file_type,
            getattr(self.device_info,
                    '%s_conversion' % info.file_type)) == u'copy':
            return 'copy'

        try:
            media_info = conversions.get_media_info(info.filename)
        except ValueError:
            logging.exception('error getting media info for %r',
                              info.filename)
            return 'copy'
        
        requires_conversion = False
        def ensure_set(v):
            if isinstance(v, basestring):
                return set([v])
            else:
                return set(v)
        if 'container' in media_info:
            info_containers = ensure_set(media_info['container'])
            if not (self.device_info.container_types & info_containers):
                requires_conversion = True # container doesn't match
        else:
            requires_conversion = True
        if 'audio_codec' in media_info:
            info_audio_codecs = ensure_set(media_info['audio_codec'])
            if not (self.device_info.audio_types & info_audio_codecs):
                requires_conversion = True # audio codec doesn't match
        else:
            requires_conversion = True
        if info.file_type == 'video':
            if (self.device_settings.get(u'always_sync_videos') or
                'video_codec' not in media_info):
                requires_conversion = True
            else:
                info_video_codecs = ensure_set(media_info['video_codec'])
                if not (self.device_info.video_types & info_video_codecs):
                    requires_conversion = True # video codec doesn't match
        if not requires_conversion:
            return 'copy' # so easy!
        elif info.file_type == 'audio':
            return (self.device_settings.get(u'audio_conversion') or
                    self.device_info.audio_conversion)
        elif info.file_type == 'video':
            return (self.device_settings.get(u'video_conversion') or
                    self.device_info.video_conversion)

    def start_conversion(self, conversion, info, target):
        conversion_manager = conversions.conversion_manager
        start_conversion = conversion_manager.start_conversion

        if not self.signal_handles:
            for signal, callback in (
                ('task-changed', self._conversion_changed_callback),
                ('task-staged', self._conversion_staged_callback),
                ('task-failed', self._conversion_removed_callback),
                ('task-removed', self._conversion_removed_callback),
                ('all-tasks-removed', self._conversion_removed_callback)):
                self.signal_handles.append(conversion_manager.connect(
                        signal, callback))

        task = start_conversion(conversion, info, target,
                                create_item=False)
        self.total_size[task.key] = (task.get_output_size_guess() *
                                     CONVERSION_SCALE)
        self.waiting.add(task.key)

    def copy_file(self, info, final_path):
        if (info, final_path) in self.copying:
            logging.warn('tried to copy %r twice', info)
            return
        file(final_path, 'w').close() # create the file so that future tries
                                      # will see it
        self.copying[final_path] = info
        self.total_size[info.id] = info.size
        if not self._copy_iter_running:
            self._copy_iter_running = True
            eventloop.idle_iterate(self._copy_as_iter,
                                   'copying files to device')

    def _copy_as_iter(self):
        while self.copying:
            final_path, info = self.copying.popitem()
            iterable = fileutil.copy_with_progress(info.filename, final_path,
                                                   block_size=128 * 1024)
            try:
                for count in iterable:
                    self.progress_size[info.id] += count
                    if self.stopping:
                        iterable.close()
                        eventloop.add_idle(fileutil.delete,
                                           "deleting canceled sync",
                                           args=(final_path,))
                        final_path = None
                        break
                    # let other stuff run
                    self._schedule_sync_changed()
                    yield
            except IOError:
                final_path = None
            if final_path:
                self._add_item(final_path, info)
            # don't throw off the progress bar; we're done so pretend we got
            # all the bytes
            self.progress_size[info.id] = self.total_size[info.id]
            self.finished += 1
            self._check_finished()
            if self.stopping:
                break # no more copies
            yield
        for final_path in self.copying:
            # canceled the sync, so remove the non-synced files
            eventloop.add_idle(fileutil.delete,
                               "deleting canceled sync",
                               args=(final_path,))
        self._copy_iter_running = False

    def _conversion_changed_callback(self, conversion_manager, task):
        total = self.total_size[task.key]
        self.progress_size[task.key] = task.progress * total
        self._schedule_sync_changed()

    def _conversion_removed_callback(self, conversion_manager, task=None):
        if task is not None:
            self.finished += 1
            try:
                self.waiting.remove(task.key)
                # don't throw off the progress bar; we're done so pretend we
                # got all the bytes
                self.progress_size[task.key] = self.total_size[task.key]
            except KeyError:
                pass
        else: # remove all tasks
            self.finished += len(self.waiting)
            for key in self.waiting:
                self.progress_size[key] = self.total_size[key]
            self.waiting = set()
        self._check_finished()

    def _conversion_staged_callback(self, conversion_manager, task):
        self.finished += 1
        try:
            self.waiting.remove(task.key)
            # don't throw off the progress bar; we're done so pretend we got
            # all the bytes
            self.progress_size[task.key] = self.total_size[task.key]
        except KeyError:
            pass # missing for some reason
        else:
            if not task.error: # successful!
                self._add_item(task.final_output_path, task.item_info)
        self._check_finished()

    @eventloop.as_idle
    def _add_item(self, final_path, item_info):
        dirname, basename = os.path.split(final_path)
        _, extension = os.path.splitext(basename)
        new_basename = "%s%s" % (unicode_to_filename(item_info.title,
                                                     self.device.mount),
                                 extension)
        new_path = os.path.join(dirname, new_basename)
        if os.path.exists(new_path):
            logging.debug('final destination %r exists, making a new one',
                          new_path)
            new_path, fp = next_free_filename(new_path)

        def callback():
            if not os.path.exists(new_path):
                return # copy failed, just give up
            if _device_not_valid(self.device):
                return # Device has been ejected, give up.

            relpath = os.path.relpath(new_path, self.device.mount)
            auto_sync = item_info.id in self.auto_syncs
            device_item = item.DeviceItem(self.device, relpath, item_info,
                                          auto_sync=auto_sync)
            self.device.remaining -= device_item.size

        fileutil.migrate_file(final_path, new_path, callback)

    def _check_finished(self):
        if not self.waiting and not self.copying:
            # finished!
            if not self.stopping:
                self._send_sync_finished()
        self._schedule_sync_changed()

    def _schedule_sync_changed(self):
        if not self._change_timeout:
            self._change_timeout = eventloop.add_timeout(
                1.0,
                self._send_sync_changed,
                'sync changed update')

    def _send_sync_changed(self):
        message = messages.DeviceSyncChanged(self)
        message.send_to_frontend()
        self._change_timeout = None

    def _send_sync_finished(self):
        for handle in self.signal_handles:
            conversions.conversion_manager.disconnect(handle)
        self.signal_handles = []
        self.device.is_updating = False # stop the spinner
        messages.TabsChanged('connect', [], [self.device],
                             []).send_to_frontend()
        del app.device_manager.syncs_in_progress[self.device.id]


    def is_finished(self):
        if self.stopping or not self.started:
            return True
        if self.waiting or self.copying:
            return False
        return self.device.id not in app.device_manager.syncs_in_progress

    def get_eta(self):
        progress = self.get_progress() * 100
        if not progress:
            return None
        
        duration = time.time() - self.start_time
        time_per_percent = duration / progress
        return int(time_per_percent * (100 - progress))

    def get_progress(self):
        total = sum(self.total_size.itervalues())
        if not total:
            return 0.0
        progress = float(sum(self.progress_size.itervalues()))
        return min(progress / total, 1.0)

    def cancel(self):
        if not self.started:
            return
        for key in self.waiting:
            conversions.conversion_manager.cancel(key)
        self.stopping = True # kill in-progress copies
        self._send_sync_changed()
        self._send_sync_finished()

class DeviceDatabase(dict, signals.SignalEmitter):
    def __init__(self, data=None, parent=None):
        if data:
            dict.__init__(self, data)
            self.created_new = False
        else:
            dict.__init__(self)
            self.created_new = True
        signals.SignalEmitter.__init__(self, 'changed', 'item-added',
                                       'item-changed', 'item-removed')
        self.parent = parent
        self.changing = False
        self.bulk_mode = False
        self.did_change = False
        self.check_old_key_usage = False
        self.write_manager = None

    def __getitem__(self, key):
        check_u(key)
        if self.check_old_key_usage:
            if key in (u'audio', u'video', u'other'):
                raise AssertionError()
        value = super(DeviceDatabase, self).__getitem__(key)
        if isinstance(value, dict) and not isinstance(value, DeviceDatabase):
            value = DeviceDatabase(value, self.parent or self)
             # don't trip the changed signal
            super(DeviceDatabase, self).__setitem__(key, value)
        return value

    def __setitem__(self, key, value):
        check_u(key)
        super(DeviceDatabase, self).__setitem__(key, value)
        if self.parent:
            self.parent.notify_changed()
        else:
            self.notify_changed()

    def notify_changed(self):
        self.did_change = True
        if not self.bulk_mode and not self.changing:
            self.changing = True
            try:
                self.emit('changed')
                if self.write_manager:
                    self.write_manager.schedule_write(self)
            finally:
                self.changing = False
                self.did_change = False

    def set_bulk_mode(self, bulk):
        self.bulk_mode = bulk
        if not bulk and self.did_change:
            self.notify_changed()

    def _find_item_data(self, path):
        """Find the data for an item in the database

        Returns (item_data, file_type) tuple
        """

        for file_type in (u'audio', u'video', u'other'):
            if file_type in self and path in self[file_type]:
                return (self[file_type][path], file_type)
        raise KeyError(path)

    def shutdown(self):
        if self.write_manager and self.write_manager.is_dirty():
            self.write_manager.write()

class DatabaseWriteManager(object):
    """
    Keeps track of writing a database periodically.
    """
    SAVE_INTERVAL = 10 # seconds between writes

    def __init__(self, mount):
        self.mount = mount
        self.scheduled_write = None
        self.database = None

    def schedule_write(self, database):
        self.database = database
        if self.is_dirty():
            return
        self.scheduled_write = eventloop.add_timeout(self.SAVE_INTERVAL,
                                                     self.write,
                                                     'writing device database')

    def is_dirty(self):
        return self.scheduled_write is not None

    def write(self):
        if self.is_dirty():
            write_database(self.database, self.mount)
            self.database = self.scheduled_write = None

def load_database(mount, countdown=0):
    """
    Returns a dictionary of the JSON database that lives on the given device.

    The database lives at [MOUNT]/.miro/json
    """
    file_name = os.path.join(mount, '.miro', 'json')
    if not os.path.exists(file_name):
        db = {}
    else:
        try:
            fp = codecs.open(file_name, 'rb', 'utf8')
            db = json.load(fp)
        except ValueError:
            logging.exception('JSON decode error on %s', mount)
            db = {}
        except EnvironmentError:
            if countdown == 5:
                logging.exception('file error with JSON on %s', mount)
                db = {}
            else:
                # wait a little while; total time is ~1.5s
                time.sleep(0.20 * 1.2 ** countdown)
                return load_database(mount, countdown + 1)
    ddb = DeviceDatabase(db)
    ddb.write_manager = DatabaseWriteManager(mount)
    return ddb

def sqlite_database_path(mount):
    return os.path.join(mount, '.miro', 'sqlite')

def load_sqlite_database(mount, device_size, countdown=0, is_hidden=False):
    """
    Returns a LiveStorage object for an sqlite database on the device

    The database lives at [MOUNT]/.miro/sqlite
    """
    threadcheck.confirm_eventloop_thread()
    if mount == ':memory:': # special case for the unittests
        path = ':memory:'
        preallocate = None
        start_in_temp_mode = False
    else:
        directory = os.path.join(mount, '.miro')
        start_in_temp_mode = False
        if is_hidden and not os.path.exists(directory):
            # don't write to the disk initially.  This works because we set
            # `force_directory_creation` to False further down, which prevents
            # LiveStorage from creating the .miro directory itself
            start_in_temp_mode = True
        path = os.path.join(directory, 'sqlite')
        preallocate = calc_sqlite_preallocate_size(device_size)
    logging.info('loading SQLite db on device %r: %r', mount, path)
    error_handler = storedatabase.DeviceLiveStorageErrorHandler(mount)
    try:
        live_storage = storedatabase.DeviceLiveStorage(
            path, error_handler,
            preallocate=preallocate,
            object_schemas=schema.device_object_schemas,
            schema_version=DB_VERSION,
            start_in_temp_mode=start_in_temp_mode)
    except EnvironmentError:
        if countdown == 5:
            logging.exception('file error with JSON on %s', mount)
            return load_sqlite_database(':memory:', 0, countdown)
        else:
            # wait a little while; total time is ~1.5s
            time.sleep(0.20 * 1.2 ** countdown)
            return load_sqlite_database(mount, device_size, countdown + 1)
    if live_storage.created_new:
        # force the version to match the current schema.  This is a hack to
        # make databases from the nightlies match the ones from users starting
        # with 5.0
        live_storage.set_version(DB_VERSION)
        if start_in_temp_mode:
            # We won't create an SQLite database until something else writes to
            # the .miro directory on the device.
            live_storage.force_directory_creation = False
    else:
        device_db_version = live_storage.get_version()
        if device_db_version < DB_VERSION:
            logging.info("upgrading device database: %r", mount)
            live_storage.upgrade_database(context='device')
        elif device_db_version > DB_VERSION:
            # Newer versions of miro should store their device databases in a
            # way that's compatible with previous ones.  We just have to hope
            # that's true in this case.
            logging.warn("database from newer miro version: %r (version=%s)",
                         mount, device_db_version)

    return live_storage

def calc_sqlite_preallocate_size(device_size):
    """Calculate the size we should preallocate for our sqlite database.  """
    # Estimate that the device can store 1 item per megabyte and each item
    # takes 400 bytes in the database.
    max_items_estimate = device_size / (2 ** 20)
    size = max_items_estimate * 400
    # force the size to be between 512K and 10M
    size = max(size, 512 * (2 ** 10))
    size = min(size, 10 * (2 ** 20))
    return size

def make_metadata_manager(mount, db_info, device_id):
    """
    Get a MetadataManager for a device.
    """
    manager = metadata.DeviceMetadataManager(db_info, device_id, mount)
    manager.connect("new-metadata", on_new_metadata, device_id)
    return manager

def on_new_metadata(metadata_manager, new_metadata, device_id):
    try:
        device = app.device_manager.connected[device_id]
    except KeyError:
        # bz18893: don't crash if the device isn't around any more.
        logging.warn("devices.py - on_new_metadata: KeyError getting %r",
                     device_id)
        return

    path_map = item.DeviceItem.items_for_paths(new_metadata.keys(),
                                               device.db_info)
    device.db_info.bulk_sql_manager.start()
    try:
        for path, metadata in new_metadata.iteritems():
            try:
                device_item = path_map[path.lower()]
            except KeyError:
                logging.warn("devices.py - on_new_metadata: Got metadata "
                             "but can't find item for %r", path)
            else:
                device_item.update_from_metadata(metadata)
                device_item.signal_change()
    finally:
        device.db_info.bulk_sql_manager.finish()

def write_database(db, mount):
    """
    Writes the given dictionary to the device.

    The database lives at [MOUNT]/.miro/json
    """
    threadcheck.confirm_eventloop_thread()
    if not os.path.exists(mount):
        # device disappeared, so we can't write to it
        return
    try:
        fileutil.makedirs(os.path.join(mount, '.miro'))
    except OSError:
        pass
    try:
        with file(os.path.join(mount, '.miro', 'json'), 'wb') as output:
            iterable = json._default_encoder.iterencode(db)
            output.writelines(iterable)
    except IOError:
        # couldn't write to the device
        # XXX throw up an error?
        pass

def clean_database(device):
    """Go through a device and remove any items that have been deleted.

    :returns: list of paths that are still valid
    """
    metadata.remove_invalid_device_metadata(device)

    known_files = set()
    to_remove = []
    # Use select_paths() since it avoids constructing DeviceItem objects
    for row in item.DeviceItem.select_paths(device.db_info):
        relpath = row[0]
        full_path = os.path.join(device.mount, relpath)
        if os.path.exists(full_path):
            known_files.add(relpath.lower())
        else:
            to_remove.append(relpath)

    if to_remove:
        device.db_info.bulk_sql_manager.start()
        try:
            for relpath in to_remove:
                device_item = item.DeviceItem.get_by_path(relpath,
                                                          device.db_info)
                device_item.remove(device)
        finally:
            device.db_info.bulk_sql_manager.finish()

    return known_files

def on_mount(info):
    """Stuff that we need to do when the device is first mounted.
    """
    if info.database.get(u'sync', {}).get(u'auto', False):
        message = messages.DeviceSyncFeeds(info)
        message.send_to_backend()
    scan_device_for_files(info)

def _device_not_valid(device):
    if not app.device_manager.running: # user quit, so we will too
        logging.debug('stopping scan on %r: user quit', device.mount)
        return True
    if device.metadata_manager is None or device.metadata_manager.closed: # device was ejected
        return True
    if not os.path.exists(device.mount): # device disappeared
        logging.debug('stopping scan on %r: disappeared', device.mount)
        return True
    if app.device_manager._is_hidden(device): # device no longer being
                                              # shown
        logging.debug('stopping scan on %r: hidden', device.mount)
        return True
    return False

@eventloop.idle_iterator
def scan_device_for_files(device):
    # XXX is this as_idle() safe?

    # prepare paths to add
    if device.read_only:
        logging.debug('skipping scan on read-only device %r', device.mount)
        return
    logging.debug('starting scan on %r', device.mount)
    known_files = clean_database(device)
    found_files = []
    start = time.time()

    for path in fileutil.miro_allfiles(device.mount):
        relpath = os.path.relpath(path, device.mount)
        if ((filetypes.is_video_filename(path) or
            filetypes.is_audio_filename(path)) and
            relpath.lower() not in known_files):
            found_files.append(relpath)
        if time.time() - start > 0.3:
            yield # let other stuff run
            if _device_not_valid(device):
                break
            start = time.time()

    yield # yield after prep work
    if _device_not_valid(device):
        return

    device.database.setdefault(u'sync', {})
    logging.debug('scanned %r, found %i files (%i total)',
                  device.mount, len(found_files),
                  len(known_files) + len(found_files))

    found_files_iter = iter(found_files)
    while not _create_items_for_files(device, found_files_iter, 0.4):
        # _create_items_for_files hit our timeout.  let other idle
        # functions run for a bit
        yield
        if _device_not_valid(device):
            break

def _create_items_for_files(device, path_iter, timeout):
    """Create a batch of DeviceItems

    :param device: DeviceInfo to create the items for
    :param path_iter: iterator that yields paths to create (must be relative
    to the device mount)
    :param timeout: stop after this many seconds
    :returns: True if we exausted the iterator, False if we stopped because we
    hit the timeout
    """
    start = time.time()
    device.db_info.bulk_sql_manager.start()
    try:
        while time.time() - start < 0.4:
            try:
                path = path_iter.next()
            except StopIteration:
                # path_iter has been exhausted, return True
                return True
            try:
                item.DeviceItem(device, path)
            except StandardError:
                logging.exception("Error adding DeviceItem: %r", path)
        # we timed out, return False
        return False
    finally:
        device.db_info.bulk_sql_manager.finish()
