# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""``miro.iteminfocache`` -- Cache ItemInfo objects to speed up TrackItem
calls.

TrackItem calls result in the largest DB queries and therefore should be
optimized well.  This module handles remembering ItemInfo objects, both while
Miro is running and between runs.  This results in 2 speedups:

    1) We don't have to rebuild the ItemInfo objects, which takes a sizeable
    amount of time.

    2) We can avoid building Item objects by just fetching the ids of the
    result set, then returning the ItemInfos for those ids.  (Actually we also
    need to build IconCache objects and Feed objects in order to create
    ItemInfos).

The general strategy is to just dumbly pickle the data and if we notice any
errors, or if the DB version changes, throw away the cache and rebuild.  We
use a lot of direct SQL queries in this code, borrowing app.db's cursor.  This
is slightly naughty, but results in fast peformance.
"""

import cPickle
import logging

from miro import app
from miro import eventloop
from miro import messages
from miro import models
from miro import schema

class ItemInfoCache(object):
    # how often should we save cache data to the DB? (in seconds)
    SAVE_INTERVAL = 30
    VERSION_KEY = 'item_info_cache_db_version'

    def __init__(self):
        self.id_to_info = None
        did_failsafe_load = False
        try:
            self._quick_load()
        except (StandardError, cPickle.UnpicklingError), e:
            logging.warn("Error loading item info cache: %s", e)
        if self.id_to_info is None:
            self._failsafe_load()
            # the current data is suspect, delete it
            app.db.cursor.execute("DELETE FROM item_info_cache")
            did_failsafe_load = True
        app.db.set_variable(self.VERSION_KEY, self.version())
        self._reset_changes()
        self._save_dc = None
        if did_failsafe_load:
            # Need to save the cache data we just created
            self._infos_added = self.id_to_info.copy()
            self.schedule_save_to_db()

    def version(self):
        return "%s-%s" % (schema.VERSION, messages.ItemInfo.VERSION)

    def _info_to_blob(self, info):
        return buffer(cPickle.dumps(info))

    def _blob_to_info(self, blob):
        return cPickle.loads(str(blob))

    def _quick_load(self):
        """Load ItemInfos using the item_info_cache table

        This is much faster than _failsafe_load(), but could result in errors.
        """
        saved_db_version = app.db.get_variable(self.VERSION_KEY)
        if saved_db_version == self.version():
            quick_load_values = {}
            app.db.cursor.execute("SELECT id, pickle FROM item_info_cache")
            for row in app.db.cursor:
                quick_load_values[row[0]] = self._blob_to_info(row[1])
            # double check that we have the right number of rows
            app.db.cursor.execute("SELECT COUNT(*) from item")
            item_count = app.db.cursor.fetchone()[0]
            if item_count == len(quick_load_values):
                self.id_to_info = quick_load_values

    def _failsafe_load(self):
        """Load ItemInfos using Item objects.

        This is much slower than _quick_load(), but more robust.
        """

        self.id_to_info = {}
        for item in models.Item.make_view():
            self.id_to_info[item.id] = messages.ItemInfo(item)

    def schedule_save_to_db(self):
        if self._save_dc is None:
            self._save_dc = eventloop.add_timeout(self.SAVE_INTERVAL,
                    self.save, 'save item info cache')

    def _reset_changes(self):
        self._infos_added = {}
        self._infos_changed = {}
        self._infos_deleted = set()

    def save(self):
        app.db.cursor.execute("BEGIN TRANSACTION")
        try:
            self._run_inserts()
            self._run_updates()
            self._run_deletes()
        except:
            app.db.cursor.execute("ROLLBACK TRANSACTION")
            raise
        else:
            app.db.cursor.execute("COMMIT TRANSACTION")
        self._reset_changes()

    def _run_inserts(self):
        if not self._infos_added:
            return
        sql = "INSERT INTO item_info_cache (id, pickle) VALUES (?, ?)"
        values = ((id, self._info_to_blob(info)) for (id,
            info) in self._infos_added.iteritems())
        app.db.cursor.executemany(sql, values)

    def _run_updates(self):
        if not self._infos_changed:
            return
        sql = "UPDATE item_info_cache SET PICKLE=? WHERE id=?"
        values = ((self._info_to_blob(info), id) for (id, info) in
                self._infos_changed.iteritems())
        app.db.cursor.executemany(sql, values)

    def _run_deletes(self):
        if not self._infos_deleted:
            return
        id_list = ', '.join(self._infos_deleted)
        app.db.cursor.execute("DELETE FROM item_info_cache "
                "WHERE id IN (%s)" % id_list)

    def iter_infos(self, view):
        """Given a view for Item objects, return the ItemInfos for each result

        This method is optimized to avoid constructing Item objects.
        """
        if view.klass not in (models.Item, models.FileItem):
            raise ValueError("view is not for Item")
        return (self.id_to_info[id_] for id_ in view.id_iter())

    def item_created(self, item):
        info = messages.ItemInfo(item)
        self.id_to_info[item.id] = info
        self._infos_added[item.id] = info
        self.schedule_save_to_db()

    def item_changed(self, item):
        info = messages.ItemInfo(item)
        self.id_to_info[item.id] = info
        if item.id in self._infos_added:
            # no need to update if we insert the new values
            self._infos_added[item.id] = info
        else:
            self._infos_changed[item.id] = info
        self.schedule_save_to_db()

    def item_removed(self, item):
        del self.id_to_info[item.id]

        if item.id in self._infos_added:
            del self._infos_added[item.id]
            # no need to delete if we don't add the row in the 1st place
        elif item.id in self._infos_changed:
            # no need to change, since we're going to delete it
            del self._infos_changed[item.id]
            self._infos_deleted.add(item.id)
        else:
            self._infos_deleted.add(item.id)
        self.schedule_save_to_db()

def create_sql():
    """Get the SQL needed to create the tables we need for the ItemInfo cache
    """
    return "CREATE TABLE item_info_cache(id INTEGER PRIMARY KEY, pickle BLOB)"
