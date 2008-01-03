# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import os
import sys
import logging

# Import the pysqlite module before the Foundation or AppKit modules to avoid
# (very) weird errors ("library routine called out of sequence") and even 
# crashes on Leopard, probably due to a conflict between the standard OS X 
# sqlite lib and our own most recent one.
from pysqlite2 import dbapi2

import Foundation

# =============================================================================

def activatePsyco():
    # Detect cpu type
    import subprocess
    p = subprocess.Popen(["uname", "-p"], stdout=subprocess.PIPE) 
    cpu = p.stdout.read().strip()
    p.stdout.close()

    # Activate only if we are on an Intel Mac.
    if cpu == 'i386':
        try:
            print "DTV: Intel CPU detected, using psyco charge profiler."
            import psyco
            psyco.profile()
        except:
            print "DTV: Error while trying to launch psyco charge profiler."

# =============================================================================

def launchApplication():
    import migrateappname
    migrateappname.migrateSupport('Democracy', 'Miro')

    # We can now import our stuff
    import platformutils
    platformutils.initializeLocale()

    import gtcache
    gtcache.init()

    import controller
    import prefs
    import config

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
    controller.main()

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
    resource.setrlimit(resource.RLIMIT_NOFILE, (-1,-1))

    # Insert the downloader private module path
    daemonPath = getModulePath('dl_daemon')
    daemonPrivatePath = os.path.join(daemonPath, 'private')
    sys.path[0:0] = [daemonPath, daemonPrivatePath]
    
    # Make sure we don't leak from the downloader eventloop
    import eventloop

    def beginLoop(loop):
        loop.pool = Foundation.NSAutoreleasePool.alloc().init()
    eventloop.connect('begin-loop', beginLoop)

    def endLoop(loop):
        del loop.pool
    eventloop.connect('end-loop', endLoop)
    
    # And launch
    import Democracy_Downloader
    Democracy_Downloader.launch()

# =============================================================================

# Uncomment the following two lines to check for non unicode string trying to
# cross the PyObjC bridge...
#import objc
#objc.setStrBridgeEnabled(False)

# If the bundle is an alias bundle, we need to tweak the search path
bundle = Foundation.NSBundle.mainBundle()
bundleInfo = bundle.infoDictionary()
if bundleInfo['PyOptions']['alias']:
    root = os.path.dirname(bundle.bundlePath())
    root = os.path.join(root, '..', '..')
    root = os.path.normpath(root)
    sys.path[0:0] = ['%s/portable' % root]

# Activate psyco, if we are running on an Intel Mac
#
# We currently dont do it because psyco does not work correctly on Intel Macs 
# yet, as explained here: 
# http://mail.python.org/pipermail/pythonmac-sig/2006-June/017533.html

#activatePsyco()


# Launch player or downloader, depending on command line parameter
if len(sys.argv) > 1 and sys.argv[1] == "download_daemon":
    launchDownloaderDaemon()
else:
    launchApplication()

