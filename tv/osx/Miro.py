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

import optparse
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

from Foundation import *

# =============================================================================

def launch_unit_tests():
    sys.argv.remove('--unittest')

    logging.basicConfig(level=logging.CRITICAL)

    from miro.plat.utils import initialize_locale
    initialize_locale()
    from miro import bootstrap
    bootstrap.bootstrap()
    from miro import test

    print 'Running Miro unit tests:'
    test.run_tests()
    
# =============================================================================

def launch_application(parsed_options, args):
    from miro.plat import migrateappname
    migrateappname.migrateSupport('Democracy', 'Miro')

    from miro.plat.utils import initialize_locale
    initialize_locale()

    from glob import glob
    theme = None
    bundle = NSBundle.mainBundle()
    bundle_path = bundle.bundlePath()
    bundle_theme_dir_path = os.path.join(bundle_path, "Contents", "Theme")
    if os.path.exists(bundle_theme_dir_path):
        theme_dirs = glob(os.path.join(bundle_theme_dir_path, "*"))
        theme_dir = theme_dirs[0]
        if os.path.isdir(theme_dir):
            theme = os.path.basename(theme_dir)

    from miro import bootstrap
    bootstrap.bootstrap()

    from miro import app
    from miro import prefs

    # Tee output off to a log file
    class AutoflushingTeeStream:
        def __init__(self, streams):
            self.streams = streams
        def write(self, *args):
            for s in self.streams:
                try:
                    s.write(*args)
                except IOError:
                    pass
            self.flush()
        def flush(self):
            for s in self.streams:
                try:
                    s.flush()
                except IOError:
                    pass

    log_file = app.config.get(prefs.LOG_PATHNAME)
    if log_file:
        h = open(log_file, "wt")
        sys.stdout = AutoflushingTeeStream([h, sys.stdout])
        sys.stderr = AutoflushingTeeStream([h, sys.stderr])

    # handle command line args
    if parsed_options.debugmode:
        if parsed_options.debugmode.lower() in ("y", "yes"):
            app.debugmode = True
        else:
            app.debugmode = False
    from miro import commandline
    commandline.set_command_line_args(args)

    # Kick off the application
    from miro import startfrontend
    startfrontend.run_application(parsed_options.frontend, {}, theme)

    # This code is useless, but it tells py2app that we need to import these
    # modules
    import miro.plat.frontends.widgets.application
    import miro.frontends.cli.application
    import miro.frontends.profilewidgets.application
    import miro.frontends.shell.application

# =============================================================================

def launch_downloader_daemon():
    # Increase the maximum file descriptor count (to the max)
    # NOTE: the info logging is REQUIRED for some unknown reason, if it is not
    # done here, no further logging can be done in the daemon and it gets stuck.
    try:
        import resource
        logging.debug('Increasing file descriptor count limit in Downloader')
        resource.setrlimit(resource.RLIMIT_NOFILE, (10240, -1))
    except ValueError:
        logging.warn('setrlimit failed.')

    # Make sure we don't leak from the downloader eventloop
    from miro import eventloop

    def beginLoop(loop):
        loop.pool = NSAutoreleasePool.alloc().init()
    eventloop.connect('begin-loop', beginLoop)
    eventloop.connect('thread-will-start', beginLoop)

    def endLoop(loop):
        del loop.pool
    eventloop.connect('end-loop', endLoop)
    eventloop.connect('thread-did-start', endLoop)
 
    # set as background task
    info = NSBundle.mainBundle().infoDictionary()
    info["LSBackgroundOnly"] = "1"

    # And launch
    from miro.dl_daemon import MiroDownloader
    MiroDownloader.launch()

    # Wait for the event loop thread to finish.
    # Although this is theorically not necessary since the event loop thread is
    # a non-daemon thread, situations where the downloader daemon exits right
    # after its launch as this function returns have been seen in the wild.
    eventloop.join()

def launch_miro_helper():
    from miro import miro_helper
    from miro.plat import qt_extractor

    # set as background task
    info = NSBundle.mainBundle().infoDictionary()
    info["LSBackgroundOnly"] = "1"

    # Register the quicktime components
    qt_extractor.register_quicktime_components()

    miro_helper.launch()

# =============================================================================

# Uncomment the following two lines to check for non unicode string trying to
# cross the PyObjC bridge...
#import objc
#objc.setStrBridgeEnabled(False)

usage = "usage: %prog [options] [torrent files] [video files]"
parser = optparse.OptionParser(usage=usage)
parser.add_option('--frontend',
                  dest='frontend', metavar='<FRONTEND>',
                  help='Frontend to use (widgets, cli, shell).')
parser.set_defaults(frontend="widgets")

parser.add_option('--download-daemon',
                  dest='download_daemon',
                  action='store_true',
                  help='Start Downloader Process')
parser.set_defaults(download_daemon=False)

parser.add_option('--miro-helper',
                  dest='miro_helper',
                  action='store_true',
                  help='Start Miro Helper Process')
parser.set_defaults(miro_helper=False)

parser.add_option('-p',
                  dest='pid',
                  help='Processor id (used by OS X)')

group = optparse.OptionGroup(parser, "Debugging options")
group.add_option('--debug',
                 dest='debugmode',
                 metavar='<YESNO>',
                 help='Puts Miro in debug mode for easier debugging.')
parser.set_defaults(debugmode="")
group.add_option('--unittest',
                 dest='unittest', action='store_true',
                 help='Run unittests instead of launching the program.')
parser.set_defaults(unittest=False)
group.add_option('-v',
                 dest='unittest_verbose', action='store_true',
                 help='Run unittests in verbose mode.')
parser.set_defaults(unittest_verbose=False)
group.add_option('--failfast',
                  dest='unittest_failfast', action='store_true',
                  help='Run unittests and stop on first failure.')
parser.set_defaults(unittest_failfast=False)
(parsed_options, args) = parser.parse_args()

# Launch player or downloader, depending on command line parameter`
if parsed_options.download_daemon:
    launch_downloader_daemon()
elif parsed_options.miro_helper:
    launch_miro_helper()
elif parsed_options.unittest:
    launch_unit_tests()
else:
    launch_application(parsed_options, args)
