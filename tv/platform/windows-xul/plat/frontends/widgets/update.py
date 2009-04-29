# Miro - an RSS based video player application
# Copyright (C) 2009 Participatory Culture Foundation
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

from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.widgetset import Widget

import gtk
import gobject

from miro.plat.frontends.widgets import xulrunnerbrowser
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import dialogs, widgetutil
from miro.gtcache import gettext as _
from miro import app, config, prefs

class UpdateAvailableBrowserWidget(gtk.DrawingArea):
    # this is partially duplicated from browser.py
    def __init__(self, url):
        gtk.DrawingArea.__init__(self)
        self.browser = None
        self.url = url
        self.set_size_request(200, 300)
        self.add_events(gtk.gdk.EXPOSURE_MASK)

    def navigate(self, url):
        self.browser.load_uri(url)

    def do_realize(self):
        gtk.DrawingArea.do_realize(self)
        if self.browser is None:
            self.browser = xulrunnerbrowser.XULRunnerBrowser(self.window.handle,
                                                             0, 0, 1, 1)
            self.browser.set_callback_object(self)
            self.navigate(self.url)
        self.browser.resize(0, 0, self.allocation.width,
                self.allocation.height)
        self.browser.enable()

    def do_unrealize(self):
        gtk.DrawingArea.do_unrealize(self)
        self.browser.disable()

    def do_destroy(self):
        gtk.DrawingArea.do_destroy(self)
        # This seems to be able to get called after our browser attribute no
        # longer exists.  Double check to make sure that's not the case.
        if hasattr(self, 'browser'):
            self.browser.destroy()

    def do_focus_in_event(self, event):
        gtk.DrawingArea.do_focus_in_event(self, event)
        self.browser.focus()

    def do_size_allocate(self, rect):
        gtk.DrawingArea.do_size_allocate(self, rect)
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
        if uri == self.url:
            return True
        else:
            app.widgetapp.open_url(uri)
            return False

    def on_net_start(self):
        wrappermap.wrapper(self).emit('net-start')

    def on_net_stop(self):
        wrappermap.wrapper(self).emit('net-stop')

gobject.type_register(UpdateAvailableBrowserWidget)

class UpdateAvailableBrowser(Widget):
    def __init__(self, url):
        Widget.__init__(self)
        self.set_widget(UpdateAvailableBrowserWidget(url))
        self._widget.set_property('can-focus', True)
        self.url = url

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

class UpdateAvailableDialog(dialogs.MainDialog):
    def __init__(self, url):
        dialogs.MainDialog.__init__(self, _("Update Available"))
        self.browser = UpdateAvailableBrowser(url)
        label = widgetset.Label()
        label.set_text(
            _('A new version of %(appname)s is available for download.',
              {"appname": config.get(prefs.SHORT_APP_NAME)}))
        label2 = widgetset.Label()
        label2.set_text(
            _('Do you want to download it now?'))
        self.vbox = widgetset.VBox(spacing=6)
        self.vbox.pack_end(widgetutil.align_center(label2))
        self.vbox.pack_end(self.browser, expand=True)
        self.vbox.pack_end(widgetutil.align_center(label))
        self.set_extra_widget(self.vbox)
        self.add_button(dialogs.BUTTON_YES.text)
        self.add_button(dialogs.BUTTON_NO.text)

    def run(self):
        response = dialogs.MainDialog.run(self)
        if response:
            return dialogs.BUTTON_NO
        else:
            return dialogs.BUTTON_YES


