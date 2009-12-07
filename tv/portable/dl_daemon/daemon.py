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

from miro.dl_daemon import command
import os
import cPickle
import socket
import traceback
from time import sleep
from struct import pack, unpack, calcsize
import tempfile
from miro import config
from miro import prefs
from miro import eventloop
from miro import util
import logging
from miro.plat.utils import launch_download_daemon, kill_process
from miro import signals
from miro import trapcall
from miro.httpclient import ConnectionHandler

SIZE_OF_INT = calcsize("I")

class DaemonError(Exception):
    """Exception while communicating to a daemon (either controller or
    downloader).
    """
    pass

firstDaemonLaunch = '1'
def startDownloadDaemon(oldpid, port):
    global firstDaemonLaunch

    daemonEnv = {
        'DEMOCRACY_DOWNLOADER_PORT' : str(port),
        'DEMOCRACY_DOWNLOADER_FIRST_LAUNCH' : firstDaemonLaunch,
        'DEMOCRACY_SHORT_APP_NAME' : config.get(prefs.SHORT_APP_NAME),
    }
    launch_download_daemon(oldpid, daemonEnv)
    firstDaemonLaunch = '0'

def getDataFile(short_app_name):
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

pidfile = None
def writePid(short_app_name, pid):
    """Write out our pid.

    This method locks the pid file until the downloader exits.  On windows
    this is achieved by keeping the file open.  On Unix/OS X, we use the
    fcntl.lockf() function.
    """

    global pidfile
    # NOTE: we want to open the file in a mode the standard open() doesn't
    # support.  We want to create the file if nessecary, but not truncate it
    # if it's already around.  We can't truncate it because on unix we haven't
    # locked the file yet.
    fd = os.open(getDataFile(short_app_name), os.O_WRONLY | os.O_CREAT)
    pidfile = os.fdopen(fd, 'w')
    try:
        import fcntl
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        pass
    else:
        fcntl.lockf(pidfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    pidfile.write("%s\n" % pid)
    pidfile.flush()
    # NOTE: There may be extra data after the line we write left around from
    # previous writes to the pid file.  This is fine since readPid() only reads
    # the 1st line.
    #
    # NOTE 2: we purposely don't close the file, to achieve locking on
    # windows.

def readPid(short_app_name):
    try:
        f = open(getDataFile(short_app_name), "r")
    except IOError:
        return None
    try:
        try:
            return int(f.readline())
        except ValueError:
            return None
    finally:
        f.close()

lastDaemon = None

class Daemon(ConnectionHandler):
    def __init__(self):
        ConnectionHandler.__init__(self)
        global lastDaemon
        lastDaemon = self
        self.waitingCommands = {}
        self.returnValues = {}
        self.size = 0
        self.states['ready'] = self.onSize
        self.states['command'] = self.onCommand
        self.queuedCommands = []
        self.shutdown = False
        self.stream.disableReadTimeout = True
        # disable read timeouts for the downloader daemon communication.  Our
        # normal state is to wait for long periods of time for without seeing
        # any data.

    def onError(self, error):
        """Call this when an error occurs.  It forces the
        daemon to close its connection.
        """
        logging.warning ("socket error in daemon, closing my socket")
        self.closeConnection()
        raise error

    def onConnection(self, socket):
        self.changeState('ready')
        for (comm, callback) in self.queuedCommands:
            self.send(comm, callback)
        self.queuedCommands = []

    def onSize(self):
        if self.buffer.length >= SIZE_OF_INT:
            (self.size,) = unpack("I", self.buffer.read(SIZE_OF_INT))
            self.changeState('command')

    def onCommand(self):
        if self.buffer.length >= self.size:
            try:
                comm = cPickle.loads(self.buffer.read(self.size))
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                logging.exception ("WARNING: error unpickling command.")
            else:
                self.processCommand(comm)
            self.changeState('ready')

    def processCommand(self, comm):
        trapcall.time_trap_call("Running: %s" % (comm,), self.runCommand, comm)

    def runCommand(self, comm):
        comm.setDaemon(self)
        comm.action()

    def send(self, comm, callback = None):
        if self.state == 'initializing':
            self.queuedCommands.append((comm, callback))
        else:
            raw = cPickle.dumps(comm, cPickle.HIGHEST_PROTOCOL)
            self.sendData(pack("I",len(raw)) + raw, callback)

class DownloaderDaemon(Daemon):
    def __init__(self, port, short_app_name):
        # before anything else, write out our PID 
        writePid(short_app_name, os.getpid())
        # connect to the controller and start our listen loop
        Daemon.__init__(self)
        self.openConnection('127.0.0.1', port, self.onConnection, self.onError)
        signals.system.connect('error', self.handleError)

    def handleError(self, obj, report):
        command.DownloaderErrorCommand(self, report).send()

    def handleClose(self, type):
        if self.shutdown:
            return
        self.shutdown = True
        eventloop.quit()
        logging.warning ("downloader: connection closed -- quitting")
        from miro.dl_daemon import download
        download.shutDown()
        import threading
        for thread in threading.enumerate():
            if thread != threading.currentThread() and not thread.isDaemon():
                thread.join()

class ControllerDaemon(Daemon):
    def __init__(self):
        Daemon.__init__(self)
        self.stream.acceptConnection('127.0.0.1', 0, self.onConnection, self.onError)
        self.port = self.stream.port
        data = {}
        remoteConfigItems = [prefs.LIMIT_UPSTREAM,
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

        for desc in remoteConfigItems:
            data[desc.key] = config.get(desc)
        c = command.InitialConfigCommand(self, data)
        c.send()
        config.add_change_callback(self.updateConfig)

    def start_downloader_daemon(self):
        startDownloadDaemon(self.read_pid(), self.port)

    def updateConfig (self, key, value):
        if not self.shutdown:
            c = command.UpdateConfigCommand (self, key, value)
            c.send()

    def read_pid(self):
        short_app_name = config.get(prefs.SHORT_APP_NAME)
        return readPid(short_app_name)
            
    def handleClose(self, type):
        if not self.shutdown:
            logging.warning ("Downloader Daemon died")
            # FIXME: replace with code to recover here, but for now,
            # stop sending.
            self.shutdown = True
            config.remove_change_callback(self.updateConfig)

    def shutdown_timeout_cb(self):
        logging.warning ("killing download daemon")
        kill_process(self.read_pid())
        self.shutdownResponse()

    def shutdownResponse(self):
        if self.shutdown_callback:
            self.shutdown_callback()
        self.shutdown_timeout_dc.cancel()

    def shutdown_downloader_daemon(self, timeout=5, callback = None):
        """Send the downloader daemon the shutdown command.  If it doesn't
        reply before timeout expires, kill it.  (The reply is not sent until
        the downloader daemon has one remaining thread and that thread will
        immediately exit).
        """
        self.shutdown_callback = callback
        c = command.ShutDownCommand(self)
        c.send()
        self.shutdown = True
        config.remove_change_callback(self.updateConfig)
        self.shutdown_timeout_dc = eventloop.addTimeout(timeout, self.shutdown_timeout_cb, "Waiting for dl_daemon shutdown")
