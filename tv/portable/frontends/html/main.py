# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

"""Main module for the HTML frontend.  Responsible for startup, shutdown,
error reporting, etc.
"""

from gtcache import gettext as _
import dialogs
import frontendutil
import signals

class HTMLApplication:
    def __init__(self):
        self.ignoreErrors = False

    def startup(self):
        signals.system.connect('error', self.handleError)

    def handleError(self, obj, report):
        if self.ignoreErrors:
            return

        def callback(dialog):
            if dialog.choice == dialogs.BUTTON_IGNORE:
                self.ignoreErrors = True
                return
            try:
                send_dabatase = dialogs.checkbox_value
            except AttributeError:
                send_dabatase = False
            try:
                description = dialog.textbox_value
            except AttributeError:
                description = u"Description text not implemented"
            frontendutil.sendBugReport(report, description, send_dabatase)
        chkboxdialog = dialogs.CheckboxTextboxDialog(_("Internal Error"),_("Miro has encountered an internal error. You can help us track down this problem and fix it by submitting an error report."), _("Include entire program database including all video and channel metadata with crash report"), False, _("Describe what you were doing that caused this error"), dialogs.BUTTON_SUBMIT_REPORT, dialogs.BUTTON_IGNORE)
        chkboxdialog.run(callback)
