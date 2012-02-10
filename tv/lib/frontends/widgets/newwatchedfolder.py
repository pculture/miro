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

from miro import app
from miro import prefs
from miro.gtcache import gettext_lazy as _
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.dialogs import MainDialog, ask_for_directory
from miro.dialogs import BUTTON_CANCEL, BUTTON_ADD_FOLDER

from miro.plat.frontends.widgets import widgetset
from miro.plat import resources
from miro.plat.utils import filename_to_unicode, PlatformFilenameType

class NewWatchedFolderDialog(MainDialog):
    TITLE = _("Add Watched Folder")
    DESCRIPTION = _("%(appname)s can watch a folder on your computer and "
                    "show those media files in your library.",
                    {"appname": app.config.get(prefs.SHORT_APP_NAME)})
    def __init__(self, path, error=None):
        MainDialog.__init__(self, self.TITLE, self.DESCRIPTION)
        self.path = path # PlatformFilenameType
        self.vbox = None
        self.previous_error = error

    def run_dialog(self):
        """
        Returns (directory, show-in-sidebar) or None
        """
        try:
            extra = widgetset.VBox(spacing=10)
            if self.previous_error:
                extra.pack_start(widgetset.Label(self.previous_error))

            self.folder_entry = widgetset.TextEntry()
            self.folder_entry.set_activates_default(True)
            self.folder_entry.set_text(filename_to_unicode(self.path))
            self.folder_entry.set_size_request(300, -1)

            choose_button = widgetset.Button(_("Choose..."))
            choose_button.connect('clicked', self.handle_choose)

            h = widgetset.HBox(spacing=5)
            h.pack_start(widgetutil.align_middle(
                widgetset.Label(_("Directory:"))))
            h.pack_start(widgetutil.align_middle(self.folder_entry))
            h.pack_start(widgetutil.align_middle(choose_button))

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
                # 17407 band-aid - don't init with PlatformFilenameType since
                # str use ascii codec
                dir = self.folder_entry.get_text()
                if PlatformFilenameType == str:
                    dir = dir.encode('utf-8')
                return (dir, self.visible_checkbox.get_checked())

            return None

        except StandardError:
            logging.exception("newwatchedfolder threw exception.")

    def handle_choose(self, widget):
        # 17407 band-aid - don't init with PlatformFilenameType since
        # str use ascii codec
        path = self.folder_entry.get_text()
        if PlatformFilenameType == str:
            path = path.encode('utf-8')
        if not os.path.exists(path):
            path = resources.get_default_search_dir()

        newpath = ask_for_directory(_("Choose Watched Folder Directory"), path)

        if newpath:
            self.folder_entry.set_text(newpath)

def run_dialog():
    """Returns (path, showinsidebar) or None.
    """
    NOT_FOUND = _("That directory could not be found. "
                  "Please check the path and try again.")
    NO_ACCESS = _("That directory could not be accessed. "
                  "Please check the permissions and try again.")
    path = resources.get_default_search_dir()
    error = None

    while 1:
        ret = None
        nwfd = None
        try:
            nwfd = NewWatchedFolderDialog(path, error)
            ret = nwfd.run_dialog()
        finally:
            if nwfd:
                nwfd.destroy()

        if ret is None:
            return None

        path, showinsidebar = ret
        if not os.path.exists(path):
            error = NOT_FOUND
        elif not os.access(path, os.R_OK):
            error = NO_ACCESS
        else:
            return (path, showinsidebar)
