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

"""Main Miro widget."""

from miro import app

from miro.frontends.widgets import tablist
from miro.frontends.widgets import videobox
from miro.plat.frontends.widgets import widgetset

class WidgetHolder(widgetset.VBox):
    """Widget used to hold a single child widget."""
    def __init__(self):
        widgetset.VBox.__init__(self)
        self.child = None

    def set(self, widget):
        if self.child:
            self.remove(self.child)
        self.pack_start(widget, expand=True)
        self.child = widget

    def unset(self):
        self.remove(self.child)
        self.child = None

class MiroWindow(widgetset.MainWindow):
    def __init__(self, title, rect):
        widgetset.MainWindow.__init__(self, title, rect)
        self.splitter = widgetset.Splitter()
        self.videobox = videobox.VideoBox()
        self.main_area_holder = WidgetHolder()
        vbox = widgetset.VBox()
        vbox.pack_start(self.main_area_holder, True)
        vbox.pack_start(self.videobox)
        self.splitter.set_left(tablist.TabListBox())
        self.splitter.set_right(vbox)
        self.splitter.set_left_width(200)
        self.set_content_widget(self.splitter)
        self.connect("active-change", self.on_active_change)

    def on_active_change(self, window):
        self.videobox.queue_redraw()

    def set_main_area(self, widget):
        self.main_area_holder.set(widget)
