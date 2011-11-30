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
try:
    from collections import Counter
except ImportError:
    from collections import defaultdict
    class Counter(defaultdict):
        def __init__(self, *args, **kwargs):
            super(Counter, self).__init__(int, *args, **kwargs)

from miro import app
from miro import database
from miro import eventloop
from miro import item
from miro import itemsource
from miro import feed
from miro import fileutil
from miro import filetypes
from miro import prefs
from miro import playlist
from miro.gtcache import gettext as _
from miro import messages
from miro import signals
from miro import conversions
from miro.util import check_u

from miro.download_utils import next_free_filename

from miro.plat import resources
from miro.plat.utils import (filename_to_unicode, unicode_to_filename,
                             utf8_to_filename)


# how much slower converting a file is, compared to copying
CONVERSION_SCALE = 500

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
            getattr(self, "vendor_id", 0),
            getattr(self, "product_id", 0))

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
                    self.device_by_id[key] = self.merge(existing, info)

    def remove_device(self, info):
        # FIXME - need this
        pass

    def startup(self):
        # load devices
        self.load_devices(resources.path('devices/*.py'))
        self.running = True

    def shutdown(self):
        self.running = False
        for device in self.connected.values():
            if device.mount and not self._is_hidden(device):
                write_database(device.database, device.mount)

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
                           if self._is_unknown(info)]
        if show: # now we're showing them
            for info in unknown_devices:
                self._send_connect(info)
        else: # now we're hiding them
            for info in unknown_devices:
                self._send_disconnect(info)
        self.show_unknown = show
        app.config.set(prefs.SHOW_UNKNOWN_DEVICES, show)

    @staticmethod
    def _is_unknown(info):
        if not getattr(info.info, 'generic', False):
            # not a generic device
            return False
        if info.mount and info.database.get(u'settings', {}).get(
            'always_show', False):
            # we want to show this device all the time
            return False
        return True

    def _is_hidden(self, info):
        # like _is_unknown(), but takes the self.show_unknown flag into account
        if self.show_unknown:
            return False
        else:
            return self._is_unknown(info)

    def _set_connected(self, id_, kwargs):
        if kwargs.get('mount'):
            db = load_database(kwargs['mount'])
            device_name = db.get(u'device_name',
                                       kwargs.get('device_name'))
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

        info = self.connected[id_] = messages.DeviceInfo(
            id_, info, kwargs.get('mount'), db,
            kwargs.get('size'), kwargs.get('remaining'))

        return info

    def device_connected(self, id_, **kwargs):
        if id_ in self.connected:
            # backend got confused
            self.device_changed(id_, **kwargs)
            return

        info = self._set_connected(id_, kwargs)

        if not self._is_hidden(info):
            self._send_connect(info)
        else:
            logging.debug('ignoring %r', info)

    def _send_connect(self, info):
        if info.mount:
            self.info_cache.setdefault(info.mount, {})
            on_mount(info)
        messages.TabsChanged('connect', [info], [], []).send_to_frontend()

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

        if self._is_hidden(info):
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

    def device_disconnected(self, id_):
        if id_ not in self.connected:
            return # don't bother with sending messages

        info = self.connected.pop(id_)
        if not self._is_hidden(info):
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
        self.stopping = False
        self._change_timeout = None
        self._copy_iter_running = False
        self._info_to_conversion = {}
        self.started = False

    def get_sync_items(self, max_size=None):
        """
        Returns two lists of ItemInfos; one for items we need to sync, and one
        for items which have expired.
        """
        sync = self.device.database[u'sync']
        views = []
        url_to_view = {}
        infos = set()
        expired = set()
        sync_all_podcasts = sync[u'podcasts'].get(u'all', True)
        if sync.setdefault(u'podcasts', {}).get(u'enabled', False):
            for url in sync[u'podcasts'].setdefault(u'items', []):
                feed_ = feed.lookup_feed(url)
                if feed_ is not None:
                    if sync_all_podcasts:
                        view = feed_.downloaded_items
                    else:
                        view = feed_.unwatched_items
                    views.append(view)
                    url_to_view[url] = view

        if sync.setdefault(u'playlists', {}).get(u'enabled', False):
            for name in sync[u'playlists'].setdefault(u'items', []):
                try:
                    playlist_ = playlist.SavedPlaylist.get_by_title(name)
                except database.ObjectNotFoundError:
                    continue
                views.append(item.Item.playlist_view(playlist_.id))

        for view in views:
            source = itemsource.DatabaseItemSource(view)
            try:
                infos.update(
                    [info for info in source.fetch_all()
                     if not self.device.database.item_exists(info)])
            finally:
                source.unlink()

        # check for expired items
        if sync[u'podcasts'].get(u'expire', True):
            for file_type in (u'audio', u'video'):
                for info in itemsource.DeviceItemSource(self.device,
                                                        file_type).fetch_all():
                    if (info.feed_url and info.file_url and
                        info.feed_url in url_to_view):
                        view = url_to_view[info.feed_url]
                        new_view = database.View(
                            view.fetcher,
                            view.where + (' AND (rd.origURL=? OR rd.url=? '
                                          'OR item.url=?)'),
                            view.values + (info.file_url, info.file_url,
                                           info.file_url),
                            view.order_by,
                            view.joins,
                            view.limit)
                        if not new_view.count():
                            expired.add(info)
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
        sync = self.device.database[u'sync']
        if not sync.get(u'auto_fill', False):
            return []

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
            '%s AND item.filename NOT IN (NULL, "")' % (
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
                    playlist_view = item.Item.playlist_view(playlist_.id)
                    infos = itemsource.DatabaseItemSource(
                        playlist_view).fetch_all()
                    size = self.get_sync_size(infos)[1]
                    if size and size < remaining:
                        for info in infos:
                            info.auto_sync = True
                        syncs.update(infos)
                        remaining -= size
            else:
                source = itemsource.DatabaseItemSource(view)
                for info in source.fetch_all():
                    size = self.get_sync_size([info])[1]
                    if size and size < remaining:
                        info.auto_sync = True
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
            del self.device.database[info.file_type][info.id]
            fileutil.delete(info.video_path)
            self.device.remaining += info.size
        self._check_finished()

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
        sizes = [(data[u'size'], (file_type, id_))
                 for file_type in u'audio', u'video'
                 for id_, data in self.device.database[file_type].items()
                 if data.get(u'auto_sync', False)]
        for (file_type, id_) in self.yield_items_to_get_to(size, sizes):
            data = self.device.database[file_type].pop(id_)
            fileutil.delete(os.path.join(self.device.mount,
                                         utf8_to_filename(
                        id_.encode('utf8'))))
            self.device.remaining += data[u'size']

    def add_items(self, item_infos):
        for info in item_infos:
            if self.stopping:
                self._check_finished()
                return
            if self.device.database.item_exists(info):
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
            self.total += 1
            if conversion == 'copy':
                final_path = os.path.join(target_folder,
                                          os.path.basename(
                        info.video_path))
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
        if not info.video_path:
            app.controller.failed_soft("device conversion",
                                       "got video %r without video_path" % (
                    info.name,))
            return None

        if info.file_type not in ('audio', 'video'):
            logging.debug("got item %r that's not audio or video", info.name)
            return None

        # shortcut, if we're just going to copy the file
        if self.device_settings.get(
            u'%s_conversion' % info.file_type,
            getattr(self.device_info,
                    '%s_conversion' % info.file_type)) == u'copy':
            return 'copy'

        try:
            media_info = conversions.get_media_info(info.video_path)
        except ValueError:
            logging.exception('error getting media info for %r',
                              info.video_path)
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
            iterable = fileutil.copy_with_progress(info.video_path, final_path,
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
        new_basename = "%s%s" % (unicode_to_filename(item_info.name,
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

            device_item = item.DeviceItem(
                device=self.device,
                file_type=item_info.file_type,
                video_path=new_path[len(self.device.mount):],
                title=item_info.name,
                feed_name=item_info.feed_name,
                feed_url=item_info.feed_url,
                description=item_info.description,
                release_date=time.mktime(item_info.release_date.timetuple()),
                duration=(item_info.duration and item_info.duration * 1000 or
                          None),
                permalink=item_info.permalink,
                commentslink=item_info.commentslink,
                payment_link=item_info.payment_link,
                screenshot=item_info.thumbnail,
                thumbnail_url=item_info.thumbnail_url,
                file_format=item_info.file_format,
                license=item_info.license,
                url=item_info.file_url,
                media_type_checked=item_info.media_type_checked,
                mime_type=item_info.mime_type,
                creation_time=time.mktime(item_info.date_added.timetuple()),
                title_tag=item_info.title_tag,
                artist=item_info.artist,
                album=item_info.album,
                track=item_info.track,
                year=item_info.year,
                genre=item_info.genre,
                metadata_version=item_info.metadata_version,
                mdp_state=item_info.mdp_state,
                auto_sync=getattr(item_info, 'auto_sync', False)
                )
            device_item._migrate_thumbnail()
            database = self.device.database
            database.setdefault(device_item.file_type, {})
            database[device_item.file_type][device_item.id] = \
                device_item.to_dict()
            database.emit('item-added', device_item)
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
        else:
            dict.__init__(self)
        signals.SignalEmitter.__init__(self, 'changed', 'item-added',
                                       'item-changed', 'item-removed')
        self.parent = parent
        self.changing = False
        self.bulk_mode = False
        self.did_change = False

    def __getitem__(self, key):
        check_u(key)
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
            finally:
                self.changing = False
                self.did_change = False

    def set_bulk_mode(self, bulk):
        self.bulk_mode = bulk
        if not bulk and self.did_change:
            self.notify_changed()

    # XXX does this belong here?
    def item_exists(self, item_info):
        """Checks if the given ItemInfo exists in our database.  Should only be
        called on the parent database.
        """
        if self.parent:
            raise RuntimeError('item_exists() called on sub-dictionary')
        if item_info.file_type not in self:
            return False
        for existing in self[item_info.file_type].values():
            if (item_info.file_url and
                existing.get('url') == item_info.file_url):
                return True
            if ((item_info.name, item_info.description, item_info.size,
                 item_info.duration * 1000 if item_info.duration
                 else None) ==
                  (existing.get('title'), existing.get('description'),
                   existing.get('size'), existing.get('duration'))):
                # if a bunch of qualities are the same, we'll call it close
                # enough
                return True
        return False

class DatabaseWriteManager(object):
    """
    Keeps track of writing a database periodically.
    """
    SAVE_INTERVAL = 10 # seconds between writes

    def __init__(self, mount):
        self.mount = mount
        self.scheduled_write = None
        self.database = None

    def __call__(self, database):
        self.database = database
        if self.scheduled_write:
            return
        self.scheduled_write = eventloop.add_timeout(self.SAVE_INTERVAL,
                                                     self.write,
                                                     'writing device database')
    def write(self):
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
        except (IOError, OSError):
            if countdown == 5:
                logging.exception('file error with JSON on %s', mount)
                db = {}
            else:
                # wait a little while; total time is ~1.5s
                time.sleep(0.20 * 1.2 ** countdown)
                return load_database(mount, countdown + 1)
    ddb = DeviceDatabase(db)
    ddb.connect('changed', DatabaseWriteManager(mount))
    return ddb

def write_database(db, mount):
    """
    Writes the given dictionary to the device.

    The database lives at [MOUNT]/.miro/json
    """
    database.confirm_db_thread()
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
    def _exists(item_path):
        return os.path.exists(os.path.join(device.mount,
                                           item_path))
    known_files = set()
    to_remove = []
    for item_type in (u'video', u'audio', u'other'):
        device.database.setdefault(item_type, {})
        if isinstance(device.database[item_type], list):
            # 17554: we could accidentally set this to a list
            device.database[item_type] = {}
        for item_path_unicode in device.database[item_type]:
            item_path = utf8_to_filename(item_path_unicode.encode('utf8'))
            if _exists(item_path):
                known_files.add(os.path.normcase(item_path))
            else:
                to_remove.append((item_type, item_path_unicode))

    if to_remove:
        device.database.set_bulk_mode(True)
        for item_type, item_path in to_remove:
            del device.database[item_type][item_path]
        device.database.set_bulk_mode(False)

    return known_files

def on_mount(info):
    """Stuff that we need to do when the device is first mounted.
    """
    if info.database.get(u'sync', {}).get(u'auto', False):
        message = messages.DeviceSyncFeeds(info)
        message.send_to_backend()
    scan_device_for_files(info)

@eventloop.idle_iterator
def scan_device_for_files(device):
    # XXX is this as_idle() safe?

    # prepare paths to add
    logging.debug('starting scan on %s', device.mount)
    known_files = clean_database(device)
    item_data = []
    start = time.time()
    filenames = []
    def _stop():
        if not app.device_manager.running: # user quit, so we will too
            logging.debug('stopping scan on %s: user quit', device.mount)
            return True
        if not os.path.exists(device.mount): # device disappeared
            logging.debug('stopping scan on %s: disappeared', device.mount)
            return True
        if app.device_manager._is_hidden(device): # device no longer being
                                                  # shown
            logging.debug('stopping scan on %s: hidden', device.mount)
            return True
        return False

    for filename in fileutil.miro_allfiles(device.mount):
        short_filename = filename[len(device.mount):]
        ufilename = filename_to_unicode(short_filename)
        item_type = None
        if os.path.normcase(short_filename) in known_files:
            continue
        if filetypes.is_video_filename(ufilename):
            item_type = u'video'
        elif filetypes.is_audio_filename(ufilename):
            item_type = u'audio'
        if item_type is not None:
            item_data.append((ufilename, item_type))
            filenames.append(filename)
        if time.time() - start > 0.3:
            app.metadata_progress_updater.will_process_paths(filenames,
                                                             device)
            yield # let other stuff run
            if _stop():
                break
            start = time.time()
            filenames = []

    if app.device_manager.running and os.path.exists(device.mount):
        # we don't re-check if the device is hidden because we still want to
        # save the items we found in that case
        yield # yield after prep work

        device.database.setdefault(u'sync', {})
        logging.debug('scanned %s, found %i files (%i total)',
                      device.mount, len(item_data),
                      len(known_files) + len(item_data))

        device.database.set_bulk_mode(True)
        start = time.time()
        for ufilename, item_type in item_data:
            i = item.DeviceItem(video_path=ufilename,
                           file_type=item_type,
                           device=device)
            device.database[item_type][ufilename] = i.to_dict()
            device.database.emit('item-added', i)
            if time.time() - start > 0.4:
                device.database.set_bulk_mode(False) # save the database
                yield # let other idle functions run
                if _stop():
                    break
                device.database.set_bulk_mode(True)
                start = time.time()

        device.database.set_bulk_mode(False)
