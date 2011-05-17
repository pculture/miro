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

"""Defines the first time dialog and all behavior.
"""

from miro import app
from miro import prefs
from miro import util
from miro import messages
from miro.fileobject import FilenameType
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import threads
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import prefpanel
from miro.frontends.widgets import dialogs
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro import gtcache
from miro.plat.utils import (filename_to_unicode,
                             get_plat_media_player_name_path)
from miro.plat.resources import get_default_search_dir

import os
import logging

_SYSTEM_LANGUAGE = os.environ.get("LANGUAGE", "")

def _get_user_media_directory():
    """Returns the user's media directory.
    """
    return get_default_search_dir()

def _build_title(text):
    """Builds and returns a title widget for the panes in the
    First Time Startup dialog.
    """
    lab = widgetset.Label(text)
    lab.set_bold(True)
    lab.set_wrap(True)
    return widgetutil.align_left(lab, bottom_pad=10)

WIDTH = 475
HEIGHT = 500

class FirstTimeDialog(widgetset.DialogWindow):
    def __init__(self, done_firsttime_callback, title=None):
        if title == None:
            title = _("%(appname)s First Time Setup",
                      {"appname": app.config.get(prefs.SHORT_APP_NAME)})

        widgetset.DialogWindow.__init__(
            self, title, widgetset.Rect(100, 100, WIDTH, HEIGHT))

        # the directory panel 3 searches for files in
        self.search_directory = None

        self.finder = None

        self.cancelled = False
        self.gathered_media_files = None
        self.progress_bar = None
        self.progress_label = None
        self.search_cancel_button = None
        self.search_prev_button = None
        self.search_next_button = None

        self._done_firsttime_callback = done_firsttime_callback

        self.mp_name, self.mp_path = get_plat_media_player_name_path()
        self._has_media_player = (
            self.mp_name is not None and self.mp_path is not None)

        self._page_box = widgetset.VBox()
        self._pages = self.build_pages()
        self._page_index = -1

        self.set_content_widget(widgetutil.pad(self._page_box, 20, 20, 20, 20))

        self.on_close_handler = self.connect('will-close', self.on_close)

    def build_pages(self):
        pages = [self.build_language_page(),
                 self.build_startup_page(),
                 self.build_import_page(),
                 self.build_search_page()]

        if self._has_media_player:
            pages.append(self.build_media_player_import_page())

        for page in pages:
            page.set_size_request(WIDTH - 40, HEIGHT - 40)
        return pages

    def run(self):
        self._switch_page(0)
        self.show()

    def on_close(self, widget=None):
        if self.gathered_media_files:
            messages.AddFiles(self.gathered_media_files).send_to_backend()
        self._done_firsttime_callback()

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

        # when we switch to the search page, it needs to kick off a
        # search.  since we build the pages when the dialog is
        # created, i needed a way to specify a function that runs when
        # we switch to that page.  so that's why i'm doing this
        # totally goofy thing.
        if hasattr(self._pages[i], "run_me_on_switch"):
            self._pages[i].run_me_on_switch()

    def this_page(self, rebuild=False):
        self._switch_page(self._page_index, rebuild)

    def next_page(self, rebuild=False, skip=0):
        self._switch_page(self._page_index + 1 + skip, rebuild)

    def prev_page(self, skip=0):
        self._switch_page(self._page_index - 1 - skip)

    def _force_space_label(self):
        lab = widgetset.Label(" ")
        lab.set_size_request(WIDTH - 40, -1)
        return lab

    def build_language_page(self):
        vbox = widgetset.VBox(spacing=5)

        vbox.pack_start(_build_title(_("Choose Language")))

        lab = widgetset.Label(_(
            "Welcome to the %(name)s first time setup!\n"
            "\n"
            "The next few screens will help you set up %(name)s so that "
            "it works best for you.\n"
            "\n"
            "What language would you like Miro to be in?",
            {'name': app.config.get(prefs.SHORT_APP_NAME)}))
        lab.set_wrap(True)
        lab.set_size_request(WIDTH - 40, -1)
        vbox.pack_start(widgetutil.align_left(lab))

        lang_options = gtcache.get_languages()
        lang_options.insert(0, ("system", _("System default")))

        lang_option_menu = widgetset.OptionMenu([op[1] for op in lang_options])
        lang = app.config.get(prefs.LANGUAGE)
        try:
            lang_option_menu.set_selected([op[0] for op in lang_options].index(lang))
        except ValueError:
            lang_option_menu.set_selected(1)

        def update_clicked(widget):
            os.environ["LANGUAGE"] = _SYSTEM_LANGUAGE
            app.config.set(prefs.LANGUAGE,
                       str(lang_options[lang_option_menu.get_selected()][0]))
            gtcache.init()
            self.this_page(rebuild=True)

        def next_clicked(widget):
            os.environ["LANGUAGE"] = _SYSTEM_LANGUAGE
            app.config.set(prefs.LANGUAGE,
                       str(lang_options[lang_option_menu.get_selected()][0]))
            gtcache.init()
            self.next_page(rebuild=True)

        update_button = widgetset.Button(_("Update"))
        update_button.connect('clicked', update_clicked)

        hbox = widgetset.HBox()
        hbox.pack_start(widgetset.Label(_("Language:")), padding=0)
        hbox.pack_start(lang_option_menu, padding=5)
        hbox.pack_start(update_button, padding=5)

        vbox.pack_start(widgetutil.align_center(hbox))

        vbox.pack_start(self._force_space_label())

        next_button = widgetset.Button(_("Next >"))
        next_button.connect('clicked', next_clicked)

        vbox.pack_start(
            widgetutil.align_bottom(widgetutil.align_right(
                    widgetutil.build_hbox((next_button,)))),
            expand=True)

        vbox = widgetutil.pad(vbox)

        return vbox

    def build_startup_page(self):
        vbox = widgetset.VBox(spacing=5)

        vbox.pack_start(_build_title(
            _("%(name)s Startup",
              {'name': app.config.get(prefs.SHORT_APP_NAME)})))

        lab = widgetset.Label(_(
            "We recommend that you have %(name)s launch when your computer "
            "starts up.  This way, downloads in progress can finish "
            "downloading and new media files can be downloaded in the "
            "background, ready when you want to watch.",
            {'name': app.config.get(prefs.SHORT_APP_NAME)}))
        lab.set_wrap(True)
        lab.set_size_request(WIDTH - 40, -1)
        vbox.pack_start(widgetutil.align_left(lab))

        lab = widgetset.Label(_("Would you like to run %(name)s on startup?",
                              {'name': app.config.get(prefs.SHORT_APP_NAME)}))
        lab.set_bold(True)
        vbox.pack_start(widgetutil.align_left(lab))

        rbg = widgetset.RadioButtonGroup()
        yes_rb = widgetset.RadioButton(_("Yes"), rbg)
        no_rb = widgetset.RadioButton(_("No"), rbg)

        prefpanel.attach_radio([(yes_rb, True), (no_rb, False)],
                               prefs.RUN_AT_STARTUP)
        vbox.pack_start(widgetutil.align_left(yes_rb))
        vbox.pack_start(widgetutil.align_left(no_rb))

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page())

        next_button = widgetset.Button(_("Next >"))
        next_button.connect('clicked', lambda x: self.next_page())

        vbox.pack_start(self._force_space_label())

        vbox.pack_start(
            widgetutil.align_bottom(widgetutil.align_right(
                    widgetutil.build_hbox((prev_button, next_button)))),
            expand=True)

        vbox = widgetutil.pad(vbox)

        return vbox

    def build_import_page(self):
        vbox = widgetset.VBox(spacing=5)

        vbox.pack_start(_build_title(_("Finding Files")))

        lab = widgetset.Label(_(
            "%(name)s can find all the media files on your computer to help "
            "you organize your collection.\n"
            "\n"
            "Would you like %(name)s to look for media files on your "
            "computer?",
            {'name': app.config.get(prefs.SHORT_APP_NAME)}))
        lab.set_size_request(WIDTH - 40, -1)
        lab.set_wrap(True)
        vbox.pack_start(widgetutil.align_left(lab))

        rbg = widgetset.RadioButtonGroup()
        no_rb = widgetset.RadioButton(_("No"), rbg)
        yes_rb = widgetset.RadioButton(_("Yes"), rbg)
        no_rb.set_selected()
        vbox.pack_start(widgetutil.align_left(no_rb))
        vbox.pack_start(widgetutil.align_left(yes_rb, bottom_pad=5))

        group_box = widgetset.VBox(spacing=5)

        rbg2 = widgetset.RadioButtonGroup()
        restrict_rb = widgetset.RadioButton(
            _("Restrict to all my personal files."), rbg2)
        search_rb = widgetset.RadioButton(_("Search custom folders:"), rbg2)
        restrict_rb.set_selected()
        group_box.pack_start(widgetutil.align_left(restrict_rb, left_pad=30))
        group_box.pack_start(widgetutil.align_left(search_rb, left_pad=30))

        search_entry = widgetset.TextEntry()
        search_entry.set_width(20)
        change_button = widgetset.Button(_("Change"))
        hbox = widgetutil.build_hbox((
            widgetutil.align_middle(search_entry),
            widgetutil.align_middle(change_button)))
        group_box.pack_start(widgetutil.align_left(hbox, left_pad=30))

        def handle_change_clicked(widget):
            dir_ = dialogs.ask_for_directory(
                _("Choose directory to search for media files"),
                initial_directory=_get_user_media_directory(),
                transient_for=self)
            if dir_:
                search_entry.set_text(filename_to_unicode(dir_))
                self.search_directory = dir_
            else:
                self.search_directory = _get_user_media_directory()
            # reset the search results if they change the directory
            self.gathered_media_files = None

        change_button.connect('clicked', handle_change_clicked)

        vbox.pack_start(group_box)

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page())

        def handle_search_finish_clicked(widget):
            if widget.mode == "search":
                if rbg2.get_selected() == restrict_rb:
                    self.search_directory = _get_user_media_directory()

                self.next_page()
            elif self._has_media_player:
                self.next_page(skip=1)
            else:
                self.destroy()

        search_button = widgetset.Button(_("Search"))
        search_button.connect('clicked', handle_search_finish_clicked)
        search_button.text_faces = {"search": _("Next >")}
        if not self._has_media_player:
            search_button.text_faces["next"] = _("Finish")
        else:
            search_button.text_faces["next"] = _("Next >")

        search_button.mode = "search"

        def switch_mode(mode):
            search_button.set_text(search_button.text_faces[mode])
            search_button.mode = mode

        vbox.pack_start(self._force_space_label())

        vbox.pack_start(
            widgetutil.align_bottom(widgetutil.align_right(
                    widgetutil.build_hbox((prev_button, search_button)))),
            expand=True)

        def handle_radio_button_clicked(widget):
            # Uggh  this is a bit messy.
            if widget is no_rb:
                group_box.disable()
                search_entry.disable()
                change_button.disable()
                switch_mode("next")
                self.gathered_media_files = None

            elif widget is yes_rb:
                group_box.enable()
                if rbg2.get_selected() is restrict_rb:
                    search_entry.disable()
                    change_button.disable()
                else:
                    search_entry.enable()
                    change_button.enable()

                switch_mode("search")

            elif widget is restrict_rb:
                search_entry.disable()
                change_button.disable()
                self.gathered_media_files = None

            elif widget is search_rb:
                search_entry.enable()
                change_button.enable()
                self.gathered_media_files = None

            if widget is restrict_rb or widget is search_rb:
                switch_mode("search")

        no_rb.connect('clicked', handle_radio_button_clicked)
        yes_rb.connect('clicked', handle_radio_button_clicked)
        restrict_rb.connect('clicked', handle_radio_button_clicked)
        search_rb.connect('clicked', handle_radio_button_clicked)

        handle_radio_button_clicked(restrict_rb)
        handle_radio_button_clicked(no_rb)

        vbox = widgetutil.pad(vbox)

        return vbox

    def stop_search_progress(self):
        self.progress_bar.stop_pulsing()
        self.progress_bar.set_progress(1.0)
        self.cancel_search_button.disable()
        self.cancelled = True
        self.search_prev_button.enable()
        self.search_next_button.enable()

    def handle_search_cancel_clicked(self, widget):
        self.stop_search_progress()
        self.gathered_media_files = None
        self.progress_label.set_text(_("Cancelled"))

    def search_complete(self, text):
        self.stop_search_progress()
        self.progress_label.set_text(text)

    def make_search_progress(self):
        if self.cancelled:
            self.finder = None
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
            self.progress_label.set_text(u"%s - %s" % (
                    num_files, num_media_files))

            threads.call_on_ui_thread(self.make_search_progress)

        except StopIteration:
            num_found = len(self.gathered_media_files)
            self.search_complete(
                ngettext(
                    "found %(count)s media file",
                    "found %(count)s media files",
                    num_found,
                    {"count": num_found}))
            self.finder = None

        except Exception:
            # this is here to get more data for bug #17422
            logging.exception("exception thrown in make_search_progress")

            # we want to clean up after this exception, too.
            num_found = len(self.gathered_media_files)
            self.search_complete(
                ngettext(
                    "found %(count)s media file",
                    "found %(count)s media files",
                    num_found,
                    {"count": num_found}))
            self.finder = None


    def start_search(self):
        # only start a search if we haven't gathered anything, yet.
        if self.gathered_media_files is not None:
            return

        # this starts the search as soon as the dialog is built
        self.cancelled = False
        self.cancel_search_button.enable()
        self.search_prev_button.disable()
        self.search_next_button.disable()

        search_directory = FilenameType(self.search_directory)
        self.finder = util.gather_media_files(search_directory)
        self.progress_bar.start_pulsing()
        threads.call_on_ui_thread(self.make_search_progress)

    def build_search_page(self):
        vbox = widgetset.VBox(spacing=5)

        vbox.pack_start(_build_title(_("Searching for media files")))

        self.progress_bar = widgetset.ProgressBar()
        self.progress_bar.set_size_request(400, -1)
        vbox.pack_start(widgetutil.align_center(
                self.progress_bar, top_pad=50))

        self.progress_label = widgetset.Label("")
        vbox.pack_start(
            widgetutil.align_top(
                widgetutil.align_center(self.progress_label),
                top_pad=10))

        self.cancel_search_button = widgetset.Button(_("Cancel Search"))
        self.cancel_search_button.connect(
            'clicked', self.handle_search_cancel_clicked)

        vbox.pack_start(widgetutil.align_right(self.cancel_search_button))

        vbox.pack_start(self._force_space_label(), expand=True)

        self.search_prev_button = widgetset.Button(_("< Previous"))
        self.search_prev_button.connect('clicked', lambda x: self.prev_page())

        if self._has_media_player:
            self.search_next_button = widgetset.Button(_("Next >"))
            self.search_next_button.connect('clicked',
                                            lambda x: self.next_page())
        else:
            self.search_next_button = widgetset.Button(_("Finish"))
            self.search_next_button.connect('clicked',
                                            lambda x: self.destroy())

        vbox.pack_start(
            widgetutil.align_bottom(widgetutil.align_right(
                    widgetutil.build_hbox((self.search_prev_button,
                                           self.search_next_button)))),
            expand=True)

        vbox = widgetutil.pad(vbox)
        vbox.run_me_on_switch = self.start_search

        return vbox


    def build_media_player_import_page(self):
        vbox = widgetset.VBox(spacing=5)
        vbox.pack_start(_build_title(
                _("Display %(player)s Library",
                  {"player": self.mp_name})))

        lab = widgetset.Label(_(
                "Would you like to display your %(player)s music and "
                "video in %(appname)s?",
                {"player": self.mp_name,
                 "appname": app.config.get(prefs.SHORT_APP_NAME)}))
        lab.set_size_request(WIDTH - 40, -1)
        lab.set_wrap(True)
        vbox.pack_start(widgetutil.align_left(lab))

        rbg = widgetset.RadioButtonGroup()
        yes_rb = widgetset.RadioButton(_("Yes"), rbg)
        no_rb = widgetset.RadioButton(_("No"), rbg)
        yes_rb.set_selected()

        vbox.pack_start(widgetutil.align_left(yes_rb))
        vbox.pack_start(widgetutil.align_left(no_rb))

        lab = widgetset.Label(_(
                "Note: Miro won't move or copy any files on your disk.  "
                "It will just add them to your %(appname)s library.",
                {"appname": app.config.get(prefs.SHORT_APP_NAME)}))
        lab.set_size_request(WIDTH - 40, -1)
        lab.set_wrap(True)
        vbox.pack_start(widgetutil.align_left(lab))

        def handle_finish(widget):
            if rbg.get_selected() == yes_rb:
                app.watched_folder_manager.add(self.mp_path)
            self.destroy()

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page(skip=1))

        finish_button = widgetset.Button(_("Finish"))
        finish_button.connect('clicked', handle_finish)

        vbox.pack_start(
            widgetutil.align_bottom(widgetutil.align_right(
                    widgetutil.build_hbox((prev_button, finish_button)))),
            expand=True)

        vbox = widgetutil.pad(vbox)

        return vbox
