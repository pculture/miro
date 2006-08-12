from gettext import gettext as _

import app
import dialogs
from database import DDBObject
from databasehelper import makeSimpleGetSet

class ChannelFolder(DDBObject):
    def __init__(self, title):
	self.title = title
        self.expanded = False
	DDBObject.__init__(self)

    getTitle, setTitle = makeSimpleGetSet('title')
    getExpanded, setExpanded = makeSimpleGetSet('expanded')

    def rename(self):
        title = _("Rename Channel Folder")
        description = _("Enter a new name for the channel folder %s" % self.getTitle())
        def callback(dialog):
            if self.idExists() and dialog.choice == dialogs.BUTTON_OK:
                self.setTitle(dialog.value)
        dialogs.TextEntryDialog(title, description, dialogs.BUTTON_OK,
                dialogs.BUTTON_CANCEL).run(callback)

class PlaylistFolder(DDBObject):
    def __init__(self, title):
	self.title = title
        self.expanded = False
	DDBObject.__init__(self)

    getTitle, setTitle = makeSimpleGetSet('title')
    getExpanded, setExpanded = makeSimpleGetSet('expanded')

    def rename(self):
        title = _("Rename Playlist Folder")
        description = _("Enter a new name for the playlist folder %s" % self.getTitle())
        def callback(dialog):
            if self.idExists() and dialog.choice == dialogs.BUTTON_OK:
                self.setTitle(dialog.value)
        dialogs.TextEntryDialog(title, description, dialogs.BUTTON_OK,
                dialogs.BUTTON_CANCEL).run(callback)

def createNewChannelFolder():
    title = _("Create Channel Folder")
    description = _("Enter a name for the new channel folder")

    def callback(dialog):
        if dialog.choice == dialogs.BUTTON_CREATE:
            playlist = ChannelFolder(dialog.value)
            app.controller.selection.selectTabByObject(playlist)

    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)

def createNewPlaylistFolder():
    title = _("Create Playlist Folder")
    description = _("Enter a name for the new playlist folder")

    def callback(dialog):
        if dialog.choice == dialogs.BUTTON_CREATE:
            playlist = PlaylistFolder(dialog.value)
            app.controller.selection.selectTabByObject(playlist)

    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)
