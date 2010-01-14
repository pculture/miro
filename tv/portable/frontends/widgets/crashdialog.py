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

"""miro.frontends.widgets.crashdialog -- Code for showing the
crash dialog.
"""

import logging
from miro import messages
from miro import config
from miro import prefs

from miro.gtcache import gettext as _

from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.dialogs import MainDialog
from miro.dialogs import BUTTON_IGNORE, BUTTON_SUBMIT_REPORT

IGNORE_ERRORS = -1

def run_dialog(obj, report):
    window = MainDialog(_("Internal Error"))
    try:
        try:
            vbox = widgetset.VBox(spacing=5)

            lab = widgetset.Label(_(
                "%(appname)s has encountered an internal error.  You can help us track "
                "down this problem and fix it by submitting an error report.",
                {"appname": config.get(prefs.SHORT_APP_NAME)}
                ))

            lab.set_wrap(True)
            vbox.pack_start(widgetutil.align_left(lab))

            cbx = widgetset.Checkbox(_(
                "Include entire program database including all video and "
                "feed metadata with crash report"
            ))
            vbox.pack_start(widgetutil.align_left(cbx))

            lab2 = widgetset.Label(_("Describe what you were doing when you got this error:"))
            vbox.pack_start(widgetutil.align_left(lab2))

            text = widgetset.TextEntry()
            text.set_width(45)
            vbox.pack_start(widgetutil.align_left(text))

            window.set_extra_widget(vbox)
            window.add_button(BUTTON_SUBMIT_REPORT.text)
            window.add_button(BUTTON_IGNORE.text)

            ret = window.run()
            if ret == 0:
                messages.ReportCrash(report, text.get_text(), cbx.get_checked()).send_to_backend()
            else:
                return IGNORE_ERRORS
        except StandardError:
            logging.exception("crashdialog threw exception.")
    finally:
        window.destroy()
