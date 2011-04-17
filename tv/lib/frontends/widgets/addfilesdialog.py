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

"""Defines the add files dialog.
"""

from miro import app
from miro import util
from miro import messages
from miro import filetypes

from miro.gtcache import gettext as _
from miro.gtcache import ngettext
# from miro.fileobject import FilenameType
from miro.frontends.widgets import widgetutil
# from miro.plat.utils import filename_to_unicode
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import threads

from miro.dialogs import BUTTON_CANCEL, BUTTON_IMPORT_FILES
from miro.frontends.widgets.dialogs import (
    ask_for_directory, ask_for_open_pathname)
from miro.plat import resources


class AddFilesDialog(widgetset.DialogWindow):
    def __init__(self):
        try:
            rect = app.widgetapp.window.get_frame()
            x, y = rect.x, rect.y
        except AttributeError:
            x, y = 100, 100

        # note: we make this 600 x 230 so that on OSX the ask_for_directory
        # sheet doesn't look weird by sticking out the sides.
        widgetset.DialogWindow.__init__(
            self, _("Add Files and Folders"),
            widgetset.Rect(x + 100, y + 100, 600, 230))

        self.gathered_media_files = []
        self.searching = False

        self._page_box = widgetset.VBox()
        self._pages = self.build_pages()
        self._page_index = -1

        self.set_content_widget(widgetutil.pad(self._page_box, 20, 20, 20, 20))

    def build_pages(self):
        return [
            self.build_choice_page(),
            self.build_search_page(),
            self.build_results_page(),
            ]

    def run(self):
        self._switch_page(0)
        self.show()

    def destroy_dialog(self):
        if self.gathered_media_files:
            messages.AddFiles(self.gathered_media_files).send_to_backend()
        self.destroy()

    def _switch_page(self, i, rebuild=False):
        if i == self._page_index:
            return
        if i < 0 or i > len(self._pages)-1:
            return

        if self._page_index != -1:
            self._page_box.remove(self._pages[self._page_index])
        if rebuild:
            self._pages = self.build_pages()
        self._page_box.pack_start(self._pages[i], expand=True)
        self._page_index = i

    def this_page(self, rebuild=False):
        self._switch_page(self._page_index, rebuild)

    def next_page(self, rebuild=False):
        self._switch_page(self._page_index + 1, rebuild)

    def prev_page(self):
        self._switch_page(self._page_index - 1)

    def _centered_label(self, text):
        return widgetutil.align_middle(
            widgetutil.align_right(
                widgetset.Label(text)))

    def on_cancel(self, widget):
        self.end_file_search()
        self.gathered_media_files = []
        self.destroy_dialog()

    def _force_space_label(self):
        lab = widgetset.Label(" ")
        lab.set_size_request(560, -1)
        return lab

    def build_choice_page(self):
        vbox = widgetset.VBox(spacing=5)

        choose_files_link = widgetutil.LinkButton(
            _("Choose files to add"))
        choose_files_link.connect('clicked', self.on_choose_files)
        vbox.pack_start(widgetutil.align_center(choose_files_link))

        search_files_link = widgetutil.LinkButton(
            _("Search all my files for music and video"))
        search_files_link.connect('clicked', self.on_search_my_files)
        vbox.pack_start(widgetutil.align_center(search_files_link))

        select_folder_button = widgetutil.LinkButton(
            _("Select a specific folder for search"))
        select_folder_button.connect('clicked', self.on_select_folder)
        vbox.pack_start(widgetutil.align_center(select_folder_button))

        vbox.pack_start(self._force_space_label(), expand=True)

        cancel_button = widgetset.Button(BUTTON_CANCEL.text)
        cancel_button.connect('clicked', self.on_cancel)

        vbox.pack_start(widgetutil.align_right(cancel_button))
        return vbox

    def on_choose_files(self, widget):
        # opens dialog allowing you to choose files and folders
        audio_extensions = [mem.replace(".", "")
                            for mem in filetypes.AUDIO_EXTENSIONS]
        video_extensions = [mem.replace(".", "")
                            for mem in filetypes.VIDEO_EXTENSIONS]
        files_ = ask_for_open_pathname(
            _("Choose files to import"),
            filters=[
                (_("Video Files"), video_extensions),
                (_("Audio Files"), audio_extensions)
                ],
            transient_for=self,
            select_multiple=True)

        self.gathered_media_files = files_
        self.destroy_dialog()

    def on_search_my_files(self, widget):
        """Searches the user's media directory.
        """
        self.next_page()
        self.start_file_search(resources.get_default_search_dir())

    def on_select_folder(self, widget):
        """Opens a dialog allowing you to choose the folder to
        search for files in.
        """
        dir_ = ask_for_directory(
            _("Choose directory to search for media files"),
            initial_directory=resources.get_default_search_dir(),
            transient_for=self)

        if dir_:
            self.next_page()
            self.start_file_search(dir_)

    def build_search_page(self):
        vbox = widgetset.VBox(spacing=5)

        self.progress_bar = widgetset.ProgressBar()
        self.progress_bar.set_size_request(400, -1)
        vbox.pack_start(widgetutil.align_center(self.progress_bar,
                                                top_pad=50))

        self.progress_label = widgetset.Label("")
        vbox.pack_start(
            widgetutil.align_top(
                widgetutil.align_center(self.progress_label),
                top_pad=10))

        vbox.pack_start(self._force_space_label(), expand=True)

        cancel_button = widgetset.Button(_("Cancel Search"))
        cancel_button.connect('clicked', self.on_cancel)

        vbox.pack_start(widgetutil.align_right(cancel_button))

        return vbox

    def build_results_page(self):
        # FIXME - this is built just like the search_page.  it'd be
        # better to just change the buttons on the bottom of the
        # search page.
        vbox = widgetset.VBox(spacing=5)

        progress_bar = widgetset.ProgressBar()
        progress_bar.set_size_request(400, -1)
        vbox.pack_start(widgetutil.align_center(progress_bar,
                                                top_pad=50))

        progress_bar.stop_pulsing()
        progress_bar.set_progress(1.0)

        self.results_label = widgetset.Label("")
        vbox.pack_start(
            widgetutil.align_top(
                widgetutil.align_center(self.results_label),
                top_pad=10))

        vbox.pack_start(self._force_space_label(), expand=True)

        cancel_button = widgetset.Button(BUTTON_CANCEL.text)
        cancel_button.connect('clicked', self.on_cancel)

        import_button = widgetset.Button(BUTTON_IMPORT_FILES.text)
        import_button.connect('clicked', lambda x: self.destroy_dialog())

        vbox.pack_start(widgetutil.align_right(
                widgetutil.build_hbox((cancel_button, import_button))))

        return vbox

    def start_file_search(self, search_directory):
        self.searching = True

        self.finder = util.gather_media_files(search_directory)
        self.progress_bar.start_pulsing()

        threads.call_on_ui_thread(self.make_progress)

    def end_file_search(self):
        if self.searching:
            self.progress_bar.stop_pulsing()
            self.progress_bar.set_progress(1.0)
        self.searching = False

    def make_progress(self):
        if not self.searching:
            self.finder = None
            self.progress_label.set_text("")
            return

        try:
            num_parsed, found = self.finder.next()
            self.gathered_media_files = found
            self.parsed_files = num_parsed

            num_found = len(found)

            self.progress_label.set_text(
                self._build_progress_label(num_found, num_parsed))

            threads.call_on_ui_thread(self.make_progress)

        except StopIteration:
            self.end_file_search()
            self.finder = None

            num_found = len(self.gathered_media_files)
            num_parsed = self.parsed_files

            self.results_label.set_text(
                self._build_progress_label(num_found, num_parsed))

            self.next_page()

    def _build_progress_label(self, num_found, num_parsed):
            num_files = ngettext(
                "Searched %(count)s file",
                "Searched %(count)s files",
                num_parsed,
                {"count": num_parsed})

            num_media_files = ngettext(
                "found %(count)s media file",
                "found %(count)s media files",
                num_found,
                {"count": num_found})

            return u"%s - %s" % (num_files, num_media_files)
