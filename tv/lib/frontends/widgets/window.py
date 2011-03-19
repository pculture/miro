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

"""``miro.frontends.widgets.window`` -- Main Miro widget.
"""

from miro import app
from miro import prefs

from miro.frontends.widgets import separator
from miro.frontends.widgets import tablist
from miro.frontends.widgets import videobox
from miro.frontends.widgets import searchbox
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset

class MiroWindow(widgetset.MainWindow):
    """The main Miro Window.
    """
    def __init__(self, title, rect):
        widgetset.MainWindow.__init__(self, title, rect)

        GREY = (0.85, 0.85, 0.85)
        vbox = widgetset.VBox()
        vbox.pack_start(separator.HSeparator(GREY))
        vbox.pack_start(tablist.TabListBox(), expand=True)

        hbox = widgetset.HBox()
        hbox.pack_start(vbox, expand=True)
        hbox.pack_start(separator.VSeparator(GREY))

        self.main_area_holder = widgetutil.WidgetHolder()

        main_hbox = widgetset.HBox()
        main_hbox.pack_start(separator.VSeparator(GREY))
        main_hbox.pack_start(self.main_area_holder, expand=True)
        
        self.splitter = widgetset.Splitter()
        self.splitter.set_left(hbox)
        self.splitter.set_right(main_hbox)

        hbox = widgetset.HBox()
        self.videobox = videobox.VideoBox()
        hbox.pack_end(self.videobox, expand=True)
        self.controls_hbox = hbox

        vbox = widgetset.VBox()
        vbox.pack_start(self.splitter, expand=True)
        vbox.pack_end(hbox)
        self.main_vbox = vbox

        self.set_content_widget(vbox)
        self.connect("active-change", self.on_active_change)

        try:
            left_width = int(app.config.get(prefs.LEFT_VIEW_SIZE))
            if left_width is None or left_width == "":
                left_width = 200
        except (TypeError, ValueError):
            # Note: TypeError gets thrown because LEFT_VIEW_SIZE
            # defaults to None.
            left_width = 200
        self.splitter.set_left_width(left_width)

    def on_active_change(self, window):
        self.videobox.queue_redraw()

    def set_main_area(self, widget):
        """Sets the main area to specified widget.
        """
        self.main_area_holder.set(widget)
