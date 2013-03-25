# Miro - an RSS based video player application
# Copyright (C) 2012
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

"""Upgrade old device databases """

import datetime
import itertools
import logging
import os.path
import shutil
import urllib

from miro import app
from miro import databaseupgrade
from miro import item
from miro import metadata
from miro import prefs
from miro import schema
from miro import storedatabase
from miro.plat.utils import filename_to_unicode

class OldItemImporter(object):
    """Import items from the database of old versions.

    This class is made to import items from previous versions of Miro.  There
    are basically 2 cases:

    Upgrading from Miro 4.x -- In this case we get all data from the JSON db.

    Upgrading from Miro 5.x -- In this case we get the data from both the JSON
    db and also the metadata tables in the sqlite db.

    Importing data requires some careful ordering of how we do things.  The
    steps are:
        - import_metadata() imports data into the metadata tables
        - the calling code should then create a MetadataManager for the device
        - the MetadataManager is then passed to import_device_items()
    """

    # FIXME: this code is tied to the 5.0 release and may not work for future
    # versions

    # map old MDP states to their new values
    mdp_state_map = {
        None : 'N',
        0 : 'S',
        1 : 'C',
        2 : 'F',
    }

    # list that contains tuples in the form of
    # (metadata_column_name, device_item_key
    column_map = [
        ('duration', 'duration'),
        ('album', 'album'),
        ('album_artist', 'album_artist'),
        ('album_tracks', 'album_tracks'),
        ('artist', 'artist'),
        ('screenshot', 'screenshot'),
        ('drm', 'has_drm'),
        ('genre', 'genre'),
        ('title ', 'title'),
        ('track', 'track'),
        ('year', 'year'),
        ('description', 'description'),
        ('rating', 'rating'),
        ('show', 'show'),
        ('episode_id', 'episode_id'),
        ('episode_number', 'episode_number'),
        ('season_number', 'season_number'),
        ('kind', 'kind'),
    ]

    insert_columns = ['id', 'status_id', 'file_type', 'source', 'priority',
                      'disabled']
    for new_name, old_name in column_map:
        insert_columns.append(new_name)

    # SQL to insert a row into the metadata table
    metadata_insert_sql = (
        "INSERT INTO metadata (%s) VALUES (%s)" %
        (', '.join(insert_columns),
         ', '.join('?' for i in xrange(len(insert_columns)))))

    # SQL to insert a row into the device_item table
    device_item_insert_sql = (
        "INSERT INTO device_item (%s) VALUES (%s)" %
        (', '.join(name for name, field in schema.DeviceItemSchema.fields),
         ', '.join('?' for i in xrange(len(schema.DeviceItemSchema.fields)))))

    def __init__(self, live_storage, mount, json_db):
        self.cover_art_dir = os.path.join(mount, '.miro', 'cover-art')
        self.net_lookup_enabled = app.config.get(prefs.NET_LOOKUP_BY_DEFAULT)
        self.mount = mount
        self.cursor = live_storage.cursor
        # track the next id that we should create in the database
        next_id = databaseupgrade.get_next_id(self.cursor)
        self.id_counter = itertools.count(next_id)

        self.select_paths_from_db()
        self.init_device_items(json_db)

    def import_metadata(self):
        """Import data into the metadata tables."""
        if not self.old_device_items:
            # nothing new to import
            return

        logging.info("Importing metadata for %d old device items",
                     len(self.old_device_items))

        self.cursor.execute("BEGIN TRANSACTION")
        try:
            for file_type, path, old_item in self.old_device_items:
                try:
                    if path not in self.paths_in_metadata_table:
                        self.add_metadata_to_db(file_type, path, old_item)
                        self.fix_json_data(old_item)
                except StandardError, e:
                    logging.warn("error converting device item for %r ", path,
                                 exc_info=True)
        finally:
            self.cursor.execute("COMMIT TRANSACTION")

    def import_device_items(self, metadata_manager):
        if not self.old_device_items:
            # nothing new to import
            return

        logging.info("Importing device items for %d old device items",
                     len(self.old_device_items))

        self.cursor.execute("BEGIN TRANSACTION")
        try:
            for file_type, path, old_item in self.old_device_items:
                if isinstance(path, unicode):
                    # when we use the json module instead of the simplejson
                    # module, paths are unicode rather than bytestrings.
                    # There's no great solution here, but the best practice is
                    # probably to force them to be utf-8.  (see #19507)
                    path = path.encode('utf-8')
                try:
                    self.add_device_item(file_type, path, old_item,
                                         metadata_manager)
                except StandardError, e:
                    logging.warn("error converting device item for %r ", path,
                                 exc_info=True)
        finally:
            self.cursor.execute("COMMIT TRANSACTION")

    def select_paths_from_db(self):
        """Setup paths_in_metadata_table and paths_in_device_items_table

        These variables track which paths are in our sqlite database for the
        metadata_status and device_item tables.
        """
        self.cursor.execute("SELECT path FROM metadata_status")
        self.paths_in_metadata_table = set(row[0] for row in self.cursor)

        self.cursor.execute("SELECT filename FROM device_item")
        self.paths_in_device_items_table = set(row[0] for row in self.cursor)

    def init_device_items(self, json_db):
        """Initialize device_items

        device_items stores a (file_type, path, item_data) tuple for each
        device item that we should convert
        """
        # get info about each item on the device
        paths_added = set()
        self.old_device_items = []
        for file_type in (u'audio', u'video', u'other'):
            if file_type not in json_db:
                continue
            for path, data in json_db[file_type].iteritems():
                if path in paths_added:
                    # duplicate filename, just skip this data
                    continue
                paths_added.add(path)
                if (path not in self.paths_in_metadata_table or
                    path not in self.paths_in_device_items_table):
                    self.old_device_items.append((file_type, path, data))

    def add_metadata_to_db(self, file_type, path, old_item):
        """Add rows to the metadata and metadata_status tables for old items.
        """

        # title and title_tag were pretty confusing before 5.0.  We would set
        # title_tag based on the ID3 tags, and if that didn't work, then set
        # title based on the filename.  get_title() would try the title
        # attribute first, then fallback to title_tag.  After 5.0, we just
        # only use title.
        #
        # This code should make it so that titles work correctly for upgraded
        # items, both in 5.0 and also if you go back to a pre-5.0 versions.
        if 'title_tag' in old_item:
            if not old_item['title']:
                old_item['title'] = old_item['title_tag']
            old_item['title_tag'] = None

        has_drm = old_item.get('has_drm') # other doesn't have DRM
        OLD_ITEM_PRIORITY = 10
        # Make an entry in the metadata_status table.  We're not sure if
        # mutagen completed successfully or not, so we just call its status
        # SKIPPED.  moviedata_status is based on the old mdp_state column
        moviedata_status = self.mdp_state_map[old_item.get('mdp_state')]
        finished_status = bool(moviedata_status !=
                               metadata.MetadataStatus.STATUS_NOT_RUN)

        if self.net_lookup_enabled:
            echonest_status = metadata.MetadataStatus.STATUS_NOT_RUN
        else:
            echonest_status = metadata.MetadataStatus.STATUS_SKIP
        status_id = self.insert_into_metadata_status(
            path, file_type, finished_status, 'S', moviedata_status,
            echonest_status, has_drm, OLD_ITEM_PRIORITY)
        # Make an entry in the metadata table with the metadata that was
        # stored.  We don't know if it came from mutagen, movie data, torrent
        # data or wherever, so we use "old-item" as the source and give it a
        # low priority.
        values = [self.id_counter.next(), status_id, file_type, 'old-item',
                  10, False]
        for new_name, old_name in self.column_map:
            value = old_item.get(old_name)
            if value == '':
                value = None
            values.append(value)

        self.cursor.execute(self.metadata_insert_sql, values)

    def insert_into_metadata_status(self, path, file_type, finished_status,
                                    mutagen_status, moviedata_status,
                                    echonest_status, has_drm,
                                    max_entry_priority):
        status_id = self.id_counter.next()
        sql = ("INSERT INTO metadata_status "
               "(id, path, file_type, finished_status, mutagen_status, "
               "moviedata_status, echonest_status, net_lookup_enabled, "
               "mutagen_thinks_drm, max_entry_priority) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")

        self.cursor.execute(sql, (status_id, path, file_type, finished_status,
                             mutagen_status, moviedata_status,
                             echonest_status, self.net_lookup_enabled,
                             has_drm, max_entry_priority))
        return status_id

    def add_device_item(self, file_type, path, old_item, metadata_manager):
        """Insert a device_item row for an old item."""
        values = []
        # copy data from old_item so that we don't modify it
        old_data = dict(old_item)
        if path in self.paths_in_metadata_table:
            # This item comes from a 5.x database, so there's data in the
            # metadata tables for it.
            metadata_dict = metadata_manager.get_metadata(path)
            for key, value in metadata_dict.items():
                old_data[key] = value
        for name, field in schema.DeviceItemSchema.fields:
            # get value from the old item
            if name == 'id':
                value = self.id_counter.next()
            elif name == 'filename':
                value = filename_to_unicode(path)
            elif name == 'file_type':
                value = file_type
            elif name == 'net_lookup_enabled':
                value = False
            else:
                value = old_data.get(name)
            # convert value
            if value is not None:
                if isinstance(field, schema.SchemaDateTime):
                    value = datetime.datetime.fromtimestamp(value)
            values.append(value)
        self.cursor.execute(self.device_item_insert_sql, values)

    def fix_json_data(self, old_item):
        """Update the data in the JSON db after upgrading an old item."""
        if 'cover_art' in old_item:
            self.upgrade_cover_art(old_item)
        # Use the RAN state for all old items.  This will prevent old miro
        # versions from running the movie data program on them.  This seems
        # the safest option and old versions should still pick up new metadata
        # when newer versions run MDP.
        old_item['mdp_state'] = item.MDP_STATE_RAN

    def upgrade_cover_art(self, device_item):
        """Drop the cover_art field and move cover art to a filename based on
        the album
        """

        if 'album' not in device_item or 'cover_art' not in device_item:
            return
        cover_art = device_item.pop('cover_art')
        device_item['cover_art'] = None # default in case the upgrade fails.
        # quote the filename using the same logic as
        # filetags.calc_cover_art_filename()
        dest_filename = urllib.quote(device_item['album'].encode('utf-8'),
                                     safe=' ,.')
        dest_path = os.path.join(self.cover_art_dir, dest_filename)
        if not os.path.exists(dest_path):
            if not os.path.exists(cover_art):
                logging.warn("upgrade_cover_art: Error moving cover art, "
                             "source path doesn't exist: %s", cover_art)
                return
            try:
                shutil.move(cover_art, dest_path)
            except StandardError:
                logging.warn("upgrade_cover_art: Error moving %s -> %s", 
                             cover_art, dest_path)
                return
        device_item['cover_art'] = dest_path
