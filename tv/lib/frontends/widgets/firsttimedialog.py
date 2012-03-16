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
from miro import fileutil
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
import sys

_SYSTEM_LANGUAGE = os.environ.get("LANGUAGE", "")
WIDTH = 475
HEIGHT = 375

def get_media_player_name_path(where):
    """Get the media player name and path from the platform.

    This method wraps the platform version with a bit of error checking and
    logging.

    :param where: what piece of code calling this?
    """
    mp_name, mp_path = get_plat_media_player_name_path()
    logging.debug("%s: got media player name/path: %r %r",
                  where, mp_name, mp_path)
    if mp_path is None or mp_name is None:
        # If either path or name is not given, make sure that neither are
        # set.  See #18865.
        return None, None
    return mp_name, mp_path

def _build_title(text):
    """Builds and returns a title widget for the panes in the
    First Time Startup dialog.
    """
    lab = widgetset.Label(text)
    lab.set_bold(True)
    lab.set_wrap(True)
    lab.set_size_request(WIDTH - 40, -1)
    return widgetutil.align_left(lab, bottom_pad=15)

def _build_paragraph_text(text):
    lab = widgetset.Label(text)
    lab.set_wrap(True)
    lab.set_size_request(WIDTH - 40, -1)
    return widgetutil.align_left(lab, bottom_pad=15)

def _build_checkbox_and_label(checkbox, label_text):
    """Build a checkbox with a label right under it.

    This is useful because checkboxes don't wrap properly.  Labels don't
    wrap great either, but we can hack things to make labels wrape.
    """
    label = widgetset.Label(label_text)
    label.set_size_request(WIDTH - 40, -1)
    label.set_wrap(True)
    vbox = widgetset.VBox(spacing=0)
    vbox.pack_start(widgetutil.align_left(checkbox))
    vbox.pack_start(widgetutil.align_left(label))
    return vbox

class FirstTimeDialog(widgetset.DialogWindow):
    def __init__(self, done_firsttime_callback, title=None):
        if title == None:
            title = _("%(appname)s Setup",
                      {"appname": app.config.get(prefs.SHORT_APP_NAME)})

        x, y = widgetset.get_first_time_dialog_coordinates(WIDTH, HEIGHT)

        widgetset.DialogWindow.__init__(
            self, title, widgetset.Rect(x, y, WIDTH, HEIGHT))

        # the directory panel 3 searches for files in
        self.search_directory = None

        self.finder = None

        self.cancelled = False
        self.gathered_media_files = None
        self.import_media_player_stuff = False
        self.progress_bar = None
        self.progress_label = None
        self.search_cancel_button = None
        self.search_prev_button = None
        self.search_next_button = None

        self._done_firsttime_callback = done_firsttime_callback

        mp_info = get_media_player_name_path('firsttimedialog')
        self.mp_name, self.mp_path = mp_info

        self._page_box = widgetset.VBox()
        self._pages = self.build_pages()
        self._page_index = -1

        self.set_content_widget(widgetutil.pad(self._page_box, 20, 20, 20, 20))

        self.on_close_handler = self.connect('will-close', self.on_close)

    def build_pages(self):
        pages = [self.build_language_page(),
                 self.build_startup_page(),
                 self.build_music_page(),
                 self.build_find_files_page(),
                 self.build_search_page()]

        for page in pages:
            page.set_size_request(WIDTH - 40, HEIGHT - 40)
        return pages

    def run(self):
        self._switch_page(0)
        self.show()

    def on_close(self, widget=None):
        if self.import_media_player_stuff:
            logging.debug("firsttimedialog: adding mp_path (%r)",
                          self.mp_path)
            app.watched_folder_manager.add(self.mp_path)
        if self.gathered_media_files:
            logging.debug("firsttimedialog: adding %d files",
                          len(self.gathered_media_files))
            messages.AddFiles(self.gathered_media_files).send_to_backend()
        self._done_firsttime_callback()

    def _switch_page(self, i, rebuild=False):
        if i == self._page_index and not rebuild:
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

        vbox.pack_start(_build_paragraph_text(_(
                    "Welcome to %(name)s!  We have a couple of questions "
                    "to help you get started.",
                    {'name': app.config.get(prefs.SHORT_APP_NAME)})))

        vbox.pack_start(_build_title(_(
                    "What language would you like %(name)s to be in?",
                    {'name': app.config.get(prefs.SHORT_APP_NAME)})))

        lang_options = gtcache.get_languages()
        lang_options.insert(0, ("system", _("System default")))

        def update_language(widget, index):
            os.environ["LANGUAGE"] = _SYSTEM_LANGUAGE
            app.config.set(prefs.LANGUAGE,
                       str(lang_options[index][0]))
            gtcache.init()

            # FIXME - this is totally awful and may break at some
            # point.  what happens is that widgetconst translates at
            # import time, so if someone changes the language, then
            # the translations have already happened.  we reload the
            # module to force them to happen again.  bug 17515
            if "miro.frontends.widgets.widgetconst" in sys.modules:
                reload(sys.modules["miro.frontends.widgets.widgetconst"])
            self.this_page(rebuild=True)

        lang_option_menu = widgetset.OptionMenu([op[1] for op in lang_options])
        lang = app.config.get(prefs.LANGUAGE)
        try:
            lang_option_menu.set_selected([op[0] for op in lang_options].index(lang))
        except ValueError:
            lang_option_menu.set_selected(1)

        lang_option_menu.connect('changed', update_language)

        def next_clicked(widget):
            os.environ["LANGUAGE"] = _SYSTEM_LANGUAGE
            app.config.set(prefs.LANGUAGE,
                       str(lang_options[lang_option_menu.get_selected()][0]))
            gtcache.init()
            self.next_page(rebuild=True)

        hbox = widgetset.HBox()
        hbox.pack_start(widgetset.Label(_("Language:")), padding=0)
        hbox.pack_start(lang_option_menu, padding=5)

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

        vbox.pack_start(_build_paragraph_text(_(
                    "%(name)s can automatically run when you start your "
                    "computer so that it can resume your downloads "
                    "and update your podcasts.",
                    {'name': app.config.get(prefs.SHORT_APP_NAME)})))

        vbox.pack_start(_build_title(_(
                    "Would you like to run %(name)s on startup?",
                    {'name': app.config.get(prefs.SHORT_APP_NAME)})))

        rbg = widgetset.RadioButtonGroup()
        yes_rb = widgetset.RadioButton(_("Yes"), rbg)
        no_rb = widgetset.RadioButton(_("No"), rbg)

        prefpanel.attach_radio([(yes_rb, True), (no_rb, False)],
                               prefs.RUN_AT_STARTUP)
        vbox.pack_start(widgetutil.align_left(yes_rb, left_pad=10))
        vbox.pack_start(widgetutil.align_left(no_rb, left_pad=10))

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

    def build_find_files_page(self):
        vbox = widgetset.VBox(spacing=5)

        vbox.pack_start(_build_paragraph_text(_(
                    "%(name)s can find music and video on your computer "
                    "and show them in your %(name)s library.  No files "
                    "will be copied or duplicated.",
                    {"name": app.config.get(prefs.SHORT_APP_NAME)})))

        vbox.pack_start(_build_title(_(
                    "Would you like %(name)s to search your computer "
                    "for media files?",
                    {"name": app.config.get(prefs.SHORT_APP_NAME)})))

        rbg = widgetset.RadioButtonGroup()
        no_rb = widgetset.RadioButton(_("No"), rbg)
        yes_rb = widgetset.RadioButton(_("Yes"), rbg)
        no_rb.set_selected()
        vbox.pack_start(widgetutil.align_left(no_rb, left_pad=10))
        vbox.pack_start(widgetutil.align_left(yes_rb,
                                              left_pad=10, bottom_pad=5))

        group_box = widgetset.VBox(spacing=5)

        rbg2 = widgetset.RadioButtonGroup()
        restrict_rb = widgetset.RadioButton(
            _("Search everywhere."), rbg2)
        search_rb = widgetset.RadioButton(
            _("Just search in this folder:"), rbg2)
        restrict_rb.set_selected()
        group_box.pack_start(widgetutil.align_left(restrict_rb, left_pad=30))
        group_box.pack_start(widgetutil.align_left(search_rb, left_pad=30))

        search_entry = widgetset.TextEntry(
            filename_to_unicode(get_default_search_dir()))
        search_entry.set_width(20)
        change_button = widgetset.Button(_("Choose..."))
        hbox = widgetutil.build_hbox((
            widgetutil.align_middle(search_entry),
            widgetutil.align_middle(change_button)))
        group_box.pack_start(widgetutil.align_left(hbox, left_pad=30))

        def handle_change_clicked(widget):
            dir_ = dialogs.ask_for_directory(
                _("Choose directory to search for media files"),
                initial_directory=get_default_search_dir(),
                transient_for=self)
            if dir_:
                search_entry.set_text(filename_to_unicode(dir_))
                self.search_directory = dir_
            else:
                self.search_directory = get_default_search_dir()
            # reset the search results if they change the directory
            self.gathered_media_files = None

        change_button.connect('clicked', handle_change_clicked)

        vbox.pack_start(group_box)

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page())

        def handle_search_finish_clicked(widget):
            if widget.mode == "search":
                if rbg2.get_selected() == restrict_rb:
                    self.search_directory = get_default_search_dir()

                self.next_page()
            else:
                self.destroy()

        search_button = widgetset.Button(_("Search"))
        search_button.connect('clicked', handle_search_finish_clicked)
        # FIXME - this is goofy naming
        search_button.text_faces = {"search": _("Next >"),
                                    "next": _("Finish")}

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
            if self.gathered_media_files:
                num_found = len(self.gathered_media_files)
            else:
                num_found = 0
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

        vbox.pack_start(widgetutil.align_right(self.cancel_search_button, right_pad=5))

        vbox.pack_start(self._force_space_label(), expand=True)

        self.search_prev_button = widgetset.Button(_("< Previous"))
        self.search_prev_button.connect('clicked', lambda x: self.prev_page())

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

    def build_music_page(self):
        vbox = MusicSetupVBox(self.mp_name)
        if vbox.import_cbx:
            def on_import_toggled(cbx):
                self.import_media_player_stuff = cbx.get_checked()
            vbox.import_cbx.connect("toggled", on_import_toggled)

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page())

        next_button = widgetset.Button(_("Next >"))
        next_button.connect('clicked', lambda x: self.next_page())

        vbox.pack_start(
            widgetutil.align_bottom(widgetutil.align_right(
                    widgetutil.build_hbox((prev_button, next_button)))),
            expand=True)

        return vbox

class MusicSetupVBox(widgetset.VBox):
    """VBox for the music setup page.

    This is separated out because we want to re-use it when the user first
    clicks the music tab.

    Attributes:
    - import_cbx: Checkbox to import music from the platform player
    - net_lookup_cbx: Checkbox to enable net lookups by default

    This class handles changing the NET_LOOKUP_BY_DEFAULT pref, but the class
    using it must handle responding import_cbx being checked.
    """
    def __init__(self, mp_name, pack_title=True):
        widgetset.VBox.__init__(self, spacing=5)

        if pack_title:
            self.pack_start(_build_title(_("Music Setup")))
        if mp_name is not None:
            self.import_cbx = widgetset.Checkbox(
                _("Show my %(player)s music in my %(appname)s library.",
                  {"player": mp_name,
                   "appname": app.config.get(prefs.SHORT_APP_NAME)}))
            controls = _build_checkbox_and_label(
                self.import_cbx, _("(Don't worry, no files are copied.)"))
            self.pack_start(widgetutil.pad(controls, bottom=10))
        else:
            self.import_cbx = None

        self.net_lookup_cbx = widgetset.Checkbox(_('Use online lookup'))
        self.pack_start(_build_checkbox_and_label(
            self.net_lookup_cbx, _('Miro will use Echonest and 7Digital '
                                   'to cleanup all song titles, info, and '
                                   'album art.  Highly recommended.')))
        prefpanel.attach_boolean(self.net_lookup_cbx,
                                 prefs.NET_LOOKUP_BY_DEFAULT)

        # Give the "Note:" heading top padding to separate it from the
        # checkboxes, but no bottom padding to keep it together with the rest
        # of the text.
        heading = widgetset.Label(_("Note:"))
        heading.set_wrap(True)
        heading.set_bold(True)
        heading.set_size_request(WIDTH - 40, -1)
        self.pack_start(widgetutil.pad(heading, top=15))
        text = _("You can manually set or undo song info cleanup by "
                 "right-clicking on a song or batch of songs.  You can "
                 "adjust lookup settings at any time in Miro preferences."
                 "\n\n"
                 "Online lookup involves sending anonymized data about "
                 "your songs to Miro and indirectly to Echonest and "
                 "7Digital.")
        self.pack_start(_build_paragraph_text(text))

class MusicSetupDialog(dialogs.MainDialog):
    """Ask some questions on music settings.

    We pop this up the first time the user clicks on the music tab, if we
    haven't already asked the questions in the first-time setup dialog.
    """
    def __init__(self):
        dialogs.MainDialog.__init__(self, _("Music Setup"))
        mp_info = get_media_player_name_path('musicsetupdialog')
        self.mp_name, self.mp_path = mp_info
        if self.already_added_media_player_path():
            self.mp_name = self.mp_path = None
        self.vbox = MusicSetupVBox(self.mp_name, pack_title=False)
        self.set_extra_widget(self.vbox)
        self.add_button(_("Get Started"))

    def already_added_media_player_path(self):
        if self.mp_path is None:
            return False
        wf_model = app.watched_folder_manager.model
        wf_iter = wf_model.first_iter()
        while wf_iter is not None:
            path = wf_model[wf_iter][1]
            if fileutil.samefile(path, self.mp_path):
                return True
            wf_iter = wf_model.next_iter(wf_iter)

    def import_path(self):
        """Path to import music from.

        The code using MusicSetupDialog should check this once the dialog is
        closed and create a watched folder if needed.

        :returns: path or None if we shouldn't import anything.
        """
        if self.vbox.import_cbx and self.vbox.import_cbx.get_checked():
            return self.mp_path
        else:
            return None
