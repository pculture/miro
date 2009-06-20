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

# Pyrex version of the DTV object database
#
# 09/26/2005 Checked in change that speeds up inserts, but changes
#            filters so that they no longer keep the order of the
#            parent view. So, filter before you sort.

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
    """Raised when the database encounters an internal consistency issue.
    """
    pass

class DatabaseThreadError(Exception):
    """Raised when the database encounters an internal consistency issue.
    """
    pass

class DatabaseVersionError(StandardError):
    """Raised when an attempt is made to restore a database newer than the
    one we support
    """
    pass

class ObjectNotFoundError(StandardError):
    """Raised when an attempt is made to lookup an object that doesn't exist
    """
    pass

class TooManyObjects(StandardError):
    """Raised when an attempt is made to lookup a singleton and multiple rows
    match the query.
    """
    pass

class NotRootDBError(StandardError):
    """Raised when an attempt is made to call a function that's only
    allowed to be called from the root database
    """
    pass

class NoValue:
    """Used as a dummy value so that "None" can be treated as a valid value
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
    
import traceback
def confirm_db_thread():
    global event_thread
    if event_thread is None or event_thread != threading.currentThread():
        if event_thread is None:
            errorString = "Database event thread not set"
        else:
            errorString = "Database called from %s" % threading.currentThread()
        traceback.print_stack()
        raise DatabaseThreadError, errorString

def _always_true(obj):
    return True

class View(object):
    def __init__(self, klass, where, values, order_by, joins, track_optimizer):
        self.klass = klass
        self.where = where
        self.values = values
        self.order_by = order_by
        self.joins = joins
        if track_optimizer is None and where is None:
            # If where is None, then all items will be in the view, so we can
            # build track_optimizer trivially.
            track_optimizer = _always_true
        self.track_optimizer = track_optimizer

    def __iter__(self):
        return app.db.query(self.klass, self.where, self.values,
                self.order_by, self.joins)

    def count(self):
        return app.db.query_count(self.klass, self.where, self.values,
                self.joins)

    def get_singleton(self):
        results = list(self)
        if len(results) == 1:
            return results[0]
        elif len(results) == 0:
            raise ObjectNotFoundError("Can't find singleton")
        else:
            raise TooManyObjects("Too many results returned")

    def make_tracker(self):
        return ViewTracker(self.klass, self.where, self.values, self.joins,
                self.track_optimizer)

class ViewTracker(signals.SignalEmitter):
    table_to_tracker = {} # maps table_name to trackers
    joined_table_to_tracker = {} # maps joined tables to trackers

    @classmethod
    def reset_trackers(cls):
        cls.table_to_tracker = {}
        cls.joined_table_to_tracker = {}

    @classmethod
    def trackers_for_table(cls, table_name):
        try:
            return cls.table_to_tracker[table_name]
        except KeyError:
            cls.table_to_tracker[table_name] = set()
            return cls.table_to_tracker[table_name]

    @classmethod
    def trackers_for_ddb_class(cls, klass):
        return cls.trackers_for_table(app.db.table_name(klass))

    @classmethod
    def related_trackers_for_table(cls, table_name):
        try:
            return cls.joined_table_to_tracker[table_name]
        except KeyError:
            cls.joined_table_to_tracker[table_name] = set()
            return cls.joined_table_to_tracker[table_name]

    @classmethod
    def related_trackers_for_ddb_class(cls, klass):
        return cls.related_trackers_for_table(app.db.table_name(klass))

    @classmethod
    def _update_view_trackers(cls, obj):
        for tracker in cls.trackers_for_ddb_class(obj.__class__):
            tracker.object_changed(obj)

    @classmethod
    def _update_related_view_trackers(cls, obj):
        table_name = app.db.table_name(obj.__class__)
        for tracker in cls.related_trackers_for_table(table_name):
            tracker.object_changed(obj)

    def __init__(self, klass, where, values, joins, track_optimizer):
        signals.SignalEmitter.__init__(self, 'added', 'removed', 'changed')
        self.klass = klass
        self.where = where
        if track_optimizer is not None:
            self.track_check_func = track_optimizer
        else:
            logging.warn("Making tracker without optimizer: %s %s",
                    self.klass.__name__, self.where)
            self.track_check_func = self._default_track_check_func
        if isinstance(values, list):
            raise TypeError("values must be a tuple")
        self.values = values
        self.joins = joins
        self.current_ids = set(app.db.query_ids(klass, where, values,
            joins=joins))
        self.table_name = app.db.table_name(klass)
        ViewTracker.trackers_for_table(self.table_name).add(self)
        if joins is not None:
            for table_name in joins.keys():
                ViewTracker.related_trackers_for_table(table_name).add(self)

    def unlink(self):
        ViewTracker.trackers_for_table(self.table_name).discard(self)
        if self.joins is not None:
            for table_name in self.joins.keys():
                ViewTracker.related_trackers_for_table(table_name).discard(self)

    def _default_track_check_func(self, obj):
        where = '%s.id = ?' % (self.table_name,)
        if self.where:
            where += ' AND (%s)' % (self.where,)

        values = (obj.id,) + self.values
        return app.db.query_count(self.klass, where, values, self.joins) > 0

    def object_changed(self, obj):
        if isinstance(obj, self.klass):
            # object is the type we are tracking, just need to check if the
            # change made that object enter/leave the view
            self.check_object(obj)
        else:
            # object is the type that we are joining.  Need to check all of
            # our objects to see what left/entered.
            self.check_all_objects()

    def check_object(self, obj):
        before = (obj.id in self.current_ids)
        now = self.track_check_func(obj)
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
        for id in new_ids.difference(self.current_ids):
            self.emit('added', app.db.get_obj_by_id(id))
        for id in self.current_ids.difference(new_ids):
            self.emit('removed', app.db.get_obj_by_id(id))
        for id in self.current_ids:
            # XXX this hits all the IDs, but there doesn't seem to be a way to
            # check if the objects have actually been changed.  luckily, this
            # isn't called very often.
            self.emit('changed', app.db.get_obj_by_id(id))
        self.current_ids = new_ids

    def __len__(self):
        return len(self.current_ids)

class DDBObject(signals.SignalEmitter):
    """Dynamic Database object
    """
    #The last ID used in this class
    lastID = 0

    def __init__(self, *args, **kwargs):
        self.in_db_init = True
        signals.SignalEmitter.__init__(self, 'removed')

        if len(args) == 0 and kwargs.keys() == ['restored_data']:
            restoring = True
        else:
            restoring = False

        if restoring:
            self.__dict__.update(kwargs['restored_data'])
            app.db.remember_object(self)
            self.setup_restored()
            if not self.idExists(): # handle setup_restored() calling remove()
                return
        else:
            self.id = DDBObject.lastID = DDBObject.lastID + 1
            # call remember_object so that idExists will return True when
            # setup_new() is being run
            app.db.remember_object(self)
            self.setup_new(*args, **kwargs)
            if not self.idExists(): # handle setup_new() calling remove()
                return
            app.db.update_obj(self)

        self.in_db_init = False

        if not restoring:
            self.check_constraints()
            self.on_db_insert()
            ViewTracker._update_view_trackers(self)

    @classmethod
    def make_view(cls, where=None, values=None, order_by=None, joins=None,
            track_optimizer=None):
        if values is None:
            values = ()
        return View(cls, where, values, order_by, joins, track_optimizer)

    @classmethod
    def get_by_id(cls, id):
        try:
            # try memory first before going to sqlite.
            obj = app.db.get_obj_by_id(id)
            if app.db.object_from_class_table(obj, cls):
                return obj
            else:
                raise ObjectNotFoundError(id)
        except KeyError:
            return cls.make_view('id=?', (id,)).get_singleton()

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

    def getID(self):
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
        app.db.remove_obj(self)
        self.emit('removed')
        ViewTracker._update_view_trackers(self)

    def confirm_db_thread(self):
        """Call this before you grab data from an object

        Usage:

            view.confirm_db_thread()
            ...
        """
        confirm_db_thread()

    def check_constraints(self):
        """Subclasses can override this method to do constraint checking
        before they get saved to disk.  They should raise a
        DatabaseConstraintError on problems.
        """
        pass

    def signal_change(self, needsSave=True):
        """Call this after you change the object
        """
        if self.in_db_init:
            # signal_change called while we were setting up a object, just
            # ignore it.
            return
        if not self.idExists():
            msg = "signal_change() called on non-existant object (id is %s)" \
                    % self.id
            raise DatabaseConstraintError, msg
        self.on_signal_change()
        self.check_constraints()
        if needsSave:
            app.db.update_obj(self)
        ViewTracker._update_view_trackers(self)

    def on_signal_change(self):
        pass

    def signal_related_change(self, needsSave=True):
        """Call this after you change an object and it could affect the views
        of related object.

        For example, when feeds get their autodownload settings, it could
        change the view of items waiting to be autodownloaded.  In that case,
        feed should call signal_related_change
        """
        ViewTracker._update_related_view_trackers(self)

def update_last_id():
    DDBObject.lastID = app.db.get_last_id()
