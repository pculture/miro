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

"""miro.frontends.widgets.dialogs -- Dialog boxes for the Widget frontend.

The difference between this module and rundialog.py is that rundialog handles
dialog boxes that are coming from the backend code.  This model handles
dialogs that we create from the frontend

One big difference is that we don't have to be as general about dialogs, so
they can present a somewhat nicer API.  One important difference is that all
of the dialogs run modally.
"""

from miro import app
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.dialogs import BUTTON_OK, BUTTON_CANCEL, BUTTON_IGNORE, \
        BUTTON_SUBMIT_REPORT, BUTTON_YES, BUTTON_NO, BUTTON_KEEP_VIDEOS, \
        BUTTON_DELETE_VIDEOS, BUTTON_DELETE_FILE, \
        BUTTON_REMOVE_ENTRY, BUTTON_REMOVE, BUTTON_SUBSCRIBE, \
        BUTTON_CREATE_CHANNEL, BUTTON_CONTINUE, BUTTON_QUIT, BUTTON_DELETE, \
        BUTTON_CLOSE_TO_TRAY

WARNING_MESSAGE = 0
INFO_MESSAGE = 1
CRITICAL_MESSAGE = 2

def set_transient_for_main(dialog):
    """Sets a Dialog object to be transient for the main window if possible.

    If the main window has not been created yet, this is a no-op.
    """
    if app.widgetapp.window is not None:
        dialog.set_transient_for(app.widgetapp.window)

def _set_transient_for(dialog, transient_for):
    if transient_for is None:
        set_transient_for_main(dialog)
    else:
        dialog.set_transient_for(transient_for)

class MainDialog(widgetset.Dialog):
    """Dialog that is transient for the main window."""
    def __init__(self, title, description=None):
        widgetset.Dialog.__init__(self, title, description)
        set_transient_for_main(self)

def show_about():
    window = widgetset.AboutDialog()
    set_transient_for_main(window)
    try:
        window.run()
    finally:
        window.destroy()

def show_message(title, description, alert_type=INFO_MESSAGE,
        transient_for=None):
    """Display a message to the user and wait for them to click OK"""
    window = widgetset.AlertDialog(title, description, alert_type)
    _set_transient_for(window, transient_for)
    try:
        window.add_button(BUTTON_OK.text)
        window.run()
    finally:
        window.destroy()

def show_choice_dialog(title, description, choices, transient_for=None):
    """Display a message to the user and wait for them to choose an option.
    Returns the button object chosen."""
    window = MainDialog(title, description)
    try:
        for mem in choices:
            window.add_button(mem.text)
        response = window.run()
        return choices[response]
    finally:
        window.destroy()

def ask_for_string(title, description, initial_text=None, transient_for=None):
    """Ask the user to enter a string in a TextEntry box.

    description - textual description with newlines
    initial_text - None, string or callable to pre-populate the entry box

    Returns the value entered, or None if the user clicked cancel
    """
    window = MainDialog(title, description)
    try:
        window.add_button(BUTTON_OK.text)
        window.add_button(BUTTON_CANCEL.text)
        entry = widgetset.TextEntry()
        entry.set_activates_default(True)
        if initial_text:
            if callable(initial_text):
                initial_text = initial_text()
            entry.set_text(initial_text)
        window.set_extra_widget(entry)
        response = window.run()
        if response == 0:
            return entry.get_text()
        else:
            return None
    finally:
        window.destroy()

def ask_for_open_pathname(title, initial_filename=None, filters=[],
        transient_for=None):
    """Returns the file pathname or None.
    """
    window = widgetset.FileOpenDialog(title)
    _set_transient_for(window, transient_for)
    try:
        if initial_filename:
            window.set_filename(initial_filename)

        if filters:
            window.add_filters(filters)

        response = window.run()
        if response == 0:
            return window.get_filename()
    finally:
        window.destroy()

def ask_for_save_pathname(title, initial_filename=None, transient_for=None):
    """Returns the file pathname or None.
    """
    window = widgetset.FileSaveDialog(title)
    _set_transient_for(window, transient_for)
    try:
        if initial_filename:
            window.set_filename(initial_filename)
        response = window.run()
        if response == 0:
            return window.get_filename()
    finally:
        window.destroy()

def ask_for_directory(title, initial_directory=None, transient_for=None):
    """Returns the directory pathname or None.
    """
    window = widgetset.DirectorySelectDialog(title)
    _set_transient_for(window, transient_for)
    try:
        if initial_directory:
            window.set_directory(initial_directory)

        response = window.run()
        if response == 0:
            return window.get_directory()
    finally:
        window.destroy()
