# -*- mode: python -*-

# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
import traceback
import threading

from miro import app
from miro import signals

class DatabaseConstraintError(Exception):
    """Raised when a DDBObject fails its constraint checking during
    signal_change().
    """
    pass

class DatabaseConsistencyError(Exception):
    """Raised when the database encounters an internal consistency
    issue.
    """
    pass

class DatabaseThreadError(Exception):
    """Raised when the database encounters an internal consistency
    issue.
    """
    pass

class DatabaseVersionError(StandardError):
    """Raised when an attempt is made to restore a database newer than
    the one we support
    """
    pass

class ObjectNotFoundError(StandardError):
    """Raised when an attempt is made to lookup an object that doesn't
    exist
    """
    pass

class TooManyObjects(StandardError):
    """Raised when an attempt is made to lookup a singleton and
    multiple rows match the query.
    """
    pass

class NotRootDBError(StandardError):
    """Raised when an attempt is made to call a function that's only
    allowed to be called from the root database.
    """
    pass

class NoValue:
    """Used as a dummy value so that "None" can be treated as a valid
    value.
    """
    pass

# begin* and end* no longer actually lock the database.  Instead
# confirm_db_thread prints a warning if it's run from any thread that
# isn't the main thread.  This can be removed from releases for speed
# purposes.

event_thread = None
def set_thread(thread):
    global event_thread
    if event_thread is None:
        event_thread = thread

def confirm_db_thread():
    global event_thread
    if event_thread is None or event_thread != threading.currentThread():
        if event_thread is None:
            error_string = "Database event thread not set"
        else:
            error_string = "Database called from %s" % threading.currentThread()
        traceback.print_stack()
        raise DatabaseThreadError, error_string

class View(object):
    def __init__(self, klass, where, values, order_by, joins, limit):
        self.klass = klass
        self.where = where
        self.values = values
        self.order_by = order_by
        self.joins = joins
        self.limit = limit

    def __iter__(self):
        return app.db.query(self.klass, self.where, self.values,
                            self.order_by, self.joins, self.limit)

    def count(self):
        return app.db.query_count(self.klass, self.where, self.values,
                                  self.joins, self.limit)

    def get_singleton(self):
        results = list(self)
        if len(results) == 1:
            return results[0]
        elif len(results) == 0:
            raise ObjectNotFoundError("Can't find singleton")
        else:
            raise TooManyObjects("Too many results returned")

    def make_tracker(self):
        if self.limit is not None:
            raise ValueError("tracking views with limits not supported")
        return ViewTracker(self.klass, self.where, self.values, self.joins)

class ViewTrackerManager(object):
    def __init__(self):
        # maps table_name to trackers
        self.table_to_tracker = {}
        # maps joined tables to trackers
        self.joined_table_to_tracker = {}

    def trackers_for_table(self, table_name):
        try:
            return self.table_to_tracker[table_name]
        except KeyError:
            self.table_to_tracker[table_name] = set()
            return self.table_to_tracker[table_name]

    def trackers_for_ddb_class(self, klass):
        return self.trackers_for_table(app.db.table_name(klass))

    def update_view_trackers(self, obj):
        """Update view trackers based on an object change."""

        for tracker in self.trackers_for_ddb_class(obj.__class__):
            tracker.object_changed(obj)

    def bulk_update_view_trackers(self, table_name):
        for tracker in self.trackers_for_table(table_name):
            tracker.check_all_objects()

    def bulk_remove_from_view_trackers(self, table_name, objects):
        for tracker in self.trackers_for_table(table_name):
            tracker.remove_objects(objects)

    def remove_from_view_trackers(self, obj):
        """Update view trackers based on an object change."""

        for tracker in self.trackers_for_ddb_class(obj.__class__):
            tracker.remove_object(obj)

class ViewTracker(signals.SignalEmitter):
    def __init__(self, klass, where, values, joins):
        signals.SignalEmitter.__init__(self, 'added', 'removed', 'changed')
        self.klass = klass
        self.where = where
        if isinstance(values, list):
            raise TypeError("values must be a tuple")
        self.values = values
        self.joins = joins
        self.current_ids = set(app.db.query_ids(klass, where, values,
            joins=joins))
        self.table_name = app.db.table_name(klass)
        vt_manager = app.view_tracker_manager
        vt_manager.trackers_for_table(self.table_name).add(self)

    def unlink(self):
        vt_manager = app.view_tracker_manager
        vt_manager.trackers_for_table(self.table_name).discard(self)

    def _obj_in_view(self, obj):
        where = '%s.id = ?' % (self.table_name,)
        if self.where:
            where += ' AND (%s)' % (self.where,)

        values = (obj.id,) + self.values
        return app.db.query_count(self.klass, where, values, self.joins) > 0

    def object_changed(self, obj):
        self.check_object(obj)

    def remove_object(self, obj):
        if obj.id in self.current_ids:
            self.current_ids.remove(obj.id)
            self.emit('removed', obj)

    def remove_objects(self, objects):
        object_map = dict((o.id, o) for o in objects)
        object_ids = set(object_map.keys())
        for removed_id in self.current_ids.intersection(object_ids):
            self.current_ids.remove(removed_id)
            self.emit('removed', object_map[removed_id])

    def check_object(self, obj):
        before = (obj.id in self.current_ids)
        now = self._obj_in_view(obj)
        if before and not now:
            self.current_ids.remove(obj.id)
            self.emit('removed', obj)
        elif now and not before:
            self.current_ids.add(obj.id)
            self.emit('added', obj)
        elif before and now:
            self.emit('changed', obj)

    def check_all_objects(self):
        new_ids = set(app.db.query_ids(self.klass, self.where,
            self.values, joins=self.joins))
        for id_ in new_ids.difference(self.current_ids):
            self.emit('added', app.db.get_obj_by_id(id_))
        for id_ in self.current_ids.difference(new_ids):
            self.emit('removed', app.db.get_obj_by_id(id_))
        for id_ in self.current_ids.intersection(new_ids):
            # XXX this hits all the IDs, but there doesn't seem to be
            # a way to check if the objects have actually been
            # changed.  luckily, this isn't called very often.
            self.emit('changed', app.db.get_obj_by_id(id_))
        self.current_ids = new_ids

    def __len__(self):
        return len(self.current_ids)

class BulkSQLManager(object):
    def __init__(self):
        self.active = False
        self.to_insert = {}
        self.to_remove = {}

    def start(self):
        if self.active:
            raise ValueError("BulkSQLManager.start() called twice")
        self.active = True

    def finish(self):
        if not self.active:
            raise ValueError("BulkSQLManager.finish() called twice")
        self.commit()
        self.active = False

    def commit(self):
        self._commit_sql()
        self._update_view_trackers()
        self.to_insert = {}
        self.to_remove = {}

    def _commit_sql(self):
        for table_name, objects in self.to_insert.items():
            logging.debug('bulk insert: %s %s', table_name, len(objects))
            app.db.bulk_insert(objects)
            for obj in objects:
                obj.inserted_into_db()

        for table_name, objects in self.to_remove.items():
            logging.debug('bulk remove: %s %s', table_name, len(objects))
            app.db.bulk_remove(objects)
            for obj in objects:
                obj.removed_from_db()

    def _update_view_trackers(self):
        for table_name in self.to_insert:
            app.view_tracker_manager.bulk_update_view_trackers(table_name)

        for table_name, objects in self.to_remove.items():
            if table_name in self.to_insert:
                # already updated the view above
                continue
            app.view_tracker_manager.bulk_remove_from_view_trackers(
                    table_name, objects)

    def add_insert(self, obj):
        table_name = app.db.table_name(obj.__class__)
        try:
            inserts_for_table = self.to_insert[table_name]
        except KeyError:
            inserts_for_table = []
            self.to_insert[table_name] = inserts_for_table
        inserts_for_table.append(obj)

    def add_remove(self, obj):
        table_name = app.db.table_name(obj.__class__)
        try:
            removes_for_table = self.to_remove[table_name]
        except KeyError:
            removes_for_table = []
            self.to_remove[table_name] = removes_for_table
        removes_for_table.append(obj)

class AttributeUpdateTracker(object):
    """Used by DDBObject to track changes to attributes."""

    def __init__(self, name):
        self.name = name

    # Simple implementation of the python descriptor protocol.  We
    # just want to update changed_attributes when attributes are set.

    def __get__(self, instance, owner):
        try:
            return instance.__dict__[self.name]
        except KeyError:
            raise AttributeError(self.name)
        except AttributeError:
            if instance is None:
                raise AttributeError(
                    "Can't access '%s' as a class attribute" % self.name)
            else:
                raise

    def __set__(self, instance, value):
        if instance.__dict__.get(self.name, "BOGUS VALUE FOO") != value:
            instance.changed_attributes.add(self.name)
        instance.__dict__[self.name] = value

class DDBObject(signals.SignalEmitter):
    """Dynamic Database object
    """
    #The last ID used in this class
    lastID = 0

    def __init__(self, *args, **kwargs):
        self.in_db_init = True
        signals.SignalEmitter.__init__(self, 'removed')
        self.changed_attributes = set()

        if len(args) == 0 and kwargs.keys() == ['restored_data']:
            restoring = True
        else:
            restoring = False

        if restoring:
            self.__dict__.update(kwargs['restored_data'])
            app.db.remember_object(self)
            self.setup_restored()
            # handle setup_restored() calling remove()
            if not self.idExists():
                return
        else:
            self.id = DDBObject.lastID = DDBObject.lastID + 1
            # call remember_object so that idExists will return True
            # when setup_new() is being run
            app.db.remember_object(self)
            self.setup_new(*args, **kwargs)
            # handle setup_new() calling remove()
            if not self.idExists():
                return

        self.in_db_init = False

        if not restoring:
            self._insert_into_db()

    def _insert_into_db(self):
        if not app.bulk_sql_manager.active:
            app.db.insert_obj(self)
            self.inserted_into_db()
            app.view_tracker_manager.update_view_trackers(self)
        else:
            app.bulk_sql_manager.add_insert(self)

    def inserted_into_db(self):
        self.check_constraints()
        self.on_db_insert()

    @classmethod
    def make_view(cls, where=None, values=None, order_by=None, joins=None,
            limit=None):
        if values is None:
            values = ()
        return View(cls, where, values, order_by, joins, limit)

    @classmethod
    def get_by_id(cls, id_):
        try:
            # try memory first before going to sqlite.
            obj = app.db.get_obj_by_id(id_)
            if app.db.object_from_class_table(obj, cls):
                return obj
            else:
                raise ObjectNotFoundError(id_)
        except KeyError:
            return cls.make_view('id=?', (id_,)).get_singleton()

    @classmethod
    def delete(cls, where, values=None):
        return app.db.delete(cls, where, values)

    @classmethod
    def select(cls, columns, where=None, values=None):
        return app.db.select(cls, columns, where, values)

    def setup_new(self):
        """Initialize a newly created object."""
        pass

    def setup_restored(self):
        """Initialize an object restored from disk."""
        pass

    def on_db_insert(self):
        """Called after an object has been inserted into the db."""
        pass

    @classmethod
    def track_attribute_changes(cls, name):
        """Set up tracking when attributes get set.

        Call this on a DDBObject subclass to track changes to certain
        attributes.  Each DDBObject has a changed_attributes set,
        which contains the attributes that have changed.

        This is used by the SQLite storage layer to track which
        attributes are changed between SQL UPDATE statements.

        For example:

        >> MyDDBObjectSubclass.track_attribute_changes('foo')
        >> MyDDBObjectSubclass.track_attribute_changes('bar')
        >>> obj = MyDDBObjectSubclass()
        >>> print obj.changed_attributes
        set([])
        >> obj.foo = obj.bar = obj.baz = 3
        >>> print obj.changed_attributes
        set(['foo', 'bar'])
        """
        # The AttributeUpdateTracker class does all the work
        setattr(cls, name, AttributeUpdateTracker(name))

    def reset_changed_attributes(self):
        self.changed_attributes = set()

    def get_id(self):
        """Returns unique integer assocaited with this object
        """
        return self.id

    def idExists(self):
        try:
            self.get_by_id(self.id)
        except ObjectNotFoundError:
            return False
        else:
            return True

    def remove(self):
        """Call this after you've removed all references to the object
        """
        if not app.bulk_sql_manager.active:
            app.db.remove_obj(self)
            self.removed_from_db()
            app.view_tracker_manager.remove_from_view_trackers(self)
        else:
            app.bulk_sql_manager.add_remove(self)

    def removed_from_db(self):
        self.emit('removed')

    def confirm_db_thread(self):
        """Call this before you grab data from an object

        Usage::

            view.confirm_db_thread()
            ...
        """
        confirm_db_thread()

    def check_constraints(self):
        """Subclasses can override this method to do constraint
        checking before they get saved to disk.  They should raise a
        DatabaseConstraintError on problems.
        """
        pass

    def signal_change(self, needsSave=True):
        """Call this after you change the object
        """
        if self.in_db_init:
            # signal_change called while we were setting up a object,
            # just ignore it.
            return
        if not self.idExists():
            msg = ("signal_change() called on non-existant object (id is %s)" \
                       % self.id)
            raise DatabaseConstraintError, msg
        self.on_signal_change()
        self.check_constraints()
        if needsSave:
            app.db.update_obj(self)
        app.view_tracker_manager.update_view_trackers(self)

    def on_signal_change(self):
        pass

def update_last_id():
    DDBObject.lastID = app.db.get_last_id()

def setup_managers():
    app.view_tracker_manager = ViewTrackerManager()
    app.bulk_sql_manager = BulkSQLManager()

def initialize():
    update_last_id()
    setup_managers()
