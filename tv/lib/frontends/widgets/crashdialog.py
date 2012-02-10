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

"""miro.frontends.widgets.crashdialog -- Code for showing the
crash dialog.
"""

import logging
from miro import app
from miro import messages
from miro import prefs

from miro.gtcache import gettext_lazy as _

from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.dialogs import MainDialog
from miro.dialogs import BUTTON_IGNORE, BUTTON_SUBMIT_REPORT

IGNORE_ERRORS = -1

class CrashDialog(MainDialog):
    def __init__(self):
        MainDialog.__init__(
            self,
            _("Oops!  %(appname)s has encountered an internal error",
              {"appname": app.config.get(prefs.SHORT_APP_NAME)}))
        self.vbox = None
        self.report = ""

    def on_see_crash_report(self, widget):
        self.hidden_vbox.show()
        self.see_crash_button.disable()

    def run_dialog(self, report):
        self.report = report
        try:
            vbox = widgetset.VBox(spacing=8)

            lab = widgetset.Label(_(
                    "You can help us fix this problem by submitting an "
                    "error report."))
            lab.set_wrap(True)
            lab.set_size_request(600, -1)
            vbox.pack_start(widgetutil.align_left(lab))

            warning = widgetset.Label(_(
                    "Note: This error report will not be posted publicly, "
                    "but may include uniquely identifable information "
                    "including file names, website URLs, podcast URLs, "
                    "and disk paths."))
            warning.set_wrap(True)
            warning.set_size_request(600, -1)
            vbox.pack_start(widgetutil.align_left(warning))

            self.see_crash_button = widgetset.Button(_("See crash report"))
            self.see_crash_button.set_size(widgetconst.SIZE_SMALL)
            self.see_crash_button.connect('clicked', self.on_see_crash_report)
            vbox.pack_start(widgetutil.align_right(self.see_crash_button))

            cbx = widgetset.Checkbox(_(
                    "Include entire program database including all "
                    "filenames, websites, and podcasts with the "
                    "error report."))
            vbox.pack_start(widgetutil.align_left(cbx))

            lab2 = widgetset.Label(
                _("What were you doing when you got this message?  "
                  "(Helpful, but not required.)"))
            lab2.set_wrap(True)
            lab2.set_size_request(600, -1)
            vbox.pack_start(widgetutil.align_left(lab2))

            text = widgetset.MultilineTextEntry()
            scroller = widgetset.Scroller(True, True)
            scroller.add(text)
            scroller.set_size_request(600, 100)
            vbox.pack_start(widgetutil.align_left(scroller))

            hidden_vbox = widgetset.VBox(spacing=5)
            lab = widgetset.Label(_("Crash Report:"))
            hidden_vbox.pack_start(widgetutil.align_left(lab))

            report_text = widgetset.MultilineTextEntry(self.report)
            report_text.set_editable(False)

            scroller = widgetset.Scroller(True, True)
            scroller.add(report_text)
            scroller.set_size_request(600, 100)
            hidden_vbox.pack_start(widgetutil.align_left(scroller))

            self.hidden_vbox = widgetutil.HideableWidget(hidden_vbox)
            self.hidden_vbox.hide()
            vbox.pack_start(self.hidden_vbox)

            self.set_extra_widget(vbox)
            self.add_button(BUTTON_SUBMIT_REPORT.text)
            self.add_button(BUTTON_IGNORE.text)

            self.vbox = vbox
            ret = self.run()
            if ret == 0:
                messages.ReportCrash(report, text.get_text(), cbx.get_checked()).send_to_backend()
            else:
                return IGNORE_ERRORS
        except StandardError:
            logging.exception("crashdialog threw exception.")

def run_dialog(report):
    try:
        diag = CrashDialog()
        return diag.run_dialog(report)
    finally:
        diag.destroy()
