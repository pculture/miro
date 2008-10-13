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

"""Run dialogs from the backend thread."""

from miro import dialogs
from miro.gtcache import gettext as _
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.dialogs import MainDialog
from miro.plat.frontends.widgets import widgetset

def run(dialog):
    if dialog.__class__ in (dialogs.MessageBoxDialog, dialogs.ChoiceDialog,
            dialogs.ThreeChoiceDialog):
        runner = DialogRunner(dialog)
    elif isinstance(dialog, dialogs.HTTPAuthDialog):
        runner = HTTPAuthDialogRunner(dialog)
    elif isinstance(dialog, dialogs.TextEntryDialog):
        runner = TextEntryDialogRunner(dialog)
    elif isinstance(dialog, dialogs.CheckboxTextboxDialog):
        runner = CheckboxTextboxDialogRunner(dialog)
    elif isinstance(dialog, dialogs.CheckboxDialog):
        runner = CheckboxDialogRunner(dialog)
    else:
        print 'DIALOG: ', dialog
        return
    runner.run()

class DialogRunner(object):
    def __init__(self, dialog):
        self.dialog = dialog

    def run(self):
        window = MainDialog(self.dialog.title, self.dialog.description)
        try:
            self.build_extra_widget(window)
            for button in self.dialog.buttons:
                window.add_button(button.text)
            response = window.run()
            if response == -1:
                self.dialog.runCallback(None)
            else:
                self.handle_response(response)
        finally:
            window.destroy()

    def handle_response(self, response):
        self.dialog.runCallback(self.dialog.buttons[response])

    def build_extra_widget(self, window):
        pass

class HTTPAuthDialogRunner(DialogRunner):
    def build_extra_widget(self, window):
        table = widgetset.Table(2, 2)
        table.set_column_spacing(12)
        table.pack(widgetset.Label(_("Username:")), 0, 0)
        self.username_entry = widgetset.TextEntry(self.dialog.prefillUser)
        self.username_entry.set_width(20)
        table.pack(self.username_entry, 1, 0)
        table.pack(widgetset.Label(_("Password:")), 0, 1)
        self.password_entry = widgetset.SecureTextEntry(self.dialog.prefillPassword)
        self.password_entry.set_activates_default(True)
        table.pack(self.password_entry, 1, 1)
        window.set_extra_widget(widgetutil.align_center(table))

    def handle_response(self, response):
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        self.dialog.runCallback(self.dialog.buttons[response], username,
                password)

class TextEntryDialogRunner(DialogRunner):
    def build_extra_widget(self, window):
        self.entry = widgetset.TextEntry()
        initial = None
        if self.dialog.fillWithClipboardURL:
            initial = 'http://clipboard.com/'
        if initial is None and self.dialog.prefillCallback:
            initial = self.dialog.prefillCallback()
        if initial is not None:
            self.entry.set_text(initial)
        self.entry.set_activates_default(True)
        window.set_extra_widget(self.entry)

    def handle_response(self, response):
        text = self.entry.get_text()
        self.dialog.runCallback(self.dialog.buttons[response], text)

class CheckboxDialogRunner(DialogRunner):
    def build_extra_widget(self, window):
        self.checkbox = widgetset.Checkbox(self.dialog.checkbox_text)
        self.checkbox.set_checked(self.dialog.checkbox_value)
        window.set_extra_widget(self.checkbox)

    def handle_response(self, response):
        checked = self.checkbox.get_checked()
        self.dialog.runCallback(self.dialog.buttons[response], checked)

class CheckboxTextboxDialogRunner(DialogRunner):
    def build_extra_widget(self, window):
        self.checkbox = widgetset.Checkbox(self.dialog.checkbox_text)
        self.checkbox.set_checked(self.dialog.checkbox_value)
        self.entry = widgetset.TextEntry(self.dialog.textbox_value)
        self.entry.set_activates_default(True)
        vbox = widgetset.VBox()
        vbox.pack_start(self.checkbox)
        vbox.pack_start(self.entry)
        window.set_extra_widget(vbox)

    def handle_response(self, response):
        checked = self.checkbox.get_checked()
        text = self.entry.get_text()
        self.dialog.runCallback(self.dialog.buttons[response], checked, text)
