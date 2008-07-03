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

# Most of our widgets come straight from the portable GTK code.
from miro.frontends.widgets.gtk.widgetset import *

import gtk
import gobject

from miro.plat.frontends.widgets import xulrunnerbrowser

class BrowserWidget(gtk.DrawingArea):
    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.browser = None
        self.pending_url = None
        self.set_size_request(200, 100) # seems like a reasonable default

    def navigate(self, url):
        if self.browser:
            self.browser.load_uri(url)
        else:
            self.pending_url = url

    def load_pending_url(self):
        if self.pending_url:
            self.browser.load_uri(self.pending_url)
            self.pending_url = None

    def get_current_url(self):
        return None

    def do_realize(self):
        gtk.DrawingArea.do_realize(self)
        self.browser = xulrunnerbrowser.XULRunnerBrowser(self.window.handle, 
                0, 0, self.allocation.width, self.allocation.height)
        self.browser.set_callback_object(self)
        self.load_pending_url()

    def do_destroy(self):
        # This seems to be able to get called after our browser attribute no
        # longer exists.  Double check to make sure that's not the case.
        if hasattr(self, 'browser') and self.browser is not None:
            self.browser.destroy()

    def do_focus_in_event(self, event):
        gtk.DrawingArea.do_focus_in_event(self, event)
        self.browser.focus()

    def do_size_allocate(self, rect):
        gtk.DrawingArea.do_size_allocate(self, rect)
        if self.browser:
            self.browser.resize(0, 0, rect.width, rect.height)

    def on_browser_focus(self, forward):
        def change_focus():
            toplevel = self.get_toplevel()
            toplevel.window.focus()
            if forward:
                toplevel.emit('move-focus', gtk.DIR_TAB_FORWARD)
            else:
                toplevel.emit('move-focus', gtk.DIR_TAB_BACKWARD)
        # for some reason we can't change the focus quite yet.  Using
        # idle_add() fixes the problem though
        gobject.idle_add(change_focus)

gobject.type_register(BrowserWidget)

class Browser(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.set_widget(BrowserWidget())
        self._widget.set_property('can-focus', True)

    def navigate(self, url):
        self._widget.navigate(url)

    def get_current_url(self):
        return self._widget.get_current_url()
