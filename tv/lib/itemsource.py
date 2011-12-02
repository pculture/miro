# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
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

import logging
import os.path

from miro import app
from miro import database
from miro import item
from miro import messages
from miro import metadata
from miro import signals

def _add_metadata(info_dict, item_obj):
    """Add metadata from obj to a info dictionary."""
    for name in metadata.attribute_names:
        value = getattr(item_obj, name)
        if name == 'title':
            # we change the name of "title" to "name" in ItemInfo
            name = 'name'
        if value is not None or name not in info_dict:
            info_dict[name] = value

class ItemSource(signals.SignalEmitter):
    """
    This represents a list of audio/video items.  When changes occur, various
    signals are sent to allow listeners to update their view of this source.
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'added', 'changed', 'removed')

    # Methods to implement for sources
    def fetch_all(self):
        """
        Returns a list of ItemInfo objects representing all the A/V items this
        source knows about.
        """
        raise NotImplementedError

    def unlink(self):
        """
        Do any cleanup for when this source is disappearing.
        """
        pass


class ItemHandler(object):
    """
    Controller base class for handling user actions on an item.
    """

    def mark_watched(self, info):
        """
        Mark the given ItemInfo as watched.  Should also send a 'changed'
        message.
        """
        logging.warn("%s: not handling mark_watched", self)

    def mark_unwatched(self, info):
        """
        Mark the given ItemInfo as unwatched.  Should also send a 'changed'
        message.
        """
        logging.warn("%s: not handling mark_unwatched", self)

    def mark_completed(self, info):
        """
        Mark the given ItemInfo as completed.  Should also send a 'changed'
        message.
        """
        logging.warn("%s: not handling mark_completed", self)

    def mark_skipped(self, info):
        """
        Mark the given ItemInfo as skipped.  Should also send a 'changed'
        message.
        """
        logging.warn("%s: not handling mark_skipped", self)

    def set_is_playing(self, info, is_playing):
        """
        Mark the given ItemInfo as playing, based on the is_playing bool.
        Should also send a 'changed' message, if the is_playing state changed.
        """
        logging.warn("%s: not handling set_is_playing", self)

    def set_rating(self, info, rating):
        """
        Rate the given ItemInfo.  Should also send a 'changed'
        message if the rating changed.
        """
        logging.warn("%s: not handling set_rating", self)

    def set_subtitle_encoding(self, info, encoding):
        """
        Set the subtitle encoding the given ItemInfo.  Should also send a
        'changed' message if the encoding changed.
        """
        logging.warn("%s: not handling set_subtitle_encoding", self)

    def set_resume_time(self, info, resume_time):
        """
        Set the resume time for the given ItemInfo.  Should also send a
        'changed' message.
        """
        logging.warn("%s: not handling set_resume_time", self)

    def delete(self, info):
        """
        Delete the given ItemInfo.  Should also send a 'removed' message.
        """
        logging.warn("%s: not handling delete", self)

    def bulk_delete(self, info_list):
        """
        Delete a list of infos.  Should also send 'removed' messages.
        """
        logging.warn("%s: not handling delete", self)

class DatabaseItemSource(ItemSource):
    """
    An ItemSource which pulls its data from the database, along with
    ItemInfoCache.
    """
    # bump this whenever you change the ItemInfo class, or change one of the
    # functions that ItemInfo uses to get it's attributes (for example
    # Item.get_description()).
    VERSION = 35

    def __init__(self, view):
        ItemSource.__init__(self)
        self.view = view
        self.view.fetcher = database.IDOnlyFetcher()
        self.tracker = self.view.make_tracker()
        self.tracker.connect('added', self._on_tracker_added)
        self.tracker.connect('changed', self._on_tracker_changed)
        self.tracker.connect('removed', self._on_tracker_removed)

    @staticmethod
    def _item_info_for(item):
        info = {
            'name': item.get_title(),
            'feed_id': item.feed_id,
            'feed_name': item.get_source(),
            'feed_url': item.get_feed_url(),
            'state': item.get_state(),
            'description': item.get_description(),
            'release_date': item.get_release_date(),
            'size': item.get_size(),
            'duration': item.get_duration_value(),
            'resume_time': item.resumeTime,
            'permalink': item.get_link(),
            'commentslink': item.get_comments_link(),
            'payment_link': item.get_payment_link(),
            'has_shareable_url': item.has_shareable_url(),
            'can_be_saved': item.show_save_button(),
            'pending_manual_dl': item.is_pending_manual_download(),
            'pending_auto_dl': item.is_pending_auto_download(),
            'item_viewed': item.get_viewed(),
            'downloaded': item.is_downloaded(),
            'is_external': item.is_external(),
            'video_watched': item.get_seen(),
            'video_path': item.get_filename(),
            'thumbnail': item.get_thumbnail(),
            'thumbnail_url': item.get_thumbnail_url(),
            'file_format': item.get_format(),
            'license': item.get_license(),
            'file_url': item.get_url(),
            'is_container_item': item.isContainerItem,
            'is_file_item': item.is_file_item,
            'is_playable': item.is_playable(),
            'file_type': item.file_type,
            'subtitle_encoding': item.subtitle_encoding,
            'seeding_status': item.torrent_seeding_status(),
            'mime_type': item.enclosure_type,
            'date_added': item.get_creation_time(),
            'last_played': item.get_watched_time(),
            'last_watched': item.lastWatched,
            'downloaded_time': item.downloadedTime,
            'children': [],
            'expiration_date': None,
            'download_info': None,
            'leechers': None,
            'seeders': None,
            'up_rate': None,
            'down_rate': None,
            'up_total': None,
            'down_total': None,
            'up_down_ratio': 0.0,
            'remote': False,
            'device': None,
            'source_type': 'database',
            'play_count': item.play_count,
            'skip_count': item.skip_count,
            'auto_rating': item.get_auto_rating(),
            'is_playing': item.is_playing(),
            }
        _add_metadata(info, item)
        if item.isContainerItem:
            info['children'] = [DatabaseItemSource._item_info_for(i) for i in
                                item.get_children()]
        if not item.keep and not item.is_external():
            info['expiration_date'] = item.get_expiration_time()

        if item.downloader:
            info['download_info'] = messages.DownloadInfo(item.downloader)
        elif info['state'] == 'downloading':
            info['download_info'] = messages.PendingDownloadInfo()

        ## Torrent-specific stuff
        if item.looks_like_torrent() and hasattr(item.downloader, 'status'):
            status = item.downloader.status
            if item.is_transferring():
                # gettorrentdetails only
                info['leechers'] = status.get('leechers', 0)
                info['seeders'] = status.get('seeders', 0)
                info['connections'] = status.get('connections', 0)
                info['up_rate'] = status.get('upRate', 0)
                info['down_rate'] = status.get('rate', 0)

            # gettorrentdetailsfinished & gettorrentdetails
            info['up_total'] = status.get('uploaded', 0)
            info['down_total'] = status.get('currentSize', 0)
            if info['down_total'] > 0:
                info['up_down_ratio'] = (float(info['up_total']) /
                                              info['down_total'])

        return messages.ItemInfo(item.id, **info)

    def fetch_all(self):
        return [self._get_info(id_) for id_ in self.view]

    def _get_info(self, id_):
        return app.item_info_cache.get_info(id_)

    def _on_tracker_added(self, tracker, id_):
        self.emit("added", self._get_info(id_))

    def _on_tracker_changed(self, tracker, id_):
        self.emit("changed", self._get_info(id_))

    def _on_tracker_removed(self, tracker, id_):
        self.emit("removed", id_)

    def unlink(self):
        self.tracker.unlink()

    @staticmethod
    def get_by_id(id_):
        # XXX should this be part of the ItemSource API?
        return app.item_info_cache.get_info(id_)

class DatabaseItemHandler(ItemHandler):
    def mark_watched(self, info):
        """
        Mark the given ItemInfo as watched.  Should also send a 'changed'
        message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.mark_item_seen()
        except database.ObjectNotFoundError:
            logging.warning("mark_watched: can't find item by id %s" % info.id)

    def mark_unwatched(self, info):
        """
        Mark the given ItemInfo as unwatched.  Should also send a 'changed'
        message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.mark_item_unseen()
        except database.ObjectNotFoundError:
            logging.warning("mark_unwatched: can't find item by id %s" % (
                info.id,))

    def mark_completed(self, info):
        """
        Mark the given ItemInfo as completed.  Should also send a 'changed'
        message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.mark_item_completed()
        except database.ObjectNotFoundError:
            logging.warning("mark_completed: can't find item by id %s" % (
                info.id,))

    def mark_skipped(self, info):
        """
        Mark the given ItemInfo as skipped.  Should also send a 'changed'
        message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.mark_item_skipped()
        except database.ObjectNotFoundError:
            logging.warning("mark_skipped: can't find item by id %s" % info.id)

    def set_is_playing(self, info, is_playing):
        """
        Mark the given ItemInfo as playing, based on the is_playing bool.
        Should also send a 'changed' message, if the is_playing state changed.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.set_is_playing(is_playing)
        except database.ObjectNotFoundError:
            logging.warning("mark_is_playing: can't find item by id %s" % (
                info.id,))

    def set_rating(self, info, rating):
        """
        Rate the given ItemInfo.  Should also send a 'changed'
        message if the rating changed.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.set_rating(rating)
        except database.ObjectNotFoundError:
            logging.warning("set_rating: can't find item by id %s" % info.id)

    def set_subtitle_encoding(self, info, encoding):
        """
        Set the subtitle encoding the given ItemInfo.  Should also send a
        'changed' message if the encoding changed.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.set_subtitle_encoding(encoding)
        except database.ObjectNotFoundError:
            logging.warning(
                "set_subtitle_encoding: can't find item by id %s" % info.id)

    def set_resume_time(self, info, resume_time):
        """
        Set the resume time for the given ItemInfo.  Should also send a
        'changed' message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
            item_.set_resume_time(resume_time)
        except database.ObjectNotFoundError:
            logging.warning("set_resume_time: can't find item by id %s" % (
                info.id,))

    def delete(self, info):
        """
        Delete the given ItemInfo.  Should also send a 'removed' message.
        """
        try:
            item_ = item.Item.get_by_id(info.id)
        except database.ObjectNotFoundError:
            logging.warn("delete: Item not found -- %s",  info.id)
        else:
            item_.delete_files()
            item_.expire()

    def bulk_delete(self, info_list):
        app.bulk_sql_manager.start()
        try:
            for info in info_list:
                if not app.bulk_sql_manager.will_remove(info.id):
                    self.delete(info)
        finally:
            app.bulk_sql_manager.finish()

class SharingItemSource(ItemSource):
    """
    An ItemSource which pulls data from a remote media share.
    XXX should we use the database somehow so that the OS can decide
    XXX can decide to write this data to secondary storage if it feels
    XXX like it?
    """
    def __init__(self, tracker, playlist_id=None):
        ItemSource.__init__(self)
        self.tracker = tracker
        self.playlist_id = playlist_id
        self.include_podcasts = True
        self.signal_handles = [
            self.tracker.connect('added', self._on_tracker_added),
            self.tracker.connect('changed', self._on_tracker_changed),
            self.tracker.connect('removed', self._on_tracker_removed),
        ]
        self.info_cache = tracker.info_cache

    def _item_info_for(self, item):
        info = dict(
            item_source=self,
            name=item.title,
            source_type='sharing',
            feed_id = item.feed_id,
            feed_name = None,
            feed_url = None,
            state = u'saved',
            description = item.description,
            release_date = item.get_release_date(),
            size = item.size,
            duration = item.duration,
            resume_time = 0,
            permalink = item.permalink,
            commentslink = item.comments_link,
            payment_link = item.payment_link,
            has_shareable_url = bool(item.url),
            can_be_saved = False,
            pending_manual_dl = False,
            pending_auto_dl = False,
            expiration_date = None,
            item_viewed = True,
            downloaded = True,
            is_external = False,
            video_watched = True,
            video_path = item.get_filename(),
            thumbnail = item.get_thumbnail(),
            thumbnail_url = item.thumbnail_url or u'',
            file_format = item.file_format,
            license = item.license,
            file_url = item.url or u'',
            is_container_item = False,
            is_file_item = False,
            is_playable = True,
            children = [],
            file_type = item.file_type,
            subtitle_encoding = item.subtitle_encoding,
            seeding_status = None,
            mime_type = item.enclosure_type,
            artist = item.artist,
            auto_rating = None,
            date_added = item.get_creation_time(),
            last_played = item.get_creation_time(),
            download_info = None,
            device = None,
            remote = True,
            leechers = None,
            seeders = None,
            up_rate = None,
            down_rate = None,
            up_total = None,
            down_total = None,
            up_down_ratio = 0,
            play_count=0,
            skip_count=0,
            host=item.host,
            port=item.port,
            is_playing=False)
        _add_metadata(info, item)
        return messages.ItemInfo(item.id, **info)

    def _ensure_info(self, obj):
        if not isinstance(obj, messages.ItemInfo):
            self.info_cache[obj.id] = info = self._item_info_for(obj)
            return info
        else:
            return obj

    def is_podcast(self, item):
        try:
            return item.kind == 'podcast'
        except AttributeError:
            pass
        return False

    def _on_tracker_added(self, tracker, playlist, item):
        if self.playlist_id == playlist:
            if (self.include_podcasts or
              not self.include_podcasts and not self.is_podcast(item)):
                self.emit("added", self._ensure_info(item))

    def _on_tracker_changed(self, tracker, playlist, item):
        if self.playlist_id == playlist:
            if (self.include_podcasts or
              not self.include_podcasts and not self.is_podcast(item)):
                self.emit("changed", self._ensure_info(item))

    def _on_tracker_removed(self, tracker, playlist, item):
        # Only nuke if we are removing the item from the library.
        if playlist == None:
            try:
                del self.info_cache[item.id]
            except KeyError:
                pass
        if playlist == self.playlist_id:
            if (self.include_podcasts or
              not self.include_podcasts and not self.is_podcast(item)):
                self.emit("removed", item.id)

    def fetch_all(self):
        # Always call _ensure_info() on the item when fetching.
        #
        # This is a problem for shared items because the database is not 
        # ready until some amount of time after the share is first accessed.
        # The sharing API is designed to always either returns 0 items or 
        # a fully populated media listing.  In the former case the upper layer
        # (i.e. this one) is notified via the 'added' signal.
        #
        # But this ItemSource object is a transient object that only exists
        # for the lifetime a display is active.  If the 'added' signal was
        # called and the tab has switched away and hence is no longer active,
        # then it won't be in the ItemInfo cache.
        #
        # _ensure_info() ensures that we either fetch something from the
        # cache or if it does not exist then create a new copy so this should
        # be okay.
        return [self._ensure_info(item) for item in 
                self.tracker.get_items(playlist_id=self.playlist_id)
                if self.include_podcasts or
                (not self.include_podcasts and
                 not self.is_podcast(item))]

    def unlink(self):
        for handle in self.signal_handles:
            self.tracker.disconnect(handle)
        self.signal_handles = []

class SharingItemHandler(ItemHandler):
    def set_is_playing(self, info, is_playing):
        """
        Mark the given ItemInfo as playing, based on the is_playing bool.
        Should also send a 'changed' message, if the is_playing state changed.

        Sharing items don't have a real database to back them up so just use
        a back pointer to the item source and emit a 'changed' message.
        """
        if info.is_playing != is_playing:
            # modifying the ItemInfo in-place messes up the Tracker's
            # object-changed logic, so make a copy
            info = messages.ItemInfo(info.id, **info.__dict__)
            info.is_playing = is_playing
            info.item_source.emit("changed", info)

class DeviceItemSource(ItemSource):
    """
    An ItemSource which pulls its data from a device's JSON database.
    """
    def __init__(self, device, file_type=None):
        ItemSource.__init__(self)
        self.device = device
        self.info_cache = app.device_manager.info_cache[device.mount]
        if file_type is None:
            self.type = device.id.rsplit('-', 1)[1]
        else:
            self.type = file_type
        self.signal_handles = [
            device.database.connect('item-added', self._on_device_added),
            device.database.connect('item-changed', self._on_device_changed),
            device.database.connect('item-removed', self._on_device_removed),
        ]

    def _ensure_info(self, item):
        if not isinstance(item, messages.ItemInfo):
            info = self.info_cache[item.id] = self._item_info_for(item)
            return info
        else:
            return item

    def _on_device_added(self, database, item):
        if item.file_type != self.type:
            return # don't care about other types of items
        self.emit("added", self._ensure_info(item))

    def _on_device_changed(self, database, item):
        existed = was_type = False
        if item.id in self.info_cache:
            existed = True
            was_type = (
                self.info_cache[item.id].file_type == self.type)
        is_type = (item.file_type == self.type)
        if existed:
            if was_type and not is_type:
                # type changed alway from this source
                self.emit('removed', item.id)
                return
            elif is_type and not was_type:
                # added to this source
                self.emit('added', self._ensure_info(item))
                return
        if is_type:
            if existed:
                self.emit("changed", self._ensure_info(item))
            else:
                self.emit('added', self._ensure_info(item))

    def _on_device_removed(self, database, item):
        was_type = False
        if item.id in self.info_cache:
            was_type = (
                self.info_cache[item.id].file_type == self.type)
        if item.file_type == self.type or was_type:
            self.emit("removed", item.id)
            self.info_cache.pop(item.video_path, None)

    def _item_info_for(self, item):
        if item.duration is None:
            duration = None
        else:
            duration = item.duration / 1000
        info = dict(
            source_type='device',
            name=item.get_title(),
            feed_id = item.feed_id,
            feed_name = (item.feed_name is None and item.feed_name or
                         self.device.name),
            feed_url = item.feed_url,
            state = u'saved',
            description = u'',
            release_date = item.get_release_date(),
            size = item.size,
            duration = duration,
            resume_time = 0,
            permalink = item.permalink,
            commentslink = item.comments_link,
            payment_link = item.payment_link,
            has_shareable_url = (item.url and
                                 not item.url.startswith('file://')),
            can_be_saved = False,
            pending_manual_dl = False,
            pending_auto_dl = False,
            expiration_date = None,
            item_viewed = True,
            downloaded = True,
            is_external = False,
            video_watched = True,
            video_path = item.get_filename(),
            thumbnail = item.get_thumbnail(),
            thumbnail_url = item.thumbnail_url or u'',
            file_format = item.file_format,
            license = item.license,
            file_url = item.url or u'',
            is_container_item = False,
            is_file_item = False,
            is_playable = True,
            children = [],
            file_type = item.file_type,
            subtitle_encoding = item.subtitle_encoding,
            seeding_status = None,
            mime_type = item.enclosure_type,
            artist = item.artist,
            date_added = item.get_creation_time(),
            last_played = item.get_creation_time(),
            download_info = None,
            device = item.device,
            remote = False,
            leechers = None,
            seeders = None,
            up_rate = None,
            down_rate = None,
            up_total = None,
            down_total = None,
            up_down_ratio = 0,
            play_count=0,
            skip_count=0,
            auto_rating=0,
            is_playing=item.is_playing)
        _add_metadata(info, item)
        return messages.ItemInfo(item.id, **info)

    def fetch_all(self):
        # avoid lookups
        info_cache = self.info_cache
        type_ = self.type
        device = self.device
        _item_info_for = self._item_info_for
        if type_ not in self.device.database:
            # race: we can get here before clean_database() sets us up
            return []
        data = self.device.database[type_]

        def _cache(id_):
            if id_ in info_cache:
                return info_cache[id_]
            else:
                info = info_cache[id_] = _item_info_for(
                    item.DeviceItem(
                        video_path=id_,
                        file_type=type_,
                        device=device,
                        **data[id_]))
                return info

        def _all_videos():
            for id_ in list(data.keys()):
                try:
                    yield _cache(id_)
                except (OSError, IOError): # couldn't find the file
                    pass

        return list(_all_videos())

    def unlink(self):
        for handle in self.signal_handles:
            self.device.database.disconnect(handle)
        self.signal_handles = []

class DeviceItemHandler(ItemHandler):
    def delete(self, info):
        device = info.device
        try:
            if os.path.exists(info.video_path):
                os.unlink(info.video_path)
        except (OSError, IOError):
            # we can still fail to delete an item, log the error
            logging.warn('failed to delete %r', info.video_path,
                         exc_info=True)
        else:
            del device.database[info.file_type][info.id]
            if info.thumbnail and info.thumbnail.startswith(device.mount):
                try:
                    os.unlink(info.thumbnail)
                except (OSError, IOError):
                    pass # ignore errors
            if info.cover_art and info.cover_art.startswith(device.mount):
                try:
                    os.unlink(info.cover_art)
                except (OSError, IOError):
                    pass # ignore errors
            device.remaining += info.size
            device.database.emit('item-removed', info)

    def bulk_delete(self, info_list):
        # calculate all the devices involved
        all_devices = set(info.device for info in info_list)
        # set bulk mode, delete, then unset bulk mode
        for device in all_devices:
            device.database.set_bulk_mode(True)
        try:
            for info in info_list:
                self.delete(info)
        finally:
            for device in all_devices:
                message = messages.DeviceChanged(device)
                message.send_to_frontend()
                device.database.set_bulk_mode(False)

    def set_is_playing(self, info, is_playing):
        """
        Mark the given ItemInfo as playing, based on the is_playing bool.
        Should also send a 'changed' message, if the is_playing state changed.
        """
        if info.is_playing != is_playing:
            # modifying the ItemInfo in-place messes up the Tracker's
            # object-changed logic, so make a copy
            info_cache = app.device_manager.info_cache[info.device.mount]
            info = info_cache[info.id] = messages.ItemInfo(
                info.id, **info.__dict__)
            database = info.device.database
            info.is_playing = is_playing
            database[info.file_type][info.id][u'is_playing'] = is_playing
            database.emit('item-changed', info)

def setup_handlers():
    app.source_handlers = {
            'database': DatabaseItemHandler(),
            'device': DeviceItemHandler(),
            'sharing': SharingItemHandler(),
    }

def get_handler(item_info):
    return app.source_handlers[item_info.source_type]
