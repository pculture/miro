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

from miro import app
from miro import prefs

from miro.gtcache import gettext as _
from miro.frontends.widgets import itemrenderer
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import separator
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import itemlist
from miro.plat.frontends.widgets import widgetset

from miro.conversions import conversion_manager

# FIXME: The old itemlist module is no longer around.  We need to reimplement
# this
if 0:
    class ConvertingSort(itemlist.ItemSort):
        KEY = None

        def __init__(self):
            itemlist.ItemSort.__init__(self, True)
            self.positions = []

        def sort_key(self, item):
            id_ = item.id
            if not id_ in self.positions:
                self.positions.append(id_)
            return self.positions.index(id_)

# XXX: why doesn't this guy derive from something sensible and use 
# ItemListController instead?
class ConvertingController(object):
    def __init__(self):
        self.widget = widgetset.VBox()
        self.build_widget()

    def build_widget(self):
        self.titlebar = itemlistwidgets.ConvertingTitlebar()
        self.widget.pack_start(self.titlebar)
        self.titlebar.connect('stop-all', self.on_cancel_all)
        self.titlebar.connect('reveal', self.on_reveal_conversions_folder)
        self.titlebar.connect('clear-finished', self.on_clear_finished)

        sorter = ConvertingSort()
        self.model = widgetset.InfoListModel(sorter.sort_key)
        self.table = ConvertingTableView(self.model)
        self.table.connect_weak('hotspot-clicked', self.on_hotspot_clicked)
        scroller = widgetset.Scroller(False, True)
        scroller.add(self.table)

        self.widget.pack_start(scroller, expand=True)

        conversion_manager.fetch_tasks_list()

    def on_cancel_all(self, obj):
        conversion_manager.cancel_all()

    def on_reveal_conversions_folder(self, obj):
        app.widgetapp.reveal_conversions_folder()

    def on_clear_finished(self, obj):
        conversion_manager.clear_finished_conversions()
        
    def on_hotspot_clicked(self, table_view, name, itr):
        task = table_view.model[itr][0]
        if name == 'cancel' or name == 'interrupt':
            conversion_manager.cancel(task.key)
        elif name == 'open-log' and task.state == 'failed':
            if task.log_path is not None:
                app.widgetapp.open_file(task.log_path)
        elif name == 'troubleshoot' and task.state == 'failed':
            app.widgetapp.open_url(app.config.get(prefs.TROUBLESHOOT_URL))
        elif name == 'clear-failed' and task.state == 'failed':
            conversion_manager.clear_failed_task(task.key)
        elif name == 'clear-finished' and task.state == 'finished':
            conversion_manager.clear_finished_task(task.key)
        elif name == 'reveal' and task.state == 'finished':
            app.widgetapp.reveal_file(task.output_path)

    def handle_task_list(self, running_tasks, pending_tasks, finished_tasks):
        self.model.add_infos(running_tasks)
        self.model.add_infos(pending_tasks)
        self.model.add_infos(finished_tasks)
        self.table.model_changed()
        self._update_buttons_state()

    def handle_task_added(self, task):
        try:
            self.model.add_infos([task])
        except ValueError:
            pass # task already added
        else:
            self.table.model_changed()
            self._update_buttons_state()
    
    def handle_all_tasks_removed(self):
        self.model.remove_all()
        self.table.model_changed()
        self._update_buttons_state()
    
    def handle_task_removed(self, task):
        try:
            self.model.remove_ids([task.id])
        except KeyError:
            pass # task already removed
        else:
            self.table.model_changed()
            self._update_buttons_state()
    
    def handle_task_changed(self, task):
        try:
            self.model.update_infos([task], resort=False)
        except KeyError:
            pass # task already removed
        else:
            self.table.model_changed()
            self._update_buttons_state()
    
    def _update_buttons_state(self):
        finished_count = not_finished_count = 0
        for info in self.model.info_list():
            if info.state == 'finished':
                finished_count += 1
            else:
                not_finished_count += 1

        enable_stop_all = not_finished_count > 0
        self.titlebar.enable_stop_all(enable_stop_all)

        enable_clear_finished = finished_count > 0
        self.titlebar.enable_clear_finished(enable_clear_finished)

class ConvertingTableView(widgetset.TableView):
    draws_selection = False

    def __init__(self, model):
        widgetset.TableView.__init__(self, model)
        self.set_show_headers(False)

        self.renderer = itemrenderer.ConversionItemRenderer()
        self.column = widgetset.TableColumn('conversion', self.renderer)
        self.column.set_min_width(600)
        self.add_column(self.column)

        self.set_show_headers(False)
        self.allow_multiple_select = False
        self.set_auto_resizes(True)
        self.set_background_color(widgetutil.WHITE)
