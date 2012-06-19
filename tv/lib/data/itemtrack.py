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

"""miro.data.itemtrack -- Track Items in the database
"""
import collections
import weakref

from miro import app
from miro import schema
from miro import signals
from miro import util
from miro.data import item

ItemTrackerCondition = util.namedtuple(
    "ItemTrackerCondition",
    "table column sql values",

    """ItemTrackerCondition defines one term for the WHERE clause of a query.

    :attribute table: table that contains column
    :attribute column: column that this condition refers to.  If this changes
    in the DB, then we should re-run the query.
    :attribute sql: sql string for the clause
    :attribute values: list of values to use to fill in sql
    """)

ItemTrackerOrderBy = util.namedtuple(
    "ItemTrackerOrderBy",
    "table column descending",

    """ItemTrackerOrderBy defines one term for the ORDER BY clause of a query.

    :attribute table: table that contains column
    :attribute column: column to sort on
    :attribute descending: should we add the DESC clause?
    """)

class ItemTrackerQuery(object):
    """Define the query used to get items for ItemTracker."""
    def __init__(self):
        self.conditions = []
        self.order_by = [ItemTrackerOrderBy('item', 'id', False)]

    def _parse_column(self, column):
        """Parse a column specification.

        Returns a (table, column) tuple.  If the table is explicitly
        specified, we will use that.  If not, we will default to item.
        """
        if '.' in column:
            return column.split('.', 1)
        else:
            return ('item', column)

    def add_condition(self, column, operator, value):
        """Add a condition to the WHERE clause

        column, operator, and value work together to create the clause.  For
        example to add "feed_id = ?" and have 100 be the value for the "?",
        then use "feed_id", "=", 100 for column, operator, and value.
        """
        table, column = self._parse_column(column)
        sql = "%s.%s %s ?" % (table, column, operator)
        cond = ItemTrackerCondition(table, column, sql, (value,))
        self.conditions.append(cond)

    def add_complex_condition(self, column, sql, values):
        """Add a complex condition to the WHERE clause

        This method can be used to add conditions that don't fit into the
        "<column> <op> ?" form.

        NOTE: this doesn't support all possible conditions, since some may
        depend on multiple columns, or None.  But this is good enough for how
        we use it.

        :param column: column that this condition depends on
        :param sql: sql that defines the condition
        :param values: tuple of values to substitute into sql
        """
        table, column = self._parse_column(column)
        cond = ItemTrackerCondition(table, column, sql, values)
        self.conditions.append(cond)

    def set_order_by(self, *columns):
        """Change the ORDER BY clause.

        :param columns: list of columns name to sort by.  To do a descending
        search, prefix the name with "-".
        """
        self.order_by = []
        for column in columns:
            if column[0] == '-':
                descending = True
                column = column[1:]
            else:
                descending = False
            table, column = self._parse_column(column)
            ob = ItemTrackerOrderBy(table, column, descending)
            self.order_by.append(ob)

    def get_columns_to_track(self):
        """Get the columns that affect the results of the query """
        columns = [c.column for c in self.conditions if c.table == 'item']
        columns.extend(ob.column for ob in self.order_by if ob.table == 'item')
        return columns

    def tracking_download_columns(self):
        for c in self.conditions:
            if c.table == 'remote_downloader':
                return True
        for ob in self.order_by:
            if ob.table == 'remote_downloader':
                return True
        return False

    def execute(self, connection):
        """Run the select statement for this query

        :returns: sqlite Cursor object
        """
        sql_parts = []
        arg_list = []
        sql_parts.append("SELECT item.id FROM item")
        self._add_joins(sql_parts, arg_list)
        self._add_conditions(sql_parts, arg_list)
        self._add_order_by(sql_parts, arg_list)
        sql = ' '.join(sql_parts)
        return connection.execute(sql, arg_list)

    def _calc_tables(self):
        """Calculate which tables we need to execute the query."""
        all_tables = ([c.table for c in self.conditions] +
                      [ob.table for ob in self.order_by])
        return set(all_tables)

    def _add_joins(self, sql_parts, arg_list):
        tables = self._calc_tables()
        if 'remote_downloader' in tables:
            sql_parts.append("JOIN remote_downloader "
                             "ON remote_downloader.id=item.downloader_id")
        if 'feed' in tables:
            sql_parts.append("JOIN feed ON feed.id=item.feed_id")

    def _add_conditions(self, sql_parts, arg_list):
        if not self.conditions:
            return
        where_parts = []
        for c in self.conditions:
            where_parts.append(c.sql)
            arg_list.extend(c.values)
        sql_parts.append("WHERE %s" % ' AND '.join(where_parts))

    def _add_order_by(self, sql_parts, arg_list):
        order_by_parts = []
        for ob in self.order_by:
            if ob.descending:
                order_by_parts.append("%s.%s DESC" % (ob.table, ob.column))
            else:
                order_by_parts.append("%s.%s ASC" % (ob.table, ob.column))
        sql_parts.append("ORDER BY %s" % ', '.join(order_by_parts))

    def copy(self):
        retval = ItemTrackerQuery()
        retval.conditions = self.conditions[:]
        retval.order_by = self.order_by[:]
        return retval

class ItemTracker(signals.SignalEmitter):
    """Track items in the database

    ItemTracker is used by the frontends to implement the model for its
    TableViews for lists of items.

    ItemTracker does several things efficently to make it fast for the
    frontend:

    - Fetches ids first, then fetches row data when it's requested, or in
      idle callbacks.
    - Can efficently tell what's changed in an item list when another process
      modifies the item data

    Signals:

    - "items-changed" (changed_id_list): some items have been changed, but the
    list is the same.
    - "list-changed": items have been added, removed, or reorded in the list.
    """

    # how many rows we fetch at one time in _ensure_row_loaded()
    FETCH_ROW_CHUNK_SIZE = 25

    def __init__(self, idle_scheduler, query):
        """Create an ItemTracker

        :param idle_scheduler: function to schedule idle callback functions.
        It should input a function and schedule for it to be called during
        idletime.
        """
        signals.SignalEmitter.__init__(self)
        self.create_signal("will-change")
        self.create_signal("items-changed")
        self.create_signal("list-changed")
        self.idle_scheduler = idle_scheduler
        self.item_fetcher = item.ItemFetcher()
        self._get_connection()
        self._set_query(query)
        self._fetch_id_list()
        self._reset_row_data()
        ItemTracker._schedule_fetch_rows_during_idle(self)

    def _set_query(self, query):
        """Change our ItemTrackerQuery object."""
        self.query = query
        self.tracked_columns = set(self.query.get_columns_to_track())
        self.track_dl_columns = self.query.tracking_download_columns()

    def _fetch_id_list(self):
        """Fetch the ids for this list.

        This method assumes that self.connection has been already set up.
        """
        # Strategy here is to start a transaction, fetch only the item ids,
        # then keep it open to fetch the rest of the data.  This works great
        # an WAL mode, since writer transactions can still happen.  If we
        # can't switch to WAL mode though, this blocks the backend from
        # commiting any write transactions.  It may be possible to deadlock as
        # well.
        #
        # FIXME: use alternate strategy if we couldn't switch to wal mode.
        rowlist = self._execute_query()
        self.id_list = [r[0] for r in rowlist]
        self.id_to_index = dict((id_, i) for i, id_ in enumerate(self.id_list))

    def _reset_row_data(self):
        self.row_data = {}

    def _uncache_row_data(self, id_list):
        for id_ in id_list:
            if id_ in self.row_data:
                del self.row_data[id_]

    def _refetch_id_list(self):
        """Refetch a new id list after we already have one."""

        self.emit('will-change')
        self._fetch_id_list()
        self.emit("list-changed")

    def get_items(self):
        """Get a list of all items in sorted order."""
        return [self.get_row(i) for i in xrange(len(self.id_list))]

    def __len__(self):
        return len(self.id_list)

    def _get_connection(self):
        self.connection = app.connection_pool.get_connection()
        # We need to start a connection to make our lazy fetching of the item
        # rows work.  We need to have the same view of our data when we
        # initially fetch the id list, and when we fetch the rows later.
        self.connection.execute("BEGIN TRANSACTION")

    def _release_connection(self):
        self.connection.commit()
        app.connection_pool.release_connection(self.connection)
        self.connection = None

    def _execute_query(self):
        cursor = self.query.execute(self.connection)
        return cursor.fetchall()

    @staticmethod
    def _schedule_fetch_rows_during_idle(item_list):
        """Schedule fetch_rows_during_idle to be called some time in the
        future using idle_scheduler.

        This function avoids keeping a reference around to the ItemList.  This
        way, if other components stop using the ItemTracker before the
        callback, then we can destroy the object and skip the processing
        """
        # make a weak reference to the object to use when the callback is
        # called
        ref = weakref.ref(item_list)
        def callback():
            item_list = ref()
            if item_list is not None:
                item_list.fetch_rows_during_idle()
        item_list.idle_scheduler(callback)
        # delete original reference
        del item_list

    def fetch_rows_during_idle(self):
        for i in xrange(len(self.id_list)):
            if not self._row_loaded(i):
                # row data unloaded, call _ensure_row_loaded to load this row
                # and adjecent rows then schedule another run later
                self._ensure_row_loaded(i)
                ItemTracker._schedule_fetch_rows_during_idle(self)
                return
        # all row data is loaded.  We're all done
        self._release_connection()

    def _row_loaded(self, index):
        id_ = self.id_list[index]
        return id_ in self.row_data

    def _ensure_row_loaded(self, index):
        """Ensure that we have an entry in self._item_rows for index."""

        if self._row_loaded(index):
            # we've already loaded the row for index
            return
        rows_to_load = [index]
        # as long as we're reading from disk, load a chunk of rows instead of
        # just one.
        start_row = max(index - (self.FETCH_ROW_CHUNK_SIZE // 2), 0)
        for i in xrange(start_row, index):
            if not self._row_loaded(i):
                rows_to_load.append(i)
        for i in xrange(index+1, len(self.id_list)):
            if not self._row_loaded(i):
                rows_to_load.append(i)
                if len(rows_to_load) >= self.FETCH_ROW_CHUNK_SIZE:
                    break
        self._load_rows(rows_to_load)

    def _load_rows(self, rows_to_load):
        """Query the database to fetch a set of items and put the data in
        self.row_data

        :param rows_to_load: indexes of the rows to load.
        """
        ids_to_load = [self.id_list[i] for i in rows_to_load]
        items = self.item_fetcher.fetch_many(self.connection, ids_to_load)
        for item in items:
            pos = self.id_to_index[item.id]
            self.row_data[item.id] = item

    def get_item(self, id_):
        """Get an ItemRow for a given id.

        :raises KeyError: id_ not in this list
        """
        index = self.id_to_index[id_]
        return self.get_row(index)

    def get_row(self, index):
        """Get an ItemRow for row index.

        :raises IndexError: index out of range
        """
        self._ensure_row_loaded(index)
        id_ = self.id_list[index]
        return self.row_data[id_]

    def get_index(self, item_id):
        """Get the index of an item in the list."""
        return self.id_to_index[item_id]

    def change_query(self, new_query):
        """Change the query for this select

        This will cause the list-change signal to be emitted.

        :param new_query: ItemTrackerQuery object
        """
        self._set_query(new_query)
        self._handle_connection_after_changes()
        self._refetch_id_list()

    def _handle_connection_after_changes(self):
        """Call this if the data we're tracking has changed, either because we
        have a new query, or because the backend has updated the data.
        """
        if self.connection is not None:
            # We already have a connection and are currently fetching items
            # with it.  Finish our transaction so that we can fetch fresh
            # data.
            self.connection.commit()
        else:
            # We have released our connection.  Get a new one and schedule
            # fetching our items.
            self._get_connection()
            ItemTracker._schedule_fetch_rows_during_idle(self)

    def on_item_changes(self, message):
        """Call this when items get changed and the list needs to be
        updated.

        If the changes modify this list, either the items-changed or
        list-changed signal will be emitted.

        :param message: an ItemsChanged message
        """
        self._uncache_row_data(message.changed)
        self._handle_connection_after_changes()
        if self._could_list_change(message):
            self._refetch_id_list()
        else:
            self.emit('will-change')
            changed_ids = [id_ for id_ in message.changed
                           if id_ in self.id_to_index]
            self.emit('items-changed', changed_ids)

    def _could_list_change(self, message):
        """Calculate if an ItemsChanged means the list may have changed."""
        return bool(message.added or message.removed or
                    (message.dlstats_changed and self.track_dl_columns) or
                    message.changed_columns.intersection(self.tracked_columns))
