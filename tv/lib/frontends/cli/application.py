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

import logging
import platform

from miro import app
from miro import prefs
from miro import startup
from miro import controller
from miro import messages
from miro.frontends.cli.util import print_text, print_box
from miro.frontends.cli.events import EventHandler
from miro.frontends.cli.interpreter import MiroInterpreter

def setup_logging():
    # this gets called after miro.plat.util.setup_logging, and changes
    # the logging level so it's way less spammy.
    logger = logging.getLogger('')
    logger.setLevel(logging.WARN)

def setup_movie_data_program_info():
    from miro.plat.renderers.gstreamerrenderer import movie_data_program_info
    app.movie_data_program_info = movie_data_program_info

def run_application():
    setup_logging()
    app.controller = controller.Controller()

    print "Starting up %s" % app.config.get(prefs.LONG_APP_NAME)
    print "Version:    %s" % app.config.get(prefs.APP_VERSION)
    print "OS:         %s %s %s" % (platform.system(), platform.release(),
                                    platform.machine())
    print "Revision:   %s" % app.config.get(prefs.APP_REVISION)
    print "Builder:    %s" % app.config.get(prefs.BUILD_MACHINE)
    print "Build Time: %s" % app.config.get(prefs.BUILD_TIME)

    print
    app.cli_events = EventHandler()
    app.cli_events.connect_to_signals()
    startup.install_first_time_handler(app.cli_events.handle_first_time)
    startup.startup()
    app.cli_events.startup_event.wait()
    if app.cli_events.startup_failure:
        print_box("Error Starting Up: %s" % app.cli_events.startup_failure[0])
        print
        print_text(app.cli_events.startup_failure[1])
        app.controller.shutdown()
        return

    setup_movie_data_program_info()
    messages.FrontendStarted().send_to_backend()

    print "Startup complete.  Type \"help\" for list of commands."
    app.cli_interpreter = MiroInterpreter()
    app.cli_interpreter.cmdloop()
    app.controller.shutdown()
