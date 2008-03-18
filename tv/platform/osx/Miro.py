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

import os
import sys
import logging

# Import the pysqlite module before the Foundation or AppKit modules to avoid
# (very) weird errors ("library routine called out of sequence") and even 
# crashes on Leopard, probably due to a conflict between the standard OS X 
# sqlite lib and our own most recent one.
try:
    from pysqlite2 import dbapi2
except ImportError:
    from sqlite3 import dbapi2

import Foundation

# =============================================================================

def activatePsyco():
    # Get cpu type
    info = os.uname()
    cpu = info[-1]

    # Activate only if we are on an Intel Mac.
    if cpu == 'i386':
        try:
            import psyco
            psyco.profile()
        except:
            pass

# =============================================================================

def launchApplication():
    from miro.platform import migrateappname
    migrateappname.migrateSupport('Democracy', 'Miro')

    from miro.platform.utils import initializeLocale
    initializeLocale()
    
    from glob import glob
    theme = None
    bundle = Foundation.NSBundle.mainBundle()
    bundlePath = bundle.bundlePath()
    bundleThemeDirPath = os.path.join(bundlePath, "Contents", "Theme")
    if os.path.exists(bundleThemeDirPath):
        themeDirs = glob(os.path.join(bundleThemeDirPath, "*"))
        themeDir = themeDirs[0]
        if os.path.isdir(themeDir):
            theme = os.path.basename(themeDir)

    from miro import gtcache
    gtcache.init()

    from miro import startup
    startup.initialize(theme)

    from miro import config
    from miro import prefs

    # Tee output off to a log file
    class AutoflushingTeeStream:
        def __init__(self, streams):
            self.streams = streams
        def write(self, *args):
            for s in self.streams:
                s.write(*args)
            self.flush()
        def flush(self):
            for s in self.streams:
                s.flush()

    logFile = config.get(prefs.LOG_PATHNAME)
    if logFile:
        h = open(logFile, "wt")
        sys.stdout = AutoflushingTeeStream([h, sys.stdout])
        sys.stderr = AutoflushingTeeStream([h, sys.stderr])

    # Kick off the application
    from AppKit import NSApplication
    NSApplication.sharedApplication()

    from miro.platform.frontends.html.Application import Application
    Application().run()

# =============================================================================

def getModulePath(name):
    import imp
    mfile, mpath, mdesc = imp.find_module(name)
    if mfile is not None:
        mfile.close()
    return mpath

def launchDownloaderDaemon():
    # Increase the maximum file descriptor count (to the max)
    import resource
    logging.info('Increasing file descriptor count limit in Downloader.')
    resource.setrlimit(resource.RLIMIT_NOFILE, (10240,-1))

    # Make sure we don't leak from the downloader eventloop
    from miro import eventloop

    def beginLoop(loop):
        loop.pool = Foundation.NSAutoreleasePool.alloc().init()
    eventloop.connect('begin-loop', beginLoop)

    def endLoop(loop):
        del loop.pool
    eventloop.connect('end-loop', endLoop)
    
    # And launch
    from miro.dl_daemon import Democracy_Downloader
    Democracy_Downloader.launch()

# =============================================================================

# Uncomment the following two lines to check for non unicode string trying to
# cross the PyObjC bridge...
#import objc
#objc.setStrBridgeEnabled(False)

# Activate psyco, if we are running on an Intel Mac

activatePsyco()

# Launch player or downloader, depending on command line parameter
if len(sys.argv) > 1 and sys.argv[1] == "download_daemon":
    launchDownloaderDaemon()
else:
    launchApplication()

