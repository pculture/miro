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

"""itemlistwidgets.py -- Widgets to display lists of items

itemlist, itemlistcontroller and itemlistwidgets work togetherusing the MVC
pattern.  itemlist handles the Model, itemlistwidgets handles the View and
itemlistcontroller handles the Controller.

The classes inside this module are meant to be as dumb as possible.  They
should only worry themselves about how things are displayed.  The only thing
they do in response to user input or other signals is to forward those signals
on.  It's the job of ItemListController subclasses to handle the logic
involved.
"""

from miro import config
from miro import prefs
from miro import displaytext
from miro import searchengines
from miro.gtcache import gettext as _
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset
from miro.plat.utils import get_available_bytes_for_movies

class TitleDrawer(widgetset.DrawingArea):
    """Draws the title of an item list."""
    def __init__(self, title):
        widgetset.DrawingArea.__init__(self)
        self.title = title

    def draw(self, context, layout):
        layout.set_font(2.2, family="Helvetica")
        layout.set_text_color((0.31, 0.31, 0.31))
        layout.set_text_shadow(widgetutil.Shadow((1,1,1), 1, (1.5,-1.5), 0.5))
        textbox = layout.textbox(self.title)
        textbox.set_width(context.width)
        textbox.set_wrap_style('truncated-char')
        height = textbox.font.line_height()
        y = (context.height - height) / 2
        textbox.draw(context, 0, y, context.width, height)

    def update_title(self, new_title):
        self.title = new_title
        self.queue_redraw()

class ItemListTitlebar(widgetset.Background):
    """Titlebar for feeds, playlists and static tabs that display items.

    signals:
      search-changed (self, search_text) -- The value in the search box
          changed and the items listed should be filtered
    """
    def __init__(self, title, icon):
        widgetset.Background.__init__(self)
        hbox = widgetset.HBox()
        self.add(hbox)
        # Pack the icon and title
        image = widgetset.ImageDisplay(icon)
        imagebox = widgetutil.align(image, xscale=1, yscale=1)
        imagebox.set_size_request(61, 61)
        self.title_drawer = TitleDrawer(title)
        hbox.pack_start(imagebox)
        hbox.pack_start(self.title_drawer, padding=15, expand=True)
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

        By default we add a search box, but subclasses can overide this.
        """

        self.create_signal('search-changed')
        self.searchbox = widgetset.SearchTextEntry()
        self.searchbox.connect('changed', self._on_search_changed)
        return widgetutil.align_middle(self.searchbox, right_pad=35)

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

    signals:
      save-search (self, search_text) -- The current search should be saved
          as a search channel.
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

    signals:
      search(self, engine_name search_text) -- The user is requesting a new
          search.
    """

    def get_engine(self):
        return self.engines[self.search_dropdown.get_selected()].name

    def get_text(self):
        return self.searchbox.get_text()

    def _on_search_activate(self, widget):
        self.emit('search', self.get_engine(), self.get_text())

    def _build_titlebar_extra(self):
        self.create_signal('search')
        hbox = widgetset.HBox()

        self.engines = searchengines.get_search_engines()
        engine_names = [se.title for se in self.engines]
        self.search_dropdown = widgetset.OptionMenu(engine_names)
        hbox.pack_start(self.search_dropdown, padding=5)

        self.searchbox = widgetset.SearchTextEntry(initial_text=_('Search terms'))
        self.searchbox.set_width(15)
        self.searchbox.connect('activate', self._on_search_activate)
        hbox.pack_start(widgetutil.align_middle(self.searchbox))

        self.search_button = widgetset.Button(_('Search'))
        self.search_button.set_size(widgetconst.SIZE_SMALL)
        self.search_button.connect('clicked', self._on_search_activate)
        hbox.pack_start(self.search_button, padding=5)
        return widgetutil.align_middle(hbox, right_pad=20)

    def set_search_engine(self, engine):
        index = [e.name for e in self.engines].index(engine)
        self.search_dropdown.set_selected(index)

class ItemView(widgetset.TableView):
    """TableView that displays a list of items.  """

    def __init__(self, item_list):
        widgetset.TableView.__init__(self, item_list.model)
        self.item_list = item_list
        self.set_draws_selection(False)
        renderer = self.build_renderer()
        self.add_column('item', renderer, renderer.MIN_WIDTH, data=0,
                show_details=1, throbber_counter=2)
        self.set_show_headers(False)
        self.allow_multiple_select(True)
        self.set_background_color(widgetutil.WHITE)

    def build_renderer(self):
        return style.ItemRenderer()

class HideableSection(widgetutil.HideableWidget):
    """Widget that contains an ItemView, along with an expander to show/hide
    it.

    The label for a HideableSection expander is made up of 2 parts.  The header
    is displayed first using a bold text, then the info is displayed using
    normal font.
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

class SearchToolbar(widgetutil.HideableWidget):
    """Toolbar for the search page.

    It's a hidable widget that contains the save search button.

    signals:

       save-search (self) -- The current search should be saved as a search
           channel.
    """

    def __init__(self):
        save_button = widgetset.Button(_('Save as a Channel'))
        save_button.connect('clicked', self._on_save_clicked)
        child = widgetutil.align_left(save_button, left_pad=5, bottom_pad=5)
        widgetutil.HideableWidget.__init__(self, child)
        self.create_signal('save-search')

    def _on_save_clicked(self, button):
        self.emit('save-search')

class DownloadToolbar(widgetset.VBox):
    """Widget that shows free space, pause/resume/... buttons for downloads,
    and other data.

    signals:

       pause-all -- All downloads should be paused
       resume-all -- All downloads should be resumed
       cancel-all -- All downloads should be canceled
       settings -- The preferences panel downloads tab should be opened
    """

    def __init__(self):
        widgetset.VBox.__init__(self)

        h = widgetset.HBox(spacing=10)

        self._free_disk_label = widgetset.Label("")
        self._free_disk_label.set_size(widgetconst.SIZE_SMALL)

        h.pack_start(widgetutil.align_left(self._free_disk_label,
            top_pad=5, left_pad=10), expand=True)

        self.create_signal('pause-all')
        self.create_signal('resume-all')
        self.create_signal('cancel-all')
        self.create_signal('settings')

        pause_button = widgetset.Button(_('Pause All'), style='smooth')
        pause_button.set_size(widgetconst.SIZE_SMALL)
        pause_button.set_color(style.TOOLBAR_GRAY)
        pause_button.connect('clicked', self._on_pause_button_clicked)
        h.pack_start(widgetutil.align_right(pause_button, top_pad=5,
            bottom_pad=5), expand=True)

        resume_button = widgetset.Button(_('Resume All'), style='smooth')
        resume_button.set_size(widgetconst.SIZE_SMALL)
        resume_button.set_color(style.TOOLBAR_GRAY)
        resume_button.connect('clicked', self._on_resume_button_clicked)
        h.pack_start(widgetutil.align_middle(resume_button, top_pad=5,
            bottom_pad=5))

        cancel_button = widgetset.Button(_('Cancel All'), style='smooth')
        cancel_button.set_size(widgetconst.SIZE_SMALL)
        cancel_button.set_color(style.TOOLBAR_GRAY)
        cancel_button.connect('clicked', self._on_cancel_button_clicked)
        h.pack_start(widgetutil.align_middle(cancel_button, top_pad=5,
            bottom_pad=5))

        settings_button = widgetset.Button(_('Download Settings'), style='smooth')
        settings_button.set_size(widgetconst.SIZE_SMALL)
        settings_button.set_color(style.TOOLBAR_GRAY)
        settings_button.connect('clicked', self._on_settings_button_clicked)
        h.pack_start(widgetutil.align_middle(settings_button, top_pad=5,
            bottom_pad=5, right_pad=16))

        self.pack_start(h)

        h = widgetset.HBox(spacing=10)

        first_label = widgetset.Label("")
        first_label.set_size(widgetconst.SIZE_SMALL)
        self._first_label = first_label

        h.pack_start(widgetutil.align_left(self._first_label,
            left_pad=10, bottom_pad=5))

        second_label = widgetset.Label("")
        second_label.set_size(widgetconst.SIZE_SMALL)
        self._second_label = second_label

        h.pack_start(widgetutil.align_left(self._second_label,
            bottom_pad=5))

        self.pack_start(h)

        config.add_change_callback(self.handle_config_change)

    def handle_config_change(self, key, value):
        if key == prefs.PRESERVE_X_GB_FREE.key or key == prefs.PRESERVE_DISK_SPACE.key:
            self.update_free_space()

    def update_free_space(self):
        """Updates the free space text on the downloads tab.

        amount -- the total number of bytes free.
        """
        amount = get_available_bytes_for_movies()
        if config.get(prefs.PRESERVE_DISK_SPACE):
            available = config.get(prefs.PRESERVE_X_GB_FREE) * (1024 * 1024 * 1024)
            available = amount - available

            if available < 0:
                available = available * -1.0
                text = _(
                    "%(available)s below downloads space limit (%(amount)s free on disk)",
                    {"amount": displaytext.size(amount),
                     "available": displaytext.size(available)}
                )
            else:
                text = _(
                    "%(available)s free for downloads (%(amount)s free on disk)",
                    {"amount": displaytext.size(amount),
                     "available": displaytext.size(available)}
                )
        else:
            text = _("%(amount)s free on disk",
                     {"amount": displaytext.size(amount)})
        self._free_disk_label.set_text(text)

    def _on_pause_button_clicked(self, widget):
        self.emit('pause-all')

    def _on_resume_button_clicked(self, widget):
        self.emit('resume-all')

    def _on_cancel_button_clicked(self, widget):
        self.emit('cancel-all')

    def _on_settings_button_clicked(self, widget):
        self.emit('settings')

    def update_rates(self, down_bps, up_bps):
        text_up = text_down = ''
        if up_bps >= 10:
            text_up = _("%(rate)s uploading", {"rate": displaytext.download_rate(up_bps)})
        if down_bps >= 10:
            text_down = _("%(rate)s downloading", {"rate": displaytext.download_rate(down_bps)})

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

class FeedToolbar(widgetset.Background):
    """Toolbar that appears below the title in a feed.

    signals:
       show-settings (widget) -- The show settings button was pressed
       send-to-friend (widget) -- The "send to a friend" button was pressed
       auto-download-changed (widget, value) -- The auto-download setting was
           changed by the user
    """

    def __init__(self):
        widgetset.Background.__init__(self)
        self.create_signal('remove-channel')
        self.create_signal('show-settings')
        self.create_signal('send-to-a-friend')
        self.create_signal('auto-download-changed')
        hbox = widgetset.HBox(spacing=5)

        label = widgetset.Label(_('Auto Download'))
        label.set_size(widgetconst.SIZE_SMALL)
        label.set_color(style.TOOLBAR_GRAY)

        self.autdownload_menu = widgetset.OptionMenu(
                (_("all"), _("new"), _("off")))
        self.autdownload_menu.set_size(widgetconst.SIZE_SMALL)
        self.autdownload_menu.connect('changed', self._on_autodownload_changed)

        send_button = widgetset.Button(_("Send to a friend"), style='smooth')
        send_button.set_size(widgetconst.SIZE_SMALL)
        send_button.set_color(style.TOOLBAR_GRAY)
        send_button.connect('clicked', self._on_send_clicked)

        settings_button = widgetset.Button(_("Settings"), style='smooth')
        settings_button.set_size(widgetconst.SIZE_SMALL)
        settings_button.set_color(style.TOOLBAR_GRAY)
        settings_button.connect('clicked', self._on_settings_clicked)

        remove_button = widgetset.Button(_("Remove channel"), style='smooth')
        remove_button.set_size(widgetconst.SIZE_SMALL)
        remove_button.set_color(style.TOOLBAR_GRAY)
        remove_button.connect('clicked', self._on_remove_clicked)

        hbox.pack_start(widgetutil.align_middle(label, right_pad=2))
        hbox.pack_start(widgetutil.align_middle(self.autdownload_menu))
        hbox.pack_end(widgetutil.align_middle(remove_button))
        hbox.pack_end(widgetutil.align_middle(settings_button))
        hbox.pack_end(widgetutil.align_middle(send_button))
        self.add(widgetutil.pad(hbox, top=4, bottom=4, left=10, right=10))

    def set_autodownload_mode(self, autodownload_mode):
        if autodownload_mode == 'all':
            self.autdownload_menu.set_selected(0)
        elif autodownload_mode == 'new':
            self.autdownload_menu.set_selected(1)
        elif autodownload_mode == 'off':
            self.autdownload_menu.set_selected(2)

    def draw(self, context, layout):
        if not context.style.use_custom_titlebar_background:
            return
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color((0.90, 0.90, 0.90))
        gradient.set_end_color((0.79, 0.79, 0.79))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)

    def _on_settings_clicked(self, button):
        self.emit('show-settings')

    def _on_send_clicked(self, button):
        self.emit('send-to-a-friend')

    def _on_remove_clicked(self, button):
        self.emit('remove-channel')

    def _on_autodownload_changed(self, widget, option):
        self.emit('auto-download-changed', widget.options[option])

class SortBar(widgetset.Background):
    """Bar used to sort items.

    Signals:

    sort-changed (widget, sort_key, ascending) -- User changed the sort.
       sort_key will be one of 'name', 'date', 'size' or 'length'
    """

    def __init__(self):
        widgetset.Background.__init__(self)
        self.create_signal('sort-changed')
        self._hbox = widgetset.HBox()
        alignment = widgetset.Alignment(xalign=1.0, yalign=0.5)
        alignment.add(self._hbox)
        self.add(alignment)
        self._current_sort_key = 'date'
        self._ascending = False
        self._button_map = {}
        self._make_button(_('Name'), 'name')
        self._make_button(_('Date'), 'date')
        self._make_button(_('Size'), 'size')
        self._make_button(_('Length'), 'length')
        self._button_map['date'].set_sort_state(SortBarButton.SORT_DOWN)

    def _make_button(self, text, sort_key):
        button = SortBarButton(text)
        button.connect('clicked', self._on_button_clicked, sort_key)
        self._button_map[sort_key] = button
        self._hbox.pack_start(button)

    def _on_button_clicked(self, button, sort_key):
        if self._current_sort_key == sort_key:
            self._ascending = not self._ascending
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
        width = self._hbox.get_size_request()[0]
        return width, 30

    def draw(self, context, layout):
        gradient = widgetset.Gradient(0, 0, 0, context.height)
        gradient.set_start_color((0.49, 0.49, 0.49))
        gradient.set_end_color((0.42, 0.42, 0.42))
        context.rectangle(0, 0, context.width, context.height)
        context.gradient_fill(gradient)

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
        layout.set_font(0.82, bold=True)
        text_size = layout.textbox(self._text).get_size()
        return text_size[0] + 16, text_size[1] + 6

    def draw(self, context, layout):
        layout.set_font(0.82, bold=True)
        layout.set_text_color((1, 1, 1))
        textbox = layout.textbox(self._text)
        text_size = textbox.get_size()
        y = int((context.height - textbox.get_size()[1]) / 2)
        textbox.draw(context, y, 2, text_size[0], text_size[1])
        context.set_color((1, 1, 1))
        self._draw_trangle(context, text_size[0] + 6)
        if self.state == 'hover' or self.state == 'pressed':
            widgetutil.round_rect(context, 0.5, 0.5, context.width - 2,
                    context.height - 2, 4)
            context.set_line_width(1)
            context.stroke()

    def _draw_trangle(self, context, left):
        top = int((context.height - 8) / 2)
        if self._sort_state == self.SORT_DOWN:
            context.move_to(left, top)
            context.rel_line_to(8, 0)
            context.rel_line_to(-4, 8)
            context.rel_line_to(-4, -8)
            context.fill()
        elif self._sort_state == self.SORT_UP:
            context.move_to(left, top + 8)
            context.rel_line_to(8, 0)
            context.rel_line_to(-4, -8)
            context.rel_line_to(-4, 8)
            context.fill()

class ItemListBackground(widgetset.Background):
    """Plain white background behind the item lists.  """

    def draw(self, context, layout):
        if context.style.use_custom_style:
            context.set_color((1, 1, 1))
            context.rectangle(0, 0, context.width, context.height)
            context.fill()

class ItemContainerWidget(widgetset.VBox):
    """A Widget for displaying objects that contain items (feeds, playlists,
    folders, downloads tab, etc).

    Attributes:

       titlebar_vbox - VBox for the title bar
       content_vbox - VBox for content of the widget
       sort_bar -- SortBar for the widget
    """

    def __init__(self):
        widgetset.VBox.__init__(self)
        self.content_vbox = widgetset.VBox()
        self.titlebar_vbox = widgetset.VBox()
        self.sort_bar = SortBar()
        self.pack_start(self.titlebar_vbox)
        self.pack_start(self.sort_bar)
        background = ItemListBackground()
        background.add(self.content_vbox)
        scroller = widgetset.Scroller(False, True)
        scroller.add(background)
        self.pack_start(scroller, expand=True)
