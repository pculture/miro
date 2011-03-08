# Miro - an RSS based video player application
# Copyright (C) 2011
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

"""miro.frontends.widgets.newwatchedfolder -- Holds dialog and
processing code for adding a new watched folder
"""

import logging
import os

from miro.gtcache import gettext as _
from miro.frontends.widgets.dialogs import MainDialog, ask_for_directory
from miro.dialogs import BUTTON_CANCEL, BUTTON_ADD_FOLDER

from miro.plat.frontends.widgets import widgetset
from miro.plat import resources


class NewWatchedFolderDialog(MainDialog):
    def __init__(self, title, desc, path):
        MainDialog.__init__(self, title, desc)
        self.path = path
        self.vbox = None

    def run_dialog(self):
        """
        Returns (directory, show-in-sidebar) or None
        """
        try:
            extra = widgetset.VBox()

            self.folder_entry = widgetset.TextEntry()
            self.folder_entry.set_activates_default(True)
            self.folder_entry.set_text(self.path)
            self.folder_entry.set_size_request(300, -1)

            choose_button = widgetset.Button(_("Choose..."))
            choose_button.connect('clicked', self.handle_choose)

            h = widgetset.HBox(spacing=5)
            h.pack_start(widgetset.Label(_("Directory:")))
            h.pack_start(self.folder_entry)
            h.pack_start(choose_button)

            extra.pack_start(h)

            self.visible_checkbox = widgetset.Checkbox(
                _("Show in my sidebar as a podcast"))
            self.visible_checkbox.set_checked(True)
            extra.pack_start(self.visible_checkbox)

            self.vbox = extra

            self.set_extra_widget(extra)
            self.add_button(BUTTON_ADD_FOLDER.text)
            self.add_button(BUTTON_CANCEL.text)

            ret = self.run()
            if ret == 0:
                return (self.folder_entry.get_text(),
                        self.visible_checkbox.get_checked())

            return None

        except StandardError:
            logging.exception("newwatchedfolder threw exception.")

    def handle_choose(self, widget):
        path = self.folder_entry.get_text()
        if not os.path.exists(path):
            # FIXME - do we have to unicodify this value?
            path = resources.get_default_search_dir()

        newpath = ask_for_directory(
            _("Choose Watched Folder Directory"), path, self)

        if newpath:
            self.folder_entry.set_text(newpath)


def run_dialog():
    """Returns (path, showinsidebar) or None.
    """
    title = _("Add Watched Folder")
    desc = _(
        "Miro can watch a folder on your computer and show "
        "those media files in your library.")
    path = resources.get_default_search_dir()

    while 1:
        ret = None
        try:
            nwfd = NewWatchedFolderDialog(title, desc, path)
            ret = nwfd.run_dialog()
        finally:
            nwfd.destroy()

        if ret == None:
            return None

        path, showinsidebar = ret
        if not os.path.exists(path):
            desc = _(
                "Miro can watch a folder on your computer and show "
                "those media files in your library.\n\n"
                "That path does not exist.")
            continue

        return (path, showinsidebar)
