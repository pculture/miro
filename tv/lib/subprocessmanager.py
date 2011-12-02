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

"""```subprocessmanager.py``` -- Manage child processes

This module builds on messagetools.py to implement a message passing system to
child processes.  It also supports some simple process management to restart
processes if they terminate early.

subprocessmanager runs the miro_helper.py script for it's child processes.
Platforms need to ensure that this script is available and that it can be run
with the command line and env from plat.utils.miro_helper_program_info().
"""

import cPickle as pickle
import logging
import os
import struct
import subprocess
import sys
import threading
import warnings
import Queue

from miro import app
from miro import config
from miro import prefs
from miro import crashreport
from miro import eventloop
from miro import gtcache
from miro import messagetools
from miro import trapcall
from miro import util
from miro.plat.utils import miro_helper_program_info, initialize_locale

def _on_windows():
    """Test if we are unfortunate enough to be running in windows."""
    return sys.platform == 'win32'

# DESIGN NOTES:
#
# ** Protocol between miro and subprocesses **
#
# We spawn a child process and communicate to it by sending messages through
# it's stdin and stdout.  Each message contains a length (a unsigned long)
# followed by a pickled object.
#
# The communication goes like this:
#
#   1) The main process sends the StartupInfo then HandlerInfo messages.
#   2) The subprocess and process exchange messages through stdout/stdin
#   3) The main process sends None to stdin to indicate that it's through
#      sending messages and the subprocess should quit.  The subprocess should
#      then finish up and send back None over stdout.
#
# ** MessageHandlers **
#
# We create 4 MessageHandler-like objects for each subprocess.
#
# In the subprocess, we create a SubprocessHandler to handle the messages
# coming from the main process and a PipeMessageProxy that handles messages
# going to the main process by writing them to stdout.
#
# In the main process, we create a SubprocessResponder to handle the messages
# coming back from the subprocess, and use the SubprocessManager object to
# handle messages going to the subprocess by writing them to the subproccess's
# stdin.

class SubprocessMessage(messagetools.Message):
    """Message from the main process to a subprocess.

    For every subprocess, you must define a subclass of this to pass to the
    SubprocessManager constructor.
    """

    def send_to_process(self):
        try:
            handler = self.handler
        except AttributeError:
            logging.warn("No handler for %s" % self)
        else:
            handler.handle(self)

class StartupInfo(SubprocessMessage):
    """Data needed to bootstrap the subprocess."""
    def __init__(self, config_dict):
        self.config_dict = config_dict

class HandlerInfo(SubprocessMessage):
    """Describes how to build a SubprocessHandler object."""

    def __init__(self, handler_class, handler_args):
        self.handler_class = handler_class
        self.handler_args = handler_args

class SubprocessResponse(messagetools.Message):
    """Message from a subprocess to the main process."""

    def send_to_main_process(self):
        try:
            handler = self.handler
        except AttributeError:
            logging.warn("No handler for %s" % self)
        else:
            handler.handle(self)

class SubprocessError(SubprocessResponse):
    """Handle an error in the subprocess."""

    def __init__(self, report, soft_fail):
        self.report = report
        self.soft_fail = soft_fail

def _send_subprocess_error_for_exception(soft_fail=True):
    exc_info = sys.exc_info()
    report = '---- subprocess stack ---- '
    report += crashreport.format_stack_report('in subprocess', exc_info)
    report += '-------------------------- '
    SubprocessError(report, soft_fail=soft_fail).send_to_main_process()

class SubprocessHandler(messagetools.MessageHandler):
    """Handle messages inside a spawned subprocess

    SubprocessHandler is a subclass of MessageHandler, and it uses the same
    basic approach for message passing.  Messages are sent back and forth
    between the main process and the subprocess and they are handled using
    methods named like handle_message_name.

    In addition, SubprocessHandler defines a bunch of methods that will be
    called to handle events in the process lifecycle, like startup and
    shutdown.
    """

    def call_handler(self, method, message):
        # There's only one thread in the subprocess.  We can just call the
        # method directly.
        try:
            method(message)
        except StandardError:
            _send_subprocess_error_for_exception()

    # NOTE: we use "on_" prefix to distinguish these from messages
    def on_startup(self):
        """Called after the subprocess starts up."""
        pass

    def on_shutdown(self):
        """Called just before the subprocess shuts down."""
        pass

class SubprocessResponder(messagetools.MessageHandler):
    """Handle messages coming back from a subprocess

    SubprocessResponder is a MessageHandler that runs inside the main miro
    thread.  It's methods are called inside the eventloop.

    In addition, SubprocessResponder defines a bunch of methods that will be
    called to handle events in the process lifecycle, like startup and
    shutdown.
    """

    def call_handler(self, method, message):
        # this executes in the thread reading from the subprocess pipe.  Move
        # things into the backend thread.
        name = 'handle subprocess message: %s' % message
        eventloop.add_idle(method, name, args=(message,))

    def on_startup(self):
        """Called after the subprocess starts up."""
        pass

    def on_shutdown(self):
        """Called after the subprocess shuts down."""
        pass

    def on_restart(self):
        """Called after the subprocess restarts after a crash."""
        pass

    def handle_subprocess_error(self, msg):
        if msg.soft_fail:
            app.controller.failed_soft('in subprocess', msg.report)
        else:
            logging.warn("Error in subprocess: %s", msg.report)

class LoadError(StandardError):
    """Exception for corrupt data when reading from a pipe."""

SIZEOF_LONG = struct.calcsize("L")

def _read_bytes_from_pipe(pipe, length):
    """Read size bytes from a pipe.

    This is different from just calling read() because read can return partial
    data.

    This method call read() until either:
      a) read() returns no data, meaning the pipe is closed
      b) we've read length bytes
    """
    data = []
    while length > 0:
        d = pipe.read(length)
        if d == '':
            break
        length -= len(d)
        data.append(d)
    return ''.join(data)

def _load_obj(pipe):
    """Load an object from one side of a pipe.

    _load_obj blocks until the all the data has been sent.

    :raises IOError: low-level error while reading from the pipe
    :raises LoadError: data read was corrupted

    :returns: Python object send from the other side
    """
    size_data = _read_bytes_from_pipe(pipe, SIZEOF_LONG)
    if len(size_data) < SIZEOF_LONG:
        raise LoadError("EOF reached while reading size field "
                "(read %s bytes)" % len(size_data))
    size = struct.unpack("L", size_data)[0]
    pickle_data = _read_bytes_from_pipe(pipe, size)
    if len(pickle_data) < size:
        raise LoadError("EOF reached while reading pickle data "
                "(read %s bytes)" % len(pickle_data))
    try:
        return pickle.loads(pickle_data)
    except pickle.PickleError:
        raise LoadError("Pickle data corrupt")
    except ImportError:
        raise LoadError("Pickle data references unimportable module")
    except StandardError, e:
        # log this exception for easier debugging.
        _send_subprocess_error_for_exception()
        raise LoadError("Unknown error in pickle.loads: %s" % e)

def _dump_obj(obj, pipe):
    """Dump an object to the other side of the pipe.

    :raises IOError: low-level error while writing to the pipe
    :raises pickle.PickleError: obj could not be pickled
    """

    pickle_data = pickle.dumps(obj)
    size_data = struct.pack("L", len(pickle_data))
    # NOTE: We do a blocking write here.  This should be fine, since on both
    # sides we have a thread dedicated to just reading from the pipe and
    # pushing the data into a Queue.  However, there's some chance that the
    # process on the other side has gone really haywire and the reader thread
    # is hung.  I (BDK) can't really see a way for this to realistically
    # happen, so we stick with blocking writes.
    pipe.write(size_data)
    pipe.write(pickle_data)
    pipe.flush()

class SubprocessManager(object):
    """Manages a running subprocess

    SubprocessManager handles startup/shutdown of a process, restarting the
    process if it crashes, and sending/receiving messages from the process.
    """

    def __init__(self, message_base_class, responder, handler_class,
            handler_args=None):
        """Create a new SubprocessManager.

        This method prepares the subprocess to run.  Use start() to start it
        up.

        We will install a MessageHandler for message_base_class that sends
        them to the subprocess.

        responder will receive callbacks when the subprocess sends messages.

        handler_class and handler_args are used to build the SubprocessHandler
        inside the subprocess
        """
        if handler_args is None:
            handler_args = ()
        message_base_class.install_handler(self)
        self.responder = responder
        self.handler_class = handler_class
        self.handler_args = handler_args
        self.is_running = False
        self.process = None
        self.thread = None

    # Process management

    def start(self):
        """Startup the subprocess.
        """
        if self.is_running:
            return
        self._start()

    def _start(self):
        """Does the work to startup a new process/thread."""
        # create our child process.
        self.process = self._start_subprocess()
        # create thread to handle the subprocess's output.  It would be nice
        # to eliminate this thread, but I don't see an easy way to integrate
        # it into the eventloop, since windows doesn't have support for
        # select() on pipes.
        #
        # This thread only handles the subprocess output.  We write to the
        # subprocess stdin from the eventloop.
        self.thread = SubprocessResponderThread(self.process.stdout,
                self.responder, self._on_thread_quit)
        self.thread.daemon = True
        self.thread.start()
        # work is all done, do some finishing touches
        self.is_running = True
        self._send_startup_info()
        trapcall.trap_call("subprocess startup", self.responder.on_startup)

    def _start_subprocess(self):
        cmd_line, env = miro_helper_program_info()
        kwargs = {
                  "stdout": subprocess.PIPE,
                  "stdin": subprocess.PIPE,
                  "startupinfo": util.no_console_startupinfo(),
                  "env": env,
        }
        if _on_windows():
            # normally we just clone stderr for the subprocess, but on windows
            # this doesn't work.  So we use a pipe that we immediately close
            kwargs["stderr"] = subprocess.PIPE
        else:
            kwargs["stderr"] = None
            kwargs["close_fds"] = True
        process = subprocess.Popen(cmd_line, **kwargs)
        if _on_windows():
            process.stderr.close()
        return process

    def shutdown(self, timeout=1.0):
        """Shutdown the subprocess.

        This method tries to shutdown the subprocess cleanly, waits until
        timeout expires, then terminates it.
        """
        if not self.is_running:
            return

        # we're about to shut down, tell our responder
        trapcall.trap_call("subprocess shutdown", self.responder.on_shutdown)
        # Politely ask our process to shutdown
        self.send_quit()
        # If things go right, the process will quit, then our thread will
        # quit.  Wait for a clean shutdown
        self.thread.join(timeout)
        # If things didn't shutdown, then force them to quit.  Let's not
        # bother with SIGTERM since that really also would be an abnormal
        # exit as far as the child is concerned.
        try:
            self.process.kill()
        except OSError, e:
            # Error on kill.  Just log an error and move on.  Nothing
            # much we can do here anyway.
            logging.exception('worker subprocess kill failed')
        self._cleanup_process()

    def _on_thread_quit(self, thread):
        """Handle our thread exiting."""

        # Ignore this call if it was queued from while we were in the middle
        # of shutdown().
        if not self.is_running:
            return

        if thread is not self.thread:
            # If we have lost the race between the cleanup on shutdown
            # it should be safe to ignore.
            #
            # This can happen when the process does not immediately shut down
            # because the worker process is still processing pending jobs
            # and the quit message was not processed in time and so the
            # subprocess was forcibly terminated.  When that happens
            # _cleanup_process() is called which resets the thread attribute
            # to None immediately, but _on_thread_quit() is only run some
            # time after that (when we notice the pipe to the subprocess's
            # close we add _on_thread_quit() to the idle loop).
            #
            # So if the self.thread attribute is None then it means we are done
            # and so things are all good.
            if self.thread is not None:
                app.controller.failed_soft('handling subprocess',
                        '_on_thread_quit called by an old thread')
            return

        if self.thread.quit_type == self.thread.QUIT_NORMAL:
            self._cleanup_process()
        else:
            logging.warn("Restarting failed subprocess (reason: %s)",
                    self.thread.quit_type)
            # NOTE: should we enforce some sort of cool-down time before
            # restarting the subprocess?
            self._restart()

    def _restart(self):
        # close our stream to the subprocess
        self.process.stdin.close()
        # unset our attributes for the process that just quit.  This protects
        # us in case _start() fails for some reason.
        self._cleanup_process()
        # restart ourselves
        self._start()
        trapcall.trap_call("subprocess restart", self.responder.on_restart)

    def _cleanup_process(self):
        """Cleanup after our process quits."""

        self.thread = None
        self.process = None
        self.is_running = False

    # Handle communication to our child process

    def send_message(self, msg):
        """Send a message to our subprocess """

        if not self.is_running:
            raise ValueError("subprocess not running")
        try:
            _dump_obj(msg, self.process.stdin)
        except IOError:
            logging.warn("Broken pipe in send_message()")
            # we could try to restart our subprocess here, but if the pipe is
            # really broken, then our thread will quit soon and this will
            # cause a restart.
        except pickle.PickleError:
            logging.warn("Error pickling message in send_message() (%s)", msg)

    def send_quit(self):
        """Ask the subprocess to shutdown."""
        self.send_message(None)

    def _send_startup_info(self):
        self.send_message(StartupInfo(self._get_config_dict()))
        self.send_message(HandlerInfo(self.handler_class, self.handler_args))

    def _get_config_dict(self):
        """Generate a dict with the config items needed in the subprocess.

        We just send over the bare minimum needed to make sure basic modules
        like gtcache load properly.
        """
        # On OS X, the proxy information is in a CFDictionary, so we can't
        # pickle it.  Just avoid sending it for now
        prefs_to_send = [p for p in prefs.all_prefs()
                if not p.key.startswith("HttpProxy")
        ]
        return dict((p.key, app.config.get(p)) for p in prefs_to_send)

    # implement the MessageHandler interface

    def handle(self, msg):
        # just forward the message to our process
        self.send_message(msg)

def _read_from_pipe(pipe):
    """Read objects from a pipe.

    This method is a generator that reads pickled objects from pipe.  It
    terminates when None is sent over the pipe.

    raises the same exceptions that _load_obj does, namely:

    :raises IOError: low-level error while reading from the pipe
    :raises LoadError: data read was corrupted
    """
    while True:
        msg = _load_obj(pipe)
        if msg is None:
            return # other side wants to quit
        yield msg

class SubprocessResponderThread(threading.Thread):
    """Thread that implements our run loop to handle subprocess output.

    :ivar quit_type: Reason why the thread quit (or None)
    """

    # constants for quit_type
    QUIT_NORMAL = 0
    QUIT_READ_ERROR = 1
    QUIT_BAD_DATA = 2
    QUIT_UNKNOWN = 3

    def __init__(self, subprocess_stdout, responder, quit_callback):
        """Create a new SubprocessResponderThread

        :param subprocess_stdout: STDOUT pipe from our subprocess
        :param responder: SubprocessResponder object to handle messages
        """

        threading.Thread.__init__(self)
        self.daemon = False
        self.subprocess_stdout = subprocess_stdout
        self.responder = responder
        self.quit_callback = quit_callback
        self.quit_type = None

    def run(self):
        try:
            for msg in _read_from_pipe(self.subprocess_stdout):
                self.responder.handle(msg)
        except LoadError, e:
            logging.warn("Quiting from bad data from our subprocess in "
                    "SubprocessResponderThread: %s", e)
            self.quit_type = self.QUIT_BAD_DATA
        except IOError, e:
            logging.warn("Quiting on read error from pipe in "
                    "SubprocessResponderThread: %s", e)
            self.quit_type = self.QUIT_READ_ERROR
        except Exception, e:
            logging.exception("Unknown error in SubprocessResponderThread")
            self.quit_type = self.QUIT_UNKNOWN
        else:
            self.quit_type = self.QUIT_NORMAL
        eventloop.add_idle(self.quit_callback, 'subprocess quit callback',
                args=(self,))

def subprocess_main():
    """Run loop inside the subprocess."""
    # make sure that we are using binary mode for stdout
    if _on_windows():
        import msvcrt
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    # unset stdin and stdout so that we don't accidentally print to them
    stdin = sys.stdin
    stdout = sys.stdout
    sys.stdout = sys.stdin = None
    # initialize things
    try:
        handler = _subprocess_setup(stdin, stdout)
    except Exception, e:
        # error reading our initial messages.  Try to log a warning, then
        # quit.
        _send_subprocess_error_for_exception()
        _finish_subprocess_message_stream(stdout)
        raise # reraise so that miro_helper.py returns a non-zero exit code
    # startup thread to process stdin
    queue = Queue.Queue()
    thread = threading.Thread(target=_subprocess_pipe_thread, args=(stdin,
        queue))
    thread.daemon = False
    thread.start()
    # run our message loop
    handler.on_startup()
    try:
        while True:
            msg = queue.get()
            if msg is None:
                break
            handler.handle(msg)
    finally:
        handler.on_shutdown()
        # send None to signal that we are about to quit
        _finish_subprocess_message_stream(stdout)
        # exceptions will continue on here, which causes miro_helper.py
        # to return a non-zero exit code

def _finish_subprocess_message_stream(stdout):
    """Signal that we are done sending messages in the subprocess."""
    try:
        _dump_obj(None, stdout)
    except IOError:
        # just ignore since we're done writing out anyways
        pass
    # Note we don't catch PickleError, but there should never be an issue
    # pickling None

def _subprocess_setup(stdin, stdout):
    """Does initial setup for a subprocess.

    Returns a SubprocessHandler to use for the subprocess

    raises the same exceptions that _load_obj does, namely:

    :raises IOError: low-level error while reading from the pipe
    :raises LoadError: data read was corrupted
    """
    # disable warnings so we don't get too much junk on stderr
    warnings.filterwarnings("ignore")
    # setup MessageHandler for messages going to the main process
    msg_handler = PipeMessageProxy(stdout)
    SubprocessResponse.install_handler(msg_handler)
    # load startup info
    msg = _load_obj(stdin)
    if not isinstance(msg, StartupInfo):
        raise LoadError("first message must a StartupInfo obj")
    # setup some basic modules like config and gtcache
    initialize_locale()
    config.load(config.ManualConfig())
    app.config.set_dictionary(msg.config_dict)
    gtcache.init()
    # setup our handler
    msg = _load_obj(stdin)
    if not isinstance(msg, HandlerInfo):
        raise LoadError("second message must a HandlerInfo obj")
    try:
        return msg.handler_class(*msg.handler_args)
    except StandardError, e:
        # log this exception for easier debugging.
        _send_subprocess_error_for_exception()
        raise LoadError("Exception while constructing handler: %s" % e)

def _subprocess_pipe_thread(stdin, queue):
    """Thread inside the subprocess that reads messages from stdin.

    We use a separate thread so that our pipe doesn't get backed up while we
    are process messages
    """
    try:
        for msg in _read_from_pipe(stdin):
            queue.put(msg)
    except StandardError, e:
        # we could try to send a SubprocessError message, but it's highly
        # likely that our main process is dead, so it's simplest to just avoid
        # writing to the (likely closed) stdout pipe.
        pass
    # put None to our queue so the main thread quits
    queue.put(None)

class PipeMessageProxy(object):
    """Handles messages by writing them to a pipe

    This is used in the subprocess to send messages back to the main process
    over it's stdout pipe.
    """
    def __init__(self, fileobj):
        self.fileobj = fileobj

    def handle(self, msg):
        try:
            _dump_obj(msg, self.fileobj)
        except pickle.PickleError:
            _send_subprocess_error_for_exception()
        # NOTE: we don't handle IOError here because what can we do about
        # that?  Just let it propagate up to the top and which should cause us
        # to shutdown.
