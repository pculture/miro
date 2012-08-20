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
import random
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
    "table column collation descending",

    """ItemTrackerOrderBy defines one term for the ORDER BY clause of a query.

    :attribute table: table that contains column
    :attribute column: column to sort on
    :attribute collation: collation to use
    :attribute descending: should we add the DESC clause?
    """)

class ItemTrackerQuery(object):
    """Define the query used to get items for ItemTracker."""

    def __init__(self, select_info):
        self.conditions = []
        self.match_string = None
        self.select_info = select_info
        self.order_by = [ItemTrackerOrderBy('item', 'id', None, False)]

    def join_sql(self, table):
        return self.select_info.join_sql(table, join_type='JOIN')

    def table_name(self):
        return self.select_info.table_name

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
        cond = ItemTrackerCondition(table, column, sql, (value,))
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
        #  - remove the "*" charactor from search_string
        #  - add a prefix search to the last term, since the user can still be
        #  typing it out.
        terms = search_string.lower().replace("*", "").split()
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

    def set_order_by(self, columns, collations=None):
        """Change the ORDER BY clause.

        :param columns: list of columns name to sort by.  To do a descending
        search, prefix the name with "-".
        :param collations: list of collations to use to sort by.  None
        specifies the default collation.  Otherwise, there must be 1 value for
        each column and it should specify the collation to use for that
        column.
        """
        self.order_by = []
        if collations is None:
            collations = (None,) * len(columns)
        elif len(collations) != len(columns):
            raise ValueError("sequence length mismatch")

        for column, collation in zip(columns, collations):
            if column[0] == '-':
                descending = True
                column = column[1:]
            else:
                descending = False
            table, column = self._parse_column(column)
            ob = ItemTrackerOrderBy(table, column, collation, descending)
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
        sql = ' '.join(sql_parts)
        logging.debug("ItemTracker: running query %s (%s)", sql, arg_list)
        item_ids = [row[0] for row in connection.execute(sql, arg_list)]
        logging.debug("ItemTracker: done running query")
        return item_ids

    def _calc_tables(self):
        """Calculate which tables we need to execute the query."""
        all_tables = ([c.table for c in self.conditions] +
                      [ob.table for ob in self.order_by])
        return set(all_tables)

    def _add_joins(self, sql_parts, arg_list):
        for table in self._calc_tables():
            if table != self.select_info.table_name:
                sql_parts.append(self.join_sql(table))
        if self.match_string:
            sql_parts.append(self.join_sql('item_fts'))

    def _add_conditions(self, sql_parts, arg_list):
        if not self.conditions:
            return
        where_parts = []
        for c in self.conditions:
            where_parts.append(c.sql)
            arg_list.extend(c.values)
        if self.match_string:
            where_parts.append("item_fts MATCH ?")
            arg_list.append(self.match_string)
        sql_parts.append("WHERE %s" % ' AND '.join(where_parts))

    def _add_order_by(self, sql_parts, arg_list):
        order_by_parts = [self._make_order_by_expression(ob)
                          for ob in self.order_by]
        sql_parts.append("ORDER BY %s" % ', '.join(order_by_parts))

    def _make_order_by_expression(self, ob):
        parts = []
        parts.append("%s.%s" % (ob.table, ob.column))
        if ob.collation is not None:
            parts.append("collate %s" % ob.collation)
        if ob.descending:
            parts.append("DESC")
        else:
            parts.append("ASC")
        return " ".join(parts)

    def copy(self):
        retval = ItemTrackerQuery(self.select_info)
        retval.conditions = self.conditions[:]
        retval.order_by = self.order_by[:]
        retval.match_string = self.match_string
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

    #: ItemInfo or a subclass to use to create Items
    item_info_class = item.ItemInfo

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
        self.idle_work_scheduled = False
        self.item_fetcher = None
        self._set_query(query)
        self._fetch_id_list()
        self._schedule_idle_work()

    def destroy(self):
        """Call this when you're done with the ItemTracker

        We will release any open connections to the database and reset our
        self to an empty list.
        """
        self._destroy_item_fetcher()
        self.id_list = self.id_to_index = self.row_data = None

    @classmethod
    def make_query(cls):
        return ItemTrackerQuery(cls.item_info_class.select_info)

    def connection_pool(self):
        return app.connection_pool

    def make_item_fetcher(self, connection, id_list):
        """Make an ItemFetcher to use.

        :param connection: sqlite Connection to use.  We will return data from
        this connection without commiting any pending read transaction.
        :param id_list: list of ids that we will have to fetch.
        """
        if self.connection_pool().wal_mode:
            klass = ItemFetcherWAL
        else:
            klass = ItemFetcherNoWAL
        return klass(connection, self.connection_pool(), id_list,
                     self.item_info_class)

    def _destroy_item_fetcher(self):
        if self.item_fetcher:
            self.item_fetcher.destroy()
            self.item_fetcher = None

    def _set_query(self, query):
        """Change our ItemTrackerQuery object."""
        self.query = query
        self.tracked_columns = set(self.query.get_columns_to_track())
        self.track_dl_columns = self.query.tracking_download_columns()

    def _fetch_id_list(self):
        """Fetch the ids for this list.  """
        self._destroy_item_fetcher()
        connection = self.connection_pool().get_connection()
        self.id_list = self.query.select_ids(connection)
        self.id_to_index = dict((id_, i) for i, id_ in enumerate(self.id_list))
        self.row_data = {}
        self.item_fetcher = self.make_item_fetcher(connection, self.id_list)

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

    def _refetch_id_list(self):
        """Refetch a new id list after we already have one."""

        self.emit('will-change')
        self._fetch_id_list()
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
            return self.item_fetcher.select_playable_ids()

    def has_playables(self):
        """Can we play any items from this item list?"""
        if not self.idle_work_scheduled:
            return any(i for i in self.get_items() if i.is_playable)
        else:
            return self.item_fetcher.select_has_playables()

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
        ids_to_load = [self.id_list[i] for i in rows_to_load]
        items = self.item_fetcher.fetch_items(ids_to_load)
        for item in items:
            pos = self.id_to_index[item.id]
            self.row_data[item.id] = item

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

        :param message: an ItemsChanged message
        """
        changed_ids = [item_id for item_id in message.changed
                       if self.item_in_list(item_id)]
        self._uncache_row_data(changed_ids)
        if self._could_list_change(message):
            self._refetch_id_list()
        else:
            self.item_fetcher.refresh_items(changed_ids)
            self.emit('will-change')
            self.emit('items-changed', changed_ids)

    def _could_list_change(self, message):
        """Calculate if an ItemsChanged means the list may have changed."""
        return bool(message.added or message.removed or
                    (message.dlstats_changed and self.track_dl_columns) or
                    message.changed_columns.intersection(self.tracked_columns))

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

    def __init__(self, connection, connection_pool, id_list, item_info_class):
        self.connection = connection
        self.connection_pool = connection_pool
        self.id_list = id_list
        self.item_info_class = item_info_class

    def select_columns(self):
        return self.item_info_class.select_info.select_columns

    def join_sql(self):
        return self.item_info_class.select_info.join_sql()

    def table_name(self):
        return self.item_info_class.select_info.table_name

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
    def __init__(self, connection, connection_pool, id_list, item_info_class):
        ItemFetcher.__init__(self, connection, connection_pool, id_list,
                             item_info_class)
        self._prepare_sql()

    def destroy(self):
        if self.connection is not None:
            self.connection_pool.release_connection(self.connection)
            self.connection = None

    def done_fetching(self):
        # We can safely finish the read transaction here
        self.connection.commit()

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
        return [self.item_info_class(*row) for row in cursor]

    def refresh_items(self, changed_ids):
        # We ignore changed_ids and just start a new transaction which will
        # refresh all the data.
        self.connection.commit()

    def select_playable_ids(self):
        sql = ("SELECT id FROM %s "
               "WHERE filename IS NOT NULL AND "
               "file_type != 'other' AND "
               "id in (%s)" % 
               (self.table_name, ','.join(str(id_) for id_ in self.id_list)))
        return [row[0] for row in self.connection.execute(sql)]

    def select_has_playables(self):
        sql = ("SELECT EXISTS (SELECT 1 FROM %s "
               "WHERE filename IS NOT NULL AND "
               "file_type != 'other' AND "
               "id in (%s))" %
               (self.table_name(),
                ','.join(str(id_) for id_ in self.id_list)))
        return self.connection.execute(sql).fetchone()[0] == 1

class ItemFetcherNoWAL(ItemFetcher):
    def __init__(self, connection, connection_pool, id_list, item_info_class):
        ItemFetcher.__init__(self, connection, connection_pool, id_list,
                             item_info_class)
        self._make_temp_table()
        self._select_into_temp_table(id_list)

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
        self.connection.execute("DROP TABLE %s" % self.temp_table_name)
        self.connection.commit()
        self.connection_pool.release_connection(self.connection)
        self.connection = self.temp_table_name = None

    def fetch_items(self, id_list):
        """Create Item objects."""
        # We can use SELECT * here because we know that we defined the columns
        # in the same order as select_columns() returned them.
        id_list_str = ', '.join(str(i) for i in id_list)
        sql = "SELECT * FROM %s WHERE id IN (%s)" % (self.temp_table_name,
                                                     id_list_str)
        return [self.item_info_class(*row)
                for row in self.connection.execute(sql)]

    def refresh_items(self, changed_ids):
        self._select_into_temp_table(changed_ids)

    def select_playable_ids(self):
        sql = ("SELECT id FROM %s "
               "WHERE filename IS NOT NULL AND "
               "file_type != 'other' AND "
               "id in (%s)" %
               (self.table_name(),
                ','.join(str(id_) for id_ in self.id_list)))
        return [row[0] for row in self.connection.execute(sql)]

    def select_has_playables(self):
        sql = ("SELECT EXISTS (SELECT 1 FROM %s "
               "WHERE filename IS NOT NULL AND "
               "file_type != 'other' AND "
               "id in (%s))" %
               (self.table_name(),
                ','.join(str(id_) for id_ in self.id_list)))
        return self.connection.execute(sql).fetchone()[0] == 1
