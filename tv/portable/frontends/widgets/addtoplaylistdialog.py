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

"""miro.frontends.widgets.addtoplaylistdialog -- Holds dialog and processing
code for the "Add to Playlist" dialog.
"""

from miro.gtcache import gettext as _
from miro import searchengines

from miro.util import clamp_text
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.dialogs import MainDialog
from miro.dialogs import BUTTON_CANCEL, BUTTON_ADD

from miro import app

import logging

def run_dialog():
    """Creates and launches the Add to Playlist dialog.  This dialog
    waits for the user to press "Add" or "Cancel".

    In the case of "Add", returns a tuple of:

    * ("new", playlist_name)
    * ("existing", playlist id)

    In the case of "Cancel", returns None.
    """
    title = _('Add a Playlist')
    description = _('Add items to an existing playlist or a new one.')

    playlists = app.tab_list_manager.playlist_list.get_playlists()
    playlists = [pi for pi in playlists if not pi.is_folder]

    window = MainDialog(title, description)
    try:
        try:
            window.add_button(BUTTON_ADD.text)
            window.add_button(BUTTON_CANCEL.text)

            extra = widgetset.VBox()

            choice_table = widgetset.Table(columns=2, rows=2)
            choice_table.set_column_spacing(5)
            choice_table.set_row_spacing(5)
            rbg = widgetset.RadioButtonGroup()

            existing_rb = widgetset.RadioButton(_("Existing playlist:"), rbg)
            existing_option = widgetset.OptionMenu([clamp_text(pi.name) for pi in playlists])

            choice_table.pack(existing_rb, 0, 0)
            choice_table.pack(existing_option, 1, 0)

            new_rb = widgetset.RadioButton(_("New playlist:"), rbg)
            new_text = widgetset.TextEntry()
            new_text.set_activates_default(True)
            choice_table.pack(new_rb, 0, 1)
            choice_table.pack(new_text, 1, 1)

            # only the existing row is enabled
            choice_table.disable(row=1, column=1)

            def handle_clicked(widget):
                # this enables and disables the fields in the table
                # based on which radio button is selected
                if widget is existing_rb:
                    choice_table.enable(row=0, column=1)
                    choice_table.disable(row=1, column=1)
                else:
                    choice_table.disable(row=0, column=1)
                    choice_table.enable(row=1, column=1)
                if new_rb.get_selected():
                    new_text.focus()

            existing_rb.connect('clicked', handle_clicked)
            new_rb.connect('clicked', handle_clicked)

            extra.pack_start(widgetutil.align_top(choice_table, top_pad=6))

            window.set_extra_widget(extra)
            response = window.run()

            if response == 0:
                selected_option = rbg.get_selected()
                if selected_option is existing_rb and len(playlists) > 0:
                    return ("existing", playlists[existing_option.get_selected()])
                elif new_text.get_text():
                    return ("new", new_text.get_text())
        except StandardError:
            logging.exception("addtoplaylistdialog threw exception.")
    finally:
        window.destroy()
