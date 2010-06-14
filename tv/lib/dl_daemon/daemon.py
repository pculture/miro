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

from miro.dl_daemon import command
import os
import cPickle
from struct import pack, unpack, calcsize
import tempfile
from miro import config
from miro import prefs
from miro import eventloop
from miro import httpclient
import logging
from miro.plat.utils import launch_download_daemon, kill_process
from miro import signals
from miro import trapcall
from miro.net import ConnectionHandler

SIZE_OF_INT = calcsize("I")

class DaemonError(Exception):
    """Exception while communicating to a daemon (either controller or
    downloader).
    """
    pass

FIRST_DAEMON_LAUNCH = '1'

def start_download_daemon(oldpid, port):
    global FIRST_DAEMON_LAUNCH

    daemon_env = {
        'DEMOCRACY_DOWNLOADER_PORT' : str(port),
        'DEMOCRACY_DOWNLOADER_FIRST_LAUNCH' : FIRST_DAEMON_LAUNCH,
        'DEMOCRACY_SHORT_APP_NAME' : config.get(prefs.SHORT_APP_NAME),
    }
    launch_download_daemon(oldpid, daemon_env)
    FIRST_DAEMON_LAUNCH = '0'

def get_data_filename(short_app_name):
    """Generates and returns the name of the file that stores the pid.
    """
    if hasattr(os, "getuid"):
        uid = os.getuid()
    elif "USERNAME" in os.environ:
        # This works for win32, where we don't have getuid()
        uid = os.environ['USERNAME']
    elif "USER" in os.environ:
        uid = os.environ['USER']
    else:
        # FIXME - can we do something better here on Windows
        # platforms?
        uid = "unknown"

    return os.path.join(tempfile.gettempdir(),
            ('%s_Download_Daemon_%s.txt' % (short_app_name, uid)))

PIDFILE = None

def write_pid(short_app_name, pid):
    """Write out our pid.

    This method locks the pid file until the downloader exits.

    On windows this is achieved by keeping the file open.

    On Linux/OS X, we use the fcntl.lockf() function.
    """
    global PIDFILE
    # NOTE: we want to open the file in a mode the standard open() doesn't
    # support.  We want to create the file if nessecary, but not truncate it
    # if it's already around.  We can't truncate it because on unix we haven't
    # locked the file yet.
    fd = os.open(get_data_filename(short_app_name), os.O_WRONLY | os.O_CREAT)
    PIDFILE = os.fdopen(fd, 'w')
    if os.name != "nt":
        import fcntl
        fcntl.lockf(PIDFILE, fcntl.LOCK_EX | fcntl.LOCK_NB)

    PIDFILE.write("%s\n" % pid)
    PIDFILE.flush()
    # NOTE: There may be extra data after the line we write left around from
    # previous writes to the pid file.  This is fine since read_pid() only reads
    # the 1st line.
    #
    # NOTE 2: we purposely don't close the file, to achieve locking on
    # windows.

def read_pid(short_app_name):
    try:
        f = open(get_data_filename(short_app_name), "r")
    except IOError:
        return None
    try:
        try:
            return int(f.readline())
        except ValueError:
            return None
    finally:
        f.close()

LAST_DAEMON = None

class Daemon(ConnectionHandler):
    def __init__(self):
        ConnectionHandler.__init__(self)
        global LAST_DAEMON
        LAST_DAEMON = self
        self.size = 0
        self.states['ready'] = self.on_size
        self.states['command'] = self.on_command
        self.queued_commands = []
        self.shutdown = False
        # disable read timeouts for the downloader daemon communication.  Our
        # normal state is to wait for long periods of time for without seeing
        # any data.
        self.stream.disable_read_timeout = True

    def on_error(self, error):
        """Call this when an error occurs.  It forces the daemon to
        close its connection.
        """
        logging.warning("socket error in daemon, closing my socket")
        self.close_connection()
        raise error

    def on_connection(self, socket):
        self.change_state('ready')
        for (comm, callback) in self.queued_commands:
            self.send(comm, callback)
        self.queued_commands = []

    def on_size(self):
        if self.buffer.length >= SIZE_OF_INT:
            (self.size,) = unpack("I", self.buffer.read(SIZE_OF_INT))
            self.change_state('command')

    def on_command(self):
        if self.buffer.length >= self.size:
            try:
                comm = cPickle.loads(self.buffer.read(self.size))
            except cPickle.UnpicklingError:
                logging.exception("WARNING: error unpickling command.")
            else:
                self.process_command(comm)
            self.change_state('ready')

    def process_command(self, comm):
        trapcall.time_trap_call("Running: %s" % comm, self.run_command, comm)

    def run_command(self, comm):
        logging.debug("run command: %r", comm)
        comm.set_daemon(self)
        comm.action()

    def send(self, comm, callback = None):
        if self.state == 'initializing':
            self.queued_commands.append((comm, callback))
        else:
            raw = cPickle.dumps(comm, cPickle.HIGHEST_PROTOCOL)
            self.send_data(pack("I", len(raw)) + raw, callback)

class DownloaderDaemon(Daemon):
    def __init__(self, port, short_app_name):
        # before anything else, write out our PID
        write_pid(short_app_name, os.getpid())
        # connect to the controller and start our listen loop
        Daemon.__init__(self)
        self.open_connection('127.0.0.1', port, self.on_connection,
                             self.on_error)
        signals.system.connect('error', self.handle_error)

    def handle_error(self, obj, report):
        command.DownloaderErrorCommand(self, report).send()

    def handle_close(self, type_):
        if self.shutdown:
            return
        self.shutdown = True
        eventloop.shutdown()
        httpclient.cleanup_libcurl()
        logging.warning("downloader: connection closed -- quitting")
        from miro.dl_daemon import download
        download.shutdown()
        import threading
        for thread in threading.enumerate():
            if thread != threading.currentThread() and not thread.isDaemon():
                thread.join()

class ControllerDaemon(Daemon):
    def __init__(self):
        Daemon.__init__(self)
        self.stream.acceptConnection('127.0.0.1', 0,
                                     self.on_connection, self.on_error)
        self.port = self.stream.port
        data = {}
        remote_config_items = [
            prefs.LIMIT_UPSTREAM,
            prefs.UPSTREAM_LIMIT_IN_KBS,
            prefs.LIMIT_DOWNSTREAM_BT,
            prefs.DOWNSTREAM_BT_LIMIT_IN_KBS,
            prefs.BT_MIN_PORT,
            prefs.BT_MAX_PORT,
            prefs.USE_UPNP,
            prefs.BT_ENC_REQ,
            prefs.MOVIES_DIRECTORY,
            prefs.PRESERVE_DISK_SPACE,
            prefs.PRESERVE_X_GB_FREE,
            prefs.SUPPORT_DIRECTORY,
            prefs.SHORT_APP_NAME,
            prefs.LONG_APP_NAME,
            prefs.APP_PLATFORM,
            prefs.APP_VERSION,
            prefs.APP_SERIAL,
            prefs.APP_REVISION,
            prefs.PUBLISHER,
            prefs.PROJECT_URL,
            prefs.DOWNLOADER_LOG_PATHNAME,
            prefs.LOG_PATHNAME,
            prefs.GETTEXT_PATHNAME,
            prefs.LIMIT_UPLOAD_RATIO,
            prefs.UPLOAD_RATIO,
            prefs.LIMIT_CONNECTIONS_BT,
            prefs.CONNECTION_LIMIT_BT_NUM,
            ]

        for desc in remote_config_items:
            data[desc.key] = config.get(desc)
        c = command.InitialConfigCommand(self, data)
        c.send()
        config.add_change_callback(self.update_config)
        self.shutdown_callback = None
        self.shutdown_timeout_dc = None

    def start_downloader_daemon(self):
        start_download_daemon(self.read_pid(), self.port)

    def update_config(self, key, value):
        if not self.shutdown:
            c = command.UpdateConfigCommand(self, key, value)
            c.send()

    def read_pid(self):
        short_app_name = config.get(prefs.SHORT_APP_NAME)
        return read_pid(short_app_name)

    def handle_close(self, type_):
        if not self.shutdown:
            logging.warning("Downloader Daemon died")
            # FIXME: replace with code to recover here, but for now,
            # stop sending.
            self.shutdown = True
            config.remove_change_callback(self.update_config)

    def shutdown_timeout_cb(self):
        logging.warning("killing download daemon")
        kill_process(self.read_pid())
        self.shutdown_response()

    def shutdown_response(self):
        if self.shutdown_callback:
            self.shutdown_callback()
        if self.shutdown_timeout_dc:
            self.shutdown_timeout_dc.cancel()

    def shutdown_downloader_daemon(self, timeout=5, callback=None):
        """Send the downloader daemon the shutdown command.  If it
        doesn't reply before timeout expires, kill it.  (The reply is
        not sent until the downloader daemon has one remaining thread
        and that thread will immediately exit).
        """
        self.shutdown_callback = callback
        c = command.ShutDownCommand(self)
        c.send()
        self.shutdown = True
        config.remove_change_callback(self.update_config)
        self.shutdown_timeout_dc = eventloop.add_timeout(
            timeout, self.shutdown_timeout_cb, "Waiting for dl_daemon shutdown")
