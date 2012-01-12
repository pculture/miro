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

import logging
import os.path
import shutil

from miro import app
from miro import databaseupgrade
from miro import prefs
from miro import storedatabase

def import_from_json(live_storage, json_db, mount):
    """Import data from a JSON DB for a newly created sqlite DB

    This method basically does upgrades 166 through 172

    How to handle upgrades after this?  Who knows.  We're just worrying about
    making version 5.0 work at this point.
    """
    live_storage.cursor.execute("BEGIN TRANSACTION")
    try:
        _do_import(live_storage.cursor, json_db, mount)
    except StandardError, e:
        action = live_storage.error_handler.handle_upgrade_error()
        # Our error handle should always return ACTION_START_FRESH
        if action != storedatabase.LiveStorageErrorHandler.ACTION_START_FRESH:
            logging.warn("Unexpected return value from the error handler for "
                         "a device database: %s" % action)
        handle_failed_upgrade(live_storage.cursor, json_db)
    finally:
        live_storage.cursor.execute("COMMIT TRANSACTION")

def _do_import(cursor, json_db, mount):
    # FIXME: this code is tied to the 4.5 release and may not work for future
    # versions

    cover_art_dir = os.path.join(mount, '.miro', 'cover-art')
    # map old MDP states to their new values
    mdp_state_map = {
        None : 'N',
        0 : 'S',
        1 : 'C',
        2 : 'F',
    }

    device_items = []
    for file_type in (u'audio', u'video', u'other'):
        for path, data in json_db[file_type].iteritems():
            device_items.append((file_type, path, data))

    # currently get_title() returns the contents of title and falls back on
    # title_tag.  Set the title column to be that value for the conversion and
    # erase title_tag
    for file_type, path, item in device_items:
        if 'title_tag' in item:
            if not item['title']:
                item['title'] = item['title_tag']
            del item['title_tag']

    # list that contains tuples in the form of
    # (metadata_column_name, device_item_key
    column_map = [
        ('duration', 'duration'),
        ('album', 'album'),
        ('album_artist', 'album_artist'),
        ('album_tracks', 'album_tracks'),
        ('artist', 'artist'),
        ('screenshot_path', 'screenshot'),
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

    filenames_seen = set()

    for new_name, old_name in column_map:
        insert_columns.append(new_name)

    next_id = databaseupgrade.get_next_id(cursor)
    for file_type, path, old_item in device_items:
        has_drm = old_item['has_drm']
        if path in filenames_seen:
            # duplicate filename, just skip this data
            continue
        else:
            filenames_seen.add(path)
        OLD_ITEM_PRIORITY = 10
        # Make an entry in the metadata_status table.  We're not sure if
        # mutagen completed successfully or not, so we just call its status
        # SKIPPED.  moviedata_status is based on the old mdp_state column
        moviedata_status = mdp_state_map[old_item.get('mdp_state')]
        if moviedata_status == 'N':
            current_processor = u'movie-data'
        else:
            current_processor = None
        sql = ("INSERT INTO metadata_status "
               "(id, path, current_processor, mutagen_status, "
               "moviedata_status, echonest_status, net_lookup_enabled, "
               "mutagen_thinks_drm, max_entry_priority) "
               "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
        cursor.execute(sql, (next_id, path, current_processor, 'S',
                             moviedata_status, 'N', False, has_drm,
                             OLD_ITEM_PRIORITY))
        status_id = next_id
        next_id += 1

        # Make an entry in the metadata table with the metadata that was
        # stored.  We don't know if it came from mutagen, movie data, torrent
        # data or wherever, so we use "old-item" as the source and give it a
        # low priority.
        values = [next_id, status_id, file_type, 'old-item', 10, False]
        for new_name, old_name in column_map:
            value = old_item.get(old_name)
            if value == '':
                value = None
            values.append(value)

        sql = "INSERT INTO metadata (%s) VALUES (%s)" % (
            ', '.join(insert_columns),
            ', '.join('?' for i in xrange(len(insert_columns))))
        cursor.execute(sql, values)
        next_id += 1


        # We need to alter the device info to:
        #   - drop the columns now handled by metadata_status
        #   - transform the cover art path to match our new system
        #   - make column names match the keys in MetadataManager.get_metadata()
        #   - add a new column for torrent titles

        if 'cover_art' in old_item:
            self.upgrade_cover_art(old_item, cover_art_dir)
        if 'screenshot' in old_item:
            old_item['screenshot_path'] = old_item.pop('screenshot')
        if 'mdp_state' in old_item:
            del old_item['mdp_state']
        if 'metadata_version' in old_item:
            del old_item['metadata_version']

def upgrade_cover_art(device_item, cover_art_dir):
    """Drop the cover_art field and move cover art to a filename based on the
    album
    """

    if 'album' not in device_item or 'cover_art' not in device_item:
        return
    cover_art_path = device_item.pop('cover_art')
    # quote the filename using the same logic as
    # filetags.calc_cover_art_filename()
    dest_filename = urllib.quote(device_item['album'].encode('utf-8'),
                                 safe=' ,.')
    dest_path = os.path.join(cover_art_dir, dest_filename)
    if not os.path.exists(dest_path):
        try:
            shutil.move(cover_art_path, dest_path)
        except StandardError:
            logging.warn("upgrade167: Error moving %s -> %s", cover_art_path,
                         dest_path)

def handle_failed_upgrade(cursor, json_db):
    # make a metadata_status row for each item in the database as if they were
    # just added

    sql = ("INSERT INTO metadata_status "
           "(path, current_processor, mutagen_status, moviedata_status, "
           "echonest_status, net_lookup_enabled, mutagen_thinks_drm, "
           "max_entry_priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")

    net_lookup_enabled = app.config.get(prefs.NET_LOOKUP_BY_DEFAULT)
    STATUS_NOT_RUN = 'N'

    for file_type in (u'audio', u'video', u'other'):
        if file_type not in json_db:
            continue
        for path in json_db[file_type].keys():
           values = (path, u'mutagen', STATUS_NOT_RUN, STATUS_NOT_RUN,
                     STATUS_NOT_RUN, net_lookup_enabled, False, 0)
           cursor.execute(sql, values)
