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

"""miro.frontends.widgets.newsearchfeed -- Holds dialog and processing
code for the New Search Podcast dialog.
"""

from miro.gtcache import gettext_lazy as _
from miro import searchengines

from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.dialogs import MainDialog
from miro.dialogs import BUTTON_CANCEL, BUTTON_CREATE_FEED
from miro import util

from miro import app

import logging

def run_dialog():
    """Creates and launches the New Search Podcast dialog.  This
    dialog waits for the user to press "Create Podcast" or "Cancel".

    In the case of "Create Podcast", returns a tuple of:

    * ("feed", ChannelInfo, search_term str)
    * ("search_engine", SearchEngineInfo, search_term str)
    * ("url", url str, search_term str)

    In the case of "Cancel", returns None.
    """
    title = _('New Search Podcast')
    description = _('A search podcast contains items that match a search term.')
    return NewSearchFeedDialogRunner(title, description).run_dialog()

class NewSearchFeedDialogRunner(object):
    """Helper class that runs the new search feed dialog.

    This class basically splits up the work needed to create the dialog.
    """

    def __init__(self, title, description):
        self.window = MainDialog(title, description)
        self.get_channel_info()
        self.get_search_engine_info()
        self.build_widgets()
        self.set_initial_search_text()
        self.set_initial_source()

    def get_channel_info(self):
        self.channels = [ci for ci in app.tabs['feed'].get_feeds()
                if not (ci.is_folder or ci.is_directory_feed)]
        self.channels.sort(key=lambda x: util.name_sort_key(x.name))

    def get_search_engine_info(self):
        self.search_engines = searchengines.get_search_engines()

    def build_widgets(self):
        self.window.add_button(BUTTON_CREATE_FEED.text)
        self.window.add_button(BUTTON_CANCEL.text)

        extra = widgetset.VBox()

        hb1 = widgetset.HBox()
        hb1.pack_start(widgetset.Label(_('Search for:')), padding=5)
        self.searchterm = widgetset.TextEntry()
        self.searchterm.set_activates_default(True)
        hb1.pack_start(self.searchterm, expand=True)
        extra.pack_start(hb1)

        hb2 = widgetset.HBox()
        hb2.pack_start(widgetutil.align_top(
                widgetset.Label(_('In this:')), top_pad=3), padding=5)

        self.choice_table = widgetset.Table(columns=2, rows=3)
        self.choice_table.set_column_spacing(5)
        self.choice_table.set_row_spacing(5)
        self.rbg = widgetset.RadioButtonGroup()

        self.channel_rb = widgetset.RadioButton(_("Podcast:"), self.rbg)
        self.channel_option = widgetset.OptionMenu(
            [ci.name + u" - " + ci.url for ci in self.channels])
        self.channel_option.set_size_request(250, -1)
        self.choice_table.pack(self.channel_rb, 0, 0)
        self.choice_table.pack(self.channel_option, 1, 0)

        self.search_engine_rb = widgetset.RadioButton(_("Search engine:"),
                self.rbg)
        self.search_engine_option = widgetset.OptionMenu(
            [se.title for se in self.search_engines])
        self.choice_table.pack(self.search_engine_rb, 0, 1)
        self.choice_table.pack(self.search_engine_option, 1, 1)

        url_rb = widgetset.RadioButton(_("URL:"), self.rbg)
        self.url_text = widgetset.TextEntry()
        self.choice_table.pack(url_rb, 0, 2)
        self.choice_table.pack(self.url_text, 1, 2)

        hb2.pack_start(self.choice_table, expand=True)

        # by default only the channel row is enabled
        self.enable_choice_table_row(0)

        def handle_clicked(widget):
            # this enables and disables the fields in the table
            # based on which radio button is selected
            if widget is self.channel_rb:
                self.enable_choice_table_row(0)
            elif widget is self.search_engine_rb:
                self.enable_choice_table_row(1)
            else:
                self.enable_choice_table_row(2)

        self.channel_rb.connect('clicked', handle_clicked)
        self.search_engine_rb.connect('clicked', handle_clicked)
        url_rb.connect('clicked', handle_clicked)

        extra.pack_start(widgetutil.align_top(hb2, top_pad=6))

        self.window.set_extra_widget(extra)

    def enable_choice_table_row(self, row_index):
        for i in range(3):
            if i == row_index:
                self.choice_table.enable(row=i, column=1)
            else:
                self.choice_table.disable(row=i, column=1)

    def run_dialog(self):
        response = self.window.run()

        if response == 0 and self.searchterm.get_text():
            term = self.searchterm.get_text()
            selected_option = self.rbg.get_selected()
            if selected_option is self.channel_rb:
                return ("feed",
                        self.channels[self.channel_option.get_selected()],
                        term)
            elif selected_option is self.search_engine_rb:
                index = self.search_engine_option.get_selected()
                return ("search_engine",
                        self.search_engines[index],
                        term)
            else:
                return ("url",
                        self.url_text.get_text(),
                        term)

        return None

    def set_initial_search_text(self):
        """Setup the initial search text """
        initial = app.item_list_controller_manager.get_saved_search_text()
        if initial:
            self.searchterm.set_text(initial)

    def set_initial_source(self):
        source = app.item_list_controller_manager.get_saved_search_source()
        if source is not None:
            typ, id_ = source
            if typ == 'channel':
                self.channel_rb.set_selected()
                for i, info in enumerate(self.channels):
                    if info.id == id_:
                        self.channel_option.set_selected(i)
                        break
                else:
                    # bz:17818
                    # Watched folders are not listed in this dialog, but is
                    # in the feed/channel category.  So we could come here
                    # with a watched folder selected, and fall into else
                    # path.  There used to be a soft failure here, now
                    # I think it is okay if we just print a debug message.
                    logging.debug(("didn't find channel with id: %r "
                                   "(possibly watched folder selected)"), id_)
            elif typ == 'search':
                self.search_engine_rb.set_selected()
                self.enable_choice_table_row(1)
                for i, info in enumerate(self.search_engines):
                    if info.name == id_:
                        self.search_engine_option.set_selected(i)
                        break
                else:
                    app.widgetapp.handle_soft_failure("New search feed dialog",
                            "didn't find search engine with id: %r" % id_,
                            with_exception=False)
            else:
                app.widgetapp.handle_soft_failure("New search feed dialog",
                        "unknown source type %r" % typ, with_exception=False)
