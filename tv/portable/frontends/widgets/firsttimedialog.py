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

"""Defines the "first time dialog" and all behavior."""

from miro import prefs
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil, prefpanel
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.plat.frontends.widgets.threads import call_on_ui_thread

class FirstTimeDialog(widgetset.Window):
    def __init__(self, done_firsttime_callback):
        widgetset.Window.__init__(self, _("Miro First Time Setup"), widgetset.Rect(100, 100, 475, 500))

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

    def _build_title(self, text):
        lab = widgetset.Label(text)
        lab.set_bold(True)
        lab.set_wrap(True)
        return widgetutil.align_left(lab, bottom_pad=10)

    def build_first_page(self):
        v = widgetset.VBox(spacing=5)

        v.pack_start(self._build_title(_("Welcome to the Miro First Time Setup")))

        lab = widgetset.Label(_(
            "The next few screens will help you set up Miro so that it works best "
            "for you.\n"
            "\n"
            "We recommend that you have Miro launch when your computer starts up.  "
            "This way, videos in progress can finish downloading and new videos "
            "can be downloaded in the background, ready when you want to watch."
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

        prefpanel.attach_radio([(yes_rb, True), (no_rb, False)], prefs.RUN_DTV_AT_STARTUP)
        v.pack_start(widgetutil.align_left(yes_rb))
        v.pack_start(widgetutil.align_left(no_rb))

        v.pack_start(widgetset.Label(" "), expand=True)

        next = widgetset.Button(_("Next >"))
        next.connect('clicked', lambda x: self.next_page())

        v.pack_start(widgetutil.align_right(next))

        return v

    def build_second_page(self):
        v = widgetset.VBox()

        v.pack_start(self._build_title(_("Completing the Miro First Time Setup")))

        lab = widgetset.Label(_(
            "Miro can find all the videos on your computer to help you organize "
            "your collection.\n"
            "\n"
            "Would you like Miro to look for video files on your computer?"
            ))
        lab.set_size_request(400, -1)
        lab.set_wrap(True)
        v.pack_start(widgetutil.align_left(lab))

        rbg = widgetset.RadioButtonGroup()
        no_rb = widgetset.RadioButton(_("No"), rbg)
        yes_rb = widgetset.RadioButton(_("Yes"), rbg)
        v.pack_start(widgetutil.align_left(no_rb))
        v.pack_start(widgetutil.align_left(yes_rb, bottom_pad=5))

        group_box = widgetset.VBox()

        rbg2 = widgetset.RadioButtonGroup()
        restrict_rb = widgetset.RadioButton(_("Restrict to all my personal files."), rbg2)
        search_rb = widgetset.RadioButton(_("Search custom folders:"), rbg2)
        group_box.pack_start(widgetutil.align_left(restrict_rb, left_pad=30))
        group_box.pack_start(widgetutil.align_left(search_rb, left_pad=30))

        search_box = widgetset.TextEntry()
        change_button = widgetset.Button(_("Change"))
        h = widgetutil.build_hbox((search_box, change_button))
        group_box.pack_start(widgetutil.align_left(h, left_pad=30))

        v.pack_start(group_box)

        v.pack_start(widgetset.Label(" "), expand=True)

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page())

        def handle_search_finish(widget):
            if widget.mode == "search":
                self.next_page()
            else:
                self.on_close()

        search_button = widgetset.Button(_("Search"))
        search_button.connect('clicked', handle_search_finish)
        search_button.text_faces = {"search": _("Search"), "finish": _("Finish")}
        search_button.mode = "search"

        def switch_mode(mode):
            search_button.set_text(search_button.text_faces[mode])
            search_button.mode = mode

        h = widgetutil.build_hbox((prev_button, search_button))
        v.pack_start(widgetutil.align_right(h))

        def handle_clicked(widget):
            if widget is no_rb:
                group_box.disable_widget()
                search_box.disable_widget()
                change_button.disable_widget()
                switch_mode("finish")

            elif widget is yes_rb:
                group_box.enable_widget()
                switch_mode("search")
                if rbg2.get_selected() is restrict_rb:
                    search_box.disable_widget()
                    change_button.disable_widget()
                else:
                    search_box.enable_widget()
                    change_button.enable_widget()

            elif widget is restrict_rb:
                search_box.disable_widget()
                change_button.disable_widget()

            elif widget is search_rb:
                search_box.enable_widget()
                change_button.enable_widget()

        no_rb.connect('clicked', handle_clicked)
        yes_rb.connect('clicked', handle_clicked)
        restrict_rb.connect('clicked', handle_clicked)
        search_rb.connect('clicked', handle_clicked)

        handle_clicked(restrict_rb)
        handle_clicked(no_rb)

        return v

    def build_search_page(self):
        v = widgetset.VBox()

        lab = widgetset.Label(_("Searching for videos"))
        v.pack_start(widgetutil.align_left(lab))

        lab = widgetset.Label("FIXME - progress here")
        v.pack_start(widgetutil.align_left(lab))

        count = 0
        found_lab = widgetset.Label(ngettext(
            _("%(count)d video found"),
            _("%(count)d videos found"),
            count,
            {"count": count}
        ))
        v.pack_start(widgetutil.align_left(found_lab))
        reset_button = widgetset.Button(_("Reset Search"))
        v.pack_start(widgetutil.align_left(reset_button))

        v.pack_start(widgetset.Label(" "), expand=True)

        prev_button = widgetset.Button(_("< Previous"))
        prev_button.connect('clicked', lambda x: self.prev_page())

        finish_button = widgetset.Button(_("Finish"))
        finish_button.connect('clicked', lambda x: self.on_close())

        h = widgetutil.build_hbox((prev_button, finish_button))
        v.pack_start(widgetutil.align_right(h))

        return v
