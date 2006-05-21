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

import eventloop
import app

class DialogButton(object):
    def __init__(self, text):
        self.text = text
    def __eq__(self, other):
        return isinstance(other, DialogButton) and self.text == other.text
    def __str__(self):
        return "DialogButton(%r)" % self.text

BUTTON_OK = DialogButton("Ok")
BUTTON_CANCEL = DialogButton("Cancel")
BUTTON_YES = DialogButton("Yes")
BUTTON_NO = DialogButton("No")
BUTTON_MIGRATE = DialogButton("Migrate")
BUTTON_DONT_MIGRATE = DialogButton("Don't Migrate")

class Dialog(object):
    """Abstract base class for dialogs."""

    def __init__(self, title, description, buttons):
        self.title = title
        self.description = description
        self.buttons = buttons

    def run(self, callback):
        self.callback = callback
        self.choice = None
        try:
            app.controller.getBackendDelegate().runDialog(self)
        except:
            import traceback
            print "WARNING, exception in runDialog()"
            traceback.print_exc()
            self.runCallback(None)

    def runCallback(self, choice):
        """Run the callback for this dialog.  Choice should be the button that
        the user clicked, or None if the user closed the window without
        makeing a selection.
        """

        self.choice = choice
        eventloop.addIdle(self.callback, "%s callback" % self.__class__, 
                args=(self,))

class ChoiceDialog(Dialog):
    """Give the user a choice of 2 options (Yes/No, Ok/Cancel,
    Migrate/Don't Migrate, etc.)
    """

    def __init__(self, title, description, defaultButton, otherButton):
        super(ChoiceDialog, self).__init__(title, description,
                [defaultButton, otherButton])

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
