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

"""browser.py -- WebBrowser widget."""

from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.persistentwindow import PersistentWindow
from miro.frontends.widgets.gtk.widgetset import Widget

import gtk
import gobject

from miro.plat.frontends.widgets import xulrunnerbrowser

class BrowserWidget(PersistentWindow):
    def __init__(self):
        PersistentWindow.__init__(self)
        self.browser = None
        self.set_size_request(200, 100) # seems like a reasonable default
        self.add_events(gtk.gdk.EXPOSURE_MASK)
        self.browser = xulrunnerbrowser.XULRunnerBrowser(
                self.persistent_window.handle, 0, 0, 1, 1)
        self.browser.set_callback_object(self)

    def navigate(self, url):
        self.browser.load_uri(url)

    def do_realize(self):
        PersistentWindow.do_realize(self)
        self.browser.resize(0, 0, self.allocation.width, 
                self.allocation.height)
        self.browser.enable()

    def do_unrealize(self):
        self.browser.disable()
        PersistentWindow.do_unrealize(self)

    def do_destroy(self):
        # This seems to be able to get called after our browser attribute no
        # longer exists.  Double check to make sure that's not the case.
        if hasattr(self, 'browser'):
            self.browser.destroy()
        PersistentWindow.do_destroy(self)

    def do_focus_in_event(self, event):
        PersistentWindow.do_focus_in_event(self, event)
        self.browser.focus()

    def do_size_allocate(self, rect):
        PersistentWindow.do_size_allocate(self, rect)
        if self.flags() & gtk.REALIZED:
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

    def on_uri_load(self, uri):
        rv = wrappermap.wrapper(self).should_load_url(uri)
        if rv:
            wrappermap.wrapper(self).url = uri
        return rv

    def on_net_start(self):
        wrappermap.wrapper(self).emit('net-start')

    def on_net_stop(self):
        wrappermap.wrapper(self).emit('net-stop')

gobject.type_register(BrowserWidget)

class Browser(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.set_widget(BrowserWidget())
        self._widget.set_property('can-focus', True)
        self.url = None

        # TODO: implement net-start and net-stop signaling on windows.
        self.create_signal('net-start')
        self.create_signal('net-stop')

    def navigate(self, url):
        self._widget.navigate(url)

    def get_current_url(self):
        return self.url

    def can_go_back(self):
        return self._widget.browser.can_go_back()

    def can_go_forward(self):
        return self._widget.browser.can_go_forward()

    def back(self):
        self._widget.browser.go_back()

    def forward(self):
        self._widget.browser.go_forward()

    def stop(self):
        self._widget.browser.stop()

    def reload(self):
        self._widget.browser.reload()
