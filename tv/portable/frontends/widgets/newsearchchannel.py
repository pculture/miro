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

"""miro.frontends.widgets.newsearchchannel -- Holds dialog and processing
code for the New Search Channel dialog.
"""

from miro.gtcache import gettext as _
from miro import searchengines

from miro.util import clampText
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.dialogs import BUTTON_CANCEL, BUTTON_CREATE_CHANNEL

from miro import app

def run_dialog():
    """Creates and launches the New Search Channel dialog.  This dialog waits
    for the user to press "Create Channel" or "Cancel".

    In the case of "Create Channel", returns a tuple of:

    * ("channel", ChannelInfo, search_term str)
    * ("search_engine", SearchEngineInfo, search_term str)
    * ("url", url str, search_term str)

    In the case of "Cancel", returns None.
    """
    title = _('New Search Channel')
    description = _('A search channel contains items that match a search term.')

    channels = app.tab_list_manager.feed_list.get_feeds()
    channels = [ci for ci in channels if not ci.is_folder]

    window = widgetset.Dialog(title, description)
    try:
        try:
            window.add_button(BUTTON_CREATE_CHANNEL.text)
            window.add_button(BUTTON_CANCEL.text)

            extra = widgetset.VBox()

            hb1 = widgetset.HBox()
            hb1.pack_start(widgetset.Label(_('Search for:')), padding=5)
            searchterm = widgetset.TextEntry()
            hb1.pack_start(searchterm, expand=True)
            extra.pack_start(hb1)

            hb2 = widgetset.HBox()
            hb2.pack_start(widgetutil.align_top(widgetset.Label(_('In this:')), top_pad=3), padding=5)

            choice_table = widgetset.Table(columns=2, rows=3)
            choice_table.set_column_spacing(5)
            choice_table.set_row_spacing(5)
            rbg = widgetset.RadioButtonGroup()

            channel_rb = widgetset.RadioButton("Channel:", rbg)
            channel_option = widgetset.OptionMenu([clampText(ci.name) for ci in channels])
            choice_table.set_cell(channel_rb, 0, 0)
            choice_table.set_cell(channel_option, 1, 0)

            search_engine_rb = widgetset.RadioButton("Search engine:", rbg)
            search_engines = searchengines.get_search_engines()
            search_engine_option = widgetset.OptionMenu([se.title for se in search_engines])
            choice_table.set_cell(search_engine_rb, 0, 1)
            choice_table.set_cell(search_engine_option, 1, 1)

            url_rb = widgetset.RadioButton("URL:", rbg)
            url_text = widgetset.TextEntry()
            choice_table.set_cell(url_rb, 0, 2)
            choice_table.set_cell(url_text, 1, 2)

            hb2.pack_start(choice_table, expand=True)

            # only the channel row is enabled
            choice_table.disable_widget(row=1, column=1)
            choice_table.disable_widget(row=2, column=1)

            def handle_clicked(widget):
                # this enables and disables the fields in the table
                # based on which radio button is selected
                if widget is channel_rb:
                    choice_table.enable_widget(row=0, column=1)
                    choice_table.disable_widget(row=1, column=1)
                    choice_table.disable_widget(row=2, column=1)
                elif widget is search_engine_rb:
                    choice_table.disable_widget(row=0, column=1)
                    choice_table.enable_widget(row=1, column=1)
                    choice_table.disable_widget(row=2, column=1)
                else:
                    choice_table.disable_widget(row=0, column=1)
                    choice_table.disable_widget(row=1, column=1)
                    choice_table.enable_widget(row=2, column=1)

            channel_rb.connect('clicked', handle_clicked)
            search_engine_rb.connect('clicked', handle_clicked)
            url_rb.connect('clicked', handle_clicked)

            extra.pack_start(widgetutil.align_top(hb2, top_pad=6))

            window.set_extra_widget(extra)
            response = window.run()

            if response == 0 and searchterm.get_text():
                term = searchterm.get_text()
                selected_option = rbg.get_selected()
                if selected_option is channel_rb:
                    return ("channel",
                            channels[channel_option.get_selected()],
                            term)
                elif selected_option is search_engine_rb:
                    return ("search_engine",
                            search_engines[search_engine_option.get_selected()],
                            term)
                else:
                    return ("url",
                            url_text.get_text(),
                            term)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("newsearchchannel threw exception.")
    finally:
        window.destroy()
