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

"""Defines the import items dialog.
"""

import logging

from miro import app
from miro import prefs
from miro import util
from miro import messages

from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.fileobject import FilenameType
from miro.frontends.widgets import firsttimedialog
from miro.frontends.widgets import widgetutil
from miro.plat.utils import filename_to_unicode
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import threads

from miro.dialogs import BUTTON_CANCEL, BUTTON_IMPORT_FILES
from miro.frontends.widgets.dialogs import MainDialog, ask_for_directory
from miro.plat.resources import get_default_search_dir


class ImportMediaDialog(MainDialog):
    def __init__(self):
        MainDialog.__init__(self, _("Import Media"), "")
        self.vbox = None

    def build_import_section(self):
        vbox = widgetset.VBox()

        vbox = widgetset.VBox(spacing=5)

        vbox.pack_start(firsttimedialog._build_title(_("Finding Files")))

        lab = widgetset.Label(_(
                "What media would you like %(appname)s to import?",
                {'appname': app.config.get(prefs.SHORT_APP_NAME)}))
        lab.set_size_request(400, -1)
        lab.set_wrap(True)
        vbox.pack_start(widgetutil.align_left(lab))

        self.search_type_rbg = widgetset.RadioButtonGroup()

        self.restrict_rb = widgetset.RadioButton(
            _("Restrict to all my personal files."), self.search_type_rbg)
        self.restrict_rb.set_selected()
        vbox.pack_start(widgetutil.align_left(self.restrict_rb, left_pad=30))

        self.search_rb = widgetset.RadioButton(_("Search custom folders:"), self.search_type_rbg)
        vbox.pack_start(widgetutil.align_left(self.search_rb, left_pad=30))

        self.search_entry = widgetset.TextEntry()
        self.search_entry.set_text(get_default_search_dir())
        self.search_entry.set_width(25)
        self.search_entry.disable()

        self.change_button = widgetset.Button(_("Change"))
        hbox = widgetutil.build_hbox((self.search_entry, self.change_button))
        vbox.pack_start(widgetutil.align_left(hbox, left_pad=30))

        self.change_button.connect('clicked', self.handle_change_clicked)

        vbox.pack_start(widgetset.Label(" "), expand=True)

        search_button = widgetset.Button(_("Search for files"))
        search_button.connect('clicked', self.handle_search_clicked)

        vbox.pack_start(widgetutil.align_right(search_button))

        self.restrict_rb.connect('clicked', self.handle_radio_button_clicked)
        self.search_rb.connect('clicked', self.handle_radio_button_clicked)

        self.handle_radio_button_clicked(self.restrict_rb)
        self.change_button.disable()

        return vbox

    def build_search_section(self):
        vbox = widgetset.VBox(spacing=5)

        vbox.pack_start(firsttimedialog._build_title(_("Searching for media files")))

        self.progress_bar = widgetset.ProgressBar()
        vbox.pack_start(self.progress_bar)

        self.progress_label = widgetset.Label("")
        self.progress_label.set_size_request(400, -1)
        vbox.pack_start(widgetutil.align_left(self.progress_label))

        cancel_button = widgetset.Button(_("Cancel Search"))

        vbox.pack_start(widgetutil.align_right(cancel_button))

        vbox.pack_start(widgetset.Label(" "), expand=True)

        cancel_button.connect('clicked', self.handle_cancel_clicked)

        return vbox

    def handle_radio_button_clicked(self, widget):
        if widget is self.restrict_rb:
            self.search_entry.disable()
            self.change_button.disable()

        elif widget is self.search_rb:
            self.search_entry.enable()
            self.change_button.enable()

    def handle_search_clicked(self, widget):
        self.cancelled = False

        if self.search_type_rbg.get_selected() == self.restrict_rb:
            search_directory = get_default_search_dir()
        else:
            search_directory = FilenameType(self.search_directory)
        self.finder = util.gather_media_files(search_directory)
        self.progress_bar.start_pulsing()
        self.search_section.show()

        threads.call_on_ui_thread(self.make_progress)

    def handle_change_clicked(self, widget):
        dir_ = ask_for_directory(
            _("Choose directory to search for media files"),
            initial_directory=get_default_search_dir(),
            transient_for=self)
        if dir_:
            self.search_entry.set_text(filename_to_unicode(dir_))
            self.search_directory = dir_
        else:
            self.search_directory = get_default_search_dir()


    def handle_cancel_clicked(self, widget):
        self.end_file_search()
        self.cancelled = True
        self.search_section.hide()

    def end_file_search(self):
        self.progress_bar.stop_pulsing()
        self.progress_bar.set_progress(1.0)

    def make_progress(self):
        if self.cancelled:
            self.gathered_media_files = []
            self.finder = None
            self.progress_label.set_text("")
            return

        try:
            num_parsed, found = self.finder.next()
            self.gathered_media_files = found

            num_found = len(found)
            num_files = ngettext("parsed %(count)s file",
                                 "parsed %(count)s files",
                                 num_parsed,
                                 {"count": num_parsed})

            num_media_files = ngettext("found %(count)s media file",
                                       "found %(count)s media files",
                                       num_found,
                                       {"count": num_found})
            self.progress_label.set_text(u"%s - %s" % (num_files,
                                                  num_media_files))

            threads.call_on_ui_thread(self.make_progress)

        except StopIteration:
            self.end_file_search()
            self.finder = None

    def run_dialog(self):
        """Returns the gathered files or None.
        """
        try:
            self.vbox = widgetset.VBox()

            self.vbox.pack_start(self.build_import_section())

            self.search_section = widgetutil.HideableWidget(
                self.build_search_section())
            # do this so we reserve space for the search_section so the dialog
            # doesn't need to resize which doesn't work on osx.
            self.search_section.set_size_request(
                *self.search_section.child().get_size_request())
            self.search_section.hide()
            self.vbox.pack_start(self.search_section)

            self.set_extra_widget(self.vbox)

            self.add_button(BUTTON_IMPORT_FILES.text)
            self.add_button(BUTTON_CANCEL.text)

            ret = self.run()
            if ret == 0:
                return self.gathered_media_files
            return None

        except StandardError:
            logging.exception("importmediadialog threw exception.")


def run_dialog():
    """Returns files to add.
    """
    files = None
    try:
        imd = ImportMediaDialog()
        files = imd.run_dialog()
    finally:
        if imd:
            imd.destroy()

    return files
