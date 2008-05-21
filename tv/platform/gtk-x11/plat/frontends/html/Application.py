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

import gtk

import threading
import logging
from miro.plat.frontends.html.gtk_queue import queue, gtkAsyncMethod
from miro.frontends.html.main import HTMLApplication
from miro.plat import mozsetup
from miro.plat import options
from miro import app
from miro import gtcache
from miro import config
from miro import prefs
from miro import startup
import gtk.glade
from miro.plat.utils import setMainThread

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application(HTMLApplication):
    def run(self, props_to_set):
        queue.call_nowait(mozsetup.setupMozillaEnvironment)
        gtk.glade.bindtextdomain("miro", config.get(prefs.GETTEXT_PATHNAME))
        gtk.glade.textdomain("miro")

        queue.main_thread = threading.currentThread()
        setMainThread()
        gtk.gdk.threads_init()
        startup.initialize(options.themeName)
        self.startup()
        self.setProperties(props_to_set)
        gtk.main()
        app.controller.onShutdown()

    def setProperties(self, props):
        for p, val in props:
            logging.info("Setting preference: %s -> %s", p.alias, val)
            config.set(p, val)

    @gtkAsyncMethod
    def quitUI(self):
        gtk.main_quit()
