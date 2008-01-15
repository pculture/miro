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

import gtk

import threading
from frontend_implementation.gtk_queue import queue, gtkAsyncMethod
from frontends.html.main import HTMLApplication
from miroplatform import mozsetup, options
import app
import gtcache
import config
import prefs
import gtk.glade
import platformutils

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application(HTMLApplication):
    def Run(self):
        mozsetup.setupMozillaEnvironment()
        gtk.glade.bindtextdomain("miro", config.get(prefs.GETTEXT_PATHNAME))
        gtk.glade.textdomain("miro")

        queue.main_thread = threading.currentThread()
        platformutils.setMainThread()
        gtk.gdk.threads_init()
        if options.themeName is not None:
            config.load(options.themeName)
        self.startup()
        gtk.main()
        app.controller.onShutdown()

    @gtkAsyncMethod
    def quitUI(self):
        gtk.main_quit()

###############################################################################
###############################################################################
