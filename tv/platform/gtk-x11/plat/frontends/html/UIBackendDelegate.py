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

import os
import signal
import sys
import gobject
import gtk
import threading
import traceback
from miro import app
from miro import dialogs
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
import re
import MainFrame
from miro.plat import resources
from miro import feed
from miro import util
from miro import views
from miro import indexes
import logging

from miro import config
from miro import prefs
from miro.plat.frontends.html.gtk_queue import gtkAsyncMethod
from miro.plat.frontends.html import startup

###############################################################################
#### 'Delegate' objects for asynchronously asking the user questions       ####
###############################################################################

dialogParent = None

def asUTF8(string):
    if type(string) == unicode:
        return string.encode("utf8", "replace")
    else:
        return string

inKDE = None
def checkKDE():
    global inKDE
    if inKDE is None:
        inKDE = False
        try:
            if (os.environ["KDE_FULL_SESSION"]):
                inKDE = True
        except:
            pass
    return inKDE
# Copied from feed.py and modified for edge cases.
# URL validitation and normalization
def validateFeedURL(url):
    return re.match(r"^(http|https)://[^/]+/.*", url) is not None

def normalizeFeedURL(url):
    if url is None:
        return url
    # Valid URL are returned as-is
    if validateFeedURL(url):
        return url

    originalURL = url
    
    # Check valid schemes with invalid separator
    match = re.match(r"^(http|https):/*(.*)$", url)
    if match is not None:
        url = "%s://%s" % match.group(1,2)

    # Replace invalid schemes by http
    match = re.match(r"^(([A-Za-z]*):/*)*(.*)$", url)
    if match is not None and match.group(2) in ['feed', 'podcast', None]:
        url = "http://%s" % match.group(3)
    elif match is not None and match.group(1) == 'feeds':
        url = "https://%s" % match.group(3)

    # Make sure there is a leading / character in the path
    match = re.match(r"^(http|https)://[^/]*$", url)
    if match is not None:
        url = url + "/"

    if not validateFeedURL(url):
        return None
    else:
        return url

def EscapeMessagePart(message_part):
    if '&' in message_part or '<' in message_part:
        message_part = message_part.replace ("&", "&amp;")
        message_part = message_part.replace ("<", "&lt;")
    return message_part

def BuildDialog (title, message, buttons, default):
    flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
    dialog = gtk.Dialog(title, dialogParent, flags, buttons)
    dialog.myvbox = gtk.VBox()
    dialog.myvbox.set_border_width(6)
    dialog.vbox.add(dialog.myvbox)
    dialog.myvbox.show()

    dialog.set_default_size(425, -1)
    label = gtk.Label()
    label.set_line_wrap(True)
    label.set_selectable(True)
    label.set_markup(message)
    label.set_padding (6, 6)
    dialog.myvbox.add(label)
    label.show()
    dialog.set_default_response (default)
    return dialog

def BuildTextEntryDialog(title, message, buttons, default, prefillCallback, fillWithClipboardURL):
    dialog = BuildDialog(title, message, buttons, default)
    dialog.entry = gtk.Entry()
    dialog.entry.set_activates_default(True)
    dialog.myvbox.add(dialog.entry)
    
    prefill = None
    if fillWithClipboardURL:
        global clipboard
        global primary
        init_clipboard()
        prefill = primary.wait_for_text()
        prefill = normalizeFeedURL(prefill)
        if prefill is None:
            prefill = clipboard.wait_for_text()
            prefill = normalizeFeedURL(prefill)
    if prefill is None and prefillCallback:
        prefill = prefillCallback()
        if prefill == "":
            prefill = None
    if prefill:
        dialog.entry.set_text(prefill)
    dialog.entry.show()
    return dialog

def BuildCheckboxDialog(title, message, checkbox_text, buttons, default, checkbox_value):
    dialog = BuildDialog(title, message, buttons, default)
    alignment = gtk.Alignment(.5, 0, 0, 0)
    dialog.myvbox.add(alignment)
    alignment.show()
    dialog.checkbox = gtk.CheckButton(checkbox_text)
    dialog.checkbox.set_active (checkbox_value)
    alignment.add(dialog.checkbox)
    dialog.checkbox.show()
    return dialog

def BuildCheckboxTextboxDialog(title, message, checkbox_text, buttons, default, checkbox_value, textbox_value):
    dialog = BuildCheckboxDialog(title, message, checkbox_text, buttons, default, checkbox_value)
    dialog.textbox = gtk.TextView()
    dialog.scrollWindow = gtk.ScrolledWindow()
    dialog.scrollWindow.set_policy(gtk.POLICY_AUTOMATIC,gtk.POLICY_AUTOMATIC)
    dialog.scrollWindow.add(dialog.textbox)
    dialog.scrollWindow.set_shadow_type(gtk.SHADOW_IN)
    
    textbuffer = dialog.textbox.get_buffer();
    textbuffer.set_text(textbox_value)
    dialog.textbox.set_editable(True)
    dialog.myvbox.add(dialog.scrollWindow)
    dialog.textbox.show()
    dialog.scrollWindow.show()
    return dialog

def BuildHTTPAuth(summary, message, prefillUser = None, prefillPassword = None):
    """Ask the user for HTTP login information for a location, identified
    to the user by its URL and the domain string provided by the
    server requesting the authorization. Default values can be
    provided for prefilling the form. If the user submits
    information, it's returned as a (user, password)
    tuple. Otherwise, if the user presses Cancel or similar, None
    is returned."""
    dialog = gtk.Dialog(summary, None, (), (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
    dialog.set_default_size(425, -1)
    table = gtk.Table()
    dialog.vbox.add(table)
    
    label = gtk.Label()
    label.set_line_wrap(True)
    label.set_selectable(True)
    label.set_markup(message)
    label.set_padding (6, 6)
    table.attach (label, 0, 2, 0, 1, gtk.FILL, gtk.FILL)

    label = gtk.Label()
    label.set_markup(_("Username:"))
    label.set_padding (6, 6)
    label.set_alignment (1.0, 0.5)
    table.attach (label, 0, 1, 1, 2, gtk.FILL, gtk.FILL)

    dialog.user = gtk.Entry()
    if (prefillUser != None):
        dialog.user.set_text(prefillUser)
    table.attach (dialog.user, 1, 2, 1, 2, gtk.FILL | gtk.EXPAND, gtk.FILL, 6, 6)

    label = gtk.Label()
    label.set_markup(_("Password:"))
    label.set_padding (6, 6)
    label.set_alignment (1.0, 0.5)
    table.attach (label, 0, 1, 2, 3, gtk.FILL, gtk.FILL)

    dialog.password = gtk.Entry()
    dialog.password.set_visibility(False)
    dialog.password.set_activates_default(True)
    if (prefillPassword != None):
        dialog.password.set_text(prefillPassword)
    table.attach (dialog.password, 1, 2, 2, 3, gtk.FILL | gtk.EXPAND, gtk.FILL, 6, 6)

    table.show_all()
    dialog.set_default_response (gtk.RESPONSE_OK)
    return dialog

def BuildSearchChannelDialog(dialog):
    widgetTree = MainFrame.WidgetTree(resources.path('miro.glade'), 'dialog-search', 'miro')
    gtkDialog = widgetTree['dialog-search']
    gtkDialog.set_data("glade", widgetTree)
    channel_id = -1
    engine_name = dialog.defaultEngine
#    mainWindow = self.mainFrame.widgetTree['main-window']
#    gtkDialog.set_transient_for(mainWindow)

    if dialog.style == dialog.CHANNEL:
        widgetTree["radiobutton-search-channel"].set_active(True)
        if dialog.location is not None:
            channel_id = dialog.location
    elif dialog.style == dialog.ENGINE:
        widgetTree["radiobutton-search-engine"].set_active(True)
        if dialog.location is not None:
            engine_name = str(dialog.location)
    elif dialog.style == dialog.URL:
        widgetTree["radiobutton-search-url"].set_active(True)
        if dialog.location:
            widgetTree["entry-search-url"].set_text(dialog.location)

    if dialog.term:
        widgetTree["entry-search-term"].set_text(dialog.term)

    def connect_sensitive (toggle, widget):
        toggle = widgetTree[toggle]
        widget = widgetTree[widget]
        def toggled(*args):
            widget.set_sensitive(toggle.get_active())
        toggle.connect("toggled", toggled)
        toggled()
    connect_sensitive ("radiobutton-search-channel", "combobox-search-channel")
    connect_sensitive ("radiobutton-search-engine", "combobox-search-engine")
    connect_sensitive ("radiobutton-search-url", "entry-search-url")

    store = gtk.ListStore(gobject.TYPE_INT, gobject.TYPE_STRING)
    select_iter = None
    for id, title in dialog.channels:
        iter = store.append((id, title))
        if select_iter is None or channel_id == id:
            select_iter = iter
    cell = gtk.CellRendererText()
    combo = widgetTree["combobox-search-channel"]
    combo.pack_start(cell, True)
    combo.add_attribute(cell, 'text', 1)
    combo.set_model (store)
    combo.set_active_iter(select_iter)

    store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
    select_iter = None
    for name, title in dialog.engines:
        iter = store.append((name, title))
        if select_iter is None or engine_name == name:
            select_iter = iter
    cell = gtk.CellRendererText()
    combo = widgetTree["combobox-search-engine"]
    combo.pack_start(cell, True)
    combo.add_attribute(cell, 'text', 1)
    combo.set_model (store)
    combo.set_active_iter(select_iter)

    return gtkDialog


once_dialogs = {}

@gtkAsyncMethod
def ShowDialogAsync (title, message, buttons, default = gtk.RESPONSE_CANCEL, once=None, callback=None):

    def AsyncDialogResponse(dialog, response):
        if callback:
            callback (response)
        dialog.destroy()

    def AsyncDialogDestroy (dialog):
        try:
            del once_dialogs[once]
        except:
            pass

    if once is not None and once_dialogs.has_key (once):
        return
    dialog = BuildDialog (title, message, buttons, default)
    dialog.connect("response", AsyncDialogResponse)
    dialog.connect("destroy", AsyncDialogDestroy)
    dialog.show()
    if once is not None:
        once_dialogs[once] = dialog

_stock = { dialogs.BUTTON_OK.text : gtk.STOCK_OK,
           dialogs.BUTTON_CANCEL.text : gtk.STOCK_CANCEL,
           dialogs.BUTTON_YES.text : gtk.STOCK_YES,
           dialogs.BUTTON_NO.text : gtk.STOCK_NO,
           dialogs.BUTTON_QUIT.text : gtk.STOCK_QUIT}

@gtkAsyncMethod
def ShowHTTPAuthDialogAsync(title, description, prefillUser, prefillPassword,
        callback):
    gtkDialog = BuildHTTPAuth (title, description, prefillUser,
            prefillPassword)
    gtkDialog.connect("response", callback)
    gtkDialog.show()

@gtkAsyncMethod
def ShowSearchChannelDialogAsync(dialog, callback):
    gtkDialog = BuildSearchChannelDialog (dialog)
    gtkDialog.connect("response", callback)
    gtkDialog.show()

@gtkAsyncMethod
def ShowTextEntryDialogAsync(title, description, buttons, default, prefillCallback, fillWithClipboardURL, callback):
    gtkDialog = BuildTextEntryDialog (title, description, buttons, default, prefillCallback, fillWithClipboardURL)
    gtkDialog.connect("response", callback)
    gtkDialog.show()

@gtkAsyncMethod
def ShowCheckboxDialogAsync(title, description, checkbox_text, buttons, default, checkbox_value, callback):
    gtkDialog = BuildCheckboxDialog (title, description, checkbox_text, buttons, default, checkbox_value)
    gtkDialog.connect("response", callback)
    gtkDialog.show()

@gtkAsyncMethod
def ShowCheckboxTextboxDialogAsync(title, description, checkbox_text, buttons, default, checkbox_value, textbox_value, callback):
    gtkDialog = BuildCheckboxTextboxDialog (title, description, checkbox_text, buttons, default, checkbox_value, textbox_value)
    gtkDialog.connect("response", callback)
    gtkDialog.show()


clipboard = None
primary = None

def init_clipboard ():
    global clipboard
    global primary
    if clipboard is None:
        clipboard = gtk.Clipboard(selection="CLIPBOARD")
    if primary is None:
        primary = gtk.Clipboard(selection="PRIMARY")

class UIBackendDelegate:

    def maximizeWindow(self):
        logging.warn("UIBackendDelegate.maximizeWindow() not implemented")

    def performStartupTasks(self, terminationCallback):
        startup.performStartupTasks(terminationCallback)
        
    def openExternalURL(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        if (checkKDE()):
            os.spawnlp (os.P_NOWAIT, "kfmclient", "kfmclient", "exec", url)
        else:
            os.spawnlp (os.P_NOWAIT, "gnome-open", "gnome-open", url)

    def revealFile(self, filename):
        if not os.path.isdir(filename):
            filename = os.path.dirname(filename)
        if (checkKDE()):
            os.spawnlp (os.P_NOWAIT, "kfmclient", "kfmclient", "exec", "file://" + filename)
        else:
            os.spawnlp (os.P_NOWAIT, "nautilus", "nautilus", "file://" + filename)

    def notifyDownloadCompleted(self, item):
        pass

    def notifyDownloadFailed(self, item):
        pass

    def updateAvailableItemsCountFeedback(self, count):
        # Inform the user in a way or another that newly available items are
        # available
        pass

    def notifyUnkownErrorOccurence(self, when, log = ''):
        if config.get(prefs.SHOW_ERROR_DIALOG):
            summary = _("Unknown Runtime Error")
            message = _("An unknown error has occurred %s.") % (EscapeMessagePart(when),)
            buttons = (gtk.STOCK_CLOSE, gtk.RESPONSE_OK)
            ShowDialogAsync (summary, message, buttons, once="UnknownError")
        return True

    def makeButtonTuple (self, dialog):
        """Given a dialog object, make a tuple of button/id pairs to pass to
        the gtk.Dialog constructor.
        """

        buttons = []
        i = 0
        for button in dialog.buttons:
            if _stock.has_key(button.text):
                buttons [0:0] = (_stock[button.text], i)
            else:
                buttons [0:0] = (asUTF8 (button.text), i)
            i = i + 1
        return tuple(buttons)

    def runDialog (self, dialog):
        if isinstance(dialog, dialogs.ChoiceDialog) or isinstance(dialog, dialogs.MessageBoxDialog) or isinstance(dialog, dialogs.ThreeChoiceDialog):
            def Callback (response):
                if response == gtk.RESPONSE_DELETE_EVENT:
                    dialog.runCallback (None)
                elif response >= 0 and response < len(dialog.buttons):
                    dialog.runCallback (dialog.buttons [response])
                else:
                    dialog.runCallback (None)
    
            ShowDialogAsync (EscapeMessagePart(dialog.title), EscapeMessagePart(dialog.description), self.makeButtonTuple(dialog), default=0, callback = Callback)
        elif isinstance(dialog, dialogs.HTTPAuthDialog):
            def AsyncDialogResponse(gtkDialog, response):
                retval = None
                if (response == gtk.RESPONSE_OK):
                    dialog.runCallback(dialogs.BUTTON_OK, gtkDialog.user.get_text().decode('utf8', 'replace'), gtkDialog.password.get_text().decode('utf8', 'replace'))
                else:
                    dialog.runCallback(None)
                gtkDialog.destroy()

            ShowHTTPAuthDialogAsync(EscapeMessagePart(dialog.title),
                    EscapeMessagePart(dialog.description), dialog.prefillUser,
                    dialog.prefillPassword, callback=AsyncDialogResponse)
        elif isinstance(dialog, dialogs.TextEntryDialog):
            def AsyncDialogResponse(gtkDialog, response):
                retval = None
                if response == gtk.RESPONSE_DELETE_EVENT:
                    dialog.runCallback (None)
                elif response >= 0 and response < len(dialog.buttons):
                    dialog.runCallback (dialog.buttons [response], gtkDialog.entry.get_text().decode('utf8', 'replace'))
                else:
                    dialog.runCallback (None)
                gtkDialog.destroy()

            ShowTextEntryDialogAsync (EscapeMessagePart(dialog.title), EscapeMessagePart(dialog.description), self.makeButtonTuple(dialog), default=0,
                                      prefillCallback=dialog.prefillCallback, fillWithClipboardURL=dialog.fillWithClipboardURL,
                                      callback = AsyncDialogResponse)
        elif isinstance(dialog, dialogs.CheckboxTextboxDialog):
            def AsyncDialogResponse(gtkDialog, response):
                retval = None
                if response == gtk.RESPONSE_DELETE_EVENT:
                    dialog.runCallback (None)
                elif response >= 0 and response < len(dialog.buttons):
                    dialog.runCallback (dialog.buttons [response], gtkDialog.checkbox.get_active(), gtkDialog.textbox.get_buffer().get_text(gtkDialog.textbox.get_buffer().get_start_iter(),gtkDialog.textbox.get_buffer().get_end_iter()))
                else:
                    dialog.runCallback (None)
                gtkDialog.destroy()

            ShowCheckboxTextboxDialogAsync (EscapeMessagePart(dialog.title), EscapeMessagePart(dialog.description), EscapeMessagePart(dialog.checkbox_text), self.makeButtonTuple(dialog), default=0,
                                     checkbox_value = dialog.checkbox_value,
                                     textbox_value = EscapeMessagePart(dialog.textbox_value),
                                     callback = AsyncDialogResponse)
        elif isinstance(dialog, dialogs.CheckboxDialog):
            def AsyncDialogResponse(gtkDialog, response):
                retval = None
                if response == gtk.RESPONSE_DELETE_EVENT:
                    dialog.runCallback (None)
                elif response >= 0 and response < len(dialog.buttons):
                    dialog.runCallback (dialog.buttons [response], gtkDialog.checkbox.get_active())
                else:
                    dialog.runCallback (None)
                gtkDialog.destroy()

            ShowCheckboxDialogAsync (EscapeMessagePart(dialog.title), EscapeMessagePart(dialog.description), EscapeMessagePart(dialog.checkbox_text), self.makeButtonTuple(dialog), default=0,
                                     checkbox_value = dialog.checkbox_value,
                                     callback = AsyncDialogResponse)
        elif isinstance(dialog, dialogs.SearchChannelDialog):
            def AsyncDialogResponse(gtkDialog, response):
                retval = None
                widgetTree = gtkDialog.get_data("glade")
                dialog.term = widgetTree["entry-search-term"].get_text()
                if widgetTree["radiobutton-search-channel"].get_active():
                    dialog.style = dialog.CHANNEL
                    iter = widgetTree["combobox-search-channel"].get_active_iter()
                    if iter is None:
                        dialog.location = None
                    else:
                        (dialog.location,) = widgetTree["combobox-search-channel"].get_model().get(iter, 0)
                elif widgetTree["radiobutton-search-engine"].get_active():
                    dialog.style = dialog.ENGINE
                    iter = widgetTree["combobox-search-engine"].get_active_iter()
                    if iter is None:
                        dialog.location = None
                    else:
                        (dialog.location,) = widgetTree["combobox-search-engine"].get_model().get(iter, 0)
                elif widgetTree["radiobutton-search-url"].get_active():
                    dialog.style = dialog.URL
                    dialog.location = widgetTree["entry-search-url"].get_text()

                if (response == gtk.RESPONSE_OK):
                    dialog.runCallback(dialogs.BUTTON_CREATE_CHANNEL)
                elif (response == gtk.RESPONSE_CANCEL):
                    dialog.runCallback(dialogs.BUTTON_CANCEL)
                else:
                    dialog.runCallback(None)
                gtkDialog.destroy()

            ShowSearchChannelDialogAsync(dialog, callback=AsyncDialogResponse)
        else:
            dialog.runCallback (None)


    def askForOpenPathname(self, title, callback, defaultDirectory=None,
            typeString=None, types=None):
        dialog = gtk.FileSelection("File Selection")
        def okButton(w):
            print dialog.get_filename()
            callback(dialog.get_filename())
            dialog.destroy()
        dialog.ok_button.connect("clicked", okButton)
        dialog.cancel_button.connect("clicked", lambda w: dialog.destroy())
        if defaultDirectory is not None:
            dialog.set_filename(defaultDirectory)
        dialog.show()

    def askForSavePathname(self, title, callback, defaultDirectory=None, 
            defaultFilename=None):
        dialog = gtk.FileSelection("File Selection")
        def okButton(w):
            print dialog.get_filename()
            callback(dialog.get_filename())
            dialog.destroy()
        dialog.ok_button.connect("clicked", okButton)
        dialog.cancel_button.connect("clicked", lambda w: dialog.destroy())
        if defaultFilename is not None:
            dialog.set_filename(defaultFilename)
        dialog.show()


    @gtkAsyncMethod
    def showContextMenu(self, menuItems):
        menu = gtk.Menu()
        for item in menuItems:
            if item.label:
                gtkitem = gtk.MenuItem(item.label)
                if item.callback is not None:
                    gtkitem.connect("activate", 
                            lambda foo, item=item: item.activate())
                else:
                    gtkitem.set_sensitive(False)
            else:
                gtkitem = gtk.SeparatorMenuItem()
            menu.append(gtkitem)
            gtkitem.show()
        menu.show()
        gobject.timeout_add(100, lambda: menu.popup(None, None, None,
            gtk.gdk.RIGHTBUTTON, 0))

    @gtkAsyncMethod
    def copyTextToClipboard(self, text):
        global clipboard
        global primary
        init_clipboard()
        clipboard.set_text(text)
        primary.set_text(text)
