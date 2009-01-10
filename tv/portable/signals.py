# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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
import threading
import time
import traceback
import weakref

from miro import config
from miro import prefs
import sys
from miro import util

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
        # don't create a weak refrence to the class.  That only works for
        # new-style classes.  It's highly unlikely the class will ever need to
        # be garbage collected anyways.
        self.cls = method.im_class

    def __call__(self):
        func = self.func()
        if func is None: return None
        object = self.object()
        if object is None: return None
        return func.__get__(object, self.cls)

class Callback:
    def __init__(self, func, extra_args):
        self.func = func
        self.extra_args = extra_args

    def invoke(self, obj, args):
        return self.func(obj, *(args + self.extra_args))

    def is_dead(self):
        return False

class WeakCallback:
    def __init__(self, method, extra_args):
        self.ref = WeakMethodReference(method)
        self.extra_args = extra_args

    def invoke(self, obj, args):
        callback = self.ref()
        if callback is not None:
            return callback(obj, *(args + self.extra_args))
        else:
            return None

    def is_dead(self):
        return self.ref() is None

class SignalEmitter:
    def __init__(self, *signal_names):
        self.signal_callbacks = {}
        self.id_generator = itertools.count()
        for name in signal_names:
            self.create_signal(name)

    def create_signal(self, name):
        self.signal_callbacks[name] = {}

    def get_callbacks(self, signal_name):
        try:
            return self.signal_callbacks[signal_name]
        except KeyError:
            raise KeyError("Signal: %s doesn't exist" % signal_name)

    def connect(self, name, func, *extra_args):
        """Connect a callback to a signal.  Returns an callback handle that
        can be passed into disconnect().
        """
        id = self.id_generator.next()
        callbacks = self.get_callbacks(name)
        callbacks[id] = Callback(func, extra_args)
        return (name, id)

    def connect_weak(self, name, method, *extra_args):
        """Connect a callback weakly.  Callback must be a method of some
        object.  We create a weak reference to the method, so that the
        connection doesn't keep the object from being garbage collected.
        """
        if not hasattr(method, 'im_self'):
            raise TypeError("connect_weak must be called with object methods")
        id = self.id_generator.next()
        callbacks = self.get_callbacks(name)
        callbacks[id] = WeakCallback(method, extra_args)
        return (name, id)

    def disconnect(self, callback_handle):
        """Disconnect a signal.  callback_handle must be the return value from
        connect() or connect_weak().
        """
        callbacks = self.get_callbacks(callback_handle[0])
        del callbacks[callback_handle[1]]

    def disconnect_all(self):
        for signal in self.signal_callbacks:
            self.signal_callbacks[signal] = {}

    def emit(self, name, *args):
        callback_returned_true = False
        try:
            self_callback = getattr(self, 'do_' + name.replace('-', '_'))
        except AttributeError:
            pass
        else:
            if self_callback(*args):
                callback_returned_true = True
        if not callback_returned_true:
            for callback in self.get_callbacks(name).values():
                if callback.invoke(self, args):
                    callback_returned_true = True
                    break
        self.clear_old_weak_references()
        return callback_returned_true

    def clear_old_weak_references(self):
        for callback_map in self.signal_callbacks.values():
            for id in callback_map.keys():
                if callback_map[id].is_dead():
                    del callback_map[id]

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


    """
    def __init__(self):
        SignalEmitter.__init__(self, 'error', 'startup-success',
                'startup-failure', 'shutdown',
                'update-available', 'new-dialog',
                'theme-first-run', 'videos-added')

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

    def failed_exn(self, when, details=None):
        self.failed(when, withExn=True, details=details)

    def failed(self, when, withExn=False, details=None):
        """Used to emit the error signal.  Formats a nice crash report."""

        logging.info ("failed() called; generating crash report.")
        self.emit('error', self._format_crash_report(when, withExn, details))

    def _format_crash_report(self, when, withExn, details):
        header = ""
        header += "App:        %s\n" % config.get(prefs.LONG_APP_NAME)
        header += "Publisher:  %s\n" % config.get(prefs.PUBLISHER)
        header += "Platform:   %s\n" % config.get(prefs.APP_PLATFORM)
        header += "Python:     %s\n" % sys.version.replace("\r\n"," ").replace("\n"," ").replace("\r"," ")
        header += "Py Path:    %s\n" % repr(sys.path)
        header += "Version:    %s\n" % config.get(prefs.APP_VERSION)
        header += "Serial:     %s\n" % config.get(prefs.APP_SERIAL)
        header += "Revision:   %s\n" % config.get(prefs.APP_REVISION)
        header += "Builder:    %s\n" % config.get(prefs.BUILD_MACHINE)
        header += "Build Time: %s\n" % config.get(prefs.BUILD_TIME)
        header += "Time:       %s\n" % time.asctime()
        header += "When:       %s\n" % when
        header += "\n"

        if withExn:
            header += "Exception\n---------\n"
            header += ''.join(traceback.format_exception(*sys.exc_info()))
            header += "\n"
        if details:
            header += "Details: %s\n" % (details, )
        header += "Call stack\n----------\n"
        try:
            stack = util.get_nice_stack()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            stack = traceback.extract_stack()
        header += ''.join(traceback.format_list(stack))
        header += "\n"

        header += "Threads\n-------\n"
        header += "Current: %s\n" % threading.currentThread().getName()
        header += "Active:\n"
        for t in threading.enumerate():
            header += " - %s%s\n" % \
                (t.getName(),
                 t.isDaemon() and ' [Daemon]' or '')

        # Combine the header with the logfile contents, if available, to
        # make the dialog box crash message. {{{ and }}} are Trac
        # Wiki-formatting markers that force a fixed-width font when the
        # report is pasted into a ticket.
        report = "{{{\n%s}}}\n" % header

        def read_log(logFile, logName="Log"):
            try:
                f = open(logFile, "rt")
                logContents = "%s\n---\n" % logName
                logContents += f.read()
                f.close()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                logContents = ''
            return logContents

        logFile = config.get(prefs.LOG_PATHNAME)
        downloaderLogFile = config.get(prefs.DOWNLOADER_LOG_PATHNAME)
        if logFile is None:
            logContents = "No logfile available on this platform.\n"
        else:
            logContents = read_log(logFile)
        if downloaderLogFile is not None:
            if logContents is not None:
                logContents += "\n" + read_log(downloaderLogFile, "Downloader Log")
            else:
                logContents = read_log(downloaderLogFile)

        if logContents is not None:
            report += "{{{\n%s}}}\n" % util.stringify(logContents)

        # Dump the header for the report we just generated to the log, in
        # case there are multiple failures or the user sends in the log
        # instead of the report from the dialog box. (Note that we don't
        # do this until we've already read the log into the dialog
        # message.)
        logging.info ("----- CRASH REPORT (DANGER CAN HAPPEN) -----")
        logging.info (header)
        logging.info ("----- END OF CRASH REPORT -----")
        return report

system = SystemSignals()
