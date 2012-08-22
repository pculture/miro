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

"""signals.py

GObject-like signal handling for Miro.
"""

import itertools
import logging
import sys
import weakref

from miro import crashreport

class NestedSignalError(StandardError):
    pass

class WeakMethodReference:
    """Used to handle weak references to a method.

    We can't simply keep a weak reference to method itself, because there
    almost certainly aren't any other references to it.  Instead we keep a
    weak reference to the object, it's class and the unbound method.  This
    gives us enough info to recreate the bound method when we need it.
    """

    def __init__(self, method):
        self.object = weakref.ref(method.im_self)
        self.func = weakref.ref(method.im_func)
        # don't create a weak reference to the class.  That only works for
        # new-style classes.  It's highly unlikely the class will ever need to
        # be garbage collected anyways.
        self.cls = method.im_class

    def __call__(self):
        func = self.func()
        if func is None: return None
        obj = self.object()
        if obj is None: return None
        return func.__get__(obj, self.cls)

class Callback:
    def __init__(self, func, extra_args):
        self.func = func
        self.extra_args = extra_args

    def invoke(self, obj, args):
        return self.func(obj, *(args + self.extra_args))

    def compare_function(self, func):
        return self.func == func

    def is_dead(self):
        return False

class WeakCallback:
    def __init__(self, method, extra_args):
        self.ref = WeakMethodReference(method)
        self.extra_args = extra_args

    def compare_function(self, func):
        return self.ref() == func

    def invoke(self, obj, args):
        callback = self.ref()
        if callback is not None:
            return callback(obj, *(args + self.extra_args))
        else:
            return None

    def is_dead(self):
        return self.ref() is None

class CallbackSet(object):
    """Stores callbacks connected to a signal for SignalEmitter."""
    def __init__(self):
        self.callbacks = {}
        self.callbacks_after = {}

    def add_callback(self, id_, callback):
        self.callbacks[id_] = callback

    def add_callback_after(self, id_, callback):
        self.callbacks_after[id_] = callback

    def remove_callback(self, id_):
        if id_ in self.callbacks:
            del self.callbacks[id_]
        elif id_ in self.callbacks_after:
            del self.callback_after[id_]
        else:
            logging.warning(
                "disconnect called but callback_handle not in the callback")

    def all_callbacks(self):
        """Get a list of all Callback objects stored.

        The list will contain callbacks added with add_callback() then
        callbacks added with add_callback_after().
        """
        return self.callbacks.values() + self.callbacks_after.values()

    def clear_old_weak_references(self):
        """Remove any dead WeakCallbacks."""
        for callback_dict in (self.callbacks, self.callbacks_after):
            for id_, callback in callback_dict.items():
                if callback.is_dead():
                    del callback_dict[id_]

    def __len__(self):
        return len(self.callbacks) + len(self.callbacks_after)

class SignalEmitter(object):
    def __init__(self, *signal_names):
        self.signal_callbacks = {}
        self.id_generator = itertools.count()
        self._currently_emitting = set()
        self._okay_to_nest = set()
        self._frozen = False
        for name in signal_names:
            self.create_signal(name)

    def freeze_signals(self):
        self._frozen = True

    def thaw_signals(self):
        self._frozen = False

    def create_signal(self, name, okay_to_nest=False):
        if name in self.signal_callbacks:
            raise KeyError("%s was already created" % name)
        self.signal_callbacks[name] = CallbackSet()
        if okay_to_nest:
            self._okay_to_nest.add(name)

    def get_callbacks(self, signal_name):
        try:
            return self.signal_callbacks[signal_name]
        except KeyError:
            raise KeyError("Signal: %s doesn't exist" % signal_name)

    def _check_already_connected(self, name, func):
        for callback in self.get_callbacks(name).all_callbacks():
            if callback.compare_function(func):
                raise ValueError("signal %s already connected to %s" %
                        (name, func))

    def connect(self, name, func, *extra_args):
        """Connect a callback to a signal.  Returns an callback handle that
        can be passed into disconnect().

        If func is already connected to the signal, then a ValueError will be
        raised.
        """
        self._check_already_connected(name, func)
        id_ = self.id_generator.next()
        callbacks = self.get_callbacks(name)
        callbacks.add_callback(id_, Callback(func, extra_args))
        return (name, id_)

    def connect_after(self, name, func, *extra_args):
        """Like connect(), but run the handler later

        When a signal is fired, we first run the handlers connected with
        connect() then the ones connected with connect_after()
        """
        self._check_already_connected(name, func)
        id_ = self.id_generator.next()
        callbacks = self.get_callbacks(name)
        callbacks.add_callback_after(id_, Callback(func, extra_args))
        return (name, id_)

    def connect_weak(self, name, method, *extra_args):
        """Connect a callback weakly.  Callback must be a method of some
        object.  We create a weak reference to the method, so that the
        connection doesn't keep the object from being garbage collected.

        If method is already connected to the signal, then a ValueError will be
        raised.
        """
        self._check_already_connected(name, method)
        if not hasattr(method, 'im_self'):
            raise TypeError("connect_weak must be called with object methods")
        id_ = self.id_generator.next()
        callbacks = self.get_callbacks(name)
        callbacks.add_callback(id_, WeakCallback(method, extra_args))
        return (name, id_)

    def disconnect(self, callback_handle):
        """Disconnect a signal.  callback_handle must be the return value from
        connect() or connect_weak().
        """
        callbacks = self.get_callbacks(callback_handle[0])
        callbacks.remove_callback(callback_handle[1])

    def disconnect_all(self):
        for signal in self.signal_callbacks:
            self.signal_callbacks[signal] = CallbackSet()

    def emit(self, name, *args):
        if self._frozen:
            return
        if name not in self._okay_to_nest:
            if name in self._currently_emitting:
                raise NestedSignalError("Can't emit %s while handling %s" %
                        (name, name))
            self._currently_emitting.add(name)
        try:
            callback_returned_true = self._run_signal(name, args)
        finally:
            self._currently_emitting.discard(name)
            self.clear_old_weak_references()
        return callback_returned_true

    def _run_signal(self, name, args):
        callback_returned_true = False
        try:
            self_callback = getattr(self, 'do_' + name.replace('-', '_'))
        except AttributeError:
            pass
        else:
            if self_callback(*args):
                callback_returned_true = True
        if not callback_returned_true:
            for callback in self.get_callbacks(name).all_callbacks():
                if callback.invoke(self, args):
                    callback_returned_true = True
                    break
        return callback_returned_true

    def clear_old_weak_references(self):
        for callback_set in self.signal_callbacks.values():
            callback_set.clear_old_weak_references()

class SystemSignals(SignalEmitter):
    """System wide signals for Miro.  These can be accessed from the singleton
    object signals.system.  Signals include:

    "error" - A problem occurred in Miro.  The frontend should let the user
        know this happened, hopefully with a nice dialog box or something that
        lets the user report the error to bugzilla.  

        Arguments:
        - report -- string that can be submitted to the bug tracker
        - exception -- Exception object (can be None)

    "startup-success" - The startup process is complete.  The frontend should
        wait for this signal to show the UI to the user.
        
        No arguments.

    "startup-failure" - The startup process fails.  The frontend should inform
        the user that this happened and quit.
        
        Arguments:
        - summary -- Short, user-friendly, summary of the problem
        - description -- Longer explanation of the problem

    "shutdown" - The backend has shutdown.  The event loop is stopped at this
        point.

        No arguments.

    "update-available" - A new version of Miro is available.
     
        Arguments:
        - rssItem -- The RSS item for the latest version (in sparkle
          appcast format).

    "new-dialog" - The backend wants to display a dialog to the user.

        Arguments:
        - dialog -- The dialog to be displayed.

    "theme-first-run" - A theme was used for the first time

        Arguments:
        - theme -- The name of the theme.

    "videos-added" -- Videos were added via the singleclick module.
        Arguments:
        - view -- A database view than contains the videos.

    "download-complete" -- A download was completed.
        Arguments:
        - item -- an Item of class Item.

    """
    def __init__(self):
        SignalEmitter.__init__(self, 'error', 'startup-success',
                'startup-failure', 'shutdown',
                'update-available', 'new-dialog',
                'theme-first-run', 'videos-added',
                'download-complete')

    def shutdown(self):
        self.emit('shutdown')

    def update_available(self, latest):
        self.emit('update-available', latest)

    def new_dialog(self, dialog):
        self.emit('new-dialog', dialog)

    def theme_first_run(self, theme):
        self.emit('theme-first-run', theme)

    def videos_added(self, view):
        self.emit('videos-added', view)

    def download_complete(self, item):
        self.emit('download-complete', item)

    def failed_exn(self, when, details=None):
        self.failed(when, with_exception=True, details=details)

    def failed(self, when, with_exception=False, details=None):
        """Used to emit the error signal.  Formats a nice crash report."""

        logging.info ("failed() called; generating crash report.")
        if with_exception:
            exc_info = sys.exc_info()
        else:
            exc_info = None
        self.emit('error', crashreport.format_crash_report(when,
            exc_info, details))


system = SystemSignals()
