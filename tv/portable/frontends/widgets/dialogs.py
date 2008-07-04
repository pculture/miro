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

from miro.plat.frontends.widgets import widgetset
from miro.dialogs import BUTTON_OK, BUTTON_CANCEL, BUTTON_IGNORE, \
        BUTTON_SUBMIT_REPORT, BUTTON_YES, BUTTON_NO, BUTTON_KEEP_VIDEOS, \
        BUTTON_DELETE_VIDEOS, BUTTON_CANCEL

def show_message(title, description):
    """Display a message to the user and wait for them to click OK"""
    window = widgetset.Dialog(title, description)
    try:
        window.add_button(BUTTON_OK.text)
        window.run()
    finally:
        window.destroy()

def show_choice_dialog(title, description, choices):
    """Display a message to the user and wait for them to choose an option.
    Returns the button object chosen."""
    window = widgetset.Dialog(title, description)
    try:
        for mem in choices:
            window.add_button(mem.text)
        response = window.run()
        return choices[response]
    finally:
        window.destroy()

def ask_for_string(title, description, initial_text=None):
    """Ask the user to enter a string in a TextEntry box.

    description - textual description with newlines
    initial_text - None, string or callable to pre-populate the entry box

    Returns the value entered, or None if the user clicked cancel
    """
    window = widgetset.Dialog(title, description)
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

def ask_for_open_pathname(title, initial_filename=None, filters=[]):
    """Returns the file pathname or None.
    """
    window = widgetset.FileOpenDialog(title)
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

def ask_for_save_pathname(title, initial_filename=None):
    """Returns the file pathname or None.
    """
    window = widgetset.FileSaveDialog(title)
    try:
        if initial_filename:
            window.set_filename(initial_filename)
        response = window.run()
        if response == 0:
            return window.get_filename()
    finally:
        window.destroy()
