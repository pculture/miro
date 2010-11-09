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

"""itemlistwidgets.py -- Widgets to display lists of items

itemlist, itemlistcontroller and itemlistwidgets work together using
the MVC pattern.  itemlist handles the Model, itemlistwidgets handles
the View and itemlistcontroller handles the Controller.

The classes inside this module are meant to be as dumb as possible.
They should only worry themselves about how things are displayed.  The
only thing they do in response to user input or other signals is to
forward those signals on.  It's the job of ItemListController
subclasses to handle the logic involved.
"""

from miro import app
from miro import prefs
from miro import displaytext
from miro import util
from miro.gtcache import gettext as _
from miro.gtcache import declarify
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import segmented
from miro.frontends.widgets import separator
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.plat.utils import get_available_bytes_for_movies

class TitleDrawer(widgetset.DrawingArea):
    """Draws the title of an item list."""
    def __init__(self, title):
        widgetset.DrawingArea.__init__(self)
        self.title = title

    def draw(self, context, layout):
        layout.set_font(2.2, family="Helvetica")
        layout.set_text_color((0.31, 0.31, 0.31))
        layout.set_text_shadow(widgetutil.Shadow((1, 1, 1), 1,
                                                 (1.5, -1.5), 0.5))
        textbox = layout.textbox(self.title)
        textbox.set_width(context.width)
        textbox.set_wrap_style('truncated-char')
        height = textbox.font.line_height()
        y = (context.height - height) / 2
        textbox.draw(context, 0, y, context.width, height)

    def size_request(self, layout):
        return (20, layout.font(2.2, family="Helvetica").line_height())

    def update_title(self, new_title):
        self.title = new_title
        self.queue_redraw()

class BoxedIconDrawer(widgetset.DrawingArea):
    """Draws the icon for an item list."""
    def __init__(self, image):
        widgetset.DrawingArea.__init__(self)
        self.icon = widgetset.ImageSurface(image)

    def size_request(self, layout):
        return (41, 41)

    def draw(self, context, layout):
        widgetutil.draw_rounded_icon(context, self.icon, 0, 0, 41, 41,
                                     inset=1)
        context.set_line_width(1)
        # Draw the black inner border
        context.set_color((0, 0, 0), 0.16)
        widgetutil.round_rect(context, 1.5, 1.5, 38, 38, 3)
        context.stroke()
        # Draw the white outer border
        context.set_color((1, 1, 1), 0.76)
        widgetutil.round_rect(context, 0.5, 0.5, 40, 40, 3)
        context.stroke()

class ItemListTitlebar(widgetset.Background):
    """Titlebar for feeds, playlists and static tabs that display
    items.

    :signal search-changed: (self, search_text) -- The value in the
        search box changed and the items listed should be filtered
    """
    def __init__(self, title, icon, add_icon_box=False):
        widgetset.Background.__init__(self)
        hbox = widgetset.HBox()
        self.add(hbox)
        # Pack the icon and title
        self.title_drawer = TitleDrawer(title)
        if add_icon_box:
            icon_widget = BoxedIconDrawer(icon)
        else:
            icon_widget = widgetset.ImageDisplay(icon)
        alignment = widgetset.Alignment(yalign=0.5, xalign=0.5)
        alignment.add(icon_widget)
        alignment.set_size_request(-1, 61)
        hbox.pack_start(alignment, padding=15)
        hbox.pack_start(self.title_drawer, expand=True)
        # Pack stuff to the right
        extra = self._build_titlebar_extra()
        if extra:
            if isinstance(extra, list):
                [hbox.pack_start(w) for w in extra]
            else:
                hbox.pack_start(extra)

    def draw(self, context, layout):
        if not context.style.use_custom_titlebar_background:
            return
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color((0.95, 0.95, 0.95))
        gradient.set_end_color((0.90, 0.90, 0.90))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)

    def update_title(self, new_title):
        self.title_drawer.update_title(new_title)

    def _build_titlebar_extra(self):
        """Builds the widget(s) to place to the right of the title.

        By default we add a search box, but subclasses can override
        this.
        """
        self.create_signal('search-changed')
        self.searchbox = widgetset.SearchTextEntry()
        self.searchbox.connect('changed', self._on_search_changed)
        return widgetutil.align_middle(self.searchbox, right_pad=35,
                                       left_pad=15)

    def _on_save_search(self, button):
        self.emit('save-search')

    def _on_search_changed(self, searchbox):
        self.emit('search-changed', searchbox.get_text())

    def set_title(self, title):
        self.title_drawer = title
        self.title_drawer.queue_redraw()

    def set_search_text(self, text):
        self.searchbox.set_text(text)

class ChannelTitlebar(ItemListTitlebar):
    """Titlebar for a channel

    :signal save-search: (self, search_text) The current search
        should be saved as a search channel.
    """

    def _build_titlebar_extra(self):
        self.create_signal('save-search')
        button = widgetset.Button(_('Save Search'))
        button.connect('clicked', self._on_save_search)
        self.save_button = widgetutil.HideableWidget(
                widgetutil.pad(button, right=10))
        return [
            widgetutil.align_middle(self.save_button),
            ItemListTitlebar._build_titlebar_extra(self),
        ]

    def _on_save_search(self, button):
        self.emit('save-search', self.searchbox.get_text())

    def _on_search_changed(self, searchbox):
        if searchbox.get_text() == '':
            self.save_button.hide()
        else:
            self.save_button.show()
        self.emit('search-changed', searchbox.get_text())

class SearchListTitlebar(ItemListTitlebar):
    """Titlebar for the search page.
    """
    def _on_search_activate(self, obj):
        app.search_manager.set_search_info(
            obj.selected_engine(), obj.get_text())
        app.search_manager.perform_search()

    def get_engine(self):
        return self.searchbox.selected_engine()

    def get_text(self):
        return self.searchbox.get_text()

    def set_search_engine(self, engine):
        self.searchbox.select_engine(engine)

    def _build_titlebar_extra(self):
        hbox = widgetset.HBox()

        self.searchbox = widgetset.VideoSearchTextEntry()
        w, h = self.searchbox.get_size_request()
        self.searchbox.set_size_request(w * 2, h)
        self.searchbox.connect('validate', self._on_search_activate)
        hbox.pack_start(widgetutil.align_middle(self.searchbox, 0, 0, 16, 16))

        return widgetutil.align_middle(hbox, right_pad=20)

class ItemView(widgetset.TableView):
    """TableView that displays a list of items using the standard
    view.
    """

    draws_selection = True

    def __init__(self, item_list, display_channel=True):
        widgetset.TableView.__init__(self, item_list.model)
        self.display_channel = display_channel
        self.item_list = item_list
        self.set_draws_selection(False)
        self.renderer = self.build_renderer()
        self.renderer.total_width = -1
        self.column = widgetset.TableColumn('item', self.renderer, data=0,
                show_details=1, throbber_counter=2)
        self.set_column_spacing(0)
        self.column.set_min_width(self.renderer.MIN_WIDTH)
        self.add_column(self.column)
        self.set_show_headers(False)
        self.allow_multiple_select(True)
        self.set_auto_resizes(True)
        self.set_background_color(widgetutil.WHITE)
        self._recalculate_heights_queued = False

    def build_renderer(self):
        return style.ItemRenderer(self.display_channel)

    def do_size_allocated(self, width, height):
        if width != self.renderer.total_width:
            self.renderer.total_width = width
            # We want to resize the rows with show_details set to
            # True, because they may have gotten taller/shorter based
            # on the description getting less/more width.  However, if
            # the user is quickly resizing the window, we don't want
            # to flood the system.  Use call_on_ui_thread, which
            # amounts to waiting until the widget system is idle.
            if not self._recalculate_heights_queued:
                self._recalculate_heights_queued = True
                call_on_ui_thread(self._recalculate_show_details_heights)

    def _recalculate_show_details_heights(self):
        self._recalculate_heights_queued = False
        for iter in self.item_list.find_show_details_rows():
            # We want to make this row's height get re-calculated, so
            # we use a bit of a hack, we "update" the row to the value
            # it currently has
            row = self.item_list.model[iter]
            self.item_list.model.update(iter, *row)

class ListItemView(widgetset.TableView):
    """TableView that displays a list of items using the list view."""

    def __init__(self, item_list, display_channel=True,
            display_download_info=True):
        widgetset.TableView.__init__(self, item_list.model)
        self.display_channel = display_channel
        self.display_download_info = display_download_info
        self.create_signal('sort-changed')
        self.item_list = item_list
        self._sort_name_to_column = {}
        self._current_sort_column = None
        self._set_initial_widths = False
        self._make_column('', style.StateCircleRenderer(), 'state', False)
        self._make_column(_('Title'), style.NameRenderer(), 'name')
        if display_channel:
            self._make_column(_('Feed'), style.FeedNameRenderer(),
                    'feed-name')
        self._make_column(_('Date'), style.DateRenderer(), 'date')
        self._make_column(_('Length'), style.LengthRenderer(), 'length')
        self._make_column(_('Status'), style.StatusRenderer(), 'status')
        self._make_column(_('Size'), style.SizeRenderer(), 'size')
        if display_download_info:
            self._make_column(_('ETA'), style.ETARenderer(), 'eta')
            self._make_column(_('Speed'), style.DownloadRateRenderer(),
                              'rate')
        self.set_show_headers(True)
        self.set_columns_draggable(True)
        self.set_column_spacing(12)
        self.set_row_spacing(8)
        self.set_grid_lines(False, True)
        self.set_alternate_row_backgrounds(True)
        self.set_fixed_height(True)
        self.allow_multiple_select(True)
        self.html_stripper = util.HTMLStripper()

    def get_tooltip(self, iter, column):
        if column == self._sort_name_to_column['name']:
            info = self.item_list.model[iter][0]
            text, links = self.html_stripper.strip(info.description)
            if text:
                if len(text) > 1000:
                    text = text[:994] + ' [...]'
                return text

        elif column == self._sort_name_to_column['state']:
            info = self.item_list.model[iter][0]
            # this logic is replicated in style.StateCircleRenderer
            # with text from style.StatusRenderer
            if info.state == 'downloading':
                return _("Downloading")
            elif (info.downloaded and info.is_playable
                  and not info.video_watched):
                return _("Unplayed")
            elif (not info.item_viewed and not info.expiration_date
                  and not info.is_external):
                return _("Newly Available")
        return None

    def _make_column(self, header, renderer, sort_name, resizable=True):
        column = widgetset.TableColumn(header, renderer, info=0)
        if resizable:
            column.set_resizable(True)
            column.set_min_width(renderer.min_width)
        if header and renderer.right_aligned:
            column.set_right_aligned(True)
        column.connect_weak('clicked', self._on_column_clicked, sort_name)
        self._sort_name_to_column[sort_name] = column
        self.add_column(column)

    def do_size_allocated(self, width, height):
        if not self._set_initial_widths:
            width -= 20 # allow some room for a scrollbar
            # Set this immediately, because changing the widths of
            # widgets below can invoke another size-allocate signal
            self._set_initial_widths = True
            # width_specs contains the info we need to give columns their
            # initial size.  It maps column names to
            # (min_width, extra_width_weighting)
            width_specs = {
                'state': (20, 0),    # bump
                'name': (130, 1),   # title
                'feed-name': (70, 0.5),  # channel name
                'date': (85, 0),   # date
                'length': (60, 0),   # duration
                'status': (160, 0),   # status
                'size': (65, 0),    # size
                'eta': (50, 0),    # eta
                'rate': (75, 0),    # download rate
            }

            for key in width_specs.keys():
                if key not in self._sort_name_to_column:
                    # column not visible on this view
                    del width_specs[key]

            available_width = self.width_for_columns(width)
            min_width = sum(spec[0] for spec in width_specs.values())
            extra_width = max(available_width - min_width, 0)
            total_weight = sum(spec[1] for spec in width_specs.values())
            for name, spec in width_specs.items():
                column = self._sort_name_to_column[name]
                extra = int(extra_width * spec[1] / total_weight)
                column.set_width(spec[0] + extra)

    def _on_column_clicked(self, column, sort_name):
        ascending = not (column.get_sort_indicator_visible() and
                column.get_sort_order_ascending())
        self.emit('sort-changed', sort_name, ascending)

    def change_sort_indicator(self, sort_name, ascending):
        new_sort_column = self._sort_name_to_column[sort_name]
        if self._current_sort_column is None:
            new_sort_column.set_sort_indicator_visible(True)
        elif self._current_sort_column is not new_sort_column:
            self._current_sort_column.set_sort_indicator_visible(False)
            new_sort_column.set_sort_indicator_visible(True)
        new_sort_column.set_sort_order(ascending)
        self._current_sort_column = new_sort_column

class HideableSection(widgetutil.HideableWidget):
    """Widget that contains an ItemView, along with an expander to
    show/hide it.

    The label for a HideableSection expander is made up of 2 parts.
    The header is displayed first using a bold text, then the info is
    displayed using normal font.
    """

    def __init__(self, header_text, item_view):
        self.expander = widgetset.Expander(item_view)
        self.expander.set_expanded(False)
        widget = widgetutil.pad(self.expander, top=3, bottom=3, left=5)
        self._make_label(header_text)
        widgetutil.HideableWidget.__init__(self, widget)

    def set_info(self, text):
        self.info_label.set_text(text)

    def set_header(self, text):
        self.header_label.set_text(text)

    def expand(self):
        self.expander.set_expanded(True)

    def _make_label(self, header_text):
        hbox = widgetset.HBox()
        self.header_label = widgetset.Label(header_text)
        self.header_label.set_size(0.85)
        self.header_label.set_bold(True)
        self.header_label.set_color((0.27, 0.27, 0.27))
        hbox.pack_start(self.header_label)
        self.info_label = widgetset.Label("")
        self.info_label.set_size(0.85)
        self.info_label.set_color((0.72, 0.72, 0.72))
        hbox.pack_start(widgetutil.pad(self.info_label, left=7))
        self.expander.set_label(hbox)

class DisplayToolbar(widgetset.Background):
    def draw(self, context, layout):
        if not context.style.use_custom_titlebar_background:
            return
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color((0.90, 0.90, 0.90))
        gradient.set_end_color((0.79, 0.79, 0.79))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)

class SearchToolbar(DisplayToolbar):
    """Toolbar for the search page.

    It's a hidable widget that contains the save search button.

    :signal save-search (self) -- The current search should be saved
        as a search channel.
    """

    def __init__(self):
        DisplayToolbar.__init__(self)
        hbox = widgetset.HBox()
        self.add(hbox)
        save_button = widgetset.Button(_('Save as a Feed'), style='smooth')
        save_button.set_size(widgetconst.SIZE_SMALL)
        save_button.connect('clicked', self._on_save_clicked)
        aligned = widgetutil.align_left(save_button, top_pad=5, left_pad=5,
                                        bottom_pad=5)
        self.hideable = widgetutil.HideableWidget(aligned)
        hbox.pack_start(self.hideable)
        self.create_signal('save-search')

    def _on_save_clicked(self, button):
        self.emit('save-search')

    def show(self):
        self.hideable.show()

    def hide(self):
        self.hideable.hide()

class DownloadStatusToolbar(DisplayToolbar):
    """Widget that shows free space and download and upload speed status."""

    def __init__(self):
        DisplayToolbar.__init__(self)

        v = widgetset.VBox()

        sep = separator.HSeparator((0.85, 0.85, 0.85), (0.95, 0.95, 0.95))
        v.pack_start(sep)

        h = widgetset.HBox(spacing=5)

        self._free_disk_label = widgetset.Label("")
        self._free_disk_label.set_size(widgetconst.SIZE_SMALL)

        h.pack_start(widgetutil.align_left(self._free_disk_label,
            top_pad=10, left_pad=20, bottom_pad=10), expand=True)


        # Sigh.  We want to fix these sizes so they don't jump about
        # but different languages will have different sizes for these
        # things.  What we do is, try to work out a decent size for it then
        # reserve that amount of space suitable for the user's locale.
        # Both these labels can be used for upload and download so we 
        # just need to test one.
        placeholder_bps = 500 * 1024
        text_up = _("%(rate)s uploading",
                    {"rate": displaytext.download_rate(placeholder_bps)})
        text_down = _("%(rate)s downloading",
                      {"rate": displaytext.download_rate(placeholder_bps)})

        first_label = widgetset.Label("")
        first_label.set_size(widgetconst.SIZE_SMALL)

        # Now, auto-detect the size required.
        first_label.set_text(text_up)
        width1, height1 = first_label.get_size_request()
        first_label.set_text(text_down)
        width2, height2 = first_label.get_size_request()
        
        first_label.set_size_request(max(width1, width2), -1)
        self._first_label = first_label

        h.pack_start(widgetutil.align_right(self._first_label,
            left_pad=10, top_pad=10, bottom_pad=10, right_pad=10))

        second_label = widgetset.Label("")
        second_label.set_size(widgetconst.SIZE_SMALL)
        second_label.set_size_request(max(width1, width2), -1)
        self._second_label = second_label

        h.pack_start(widgetutil.align_right(self._second_label,
            top_pad=10, bottom_pad=10, right_pad=20, left_pad=10))

        v.pack_start(h)
        self.add(v)

        app.frontend_config_watcher.connect('changed', self.on_config_change)

    def on_config_change(self, obj, key, value):
        if ((key == prefs.PRESERVE_X_GB_FREE.key
             or key == prefs.PRESERVE_DISK_SPACE.key)):
            self.update_free_space()

    def update_free_space(self):
        """Updates the free space text on the downloads tab.

        amount -- the total number of bytes free.
        """
        amount = get_available_bytes_for_movies()
        if app.config.get(prefs.PRESERVE_DISK_SPACE):
            available = (app.config.get(prefs.PRESERVE_X_GB_FREE) * 1024 * 1024 * 1024)
            available = amount - available

            if available < 0:
                available = available * -1.0
                text = _(
                    "%(available)s below downloads space limit (%(amount)s "
                    "free on disk)",
                    {"amount": displaytext.size_string(amount),
                     "available": displaytext.size_string(available)}
                )
            else:
                text = _(
                    "%(available)s free for downloads (%(amount)s free "
                    "on disk)",
                    {"amount": displaytext.size_string(amount),
                     "available": displaytext.size_string(available)}
                )
        else:
            text = _("%(amount)s free on disk",
                     {"amount": displaytext.size_string(amount)})
        self._free_disk_label.set_text(text)

    def update_rates(self, down_bps, up_bps):
        text_up = text_down = ''
        if up_bps >= 10:
            text_up = _("%(rate)s uploading",
                        {"rate": displaytext.download_rate(up_bps)})
        if down_bps >= 10:
            text_down = _("%(rate)s downloading",
                          {"rate": displaytext.download_rate(down_bps)})

        if text_up and text_down:
            self._first_label.set_text(text_down)
            self._second_label.set_text(text_up)
        elif text_up:
            self._first_label.set_text(text_up)
            self._second_label.set_text('')
        elif text_down:
            self._first_label.set_text(text_down)
            self._second_label.set_text('')
        else:
            self._first_label.set_text('')
            self._second_label.set_text('')

class DownloadToolbar(DisplayToolbar):
    """Widget that pause/resume/... buttons for downloads, and other data.

    :signal pause-all: All downloads should be paused
    :signal resume-all: All downloads should be resumed
    :signal cancel-all: All downloads should be canceled
    :signal settings: The preferences panel downloads tab should be opened
    """

    def __init__(self):
        DisplayToolbar.__init__(self)        
        vbox = widgetset.VBox()

        sep = separator.HSeparator((0.85, 0.85, 0.85), (0.95, 0.95, 0.95))
        vbox.pack_start(sep)

        h = widgetset.HBox(spacing=5)

        self.create_signal('pause-all')
        self.create_signal('resume-all')
        self.create_signal('cancel-all')
        self.create_signal('settings')

        pause_button = widgetset.Button(_('Pause All'), style='smooth')
        pause_button.set_size(widgetconst.SIZE_SMALL)
        pause_button.set_color(widgetset.TOOLBAR_GRAY)
        pause_button.connect('clicked', self._on_pause_button_clicked)
        h.pack_start(widgetutil.align_right(pause_button, top_pad=5,
            bottom_pad=5), expand=True)

        resume_button = widgetset.Button(_('Resume All'), style='smooth')
        resume_button.set_size(widgetconst.SIZE_SMALL)
        resume_button.set_color(widgetset.TOOLBAR_GRAY)
        resume_button.connect('clicked', self._on_resume_button_clicked)
        h.pack_start(widgetutil.align_middle(resume_button, top_pad=5,
            bottom_pad=5))

        cancel_button = widgetset.Button(_('Cancel All'), style='smooth')
        cancel_button.set_size(widgetconst.SIZE_SMALL)
        cancel_button.set_color(widgetset.TOOLBAR_GRAY)
        cancel_button.connect('clicked', self._on_cancel_button_clicked)
        h.pack_start(widgetutil.align_middle(cancel_button, top_pad=5,
            bottom_pad=5))

        settings_button = widgetset.Button(_('Download Settings'),
                                           style='smooth')
        settings_button.set_size(widgetconst.SIZE_SMALL)
        settings_button.set_color(widgetset.TOOLBAR_GRAY)
        settings_button.connect('clicked', self._on_settings_button_clicked)
        h.pack_start(widgetutil.align_middle(settings_button, top_pad=5,
            bottom_pad=5, right_pad=16))

        vbox.pack_start(h)

        h = widgetset.HBox(spacing=10)

        vbox.pack_start(h)
        self.add(vbox)

    def _on_pause_button_clicked(self, widget):
        self.emit('pause-all')

    def _on_resume_button_clicked(self, widget):
        self.emit('resume-all')

    def _on_cancel_button_clicked(self, widget):
        self.emit('cancel-all')

    def _on_settings_button_clicked(self, widget):
        self.emit('settings')

class FeedToolbar(DisplayToolbar):
    """Toolbar that appears below the title in a feed.

    :signal remove-feed: (widget) The 'remove feed' button was pressed
    :signal show-settings: (widget) The show settings button was pressed
    :signal share: (widget) The 'share' button was pressed
    :signal auto-download-changed: (widget, value) The auto-download
        setting was changed by the user
    """

    def __init__(self):
        DisplayToolbar.__init__(self)
        self.create_signal('remove-feed')
        self.create_signal('show-settings')
        self.create_signal('share')
        self.create_signal('auto-download-changed')
        hbox = widgetset.HBox(spacing=5)

        label = widgetset.Label(_('Auto-download'))
        label.set_size(widgetconst.SIZE_SMALL)
        label.set_color(widgetset.TOOLBAR_GRAY)
        self.autodownload_label = widgetutil.HideableWidget(label)

        self.autodownload_options = (("all", _("All")),
                                     ("new", _("New")),
                                     ("off", _("Off")))

        autodownload_menu = widgetset.OptionMenu(
            [o[1] for o in self.autodownload_options])
        autodownload_menu.set_size(widgetconst.SIZE_SMALL)
        autodownload_menu.connect('changed', self._on_autodownload_changed)
        self.autodownload_menu = widgetutil.HideableWidget(autodownload_menu)

        share_button = widgetset.Button(_("Share feed"), style='smooth')
        share_button.set_size(widgetconst.SIZE_SMALL)
        share_button.set_color(widgetset.TOOLBAR_GRAY)
        share_button.connect('clicked', self._on_share_clicked)
        self.share_button = widgetutil.HideableWidget(share_button)

        settings_button = widgetset.Button(_("Settings"), style='smooth')
        settings_button.set_size(widgetconst.SIZE_SMALL)
        settings_button.set_color(widgetset.TOOLBAR_GRAY)
        settings_button.connect('clicked', self._on_settings_clicked)
        self.settings_button = widgetutil.HideableWidget(settings_button)

        remove_button = widgetset.Button(_("Remove feed"), style='smooth')
        remove_button.set_size(widgetconst.SIZE_SMALL)
        remove_button.set_color(widgetset.TOOLBAR_GRAY)
        remove_button.connect('clicked', self._on_remove_clicked)
        self.remove_button = remove_button

        hbox.pack_start(widgetutil.align_middle(self.autodownload_label,
                                                right_pad=2, left_pad=6))
        hbox.pack_start(widgetutil.align_middle(self.autodownload_menu))
        hbox.pack_end(widgetutil.align_middle(self.remove_button))
        hbox.pack_end(widgetutil.align_middle(self.settings_button))
        hbox.pack_end(widgetutil.align_middle(self.share_button))
        self.add(widgetutil.pad(hbox, top=4, bottom=4, left=10, right=14))

    def set_autodownload_mode(self, autodownload_mode):
        if autodownload_mode == 'all':
            self.autodownload_menu.child().set_selected(0)
        elif autodownload_mode == 'new':
            self.autodownload_menu.child().set_selected(1)
        elif autodownload_mode == 'off':
            self.autodownload_menu.child().set_selected(2)

    def _on_settings_clicked(self, button):
        self.emit('show-settings')

    def _on_share_clicked(self, button):
        self.emit('share')

    def _on_remove_clicked(self, button):
        self.emit('remove-feed')

    def _on_autodownload_changed(self, widget, option):
        self.emit('auto-download-changed', self.autodownload_options[option][0])

class HeaderToolbar(widgetset.Background):
    """Toolbar used to sort items and switch views.

    Signals:

    :signal sort-changed: (widget, sort_key, ascending) User changed
        the sort.  sort_key will be one of 'name', 'date', 'size' or
        'length'
    :signal list-view-clicked: (widget) User requested to switch to
        list view
    :signal normal-view-clicked: (widget) User requested to switch to
        normal view
    :signal view-all-clicked: User requested to view all items
    :signal toggle-unwatched-clicked: User toggled the
        unwatched/unplayed items only view
    :signal toggle-non-feed-clicked: User toggled the non feed items only view
    """
    def __init__(self):
        widgetset.Background.__init__(self)
        self.create_signals()
        
        self._button_hbox = widgetset.HBox()
        self._button_hbox_container = widgetutil.HideableWidget(
            self._button_hbox)
        self._button_hbox_container.show()

        self._hbox = widgetset.HBox()
 
        self.view_switch = segmented.SegmentedButtonsRow()
        self.view_switch.add_image_button('normal-view',
                                          'normal-view-button-icon',
                                          self._on_normal_clicked)
        self.view_switch.add_image_button('list-view',
                                          'list-view-button-icon',
                                          self._on_list_clicked)
        self.view_switch.set_active('normal-view')
        self._hbox.pack_start(widgetutil.align_middle(
            self.view_switch.make_widget(), left_pad=12))

        self._hbox.pack_end(widgetutil.align_middle(
            self._button_hbox_container))
        self.pack_hbox_extra()

        self.add(self._hbox)

        self._current_sort_key = 'date'
        self._ascending = False
        self._button_map = {}
        self._make_button(_('Name'), 'name')
        self._make_button(_('Date'), 'date')
        self._make_button(_('Size'), 'size')
        self._make_button(_('Time'), 'length')
        self._button_map['date'].set_sort_state(SortBarButton.SORT_DOWN)

    def create_signals(self):
        self.create_signal('sort-changed')
        self.create_signal('list-view-clicked')
        self.create_signal('normal-view-clicked')

    def pack_hbox_extra(self):
        pass

    def active_filters(self):
        return self.filter_switch.active_buttons()

    def _on_normal_clicked(self, button):
        self.emit('normal-view-clicked')

    def _on_list_clicked(self, button):
        self.emit('list-view-clicked')

    def switch_to_normal_view(self):
        self._button_hbox_container.show()
        self.view_switch.set_active('normal-view')

    def switch_to_list_view(self):
        self._button_hbox_container.hide()
        self.view_switch.set_active('list-view')

    def _on_view_all_clicked(self, button):
        self.emit('view-all-clicked')

    def switch_to_view_all(self):
        self.filter_switch.set_active('view-all')
        self.filter_switch.set_active('view-unwatched', False)
        self.filter_switch.set_active('view-non-feed', False)

    def switch_to_view_all_if_necessary(self):
        view_all = (not self.filter_switch.is_active('view-unwatched')
                    and not self.filter_switch.is_active('view-non-feed'))
        self.filter_switch.set_active('view-all', view_all)

    def _on_toggle_unwatched_clicked(self, button):
        self.emit('toggle-unwatched-clicked')

    def toggle_unwatched_only(self):
        self.filter_switch.toggle('view-unwatched')
        self.switch_to_view_all_if_necessary()

    def _on_toggle_non_feed_clicked(self, button):
        self.emit('toggle-non-feed-clicked')
        
    def toggle_non_feed_only(self):
        self.filter_switch.toggle('view-non-feed')
        self.switch_to_view_all_if_necessary()

    def change_sort_indicator(self, sort_name, ascending):
        if not sort_name in self._button_map:
            return
        for name, button in self._button_map.iteritems():
            if name == sort_name:
                if ascending:
                    button.set_sort_state(SortBarButton.SORT_UP)
                else:
                    button.set_sort_state(SortBarButton.SORT_DOWN)
            else:
                button.set_sort_state(SortBarButton.SORT_NONE)
        self._ascending = ascending

    def _make_button(self, text, sort_key):
        button = SortBarButton(text)
        button.connect('clicked', self._on_button_clicked, sort_key)
        self._button_map[sort_key] = button
        self._button_hbox.pack_start(button, padding=4)

    def _on_button_clicked(self, button, sort_key):
        if self._current_sort_key == sort_key:
            self._ascending = not self._ascending
        else:
            # we want sort-by-name to default to alphabetical order
            if sort_key == "name":
                self._ascending = True
            else:
                self._ascending = False
            old_button = self._button_map[self._current_sort_key]
            old_button.set_sort_state(SortBarButton.SORT_NONE)
            self._current_sort_key = sort_key
        if self._ascending:
            button.set_sort_state(SortBarButton.SORT_UP)
        else:
            button.set_sort_state(SortBarButton.SORT_DOWN)
        self.emit('sort-changed', self._current_sort_key, self._ascending)

    def size_request(self, layout):
        width, height = self._hbox.get_size_request()
        return width, max(height, 30)

    def draw(self, context, layout):
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color((0.49, 0.49, 0.49))
        gradient.set_end_color((0.42, 0.42, 0.42))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)
        context.set_color((0.4, 0.4, 0.4))
        context.move_to(0.5, 0.5)
        context.rel_line_to(context.width, 0)
        context.stroke()
        context.set_color((0.16, 0.16, 0.16))
        context.move_to(0.5, context.height-0.5)
        context.rel_line_to(context.width, 0)
        context.stroke()

class LibraryHeaderToolbar(HeaderToolbar):
    def __init__(self, unwatched_label):
        self.unwatched_label = unwatched_label
        HeaderToolbar.__init__(self)

    def create_signals(self):
        HeaderToolbar.create_signals(self)
        self.create_signal('view-all-clicked')
        self.create_signal('toggle-unwatched-clicked')
        self.create_signal('toggle-non-feed-clicked')

    def pack_hbox_extra(self):
        self.filter_switch = segmented.SegmentedButtonsRow(behavior='custom')
        # this "All" is different than other "All"s in the codebase, so it
        # needs to be clarified
        self.filter_switch.add_text_button('view-all',
                                           declarify(_('View|All')),
                                           self._on_view_all_clicked)
        self.filter_switch.add_text_button('view-unwatched',
                                           self.unwatched_label,
                                           self._on_toggle_unwatched_clicked)
        self.filter_switch.add_text_button('view-non-feed',
                                           _('Non Feed'),
                                           self._on_toggle_non_feed_clicked)
        self.filter_switch.set_active('view-all')
        self._hbox.pack_start(widgetutil.align_middle(
            self.filter_switch.make_widget(), left_pad=12))

    def set_active_filters(self, filters):
        filter_set = set(filters)
        for filter in self.filter_switch.all_buttons():
            self.filter_switch.set_active(filter, filter in filter_set)

class SortBarButton(widgetset.CustomButton):
    SORT_NONE = 0
    SORT_UP = 1
    SORT_DOWN = 2

    def __init__(self, text):
        widgetset.CustomButton.__init__(self)
        self._text = text
        self._sort_state = self.SORT_NONE

    def set_sort_state(self, sort_state):
        self._sort_state = sort_state
        self.queue_redraw()

    def size_request(self, layout):
        layout.set_font(0.8, bold=True)
        text_size = layout.textbox(self._text).get_size()
        return text_size[0] + 36, text_size[1] + 6

    def draw(self, context, layout):
        if ((self.state == 'hover'
             or self.state == 'pressed'
             or self._sort_state != self.SORT_NONE)):
            if self._sort_state != self.SORT_NONE:
                context.set_color((0.29, 0.29, 0.29))
            else:
                context.set_color((0.7, 0.7, 0.7))
            widgetutil.round_rect(context, 0.5, 0.5, context.width - 2,
                                  context.height - 2, 8)
            context.fill()
        layout.set_font(0.8, bold=True)
        layout.set_text_color((1, 1, 1))
        textbox = layout.textbox(self._text)
        text_size = textbox.get_size()
        y = int((context.height - textbox.get_size()[1]) / 2) - 1.5
        textbox.draw(context, 12, y, text_size[0], text_size[1])
        context.set_color((1, 1, 1))
        self._draw_triangle(context, text_size[0] + 18)

    def _draw_triangle(self, context, left):
        top = int((context.height - 4) / 2)
        if self._sort_state == self.SORT_DOWN:
            context.move_to(left, top)
            context.rel_line_to(6, 0)
            context.rel_line_to(-3, 4)
            context.rel_line_to(-3, -4)
            context.fill()
        elif self._sort_state == self.SORT_UP:
            context.move_to(left, top + 4)
            context.rel_line_to(6, 0)
            context.rel_line_to(-3, -4)
            context.rel_line_to(-3, 4)
            context.fill()

class ItemListBackground(widgetset.Background):
    """Plain white background behind the item lists.
    """

    def draw(self, context, layout):
        if context.style.use_custom_style:
            context.set_color((1, 1, 1))
            context.rectangle(0, 0, context.width, context.height)
            context.fill()

class EmptyListHeader(widgetset.Alignment):
    """Header Label for empty item lists."""
    def __init__(self, text):
        widgetset.Alignment.__init__(self, xalign=0.5, xscale=0.0)
        self.set_padding(24, 0, 0, 0)
        self.label = widgetset.Label(text)
        self.label.set_bold(True)
        self.label.set_color((0.8, 0.8, 0.8))
        self.label.set_size(2)
        self.add(self.label)

class EmptyListDescription(widgetset.Alignment):
    """Label for descriptions of empty item lists."""
    def __init__(self, text):
        widgetset.Alignment.__init__(self, xalign=0.5, xscale=0.5)
        self.set_padding(18)
        self.label = widgetset.Label(text)
        self.label.set_color((0.8, 0.8, 0.8))
        self.label.set_wrap(True)
        self.label.set_size_request(250, -1)
        self.add(self.label)

class ItemContainerWidget(widgetset.VBox):
    """A Widget for displaying objects that contain items (feeds,
    playlists, folders, downloads tab, etc).

    :attribute titlebar_vbox: VBox for the title bar
    :attribute normal_view_vbox: VBox for normal view of the items
    :attribute list_view_vbox: VBox for list view of the items
    :attribute list_empty_mode_vbox: VBox for list empty mode
    :attribute toolbar: HeaderToolbar for the widget
    """

    def __init__(self, toolbar):
        widgetset.VBox.__init__(self)
        self._list_view_displayed = False
        self.normal_view_vbox = widgetset.VBox()
        self.list_view_vbox = widgetset.VBox()
        self.titlebar_vbox = widgetset.VBox()
        self.statusbar_vbox = widgetset.VBox()
        self.list_empty_mode_vbox = widgetset.VBox()
        self.toolbar = toolbar
        self.toolbar.connect('list-view-clicked', self.switch_to_list_view)
        self.toolbar.connect('normal-view-clicked', self.switch_to_normal_view)
        self.pack_start(self.titlebar_vbox)
        self.pack_start(self.toolbar)
        self.background = ItemListBackground()
        self.background.add(self.normal_view_vbox)
        self.pack_start(self.background, expand=True)
        self.pack_start(self.statusbar_vbox)
        self.in_list_view = False
        self.list_empty_mode = False

    def switch_to_list_view(self, toolbar=None):
        if not self.in_list_view:
            if not self.list_empty_mode:
                self.background.remove()
                self.background.add(self.list_view_vbox)
            self.toolbar.switch_to_list_view()
            self.in_list_view = True

    def switch_to_normal_view(self, toolbar=None):
        if self.in_list_view:
            if not self.list_empty_mode:
                self.background.remove()
                self.background.add(self.normal_view_vbox)
            self.toolbar.switch_to_normal_view()
            self.in_list_view = False

    def set_list_empty_mode(self, enabled):
        if enabled == self.list_empty_mode:
            return

        self.background.remove()
        if enabled:
            self.background.add(self.list_empty_mode_vbox)
        elif self.in_list_view:
            self.background.add(self.list_view_vbox)
        else:
            self.background.add(self.normal_view_vbox)
        self.list_empty_mode = enabled
