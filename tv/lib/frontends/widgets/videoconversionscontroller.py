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
from miro import displaytext
from miro import config
from miro import prefs

from miro.plat import resources
from miro.gtcache import gettext as _
from miro.frontends.widgets import style
from miro.frontends.widgets import cellpack
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

        self.stop_all_button = widgetset.Button(_('Stop All Conversions'), style='smooth')
        self.stop_all_button.set_size(widgetconst.SIZE_SMALL)
        self.stop_all_button.set_color(widgetset.TOOLBAR_GRAY)
        self.stop_all_button.disable()
        self.stop_all_button.connect('clicked', self.on_cancel_all)

        reveal_button = widgetset.Button(_('Show Conversion Folder'), style='smooth')
        reveal_button.set_size(widgetconst.SIZE_SMALL)
        reveal_button.set_color(widgetset.TOOLBAR_GRAY)
        reveal_button.connect('clicked', self.on_reveal_conversions_folder)

        self.clear_finished_button = widgetset.Button(
                _('Clear Finished Conversions'), style='smooth')
        self.clear_finished_button.set_size(widgetconst.SIZE_SMALL)
        self.clear_finished_button.set_color(widgetset.TOOLBAR_GRAY)
        self.clear_finished_button.connect('clicked', self.on_clear_finished)

        toolbar = itemlistwidgets.DisplayToolbar()
        hbox = widgetset.HBox()
        hbox.pack_start(widgetutil.pad(self.stop_all_button, top=8, bottom=8, left=8))
        hbox.pack_end(widgetutil.pad(reveal_button, top=8, bottom=8, right=8))
        hbox.pack_end(widgetutil.pad(self.clear_finished_button, top=8, bottom=8, right=8))
        toolbar.add(hbox)
        self.widget.pack_start(toolbar)
        
        self.iter_map = dict()
        self.model = widgetset.TableModel('object')
        self.table = VideoConversionTableView(self.model)
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
        if name == 'cancel' and not task.is_running():
            conversion_manager.cancel_pending(task)
        elif name == 'open-log' and task.is_failed():
            if task.log_path is not None:
                app.widgetapp.open_file(task.log_path)
        elif name == 'troubleshoot' and task.is_failed():
            app.widgetapp.open_url(config.get(prefs.TROUBLESHOOT_URL))
        elif name == 'clear-failed' and task.is_failed():
            conversion_manager.clear_failed_task(task)
        elif name == 'clear-finished' and task.is_finished():
            conversion_manager.clear_finished_task(task)
        elif name == 'interrupt' and task.is_running():
            conversion_manager.cancel_running(task)
        elif name == 'reveal' and task.is_finished():
            app.widgetapp.reveal_file(task.final_output_path)

    def handle_task_list(self, running_tasks, pending_tasks, finished_tasks):
        for task in running_tasks:
            self.iter_map[task.key] = self.model.append(task)
        for task in pending_tasks:
            self.iter_map[task.key] = self.model.append(task)
        for task in finished_tasks:
            self.iter_map[task.key] = self.model.append(task)
        self.table.model_changed()
        self._update_buttons_state()

    def handle_task_added(self, task):
        if task.key not in self.iter_map:
            self.iter_map[task.key] = self.model.append(task)
            self.table.model_changed()
        self._update_buttons_state()
    
    def handle_all_tasks_canceled(self):
        for key in self.iter_map.keys():
            itr = self.iter_map.pop(key)
            self.model.remove(itr)
        self.table.model_changed()
        self._update_buttons_state()
    
    def handle_task_canceled(self, task):
        if task.key in self.iter_map:
            itr = self.iter_map.pop(task.key)
            self.model.remove(itr)
            self.table.model_changed()
            self._update_buttons_state()
    
    def handle_task_progress(self, task):
        if task.key in self.iter_map:
            itr = self.iter_map[task.key]
            self.model.update_value(itr, 0, task)
            self.table.model_changed()
    
    def handle_task_completed(self, task):
        if task.key in self.iter_map:
            itr = self.iter_map[task.key]
            self.model.update_value(itr, 0, task)
            self.table.model_changed()
            self._update_buttons_state()
    
    def _update_buttons_state(self):
        finished_count = not_finished_count = 0
        for row in self.model:
            if row[0].is_finished():
                finished_count += 1
            else:
                not_finished_count += 1

        if not_finished_count > 0:
            self.stop_all_button.enable()
        else:
            self.stop_all_button.disable()

        if finished_count > 0:
            self.clear_finished_button.enable()
        else:
            self.clear_finished_button.disable()


class VideoConversionsTitleBar(itemlistwidgets.ItemListTitlebar):
    def _build_titlebar_extra(self):
        pass


class VideoConversionTableView(widgetset.TableView):
    def __init__(self, model):
        widgetset.TableView.__init__(self, model)
        self.set_show_headers(False)

        self.renderer = VideoConversionCellRenderer()
        self.column = widgetset.TableColumn('conversion', self.renderer, data=0)
        self.column.set_min_width(600)
        self.add_column(self.column)

        self.set_draws_selection(False)
        self.set_show_headers(False)
        self.allow_multiple_select(False)
        self.set_auto_resizes(True)
        self.set_background_color(widgetutil.WHITE)

class ConversionProgressBarColorSet(object):
    PROGRESS_BASE_TOP = (0.75, 0.28, 0.50)
    PROGRESS_BASE_BOTTOM = (0.71, 0.16, 0.42)
    BASE = (0.76, 0.76, 0.76)

    PROGRESS_BORDER_TOP = (0.60, 0.23, 0.41)
    PROGRESS_BORDER_BOTTOM = (0.53, 0.10, 0.31)
    PROGRESS_BORDER_HIGHLIGHT = (0.88, 0.50, 0.68)

    BORDER_GRADIENT_TOP = (0.58, 0.58, 0.58)
    BORDER_GRADIENT_BOTTOM = (0.68, 0.68, 0.68)

class VideoConversionCellRenderer(style.ItemRenderer):
    THUMB_WIDTH = 120
    THUMB_HEIGHT = 82
    PENDING_TASK_TEXT_COLOR = (0.8, 0.8, 0.8)
    FAILED_TASK_TEXT_COLOR = (0.8, 0.0, 0.0)
    FINISHED_TASK_TEXT_COLOR = (0.0, 0.8, 0.0)
    INTERRUPT_BUTTON = imagepool.get_surface(resources.path('images/video-download-cancel.png'))
    THUMB_OVERLAY = imagepool.get_surface(resources.path('images/thumb-overlay.png'), (THUMB_WIDTH, THUMB_HEIGHT))

    def get_size(self, style, layout):
        return 600, self.THUMB_HEIGHT + 31

    def render(self, context, layout, selected, hotspot, hover):
        self.hotspot = hotspot
        self.selected = selected
        self.setup_style(context.style)
        packing = self._pack_all(layout)
        packing.render_layout(context)

    def hotspot_test(self, style, layout, x, y, width, height):
        self.hotspot = None
        packing = self._pack_all(layout)
        hotspot_info = packing.find_hotspot(x, y, width, height)
        if hotspot_info is None:
            return None
        hotspot, x, y, width, height = hotspot_info
        return hotspot

    def add_background(self, content):
        inner = cellpack.Background(content, margin=(0, 12, 0, 12))
        if self.use_custom_style:
            inner.set_callback(self.draw_background)
        return cellpack.Background(inner, margin=(8, 12, 4, 16))

    def _pack_all(self, layout):
        hbox = cellpack.HBox()
        hbox.pack(self._pack_thumbnail(layout))
        hbox.pack(self._pack_info(layout), expand=True)
        return self.add_background(hbox)

    def _pack_thumbnail(self, layout):
        thumb = cellpack.DrawingArea(self.THUMB_WIDTH, self.THUMB_HEIGHT, self._draw_thumbnail)
        return cellpack.align_middle(cellpack.align_center(thumb))

    def _pack_info(self, layout):
        vbox = cellpack.VBox()
        if self.data.is_running() or self.data.is_finished():
            layout.set_text_color(self.ITEM_TITLE_COLOR)
        else:
            layout.set_text_color(self.PENDING_TASK_TEXT_COLOR)
        layout.set_font(1.1, bold=True)
        title = cellpack.ClippedTextLine(layout.textbox(self.data.item_info.name))
        vbox.pack(cellpack.pad(title, top=12))

        layout.set_font(0.8)
        if self.data.is_pending():
            layout.set_text_color(self.PENDING_TASK_TEXT_COLOR)
        else:
            layout.set_text_color(self.ITEM_DESC_COLOR)
        info_label = layout.textbox(
            _("Conversion to %(format)s",
              {"format": self.data.converter_info.name}))
        vbox.pack(cellpack.pad(info_label, top=4))

        if self.data.is_failed():
            vbox.pack(self._pack_failure_info(layout, self.data), expand=True)
        elif self.data.is_running():
            vbox.pack(self._pack_progress(layout), expand=True)
        elif self.data.is_finished():
            vbox.pack(self._pack_finished_info(layout), expand=True)
        else:
            vbox.pack(self._pack_pending_controls(layout), expand=True)

        return cellpack.pad(vbox, left=10)

    def _pack_progress(self, layout):
        vbox = cellpack.VBox()
        
        hbox = cellpack.HBox()
        hbox.pack(cellpack.align_middle(cellpack.align_center(self._progress_textbox(layout))), expand=True)
        hbox.pack(cellpack.pad(cellpack.align_right(cellpack.Hotspot('interrupt', self.INTERRUPT_BUTTON)), right=3))
        background = cellpack.Background(cellpack.align_middle(hbox), min_width=356, min_height=20)
        background.set_callback(style.ProgressBarDrawer(self.data.progress, ConversionProgressBarColorSet).draw)
        
        vbox.pack_end(cellpack.pad(background, bottom=12))
        
        return vbox

    def _pack_failure_info(self, layout, data):
        vbox = cellpack.VBox()

        layout.set_font(0.8, bold=True)
        layout.set_text_color(self.FAILED_TASK_TEXT_COLOR)
        info_label2 = layout.textbox(
            _("Failed: %(error)s", {"error": data.error}))
        vbox.pack(cellpack.pad(info_label2, top=4))
        
        # this resets the font so that the buttons aren't bold
        layout.set_font(0.8)
        hbox = cellpack.HBox()
        troubleshoot_button = layout.button(_("Troubleshoot"), self.hotspot=='troubleshoot', style='webby')
        hbox.pack(cellpack.Hotspot('troubleshoot', troubleshoot_button))
        open_log_button = layout.button(_("Open log"), self.hotspot=='open-log', style='webby')
        hbox.pack(cellpack.pad(cellpack.Hotspot('open-log', open_log_button), left=8))
        clear_button = layout.button(_("Clear"), self.hotspot=='clear-failed', style='webby')
        hbox.pack(cellpack.pad(cellpack.Hotspot('clear-failed', clear_button), left=8))
        vbox.pack_end(cellpack.pad(cellpack.align_right(hbox), bottom=12))

        return vbox

    def _pack_finished_info(self, layout):
        vbox = cellpack.VBox()

        layout.set_font(0.8, bold=True)
        layout.set_text_color(self.FINISHED_TASK_TEXT_COLOR)
        label = layout.textbox(_("Completed"))
        vbox.pack(cellpack.pad(label, top=4))

        hbox = cellpack.HBox()
        reveal_button = layout.button(self.REVEAL_IN_TEXT,
                self.hotspot=='reveal', style='webby')
        hbox.pack(cellpack.Hotspot('reveal', reveal_button))

        clear_button = layout.button(_("Clear"), self.hotspot=='clear-finished', style='webby')
        hbox.pack(cellpack.pad(cellpack.Hotspot('clear-finished', clear_button), left=8))

        vbox.pack_end(cellpack.pad(cellpack.align_right(hbox), bottom=12))

        return vbox

    def _pack_pending_controls(self, layout):
        vbox = cellpack.VBox()
        
        cancel_button = layout.button(_("Cancel"), self.hotspot=='cancel', style='webby')
        vbox.pack_end(cellpack.pad(cellpack.align_right(cellpack.Hotspot('cancel',
            cancel_button)), bottom=12))

        return vbox

    def _progress_textbox(self, layout):
        layout.set_font(0.8, bold=True)
        layout.set_text_color((1.0, 1.0, 1.0))
        progress = int(self.data.progress * 100)
        parts = ["%d%%" % progress]
        eta = self.data.get_eta()
        if eta:
            parts.append(displaytext.time_string(eta))
        
        return layout.textbox(' - '.join(parts))

    def _draw_thumbnail(self, context, x, y, width, height):
        fraction = 1.0
        if not self.data.is_running():
            fraction = 0.4
        icon = imagepool.get_surface(self.data.item_info.thumbnail, (width, height))
        widgetutil.draw_rounded_icon(context, icon, x, y, width, height, fraction=fraction)
        self.THUMB_OVERLAY.draw(context, x, y, width, height, fraction=fraction)
