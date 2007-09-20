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

from gettext import gettext as _

import app
import eventloop
import tabs

def makeMenu(items):
    """Convenience function to create a list of MenuItems given on a list of
    (callback, label) tuples.
    """

    return [MenuItem(callback, label) for callback, label in items]

class MenuItem:
    """A single menu item in a context menu.

    Normally frontends should display label as the text for this menu item,
    and if it's clicked on call activate().  One second case is if label is
    blank, in which case a separator should be show.  Another special case is
    if callback is None, in which case the label should be shown, but it
    shouldn't be clickable.  
    
    """

    def __init__(self, callback, label):
        self.label = label
        self.callback = callback

    def activate(self):
        """Run this menu item's callback in the backend event loop."""

        eventloop.addUrgentCall(self.callback, "context menu callback")

def makeContextMenu(templateName, view, selection, clickedID):
    if len(selection.currentSelection) == 1:
        obj = selection.getObjects()[0]
        if isinstance(obj, tabs.Tab):
            obj = obj.obj
        return obj.makeContextMenu(templateName, view)
    else:
        type = selection.getType()
        objects = selection.getObjects()
        if type == 'item':
            return makeMultiItemContextMenu(templateName, view, objects,
                    clickedID)
        elif type == "playlisttab":
            return makeMenu([
                (app.controller.removeCurrentPlaylist, _('Remove')),
            ])
        elif type == "channeltab":
            return makeMenu([
                (app.controller.updateCurrentFeed, _('Update Channels Now')),
                (app.controller.removeCurrentFeed, _('Remove')),
            ])
        else:
            return None

def makeMultiItemContextMenu(templateName, view, selectedItems, clickedID):
    c = app.controller # easier/shorter to type
    watched = unwatched = downloaded = downloading = available = uploadable = 0
    for i in selectedItems:
        if i.getState() == 'downloading':
            downloading += 1
        elif i.isDownloaded():
            if i.downloader and i.downloader.getState() == 'finished' and i.downloader.getType() == 'bittorrent':
                uploadable += 1
            downloaded += 1
            if i.getSeen():
                watched += 1
            else:
                unwatched += 1
        else:
            available += 1

    items = []
    if downloaded > 0:
        items.append((None, _('%d Downloaded Items') % downloaded))
        items.append((lambda: c.playView(view, clickedID),
            _('Play')))
        items.append((c.addToNewPlaylist, _('Add to new playlist')))
        if templateName in ('playlist', 'playlist-folder'):
            label = _('Remove From Playlist')
        else:
            label = _('Remove From the Library')
        items.append((c.removeCurrentItems, label))
        if watched:
            def markAllUnseen():
                for item in selectedItems:
                    item.markItemUnseen()
            items.append((markAllUnseen, _('Mark as Unwatched')))
        if unwatched:
            def markAllSeen():
                for item in selectedItems:
                    item.markItemSeen()
            items.append((markAllSeen, _('Mark as Watched')))

    if available > 0:
        if len(items) > 0:
            items.append((None, ''))
        items.append((None, _('%d Available Items') % available))
        items.append((app.controller.downloadCurrentItems, _('Download')))

    if downloading:
        if len(items) > 0:
            items.append((None, ''))
        items.append((None, _('%d Downloading Items') % downloading))
        items.append((app.controller.stopDownloadingCurrentItems, 
            _('Cancel Download')))
        items.append((app.controller.pauseDownloadingCurrentItems, 
            _('Pause Download')))

    if uploadable > 0:
        items.append((c.startUploads, _('Restart Upload')))

    return makeMenu(items)
