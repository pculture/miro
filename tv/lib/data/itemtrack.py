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
import logging
import string
import sqlite3
import random
import re
import weakref

from miro import app
from miro import models
from miro import prefs
from miro import schema
from miro import signals
from miro import util
from miro.data import item
from miro.gtcache import gettext as _

ItemTrackerCondition = util.namedtuple(
    "ItemTrackerCondition",
    "columns sql values",

    """ItemTrackerCondition defines one term for the WHERE clause of a query.

    :attribute columns: list of (table, column) tuples that that this
    condition refers to.  If any of these change in the DB, then we should
    re-run the query.
    :attribute sql: sql string for the clause
    :attribute values: list of values to use to fill in sql
    """)

ItemTrackerOrderBy = util.namedtuple(
    "ItemTrackerOrderBy",
    "columns sql",

    """ItemTrackerOrderBy defines one term for the ORDER BY clause of a query.

    :attribute columns: list of (table, column) tuples used in the query
    :attribute sql: sql expression
    """)

class ItemTrackerQueryBase(object):
    """Query used to select item ids for ItemTracker.  """

    select_info = item.ItemSelectInfo()

    def __init__(self):
        self.conditions = []
        self.match_string = None
        self.order_by = None
        self.limit = None

    def join_sql(self, table, join_type='LEFT JOIN'):
        return self.select_info.join_sql(table, join_type=join_type)

    def table_name(self):
        return self.select_info.table_name

    def could_list_change(self, message):
        """Given a ItemChanges message, could the id list change?
        """
        if message.added or message.removed:
            return True
        if message.changed_columns.intersection(self.get_columns_to_track()):
            return True
        return False

    def _parse_column(self, column):
        """Parse a column specification.

        Returns a (table, column) tuple.  If the table is explicitly
        specified, we will use that.  If not, we will default to item.
        """
        if '.' in column:
            (table, column) = column.split('.', 1)
            if not self.select_info.can_join_to(table):
                raise ValueError("Can't join to %s" % table)
            return (table, column)
        else:
            return (self.table_name(), column)

    def add_condition(self, column, operator, value):
        """Add a condition to the WHERE clause

        column, operator, and value work together to create the clause.  For
        example to add "feed_id = ?" and have 100 be the value for the "?",
        then use "feed_id", "=", 100 for column, operator, and value.
        """
        table, column = self._parse_column(column)
        sql = "%s.%s %s ?" % (table, column, operator)
        cond = ItemTrackerCondition([(table, column)], sql, (value,))
        self.conditions.append(cond)

    def set_search(self, search_string):
        """Set the full-text search to use for this item tracker."""
        if search_string is None:
            self.match_string = None
            return
        # parse search_string and make a string for the sqlite3 match command
        # We do the following:
        #  - lowercase the terms to ensure that they don't contain any sqlite3
        #  fts operators
        #  - remove the any non-word characters from search_string
        #  - add a prefix search to the last term, since the user can still be
        #  typing it out.
        terms = re.findall("\w+", search_string.lower())
        if 'torrent' in terms:
            # as a special case, the search string "torrent" matches torrent
            # items
            terms.remove('torrent')
            self.add_condition("remote_downloader.type", '=', 'BitTorrent')
            if not terms:
                self.match_string = None
                return
        self.match_string = " ".join(terms)
        if self.match_string and search_string[-1] != ' ':
            self.match_string += "*"

    def add_complex_condition(self, columns, sql, values=()):
        """Add a complex condition to the WHERE clause

        This method can be used to add conditions that don't fit into the
        "<column> <op> ?" form.

        NOTE: this doesn't support all possible conditions, since some may
        depend on multiple columns, or None.  But this is good enough for how
        we use it.

        :param columns: list of columns that this condition depends on
        :param sql: sql that defines the condition
        :param values: tuple of values to substitute into sql
        """
        columns = [self._parse_column(c) for c in columns]
        cond = ItemTrackerCondition(columns, sql, values)
        self.conditions.append(cond)

    def set_order_by(self, columns, collations=None):
        """Change the ORDER BY clause.

        :param columns: list of columns name to sort by.  To do a descending
        search, prefix the name with "-".
        :param collations: list of collations to use to sort by.  None
        specifies the default collation.  Otherwise, there must be 1 value for
        each column and it should specify the collation to use for that
        column.
        """
        if collations is None:
            collations = (None,) * len(columns)
        elif len(collations) != len(columns):
            raise ValueError("sequence length mismatch")

        sql_parts = []
        order_by_columns = []
        for column, collation in zip(columns, collations):
            if column[0] == '-':
                descending = True
                column = column[1:]
            else:
                descending = False
            table, column = self._parse_column(column)
            order_by_columns.append((table, column))
            sql_parts.append(self._order_by_expression(table, column,
                                                       descending, collation))
        self.order_by = ItemTrackerOrderBy(order_by_columns,
                                           ', '.join(sql_parts))

    def set_complex_order_by(self, columns, sql):
        """Change the ORDER BY clause to a complex SQL expression

        :param columns: list of column names refered to in sql
        :param sql: SQL to execute
        """
        order_by_columns = [self._parse_column(c) for c in columns]
        self.order_by = ItemTrackerOrderBy(order_by_columns, sql)

    def _order_by_expression(self, table, column, descending, collation):
        parts = []
        parts.append("%s.%s" % (table, column))
        if collation is not None:
            parts.append("collate %s" % collation)
        if descending:
            parts.append("DESC")
        else:
            parts.append("ASC")
        return " ".join(parts)

    def set_limit(self, limit):
        self.limit = limit

    def get_columns_to_track(self):
        """Get the columns that affect the results of the query """
        columns = set()
        for c in self.conditions:
            for table, column in c.columns:
                if table == self.table_name():
                    columns.add(column)
                else:
                    columns.add(self.select_info.item_join_column(table))
        if self.order_by:
            columns.update(column for (table, column)
                           in self.order_by.columns
                           if table == self.table_name())
        return columns

    def get_other_tables_to_track(self):
        """Get tables other than item that could affect this query."""
        other_tables = set()
        for c in self.conditions:
            other_tables.update(table for table, column in c.columns)
        if self.order_by:
            other_tables.update(table for (table, column)
                                in self.order_by.columns)
        other_tables.discard('item')
        return other_tables

    def select_ids(self, connection):
        """Run the select statement for this query

        :returns: list of item ids
        """
        sql_parts = []
        arg_list = []
        sql_parts.append("SELECT %s.id FROM %s" %
                         (self.table_name(), self.table_name()))
        self._add_joins(sql_parts, arg_list)
        self._add_conditions(sql_parts, arg_list)
        self._add_order_by(sql_parts, arg_list)
        self._add_limit(sql_parts, arg_list)
        sql = ' '.join(sql_parts)
        logging.debug("ItemTracker: running query %s (%s)", sql, arg_list)
        item_ids = [row[0] for row in connection.execute(sql, arg_list)]
        logging.debug("ItemTracker: done running query")
        return item_ids

    def select_item_data(self, connection):
        """Run the select statement for this query

        :returns: list of column data for all items in this query.  The
        columns will match the columns specified in our select_info.
        """
        sql_parts = []
        arg_list = []

        select_columns = ', '.join("%s.%s " % (col.table, col.column)
                                   for col in
                                   self.select_info.select_columns)
        sql_parts.append("SELECT %s" % select_columns)
        sql_parts.append("FROM %s " % self.table_name())
        self._add_joins(sql_parts, arg_list, include_select_columns=True)
        self._add_conditions(sql_parts, arg_list)
        self._add_order_by(sql_parts, arg_list)
        self._add_limit(sql_parts, arg_list)
        sql = ' '.join(sql_parts)
        logging.debug("ItemTracker: running query %s (%s)", sql, arg_list)
        item_data = list(connection.execute(sql, arg_list))
        logging.debug("ItemTracker: done running query")
        return item_data

    def _add_joins(self, sql_parts, arg_list, include_select_columns=False):
        join_tables = set()
        for c in self.conditions:
            join_tables.update(table for table, column in c.columns)
        if self.order_by:
            join_tables.update(table for (table, column)
                               in self.order_by.columns)
        if include_select_columns:
            join_tables.update(col.table
                               for col in self.select_info.select_columns)
        join_tables.discard(self.table_name())
        for table in join_tables:
            sql_parts.append(self.join_sql(table))
        if self.match_string:
            sql_parts.append(self.join_sql('item_fts', join_type='JOIN'))

    def _add_all_joins(self, sql_parts, arg_list):
        joins_for_data = set(col.table
                             for col in self.select_info.select_columns
                             if col.table != self.table_name())
        joins_for_conditions = set()
        for c in self.conditions:
            joins_for_conditions.update(table for table, column in c.columns)
        if self.order_by:
            joins_for_conditions.update(table for (table, column)
                                        in self.order_by.columns)
        for table in joins_for_data:
            if table != self.table_name():
                sql_parts.append(self.join_sql(table, 'LEFT JOIN'))
        for table in joins_for_conditions:
            if table != self.table_name() and table not in joins_for_data:
                sql_parts.append(self.join_sql(table))
        if self.match_string:
            sql_parts.append(self.join_sql('item_fts'))

    def _add_conditions(self, sql_parts, arg_list):
        if not (self.conditions or self.match_string):
            return
        where_parts = []
        for c in self.conditions:
            where_parts.append(c.sql)
            arg_list.extend(c.values)
        if self.match_string:
            where_parts.append("item_fts MATCH ?")
            arg_list.append(self.match_string)
        sql_parts.append("WHERE %s" % ' AND '.join(
            '(%s)' % part for part in where_parts))

    def _add_order_by(self, sql_parts, arg_list):
        if self.order_by:
            sql_parts.append("ORDER BY %s" % self.order_by.sql)

    def _add_limit(self, sql_parts, arg_list):
        if self.limit is not None:
            sql_parts.append("LIMIT %s" % self.limit)

    def copy(self):
        retval = self.__class__()
        retval.conditions = self.conditions[:]
        retval.order_by = self.order_by
        retval.match_string = self.match_string
        return retval

class ItemTrackerQuery(ItemTrackerQueryBase):
    """ItemTrackerQuery for items in the main db."""

    def could_list_change(self, message):
        """Given a ItemChanges message, could the id list change?
        """
        other_tables = self.get_other_tables_to_track()
        if message.dlstats_changed and 'remote_downloader' in other_tables:
            return True
        if message.playlists_changed and 'playlist_item_map' in other_tables:
            return True
        return ItemTrackerQueryBase.could_list_change(self, message)

class DeviceItemTrackerQuery(ItemTrackerQueryBase):
    """ItemTrackerQuery for DeviceItems."""

    select_info = item.DeviceItemSelectInfo()

class SharingItemTrackerQuery(ItemTrackerQueryBase):
    """ItemTrackerQuery for SharingItems."""

    select_info = item.SharingItemSelectInfo()

    def tracking_playlist_map(self):
        for c in self.conditions:
            for table, column in c.columns:
                if table == 'sharing_item_playlist_map':
                    return True
        return False

    def could_list_change(self, message):
        if message.changed_playlists and self.tracking_playlist_map():
            return True
        else:
            return ItemTrackerQueryBase.could_list_change(self, message)

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

    def __init__(self, idle_scheduler, query, item_source):
        """Create an ItemTracker

        :param idle_scheduler: function to schedule idle callback functions.
        It should input a function and schedule for it to be called during
        idletime.
        :param query: ItemTrackerQuery to use
        :param item_source: ItemSource to use.
        """
        signals.SignalEmitter.__init__(self)
        self.create_signal("will-change")
        self.create_signal("items-changed")
        self.create_signal("list-changed")
        self.idle_scheduler = idle_scheduler
        self.idle_work_scheduled = False
        self.item_fetcher = None
        self.item_source = item_source
        self._db_retry_callback_pending = False
        self._set_query(query)
        self._fetch_id_list()
        if self.item_fetcher is not None:
            self._schedule_idle_work()

    def is_valid(self):
        """Is this item list valid?

        This will return True until destroy() is called.
        """
        return self.id_list is not None

    def destroy(self):
        """Call this when you're done with the ItemTracker

        We will release any open connections to the database and reset our
        self to an empty list.
        """
        self._destroy_item_fetcher()
        self.id_list = self.id_to_index = self.row_data = None

    def make_item_fetcher(self, connection, id_list):
        """Make an ItemFetcher to use.

        :param connection: sqlite Connection to use.  We will return data from
        this connection without commiting any pending read transaction.
        :param id_list: list of ids that we will have to fetch.
        """
        if self.item_source.wal_mode():
            klass = ItemFetcherWAL
        else:
            klass = ItemFetcherNoWAL
        return klass(connection, self.item_source, id_list)

    def _destroy_item_fetcher(self):
        if self.item_fetcher:
            self.item_fetcher.destroy()
            self.item_fetcher = None

    def _run_db_error_dialog(self):
        if self._db_retry_callback_pending:
            return
        gettext_values = {
            "appname": app.config.get(prefs.SHORT_APP_NAME)
        }
        title = _("%(appname)s database query failed", gettext_values)
        description = _("%(appname)s was unable to read from its database.",
                        gettext_values)
        app.db_error_handler.run_dialog(title, description,
                                        self._retry_after_db_error)

    def _retry_after_db_error(self):
        self._db_retry_callback_pending = False
        self._refetch_id_list()

    def _set_query(self, query):
        """Change our ItemTrackerQuery object."""
        self.query = query

    def _fetch_id_list(self):
        """Fetch the ids for this list.  """
        self._destroy_item_fetcher()
        try:
            connection = self.item_source.get_connection()
            connection.execute("BEGIN TRANSACTION")
            self.id_list = self.query.select_ids(connection)
            self.item_fetcher = self.make_item_fetcher(connection, self.id_list)
        except sqlite3.DatabaseError, e:
            logging.warn("%s while fetching items", e, exc_info=True)
            self._make_empty_list_after_db_error()
        self.id_to_index = dict((id_, i) for i, id_ in enumerate(self.id_list))
        self.row_data = {}

    def _make_empty_list_after_db_error(self):
        self.id_list = []
        self._run_db_error_dialog()
        self.item_fetcher = None

    def _schedule_idle_work(self):
        """Schedule do_idle_work to be called some time in the
        future using idle_scheduler.
        """
        if not self.idle_work_scheduled:
            self.idle_scheduler(self.do_idle_work)
            self.idle_work_scheduled = True

    def do_idle_work(self):
        self.idle_work_scheduled = False
        if self.item_fetcher is None:
            # destroy() was called while the idle callback was still
            # scheduled.  Just return.
            return
        for i in xrange(len(self.id_list)):
            if not self._row_loaded(i):
                # row data unloaded, call _ensure_row_loaded to load this row
                # and adjecent rows then schedule another run later
                self._ensure_row_loaded(i)
                self._schedule_idle_work()
                return
        # no rows need loading
        self.item_fetcher.done_fetching()

    def _uncache_row_data(self, id_list):
        for id_ in id_list:
            if id_ in self.row_data:
                del self.row_data[id_]

    def _refetch_id_list(self, send_signals=True):
        """Refetch a new id list after we already have one."""

        if send_signals:
            self.emit('will-change')
        self._fetch_id_list()
        if send_signals:
            self.emit("list-changed")

    def get_items(self):
        """Get a list of all items in sorted order."""
        return [self.get_row(i) for i in xrange(len(self.id_list))]

    def get_playable_ids(self):
        """Get a list of ids for items that can be played."""
        # If we have loaded all items, then we can just use that data
        if not self.idle_work_scheduled:
            return [i.id for i in self.get_items() if i.is_playable]
        else:
            try:
                return self.item_fetcher.select_playable_ids()
            except sqlite3.DatabaseError, e:
                logging.warn("%s in select_playable_ids()", e, exc_info=True)
                self._run_db_error_dialog()
                return []

    def has_playables(self):
        """Can we play any items from this item list?"""
        if not self.idle_work_scheduled:
            return any(i for i in self.get_items() if i.is_playable)
        else:
            try:
                return self.item_fetcher.select_has_playables()
            except sqlite3.DatabaseError, e:
                logging.warn("%s in select_has_playables()", e, exc_info=True)
                self._run_db_error_dialog()
                return False

    def __len__(self):
        return len(self.id_list)

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
        ids_to_load = set(self.id_list[i] for i in rows_to_load)
        try:
            items = self.item_fetcher.fetch_items(ids_to_load)
        except sqlite3.DatabaseError, e:
            logging.warn("%s while fetching items", e, exc_info=True)
            items = [item.DBErrorItemInfo(item_id) for item_id in ids_to_load]
            self._run_db_error_dialog()
        returned_ids = set()
        for item_info in items:
            pos = self.id_to_index[item_info.id]
            self.row_data[item_info.id] = item_info
            returned_ids.add(item_info.id)
        if returned_ids != ids_to_load:
            extra = tuple(returned_ids - ids_to_load)
            missing = tuple(ids_to_load - returned_ids)
            msg = ("ItemFetcher didn't return the correct rows "
                   "(extra: %s, missing: %s)" % (extra, missing))
            raise AssertionError(msg)

    def item_in_list(self, item_id):
        """Test if an item is in the list.
        """
        return item_id in self.id_to_index

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
        try:
            id_ = self.id_list[index]
        except IndexError:
            # re-raise the error with a bit more information
            raise IndexError("%s is out of range" % index)
        return self.row_data[id_]

    def get_first_item(self):
        return self.get_row(0)

    def get_last_item(self):
        return self.get_row(len(self)-1)

    def get_index(self, item_id):
        """Get the index of an item in the list."""
        return self.id_to_index[item_id]

    def change_query(self, new_query):
        """Change the query for this select

        This will cause the list-change signal to be emitted.

        :param new_query: ItemTrackerQuery object
        """
        self._set_query(new_query)
        self._refetch_id_list()

    def on_item_changes(self, message):
        """Call this when items get changed and the list needs to be
        updated.

        If the changes modify this list, either the items-changed or
        list-changed signal will be emitted.

        :param message: an ItemChanges message
        """
        self.emit('will-change')
        changed_ids = [item_id for item_id in message.changed
                       if self.item_in_list(item_id)]
        self._uncache_row_data(changed_ids)
        if self._could_list_change(message):
            self._refetch_id_list(send_signals=False)
            self.emit("list-changed")
        else:
            if len(self.id_list) == 0:
                # special case when the list is empty.  This avoids accessing
                # item_fetcher after _make_empty_list_after_db_error() is
                # called.
                self.emit("list-changed")
                return
            try:
                need_refetch = self.item_fetcher.refresh_items(changed_ids)
            except sqlite3.DatabaseError, e:
                logging.warn("%s while refreshing items", e, exc_info=True)
                self._make_empty_list_after_db_error()
                self.emit("list-changed")
                return
            if not need_refetch:
                self.emit('items-changed', changed_ids)
            else:
                self._refetch_id_list(send_signals=False)
                self.emit("list-changed")

    def _could_list_change(self, message):
        """Calculate if an ItemChanges means the list may have changed."""
        return self.query.could_list_change(message)

class ItemFetcher(object):
    """Create ItemInfo objects for ItemTracker

    ItemFetcher gets constructed with the connection that ItemTracker used to
    select the ids for the item list along with those ids.  It's responsible
    for fetching data and creating ItemInfo objects as they are needed.

    The connection that gets passed to ItemFetcher still has a read
    transaction open from the query that selected the item ids.  ItemFetcher
    should ensure that the data it fetches to create the ItemInfo is from that
    same transaction.  ItemFetcher should take ownership of the connection and
    ensure that it gets released.

    We handle this 2 ways.  If we are using the WAL journal mode, then we can
    just keep the transaction open, since it won't block writers from
    committing data.

    If we aren't using WAL journal mode, then we select the data we need into
    a temporary table to freeze it in place.  This is slower than the WAL
    version, but not much.

    The two strategies are implemented by the 2 subclasses of ItemFetcher:
    ItemFetcherWAL and ItemFetcherNoWAL.

    Finally ItemFetcher has 2 methods, select_playable_ids and
    select_has_playables() which figure out which items in the list are
    playable using an SQL select.  This is needed because we want to calculate
    this without having to load all the ItemInfos in the list.
    """

    def __init__(self, connection, item_source, id_list):
        self.connection = connection
        self.item_source = item_source
        self.id_list = id_list

    def select_columns(self):
        return self.item_source.select_info.select_columns

    def join_sql(self):
        return self.item_source.select_info.join_sql()

    def table_name(self):
        return self.item_source.select_info.table_name

    def path_column(self):
        return self.item_source.select_info.path_column

    def release_connection(self):
        if self.connection is not None:
            self.item_source.release_connection(self.connection)
            self.connection = None

    def destroy(self):
        """Called when the ItemFetcher is no longer needed.  Release any
        resources.
        """
        pass

    def done_fetching(self):
        """Called when ItemTracker has fetched all the ItemInfos in its list

        ItemFetcher should release resources that are no longer needed,
        however it should be ready to fetch items again if refresh_items() is
        called.
        """
        pass

    def fetch_items(self, item_ids):
        """Get a list of ItemInfo

        :param item_ids: list of ids to fetch
        :returns: list of ItemInfo objects.  This is not necessarily in the
        same order as item_ids.
        """
        raise NotImplementedError()

    def refresh_items(self, changed_ids):
        """Refresh item data.

        Normally ItemFetcher uses data from the read transaction that the
        connection it was created with was in.  Use this method to force
        ItemFetcher to use new data for a list of items.

        :returns True: if we can't refresh the items and we should refetch the
        entire list instead.  This is a hack to work around #19823
        """
        raise NotImplementedError()

    def select_playable_ids(self):
        """Calculate which items are playable using a select statement

        :returns: list of item ids
        """
        raise NotImplementedError()

    def select_has_playables(self):
        """Calculate if any items are playable using a select statement.

        :returns: True/False
        """
        raise NotImplementedError()

class ItemFetcherWAL(ItemFetcher):
    def __init__(self, connection, item_source, id_list):
        ItemFetcher.__init__(self, connection, item_source, id_list)
        self._prepare_sql()
        self.item_count = self.calc_item_count()
        self.max_item_id = self.calc_max_item_id()

    def destroy(self):
        self.release_connection()

    def done_fetching(self):
        # We can safely finish the read transaction here
        self.connection.commit()

    def calc_item_count(self):
        sql = "SELECT COUNT(1) FROM %s" % self.table_name()
        return self.connection.execute(sql).fetchone()[0]

    def calc_max_item_id(self):
        sql = "SELECT MAX(id) FROM %s" % self.table_name()
        return self.connection.execute(sql).fetchone()[0]

    def _prepare_sql(self):
        """Get an SQL statement ready to fire when fetch() is called.

        The statement will be ready to go, except the WHERE clause will not be
        present, since we can't know that in advance.
        """
        columns = ['%s.%s' % (c.table, c.column)
                   for c in self.select_columns()]
        self._sql = ("SELECT %s FROM %s %s" %
                     (', '.join(columns), self.table_name(), self.join_sql()))

    def fetch_items(self, id_list):
        """Create Item objects."""
        where = ("WHERE %s.id in (%s)" %
                 (self.table_name(), ', '.join(str(i) for i in id_list)))
        sql = ' '.join((self._sql, where))
        cursor = self.connection.execute(sql)
        return [self.item_source.make_item_info(row) for row in cursor]

    def refresh_items(self, changed_ids):
        # We ignore changed_ids and just start a new transaction which will
        # refresh all the data.
        self.connection.commit()
        self.connection.execute("BEGIN TRANSACTION")
        # check if an item has been added/removed from the DB now that we have
        # a new transaction.  This can happen if the backend changes some
        # items sends an ItemsChanged message, then deletes them before we
        # process the message (see #19823)

        new_max_id = self.calc_max_item_id()
        new_item_count = self.calc_item_count()
        # checks for items have been added
        if new_max_id != self.max_item_id:
            self.max_item_id = new_max_id
            # update item_count since that could have changed too
            self.item_count = new_item_count
            return True
        # given that items haven't been added, we can use the total number of
        # items to check if any have been deleted
        if new_item_count != self.item_count:
            self.item_count = new_item_count
            return True
        # nothing has changed, we can return false
        return False

    def select_playable_ids(self):
        sql = ("SELECT id FROM %s "
               "WHERE %s IS NOT NULL AND "
               "file_type != 'other' AND "
               "id in (%s)" % 
               (self.table_name(), self.path_column(),
                ','.join(str(id_) for id_ in self.id_list)))
        return [row[0] for row in self.connection.execute(sql)]

    def select_has_playables(self):
        sql = ("SELECT EXISTS (SELECT 1 FROM %s "
               "WHERE %s IS NOT NULL AND "
               "file_type != 'other' AND "
               "id in (%s))" %
               (self.table_name(), self.path_column(),
                ','.join(str(id_) for id_ in self.id_list)))
        return self.connection.execute(sql).fetchone()[0] == 1

class ItemFetcherNoWAL(ItemFetcher):
    def __init__(self, connection, item_source, id_list):
        ItemFetcher.__init__(self, connection, item_source, id_list)
        self._make_temp_table()
        self._select_into_temp_table(id_list)
        self.connection.commit()

    def _make_temp_table(self):
        randstr = ''.join(random.choice(string.letters) for i in xrange(10))
        self.temp_table_name = 'itemtmp_' + randstr
        col_specs = ["%s %s" % (ci.attr_name, ci.sqlite_type())
                     for ci in self.select_columns()]
        create_sql = ("CREATE TABLE temp.%s(%s)" %
               (self.temp_table_name, ', '.join(col_specs)))
        index_sql = ("CREATE UNIQUE INDEX temp.%s_id ON %s (id)" %
                     (self.temp_table_name, self.temp_table_name))
        self.connection.execute(create_sql)
        self.connection.execute(index_sql)

    def _select_into_temp_table(self, id_list):
        template = string.Template("""\
INSERT OR REPLACE INTO $temp_table_name($dest_columns)
SELECT $source_columns
FROM $table_name
$join_sql
WHERE $table_name.id in ($id_list)""")
        d = {
            'temp_table_name': self.temp_table_name,
            'table_name': self.table_name(),
            'join_sql': self.join_sql(),
            'id_list': ', '.join(str(id_) for id_ in id_list),
            'dest_columns': ','.join(ci.attr_name
                                     for ci in self.select_columns()),
            'source_columns': ','.join('%s.%s' % (ci.table, ci.column)
                                       for ci in self.select_columns()),
        }
        sql = template.substitute(d)
        self.connection.execute(sql)

    def destroy(self):
        if self.connection is not None:
            self.connection.execute("DROP TABLE %s" % self.temp_table_name)
            self.connection.commit()
            self.release_connection()
            self.temp_table_name = None

    def fetch_items(self, id_list):
        """Create Item objects."""
        # We can use SELECT * here because we know that we defined the columns
        # in the same order as select_columns() returned them.
        id_list_str = ', '.join(str(i) for i in id_list)
        sql = "SELECT * FROM %s WHERE id IN (%s)" % (self.temp_table_name,
                                                     id_list_str)
        return [self.item_source.make_item_info(row)
                for row in self.connection.execute(sql)]

    def refresh_items(self, changed_ids):
        self._select_into_temp_table(changed_ids)
        return False

    def select_playable_ids(self):
        sql = ("SELECT id FROM %s "
               "WHERE %s IS NOT NULL AND "
               "file_type != 'other' AND "
               "id in (%s)" %
               (self.table_name(), self.path_column(),
                ','.join(str(id_) for id_ in self.id_list)))
        return [row[0] for row in self.connection.execute(sql)]

    def select_has_playables(self):
        sql = ("SELECT EXISTS (SELECT 1 FROM %s "
               "WHERE %s IS NOT NULL AND "
               "file_type != 'other' AND "
               "id in (%s))" %
               (self.table_name(), self.path_column(),
                ','.join(str(id_) for id_ in self.id_list)))
        return self.connection.execute(sql).fetchone()[0] == 1

class BackendItemTracker(signals.SignalEmitter):
    """Item tracker used by the backend

    BackendItemTracker works similarly to ItemTracker but with a couple
    changes that make it work better with the rest of the backend components.
    Specifically it:
        - Uses the connection in app.db rather than any connection pools
        - Fetches all ItemInfo objects up-front rather than using idle
        callbacks
        - Emits slightly different signals.  The main difference is that
        BackendItemTracker calculates exactly which items have been
        added/changed/removed rather than just emitted "list-changed" with on
        extra info.

    Signals:

    - "items-changed" (added, changed, removed): some items have been
    added/changed/removed from the list.  added/changed is a list of
    ItemInfos.  Removed is a list of item ids.
    """
    def __init__(self, query):
        signals.SignalEmitter.__init__(self)
        self.create_signal('items-changed')
        self.item_changes_callback = None
        self.query = query
        self.fetch_items()
        self.connect_to_item_changes()

    def change_query(self, query):
        self.query = query
        self.refetch_items()

    def fetch_items(self):
        self.item_map = {}
        for item_data in self.query.select_item_data(app.db.connection):
            item_info = item.ItemInfo(item_data)
            self.item_map[item_info.id] = item_info
        self.item_ids = set(self.item_map.keys())

    def get_items(self):
        return self.item_map.values()

    def connect_to_item_changes(self):
        self.item_changes_callback = models.Item.change_tracker.connect(
            'item-changes', self.on_item_changes)

    def destroy(self):
        if self.item_changes_callback is not None:
            models.Item.change_tracker.disconnect(self.item_changes_callback)
            self.item_changes_callback = None

    def on_item_changes(self, change_tracker, msg):
        if app.db.is_closed():
            return

        if self.query.could_list_change(msg):
            # items may have been added/removed from the list.  We need to
            # re-fetch the items and calculate changes
            self.refetch_items(msg.changed)
        else:
            # items changed, but the list is the same.  Just refetch the
            # changed items.
            changed_ids = msg.changed.intersection(self.item_ids)
            changed_items = item.fetch_item_infos(app.db.connection,
                                                  changed_ids)
            for item_info in changed_items:
                self.item_map[item_info.id] = item_info
            self.emit('items-changed', [], changed_items, [])

    def refetch_items(self, changed_ids=None):
        # items may have been added/removed from the list.  We need to
        # re-fetch the items and calculate changes
        old_item_ids = self.item_ids
        self.fetch_items()

        added_ids = self.item_ids - old_item_ids
        removed_ids = old_item_ids - self.item_ids
        if changed_ids:
            # remove ids from changed that aren't on the list
            changed_ids = changed_ids.intersection(self.item_ids)
            # remove ids from changed that were just added
            changed_ids = changed_ids.difference(added_ids)
        else:
            changed_ids = []
        self.emit('items-changed',
                  [self.item_map[id_] for id_ in added_ids],
                  [self.item_map[id_] for id_ in changed_ids],
                  list(removed_ids))
