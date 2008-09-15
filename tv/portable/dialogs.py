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

"""Handle dialog popups.

Simple Choices:
    For dialogs where you just want to ask the user a question use the
    ChoiceDialog class.  Pass it a title, description and a the buttons to
    display.  The call dialog.run, passing it a callback.  Here's an example:

    dialog = dialog.ChoiceDialog("Do you like pizza?",
        "Democracy would like to know if you enjoy eating pizza.",
        dialog.BUTTON_YES, dialog.BUTTON_NO)
    def handlePizzaAnswer(dialog):
        if dialog.choice is None:
            # handle the user closing the dialog windows
        elif dialog.choice == dialog.BUTTON_YES:
           # handle yes response
        elif dialog.choice == dialag.BUTTON_NO:
            # handle no respnose
    dialog.run(handlePizzaAnswer)

Advanced usage:
    For more advanced usage, check out the other Dialog subclasses.  They will
    probably have different constructor arguments and may have attributes
    other than choice that will be set.  For example, the HTTPAuthDialog has a
    "username" and "password" attribute that store what the user entered in
    the textboxes.

Frontend requirements:
    Frontends should implement the runDialog method in UIBackendDelegate
    class.  It inputs a Dialog subclass and displays it to the user.  When the
    user clicks on a button, or closes the dialog window, the frontend must
    call dialog.runCallback().

    As we add new dialog boxes, the frontend may run into Dialog subclasses
    that it doesn't recognize.  In that case, call dialog.runCallback(None).

    The frontend can layout the window however it wants, in particular buttons
    can be arranged with the default on the right or the left depending on the
    platform (The default button is the 1st button in the list).  Frontends
    should try to recognize standard buttons and display the stock icons for
    them.  
"""

from miro import eventloop
from miro import signals
from miro.gtcache import gettext as _

class DialogButton(object):
    def __init__(self, text):
        self.text = text
    def __eq__(self, other):
        return isinstance(other, DialogButton) and self.text == other.text
    def __str__(self):
        return "DialogButton(%r)" % self.text

BUTTON_OK = DialogButton(_("Ok"))
BUTTON_CLOSE = DialogButton(_("Close"))
BUTTON_CANCEL = DialogButton(_("Cancel"))
BUTTON_DONE = DialogButton(_("Done"))
BUTTON_YES = DialogButton(_("Yes"))
BUTTON_NO = DialogButton(_("No"))
BUTTON_QUIT = DialogButton(_("Quit"))
BUTTON_IGNORE = DialogButton(_("Ignore"))
BUTTON_SUBMIT_REPORT = DialogButton(_("Submit Crash Report"))
BUTTON_MIGRATE = DialogButton(_("Migrate"))
BUTTON_DONT_MIGRATE = DialogButton(_("Don't Migrate"))
BUTTON_DOWNLOAD = DialogButton(_("Download"))
BUTTON_REMOVE_ENTRY = DialogButton(_("Remove Entry"))
BUTTON_DELETE_FILE = DialogButton(_("Delete File"))
BUTTON_DELETE_FILES = DialogButton(_("Delete Files"))
BUTTON_KEEP_VIDEOS = DialogButton(_("Keep Videos"))
BUTTON_DELETE_VIDEOS = DialogButton(_("Delete Videos"))
BUTTON_CREATE = DialogButton(_("Create"))
BUTTON_CREATE_CHANNEL = DialogButton(_("Create Channel"))
BUTTON_ADD = DialogButton(_("Add"))
BUTTON_ADD_INTO_NEW_FOLDER = DialogButton(_("Add Into New Folder"))
BUTTON_KEEP = DialogButton(_("Keep"))
BUTTON_DELETE = DialogButton(_("Delete"))
BUTTON_REMOVE = DialogButton(_("Remove"))
BUTTON_NOT_NOW = DialogButton(_("Not Now"))
BUTTON_CLOSE_TO_TRAY = DialogButton(_("Close to Tray"))
BUTTON_LAUNCH_MIRO = DialogButton(_("Launch Miro"))
BUTTON_DOWNLOAD_ANYWAY = DialogButton(_("Download Anyway"))
BUTTON_INSTALL_IHEARTMIRO = DialogButton(_("Install iHeartMiro"))
BUTTON_DONT_INSTALL = DialogButton(_("Don't Install"))
BUTTON_SUBSCRIBE = DialogButton(_("Subscribe"))
BUTTON_STOP_WATCHING = DialogButton(_("Stop Watching"))

class Dialog(object):
    """Abstract base class for dialogs."""

    def __init__(self, title, description, buttons):
        self.title = title
        self.description = description
        self.buttons = buttons

    def run(self, callback):
        self.callback = callback
        self.choice = None
        signals.system.new_dialog(self)

    def runCallback(self, choice):
        """Run the callback for this dialog.  Choice should be the button that
        the user clicked, or None if the user closed the window without
        makeing a selection.
        """

        self.choice = choice
        eventloop.addUrgentCall(self.callback, "%s callback" % self.__class__, 
                args=(self,))

class MessageBoxDialog(Dialog):
    """Show the user some info in a dialog box.  The only button is Okay.  The
    callback is optional for a message box dialog.  """

    def __init__(self, title, description):
        Dialog.__init__(self, title, description, [BUTTON_OK])

    def run(self, callback=None):
        Dialog.run(self, callback)

    def runCallback(self, choice):
        if self.callback is not None:
            Dialog.runCallback(self, choice)

class ChoiceDialog(Dialog):
    """Give the user a choice of 2 options (Yes/No, Ok/Cancel,
    Migrate/Don't Migrate, etc.)
    """

    def __init__(self, title, description, defaultButton, otherButton):
        super(ChoiceDialog, self).__init__(title, description,
                [defaultButton, otherButton])

class ThreeChoiceDialog(Dialog):
    """Give the user a choice of 3 options (e.g. Remove entry/
    Delete file/Cancel).
    """

    def __init__(self, title, description, defaultButton, secondButton,
            thirdButton):
        super(ThreeChoiceDialog, self).__init__(title, description,
                [defaultButton, secondButton, thirdButton])

class HTTPAuthDialog(Dialog):
    """Ask for a username and password for HTTP authorization.  Frontends
    should create a dialog with text entries for a username and password.  Use
    prefillUser and prefillPassword for the initial values of the entries.

    The buttons are always BUTTON_OK and BUTTON_CANCEL.
    """

    def __init__(self, url, realm, prefillUser=None, prefillPassword=None):
        desc = 'location %s requires a username and password for "%s".'  % \
                (url, realm)
        super(HTTPAuthDialog, self).__init__("Login Required", desc,
                (BUTTON_OK, BUTTON_CANCEL))
        self.prefillUser = prefillUser
        self.prefillPassword = prefillPassword

    def runCallback(self, choice, username='', password=''):
        self.username = username
        self.password = password
        super(HTTPAuthDialog, self).runCallback(choice)

class TextEntryDialog(Dialog):
    """Like the ChoiceDialog, but also contains a textbox for the user to
    enter a value into.  This is used for things like the create playlist
    dialog, the rename dialog, etc.
    """

    def __init__(self, title, description, defaultButton, otherButton, prefillCallback=None, fillWithClipboardURL=False):
        super(TextEntryDialog, self).__init__(title, description,
                [defaultButton, otherButton])
        self.prefillCallback = prefillCallback
        self.fillWithClipboardURL = fillWithClipboardURL

    def runCallback(self, choice, value=None):
        self.value = value
        super(TextEntryDialog, self).runCallback(choice)

class CheckboxDialog(Dialog):
    """Like the ChoiceDialog, but also contains a checkbox for the user to
    enter a value into.  This is used for things like asking whether to show
    the dialog again.  There's also a mesage for the checkbox and an initial
    value.
    """

    def __init__(self, title, description, checkbox_text, checkbox_value, defaultButton, otherButton):
        super(CheckboxDialog, self).__init__(title, description,
                [defaultButton, otherButton])
        self.checkbox_text = checkbox_text
        self.checkbox_value = checkbox_value

    def runCallback(self, choice, checkbox_value=False):
        self.checkbox_value = checkbox_value
        super(CheckboxDialog, self).runCallback(choice)

class CheckboxTextboxDialog(CheckboxDialog):
    """Like CheckboxDialog but also with a text area. Used for
    capturing bug report data"""

    def __init__(self, title, description, checkbox_text,
        checkbox_value, textbox_value, defaultButton, otherButton):
        super(CheckboxTextboxDialog, self).__init__(title, description,
                                                    checkbox_text,
                                                    checkbox_value,
                                                    defaultButton,
                                                    otherButton)
        self.textbox_value = textbox_value

    def runCallback(self, choice, checkbox_value=False, textbox_value=""):
        self.textbox_value = textbox_value
        super(CheckboxTextboxDialog, self).runCallback(choice, checkbox_value)
