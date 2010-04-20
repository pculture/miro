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

from miro import app
from miro.plat import resources
from miro.gtcache import gettext as _
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import separator
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import itemlistwidgets
from miro.plat.frontends.widgets import widgetset

from miro.videoconversion import conversion_manager

class VideoConversionsController(object):

    def __init__(self):
        self.widget = widgetset.VBox()
        self.build_widget()

    def build_widget(self):
        image_path = resources.path("images/icon-conversions_large.png")
        icon = imagepool.get(image_path)
        titlebar = VideoConversionsTitleBar(_("Conversions"), icon)
        self.widget.pack_start(titlebar)

        sep = separator.HSeparator((0.85, 0.85, 0.85), (0.95, 0.95, 0.95))
        self.widget.pack_start(sep)

        stop_all_button = widgetset.Button(_('Stop All Conversions'), style='smooth')
        stop_all_button.set_size(widgetconst.SIZE_SMALL)
        stop_all_button.set_color(widgetset.TOOLBAR_GRAY)
        stop_all_button.disable()
        stop_all_button.connect('clicked', self.on_interrupt_all)

        reveal_button = widgetset.Button(_('Show Conversion Folder'), style='smooth')
        reveal_button.set_size(widgetconst.SIZE_SMALL)
        reveal_button.set_color(widgetset.TOOLBAR_GRAY)
        reveal_button.connect('clicked', self.on_reveal)

        toolbar = itemlistwidgets.DisplayToolbar()
        hbox = widgetset.HBox()
        hbox.pack_start(widgetutil.pad(stop_all_button, top=8, bottom=8, left=8))
        hbox.pack_end(widgetutil.pad(reveal_button, top=8, bottom=8, right=8))
        toolbar.add(hbox)
        self.widget.pack_start(toolbar)
        
        self.model = VideoConversionsTableModel()
        self.table = widgetset.TableView(self.model)
        self.table.set_show_headers(False)

        scroller = widgetset.Scroller(False, True)
        scroller.add(self.table)

        self.widget.pack_start(scroller, expand=True)
    
    def on_interrupt_all(self, object):
        conversion_manager.interrupt_all()

    def on_reveal(self, object):
        path = conversion_manager.get_default_target_folder()
        app.widgetapp.reveal_file(path)


class VideoConversionsTitleBar(itemlistwidgets.ItemListTitlebar):
    def _build_titlebar_extra(self):
        pass


class VideoConversionsTableModel(widgetset.TableModel):
    def __init__(self):
        widgetset.TableModel.__init__(self, 'object')
