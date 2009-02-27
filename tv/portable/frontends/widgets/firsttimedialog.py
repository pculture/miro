# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""Defines the "first time dialog" and all behavior."""

from miro import prefs
from miro import util
from miro import messages
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import threads
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import prefpanel
from miro.frontends.widgets import dialogs
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.plat.utils import filenameToUnicode
import os

def _get_user_media_directory():
    """Returns the user's media directory.
    """
    return os.path.expanduser("~/")

def _build_title(text):
    """Builds and returns a title widget for the panes in the
    First Time Startup dialog.
    """
    lab = widgetset.Label(text)
    lab.set_bold(True)
    lab.set_wrap(True)
    return widgetutil.align_left(lab, bottom_pad=10)

class FirstTimeDialog(widgetset.Window):
    def __init__(self, done_firsttime_callback):
        widgetset.Window.__init__(self, _("Miro First Time Setup"), widgetset.Rect(100, 100, 475, 500))

        # the directory panel 3 searches for files in
        self.search_directory = None

        self.finder = None

        self.cancelled = False

        self.gathered_media_files = None

        self._done_firsttime_callback = done_firsttime_callback

        self._page_box = widgetset.VBox()
        self._pages = [self.build_first_page(),
                self.build_second_page(),
                self.build_search_page()]
        self._page_index = -1

        self.set_content_widget(widgetutil.align_center(self._page_box,
                top_pad=20, bottom_pad=20, left_pad=20, right_pad=20))

        self.on_close_handler = self.connect('will-close', self.on_close)

    def run(self):
        self._switch_page(0)
        self.show()

    def on_close(self, widget=None):
        if self.gathered_media_files:
            messages.AddFiles(self.gathered_media_files).send_to_backend()

        self.disconnect(self.on_close_handler)
        self.on_close_handler = None
        self.close()
        self._done_firsttime_callback()

    def _switch_page(self, i):
        if i == self._page_index:
            return
        if i < 0 or i > len(self._pages)-1:
            return

        if self._page_index != -1:
            self._page_box.remove(self._pages[self._page_index])
        self._page_box.pack_start(self._pages[i], expand=True)
        self._page_index = i

    def next_page(self):
        self._switch_page(self._page_index + 1)

    def prev_page(self):
        self._switch_page(self._page_index - 1)

    def build_first_page(self):
        v = widgetset.VBox(spacing=5)

        v.pack_start(_build_title(_("Welcome to the Miro First Time Setup")))

        lab = widgetset.Label(_(
            "The next few screens will help you set up Miro so that it works best "
            "for you.\n"
            "\n"
            "We recommend that you have Miro launch when your computer starts "
            "up.  This way, downloads in progress can finish downloading and new "
            "media files can be downloaded in the background, ready when you "
            "want to watch."
            ))
        lab.set_wrap(True)
        lab.set_size_request(400, -1)
        v.pack_start(widgetutil.align_left(lab))

        lab = widgetset.Label(_("Would you like to run Miro on startup?"))
        lab.set_bold(True)
        v.pack_start(widgetutil.align_left(lab))

        rbg = widgetset.RadioButtonGroup()
        yes_rb = widgetset.RadioButton(_("Yes"), rbg)
        no_rb = widgetset.RadioButton(_("No"), rbg)

        prefpanel.attach_radio([(yes_rb, True), (no_rb, False)], prefs.RUN_AT_STARTUP)
        v.pack_start(widgetutil.align_left(yes_rb))
        v.pack_start(widgetutil.align_left(no_rb))

        v.pack_start(widgetset.Label(" "), expand=True)

        next = widgetset.Button(_("Next >"))
        next.connect('clicked', lambda x: self.next_page())

        v.pack_start(widgetutil.align_right(next))

        return v

    def build_second_page(self):
        v = widgetset.VBox(spacing=5)

        v.pack_start(_build_title(_("Completing the Miro First Time Setup")))

        lab = widgetset.Label(_(
            "Miro can find all the media files on your computer to help you "
            "organize your collection.\n"
            "\n"
            "Would you like Miro to look for media files on your computer?"
            ))
        lab.set_size_request(400, -1)
        lab.set_wrap(True)
        v.pack_start(widgetutil.align_left(lab))

        rbg = widgetset.RadioButtonGroup()
        no_rb = widgetset.RadioButton(_("No"), rbg)
        yes_rb = widgetset.RadioButton(_("Yes"), rbg)
        v.pack_start(widgetutil.align_left(no_rb))
        v.pack_start(widgetutil.align_left(yes_rb, bottom_pad=5))

        group_box = widgetset.VBox(spacing=5)

        rbg2 = widgetset.RadioButtonGroup()
        restrict_rb = widgetset.RadioButton(_("Restrict to all my personal files."), rbg2)
        search_rb = widgetset.RadioButton(_("Search custom folders:"), rbg2)
        group_box.pack_start(widgetutil.align_left(restrict_rb, left_pad=30))
        group_box.pack_start(widgetutil.align_left(search_rb, left_pad=30))

        search_entry = widgetset.TextEntry()
        search_entry.set_width(20)
        change_button = widgetset.Button(_("Change"))
        h = widgetutil.build_hbox((search_entry, change_button))
        group_box.pack_start(widgetutil.align_left(h, left_pad=30))

        def handle_change_clicked(widget):
            dir_ = dialogs.ask_for_directory(_("Choose directory to search for media files"),
                    initial_directory=_get_user_media_directory(),
                    transient_for=self)
            if dir_:
                search_entry.set_text(filenameToUnicode(dir_))
                self.search_directory = dir_
            else:
                self.search_directory = _get_user_media_directory()
        change_button.connect('clicked', handle_change_clicked)

        v.pack_start(group_box)

        v.pack_start(widgetset.Label(" "), expand=True)

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page())

        def handle_search_finish_clicked(widget):
            if widget.mode == "search":
                if rbg2.get_selected() == restrict_rb:
                    self.search_directory = _get_user_media_directory()

                self.next_page()
            else:
                self.on_close()

        search_button = widgetset.Button(_("Search"))
        search_button.connect('clicked', handle_search_finish_clicked)
        search_button.text_faces = {"search": _("Search"), "finish": _("Finish")}
        search_button.mode = "search"

        def switch_mode(mode):
            search_button.set_text(search_button.text_faces[mode])
            search_button.mode = mode

        h = widgetutil.build_hbox((prev_button, search_button))
        v.pack_start(widgetutil.align_right(h))

        def handle_radio_button_clicked(widget):
            if widget is no_rb:
                group_box.disable()
                search_entry.disable()
                change_button.disable()
                switch_mode("finish")

            elif widget is yes_rb:
                group_box.enable()
                switch_mode("search")
                if rbg2.get_selected() is restrict_rb:
                    search_entry.disable()
                    change_button.disable()
                else:
                    search_entry.enable()
                    change_button.enable()

            elif widget is restrict_rb:
                search_entry.disable()
                change_button.disable()

            elif widget is search_rb:
                search_entry.enable()
                change_button.enable()

        no_rb.connect('clicked', handle_radio_button_clicked)
        yes_rb.connect('clicked', handle_radio_button_clicked)
        restrict_rb.connect('clicked', handle_radio_button_clicked)
        search_rb.connect('clicked', handle_radio_button_clicked)

        handle_radio_button_clicked(restrict_rb)
        handle_radio_button_clicked(no_rb)

        return v

    def build_search_page(self):
        v = widgetset.VBox(spacing=5)

        v.pack_start(_build_title(_("Searching for media files")))

        progress_bar = widgetset.ProgressBar()
        v.pack_start(progress_bar)

        progress_label = widgetset.Label("")
        progress_label.set_size_request(400, -1)
        v.pack_start(widgetutil.align_left(progress_label))

        search_button = widgetset.Button(_("Search"))
        cancel_button = widgetset.Button(_("Cancel"))

        h = widgetutil.build_hbox((search_button, cancel_button))
        v.pack_start(widgetutil.align_left(h))

        v.pack_start(widgetset.Label(" "), expand=True)

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page())

        finish_button = widgetset.Button(_("Finish"))
        finish_button.connect('clicked', lambda x: self.on_close())

        h = widgetutil.build_hbox((prev_button, finish_button))
        v.pack_start(widgetutil.align_right(h))

        def handle_cancel_clicked(widget):
            progress_bar.stop_pulsing()
            progress_bar.set_progress(1.0)
            search_button.enable()
            cancel_button.disable()

            prev_button.enable()
            finish_button.enable()
            self.cancelled = True

        def make_progress():
            if self.cancelled:
                self.gathered_media_files = []
                self.finder = None
                progress_label.set_text("")
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
                progress_label.set_text(u"%s - %s" % (num_files, num_media_files))

                threads.call_on_ui_thread(make_progress)

            except StopIteration:
                handle_cancel_clicked(None)
                self.finder = None

        def handle_search_clicked(widget):
            self.cancelled = False
            search_button.disable()
            cancel_button.enable()

            prev_button.disable()
            finish_button.disable()

            self.finder = util.gather_media_files(self.search_directory)
            progress_bar.start_pulsing()
            threads.call_on_ui_thread(make_progress)

        search_button.connect('clicked', handle_search_clicked)
        cancel_button.connect('clicked', handle_cancel_clicked)

        cancel_button.disable()
        return v
