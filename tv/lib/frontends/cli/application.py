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

import logging
import platform

from miro import config
from miro import prefs
from miro import app
from miro import startup
from miro import controller
from miro.frontends.cli.util import print_text, print_box
from miro.frontends.cli.events import EventHandler
from miro.frontends.cli.interpreter import MiroInterpreter

def setup_logging():
    pathname = config.get(prefs.LOG_PATHNAME)
    try:
        rotater = logging.handlers.RotatingFileHandler(
            pathname, mode="w", maxBytes=100000,
            backupCount=5)
    except IOError:
        # bug 13338.  sometimes there's a file there and it causes
        # RotatingFileHandler to flip out when opening it.  so we
        # delete it and then try again.
        os.remove(pathname)
        rotater = logging.handlers.RotatingFileHandler(
            pathname, mode="w", maxBytes=100000,
            backupCount=5)

    rotater.setLevel(logging.WARN)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    rotater.setFormatter(formatter)
    logging.getLogger('').addHandler(rotater)
    rotater.doRollover()

    from miro import util
    util.setup_logging()

def run_application(props_to_set, theme):
    setup_logging()
    app.controller = controller.Controller()
    config.load(theme)

    # FIXME - ignoring props_to_set
    print "Starting up %s" % config.get(prefs.LONG_APP_NAME)
    print "Version:    %s" % config.get(prefs.APP_VERSION)
    print "OS:         %s %s %s" % (platform.system(), platform.release(), platform.machine())
    print "Revision:   %s" % config.get(prefs.APP_REVISION)
    print "Builder:    %s" % config.get(prefs.BUILD_MACHINE)
    print "Build Time: %s" % config.get(prefs.BUILD_TIME)

    print
    app.cli_events = EventHandler()
    app.cli_events.connect_to_signals()
    startup.startup()
    app.cli_events.startup_event.wait()
    if app.cli_events.startup_failure:
        print_box("Error Starting Up: %s" % app.cli_events.startup_failure[0])
        print
        print_text(app.cli_events.startup_failure[1])
        app.controller.shutdown()
        return
    print "Startup complete.  Type \"help\" for list of commands."
    app.cli_interpreter = MiroInterpreter()
    app.cli_interpreter.cmdloop()
    app.controller.shutdown()
