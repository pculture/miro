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

"""searchcontroller.py -- Controller for the Video Search tab
"""

from miro import app
from miro import searchengines
from miro.gtcache import gettext as _
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import widgetutil
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

class SearchEngineDisplay(widgetset.Background):

    BORDER_COLOR = widgetutil.css_to_color('#d9d9d9')

    def __init__(self, engine):
        widgetset.Background.__init__(self)
        hbox = widgetset.HBox(spacing=15)
        self.pack(hbox, imagepool.get_image_display(
                searchengines.icon_path_for_engine(engine)))
        label = widgetset.Label(engine.title)
        label.set_size(widgetutil.font_scale_from_osx_points(14))
        label.set_bold(True)
        self.pack(hbox, widgetutil.align_left(label), expand=True)
        self.add(hbox)
        self.has_border = True

    def set_has_border(self, has_border):
        self.has_border = has_border

    def pack(self, hbox, widget, expand=False):
        hbox.pack_start(widgetutil.align_middle(widget), expand=expand)

    def draw(self, context, layout):
        if self.has_border:
            context.set_line_width(1)
            context.set_color(self.BORDER_COLOR)
            context.move_to(0, context.height)
            context.line_to(context.width, context.height)
            context.stroke()

class EmptySearchList(widgetset.SolidBackground):
    TITLE = _('Video Search')
    DESC = _('Use the search box above to search for videos on these sites')

    def __init__(self):
        widgetset.SolidBackground.__init__(self,
            itemlistwidgets.StandardView.BACKGROUND_COLOR)
        bg = widgetutil.RoundedSolidBackground(widgetutil.WHITE)
        vbox = widgetset.VBox()
        title = widgetset.HBox()
        logo = imagepool.get_image_display(
            resources.path('images/icon-search_large.png'))
        title.pack_start(widgetutil.align_middle(logo))
        label = widgetset.Label(self.TITLE)
        label.set_bold(True)
        label.set_size(widgetutil.font_scale_from_osx_points(30))
        title.pack_start(widgetutil.align_middle(label, left_pad=5))
        vbox.pack_start(widgetutil.align_center(title, bottom_pad=20))
        desc = widgetset.Label(self.DESC)
        vbox.pack_start(widgetutil.align_center(desc, bottom_pad=40))

        engine_width = int((desc.get_width() - 30) / 2)

        engine_widgets = self.build_engine_widgets()
        for widgets in engine_widgets[:-1]: # widgets with borders
            hbox = widgetset.HBox(spacing=30)
            for widget in widgets:
                widget.set_size_request(engine_width, 45)
                hbox.pack_start(widget, expand=True)
            vbox.pack_start(hbox)

        hbox = widgetset.HBox(spacing=30)
        for widget in engine_widgets[-1]: # has no border
            widget.set_has_border(False)
            widget.set_size_request(engine_width, 45)
            hbox.pack_start(widget, expand=True)

        vbox.pack_start(hbox)

        bg.add(widgetutil.pad(vbox, 45, 45, 45, 45))
        self.add(widgetutil.align(bg, xalign=0.5, top_pad=50))

    def build_engine_widgets(self):
        widgets = []
        current = None
        for engine in searchengines.get_search_engines():
            if engine.name == u'all':
                continue # don't build a 'search all' label
            widget = SearchEngineDisplay(engine)
            if current: # second engine
                current.append(widget)
                widgets.append(current)
                current = None
            else: # first engine
                current = [widget]
        if current: # odd number of widgets
            widgets.append(current)
        return widgets


class SearchController(itemlistcontroller.SimpleItemListController):
    type = u'search'
    id = u'search'

    def __init__(self):
        itemlistcontroller.SimpleItemListController.__init__(self)
        self._started_handle = app.search_manager.connect('search-started',
                self._on_search_started)
        self._complete_handle = app.search_manager.connect('search-complete',
                self._on_search_complete)

    def cleanup(self):
        itemlistcontroller.SimpleItemListController.cleanup(self)
        app.search_manager.disconnect(self._started_handle)
        app.search_manager.disconnect(self._complete_handle)


    def build_widget(self):
        itemlistcontroller.SimpleItemListController.build_widget(self)
        scroller = widgetset.Scroller(False, True)
        scroller.add(EmptySearchList())
        self.widget.list_empty_mode_vbox.pack_start(
            scroller, expand=True)

    def initialize_search(self):
        if app.search_manager.text != '':
            self.titlebar.set_search_text(app.search_manager.text)
        self.titlebar.set_search_engine(app.search_manager.engine)

    def calc_list_empty_mode(self):
        # "empty list mode" is used differently for search engines.  We want
        # to show the page for empty searches, not for when a search returns
        # no results see (#16970)
        return app.search_manager.text == ''

    def make_titlebar(self):
        titlebar = itemlistwidgets.SearchListTitlebar()
        titlebar.connect('save-search', self._on_save_search)
        titlebar.hide_album_view_button()
        return titlebar

    def get_saved_search_text(self):
        return self.titlebar.get_search_text()

    def get_saved_search_source(self):
        return 'search', self.titlebar.get_engine()

    def _on_save_search(self, widget, search_text):
        engine = self.titlebar.get_engine()
        # don't need to perform the search, just set the info for saving
        app.search_manager.set_search_info(engine, search_text)
        app.search_manager.save_search()

    def _on_search_started(self, search_manager):
        self.titlebar.set_search_text(search_manager.text)
        self.titlebar.set_search_engine(search_manager.engine)
        self.check_for_empty_list()

    def _on_search_complete(self, search_manager, result_count):
        self.check_for_empty_list()
