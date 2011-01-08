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

import datetime

from miro import app
from miro import database
from miro import devices
from miro import messages
from miro import signals

class ItemSource(signals.SignalEmitter):
    """
    This represents a list of audio/video items.  When changes occur, various
    signals are sent to allow listeners to update their view of this source.
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'added', 'changed', 'removed',
                                       'new-list')
        self.limiter = None
        self.current_ids = set()

    def fetch_all(self):
        """
        Returns a list of ItemInfo objects representing all the A/V items this
        source knows about.  Code that interacts with a source should use
        fetch() instead, so that it goes through the limiter.
        """
        raise NotImplementedError

    def unlink(self):
        """
        Do any cleanup for when this source is disappearing.
        """
        pass

    def added(self, info):
        if self.limiter is None or not self.limiter.filter_info(info):
            self.current_ids.add(info.id)
            self.emit('added', info)

    def changed(self, info):
        before = info.id in self.current_ids
        if self.limiter is None:
            now = True
        else:
            now = not self.limiter.filter_info(info)
        if before and now:
            self.emit('changed', info)
        elif now and not before:
            self.emit('added', info)
            self.current_ids.add(info.id)
        elif before and not now:
            self.emit('removed', info)
            self.current_ids.remove(info.id)

    def removed(self, info):
        if self.limiter is None or not self.limiter.filter_info(info):
            if info.id in self.current_ids:
                self.current_ids.remove(info.id)
                self.emit('removed', info)

    def set_limiter(self, limiter):
        """
        Set the current limiter and reset the list.
        """
        self.limiter = limiter
        infos = self.fetch() # resets current_ids
        self.emit('new-list', infos)

    def fetch(self):
        """
        Fetch all the ItemInfos which match the current limiter.
        """
        if self.limiter is None:
            infos = self.fetch_all()
        else:
            infos = self.limiter.filter_list(self.fetch_all())
        infos = list(infos)
        self.current_ids = set(info.id for info in infos)
        return infos

class DatabaseItemSource(ItemSource):
    """
    An ItemSource which pulls its data from the database, along with
    ItemInfoCache.
    """
    # bump this whenever you change the ItemInfo class, or change one of the
    # functions that ItemInfo uses to get it's attributes (for example
    # Item.get_description()).
    VERSION = 9

    def __init__(self, view, use_cache=True):
        ItemSource.__init__(self)
        # use_cache=False for priming the cache
        self.use_cache = use_cache
        self.view = view

        if use_cache:
            self.view.fetcher = database.ItemInfoFetcher()

        self.tracker = self.view.make_tracker()
        self.tracker.connect('added', self._emit_from_db, self.added)
        self.tracker.connect('changed', self._emit_from_db, self.changed)
        self.tracker.connect('removed', self._emit_from_db, self.removed)

    @staticmethod
    def _item_info_for(item):
        info = {
            'name': item.get_title(),
            'feed_id': item.feed_id,
            'feed_name': item.get_source(),
            'feed_url': item.get_feed_url(),
            'description': item.get_description(),
            'state': item.get_state(),
            'release_date': item.get_release_date_obj(),
            'size': item.get_size(),
            'duration': item.get_duration_value(),
            'resume_time': item.resumeTime,
            'permalink': item.get_link(),
            'commentslink': item.get_comments_link(),
            'payment_link': item.get_payment_link(),
            'has_sharable_url': item.has_shareable_url(),
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
            'is_playable': item.is_playable(),
            'file_type': item.file_type,
            'subtitle_encoding': item.subtitle_encoding,
            'media_type_checked': item.media_type_checked,
            'seeding_status': item.torrent_seeding_status(),
            'mime_type': item.enclosure_type,
            'artist': item.get_artist(),
            'album': item.get_album(),
            'track': item.get_track(),
            'year': item.get_year(),
            'genre': item.get_genre(),
            'rating': item.get_rating(),
            'date_added': item.get_creation_time(),
            'last_played': item.get_watched_time(),
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
            'play_count': item.play_count,
            'skip_count': item.skip_count,
            'cover_art': item.get_cover_art(),
            'auto_rating': item.get_auto_rating(),
            }
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
                info['up_rate'] = status.get('upRate', 0)
                info['down_rate'] = status.get('rate', 0)

            # gettorrentdetailsfinished & gettorrentdetails
            info['up_total'] = status.get('uploaded', 0)
            info['down_total'] = status.get('currentSize', 0)
            if info['down_total'] > 0:
                info['up_down_ratio'] = float(info['up_total'] /
                                              info['down_total'])
        return messages.ItemInfo(item.id, **info)

    def fetch_all(self):
        if self.use_cache:
            return list(iter(self.view))
        else:
            return [self._item_info_for(i) for i in self.view]

    def _emit_from_db(self, vt, obj, signal_method):
        if self.use_cache:
            info = obj
        else:
            info = self._item_info_for(obj)
        signal_method(info)

    def unlink(self):
        self.tracker.unlink()

    @staticmethod
    def get_by_id(id_):
        # XXX should this be part of the ItemSource API?
        return app.item_info_cache.get_info(id_)

class SharingItemSource(ItemSource):
    """
    An ItemSource which pulls data from a remote media share.
    XXX should we use the database somehow so that the OS can decide
    XXX can decide to write this data to secondary storage if it feels
    XXX like it?
    """
    def __init__(self, tracker):
        print 'SHARING ITEM SOURCE INIT'
        ItemSource.__init__(self)
        self.tracker = tracker
        for signal in 'added', 'changed', 'removed':
            signal_callback = getattr(self, signal)
            # Use SQLite to create an in-memory database using a temp file, 
            # and then
            # chuck away the data.  Then the OS can page in and out as 
            # necessary 
            #handle = self.device.database.connect('item-%s' % signal,
            #                                      self._emit_from_db,
            #                                      signal_callback)
            #self.signal_handles.append(handle)

    def _emit_from_db(self, database, item, signal_callback):
        if item.file_type != self.type:
            return # don't care about other types of items
        if not isinstance(item, messages.ItemInfo):
            info = self._item_info_for(item)
        else:
            info = item
        signal_callback(info)

    def fetch_all(self):
        print 'FETCH ALL'
        return []

    def unlink(self):
        print 'SHARING ITEM SOURCE UNLINK'
        #for handle in self.signal_handles:
        #    self.device.database.disconnect(handle)
        #self.signal_handles = []

class DeviceItemSource(ItemSource):
    """
    An ItemSource which pulls its data from a device's JSON database.
    """
    def __init__(self, device):
        ItemSource.__init__(self)
        self.device = device
        self.type = device.id.rsplit('-', 1)[1]
        self.signal_handles = []
        for signal in 'added', 'changed', 'removed':
            signal_callback = getattr(self, signal)
            handle = self.device.database.connect('item-%s' % signal,
                                                  self._emit_from_db,
                                                  signal_callback)
            self.signal_handles.append(handle)

    def _emit_from_db(self, database, item, signal_callback):
        if item.file_type != self.type:
            return # don't care about other types of items
        if not isinstance(item, messages.ItemInfo):
            info = self._item_info_for(item)
        else:
            info = item
        signal_callback(info)

    def _item_info_for(self, item):
        return messages.ItemInfo(
            item.id,
            name = item.name,
            feed_id = item.feed_id,
            feed_name = (item.feed_name is None and item.feed_name or
                         self.device.name),
            feed_url = None,
            description = item.description,
            state = u'saved',
            release_date = datetime.datetime.fromtimestamp(item.release_date),
            size = item.size,
            duration = (item.duration not in (-1, None) and
                        item.duration / 1000 or 0),
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
            is_playable = True,
            children = [],
            file_type = item.file_type,
            subtitle_encoding = item.subtitle_encoding,
            seeding_status = None,
            mime_type = item.enclosure_type,
            artist = item.metadata.get('artist', u''),
            album = item.metadata.get('album', u''),
            track = item.metadata.get('track', -1),
            year = item.metadata.get('year', -1),
            genre = item.metadata.get('genre', u''),
            rating = item.rating,
            date_added = item.creation_time,
            last_played = item.creation_time,
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
            cover_art=None)

    def fetch_all(self):
        return [self._item_info_for(devices.DeviceItem(
                    video_path=video_path,
                    file_type=self.type,
                    device=self.device,
                    **json)) for video_path, json in
                self.device.database[self.type].items()]

    def unlink(self):
        for handle in self.signal_handles:
            self.device.database.disconnect(handle)
        self.signal_handles = []

class SourceLimiter(object):
    """Interface for objects that are passed into ItemSource.set_limiter.

    SourceLimiter objects allow us to filter sets of items in Python, rather
    than through the database.
    """
    def filter_info(self, info):
        """Return True if we should filter out info from fetch()."""
        raise NotImplementedError()

    def filter_list(self, infos):
        """Only return infos which should be part of fetch()."""
        raise NotImplementedError()
