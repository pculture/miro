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

from miro import displaytext
from miro import searchengines
from miro.gtcache import gettext as _
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import separator
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset

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
        self.search_button.set_size(0.85)
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
        renderer = style.ItemRenderer()
        self.add_column('item', renderer, renderer.MIN_WIDTH, data=0,
                show_details=1, throbber_counter=2)
        self.set_show_headers(False)
        self.allow_multiple_select(True)
        self.set_background_color(widgetutil.WHITE)

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
        hbox.pack_start(self.info_label)
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

class DownloadButtonToolbar(widgetset.HBox):
    """Widget that shows the pause/resume/... buttons for the downloads

    signals:

       pause-all -- All downloads should be paused
       resume-all -- All downloads should be resumed
       cancel-all -- All downloads should be canceled
    """

    def __init__(self):
        widgetset.HBox.__init__(self, spacing=10)

        self.create_signal('pause-all')
        self.create_signal('resume-all')
        self.create_signal('cancel-all')

        pause_button = widgetset.Button(_('Pause All'), style='smooth')
        pause_button.set_size(0.85)
        pause_button.set_color(style.TOOLBAR_GRAY)
        pause_button.connect('clicked', self._on_pause_button_clicked)
        self.pack_start(widgetutil.align_right(pause_button, top_pad=5,
            bottom_pad=5), expand=True)

        resume_button = widgetset.Button(_('Resume All'), style='smooth')
        resume_button.set_size(0.85)
        resume_button.set_color(style.TOOLBAR_GRAY)
        resume_button.connect('clicked', self._on_resume_button_clicked)
        self.pack_start(widgetutil.align_middle(resume_button, top_pad=5,
            bottom_pad=5))

        cancel_button = widgetset.Button(_('Cancel All'), style='smooth')
        cancel_button.set_size(0.85)
        cancel_button.set_color(style.TOOLBAR_GRAY)
        cancel_button.connect('clicked', self._on_cancel_button_clicked)
        self.pack_start(widgetutil.align_middle(cancel_button, top_pad=5,
            bottom_pad=5))

    def _on_pause_button_clicked(self, widget):
        self.emit('pause-all')

    def _on_resume_button_clicked(self, widget):
        self.emit('resume-all')

    def _on_cancel_button_clicked(self, widget):
        self.emit('cancel-all')

class DownloadLabelToolbar(widgetset.HBox):
    """Widget that shows the info.
    """

    def __init__(self):
        widgetset.HBox.__init__(self, spacing=10)

        self._free_disk_label = widgetset.Label("")
        self._free_disk_label.set_bold(True)

        self.pack_start(widgetutil.align_left(self._free_disk_label,
            top_pad=5, left_pad=10), expand=True)

        uploading_label = widgetset.Label("")
        uploading_label.set_bold(True)
        self._uploading_label = uploading_label

        self.pack_start(widgetutil.pad(uploading_label, top=5))

        downloading_label = widgetset.Label("")
        downloading_label.set_bold(True)
        self._downloading_label = downloading_label

        self.pack_start(widgetutil.pad(downloading_label, top=5, right=10))

    def update_free_space(self, bytes):
        text = _("%(amount)s free on disk", {"amount": displaytext.size(bytes)})
        self._free_disk_label.set_text(text)

    def update_uploading_rate(self, bps):
        if bps >= 10:
            text = _("%(rate)s uploading", {"rate": displaytext.download_rate(bps)})
        else:
            text = ''
        self._uploading_label.set_text(text)

    def update_downloading_rate(self, bps):
        if bps >= 10:
            text = _("%(rate)s downloading", {"rate": displaytext.download_rate(bps)})
        else:
            text = ''
        self._downloading_label.set_text(text)

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
        self.create_signal('show-settings')
        self.create_signal('send-to-a-friend')
        self.create_signal('auto-download-changed')
        hbox = widgetset.HBox(spacing=5)

        label = widgetset.Label(_('Auto Download'))
        label.set_size(0.85)
        label.set_color(style.TOOLBAR_GRAY)

        self.autdownload_menu = widgetset.OptionMenu(
                (_("all"), _("new"), _("off")))
        self.autdownload_menu.set_size(0.85)
        self.autdownload_menu.connect('changed', self._on_autodownload_changed)
        
        send_button = widgetset.Button(_("Send to a friend"), style='smooth')
        send_button.set_size(widgetset.FEEDVIEW_BUTTONS_TEXT_SIZE)
        send_button.set_color(style.TOOLBAR_GRAY)
        send_button.connect('clicked', self._on_send_clicked)

        settings_button = widgetset.Button(_("Settings"), style='smooth')
        settings_button.set_size(widgetset.FEEDVIEW_BUTTONS_TEXT_SIZE)
        settings_button.set_color(style.TOOLBAR_GRAY)
        settings_button.connect('clicked', self._on_settings_clicked)

        hbox.pack_start(widgetutil.align_middle(label, right_pad=2))
        hbox.pack_start(widgetutil.align_middle(self.autdownload_menu))
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

    def _on_autodownload_changed(self, widget, option):
        self.emit('auto-download-changed', widget.options[option])

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
    """

    def __init__(self):
        widgetset.VBox.__init__(self)
        self.content_vbox = widgetset.VBox()
        self.titlebar_vbox = widgetset.VBox()
        self.pack_start(self.titlebar_vbox)
        self.pack_start(separator.HThinSeparator((0.7, 0.7, 0.7)))
        background = ItemListBackground()
        background.add(self.content_vbox)
        scroller = widgetset.Scroller(False, True)
        scroller.add(background)
        self.pack_start(scroller, expand=True)
