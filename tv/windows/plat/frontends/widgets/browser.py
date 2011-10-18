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

"""browser.py -- WebBrowser widget."""
import urlparse
import os, os.path
import logging
import tempfile

import gtk
import gobject

from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.widgetset import Widget
from miro.plat.frontends.widgets import embeddingwidget
from miro.plat.frontends.widgets import xulrunnerbrowser

class BrowserWidget(embeddingwidget.EmbeddingWidget):
    def __init__(self):
        embeddingwidget.EmbeddingWidget.__init__(self)
        self.set_can_focus(True)
        self.browser = xulrunnerbrowser.XULRunnerBrowser(
                self.embedding_window.hwnd, 0, 0, 1, 1)
        self.browser.set_callback_object(self)
        self._downloads = {} # in-progress downloads

    def navigate(self, url):
        self.browser.load_uri(url)

    # GTK event handlers

    def do_realize(self):
        embeddingwidget.EmbeddingWidget.do_realize(self)
        self.browser.resize(0, 0, self.allocation.width,
                self.allocation.height)
        self.browser.enable()

    def do_unrealize(self):
        self.browser.disable()
        embeddingwidget.EmbeddingWidget.do_unrealize(self)

    def do_size_allocate(self, allocation):
        embeddingwidget.EmbeddingWidget.do_size_allocate(self, allocation)
        if self.flags() & gtk.REALIZED:
            # resize our browser
            self.browser.resize(0, 0, allocation.width, allocation.height)

    def destroy(self):
        self.browser.destroy()
        self.browser = None
        embeddingwidget.EmbeddingWidget.destroy(self)

    def do_focus_out_event(self, event):
        # GTK has moved the focus away from our embedded window.  Deactivate
        # the browser.
        #
        # Focus the toplevel window.  GTK normally always keeps it's toplevel
        # focused, but XULRunner stole it when we called browser.activate().
        # Now that the browser doesn't want the keyboard focus anymore, we
        # should give it back to the toplevel.
        self.browser.deactivate()
        toplevel = self.get_toplevel()
        toplevel.window.focus()

    # EmbeddingWindow callbacks

    def on_mouseactivate(self):
        # The embedding window got a WM_MOUSEACTIVATE event.  We should tell
        # GTK to focus our widget and XULRunner to activate itself.
        self.grab_focus()
        self.browser.activate()

    # XULRunnerBrowser callbacks

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
        if wrappermap.wrapper(self).should_download_url(uri):
            parsed = urlparse.urlparse(uri)
            prefix, suffix = os.path.splitext(os.path.basename(parsed.path))
            fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)
            self.browser.download_uri(uri, path)
            self._downloads[uri] = path
            return False
        else:
            rv = wrappermap.wrapper(self).should_load_url(uri)
            if rv:
                wrappermap.wrapper(self).url = uri
        return rv

    def on_net_start(self, uri):
        if uri in self._downloads:
            return # don't need to bother
        wrappermap.wrapper(self).emit('net-start')

    def on_net_stop(self, uri):
        if uri in self._downloads:
            path = self._downloads.pop(uri)
            wrappermap.wrapper(self).emit(
                'download-finished', 
                'file://%s' % path.replace(os.sep, '/'))
            return
        wrappermap.wrapper(self).emit('net-stop')
gobject.type_register(BrowserWidget)

class Browser(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.set_widget(BrowserWidget())
        self.url = None

        # TODO: implement net-start and net-stop signaling on windows.
        self.create_signal('net-start')
        self.create_signal('net-stop')
        self.create_signal('download-finished')

    def navigate(self, url):
        self._widget.navigate(url)

    def get_current_url(self):
        return self._widget.browser.get_current_uri()

    def get_current_title(self):
        title = self._widget.browser.get_current_title()
        # browser returns the title in a utf-16 encoded string,
        # so we decode it into a unicode and pass it along.
        title = title.decode("utf-16")
        return title

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

    def destroy(self):
        self._widget.browser.destroy()
