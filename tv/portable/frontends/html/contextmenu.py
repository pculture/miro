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

from gettext import gettext as _
import logging

from miro import app
from miro import eventloop
from miro import feed
from miro import folder
from miro import guide
from miro import item
from miro import playlist
from miro import tabs

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

def makeObjectContextMenu(obj, templateName, view):
    menuFunctions = {
        feed.Feed: makeFeedContextMenu,
        folder.ChannelFolder: makeChannelFolderContextMenu,
        playlist.SavedPlaylist: makePlaylistContextMenu,
        folder.PlaylistFolder: makePlaylistFolderContextMenu,
        guide.ChannelGuide: makeGuideContextMenu,
        item.Item: makeItemContextMenu,
        item.FileItem: makeItemContextMenu,
    }
    try:
        menuFunction = menuFunctions[obj.__class__]
    except KeyError:
        logging.warn("Don't know how to make a menu item for %s (class: %s)",
                obj, obj.__class__)
    else:
        return menuFunction(obj, templateName, view)

def makeContextMenu(templateName, view, selection, clickedID):
    if len(selection.currentSelection) == 1:
        obj = selection.getObjects()[0]
        if isinstance(obj, tabs.Tab):
            obj = obj.obj
        return makeObjectContextMenu(obj, templateName, view)
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
    watched = unwatched = downloaded = downloading = available = uploadable = 0
    for i in selectedItems:
        if i.getState() == 'downloading':
            downloading += 1
        elif i.isDownloaded():
            if (i.downloader
                    and i.downloader.getState() in ('finished', 'uploading-paued')
                    and i.downloader.getType() == 'bittorrent'):
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
        items.append((lambda: app.htmlapp.playView(view, clickedID),
            _('Play')))
        items.append((app.controller.addToNewPlaylist, _('Add to new playlist')))
        if templateName in ('playlist', 'playlist-folder'):
            label = _('Remove From Playlist')
        else:
            label = _('Remove From the Library')
        items.append((app.controller.removeCurrentItems, label))
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
        items.append((app.controller.startUploads, _('Restart Upload')))

    return makeMenu(items)

def makeFeedContextMenu(feedObj, templateName, view):
    items = [
        (feedObj.update, _('Update Channel Now')),
        (lambda: app.delegate.copyTextToClipboard(feedObj.getURL()),
            _('Copy URL to clipboard')),
        (feedObj.rename, _('Rename Channel')),
    ]

    if feedObj.userTitle:
        items.append((feedObj.unsetTitle, _('Revert Title to Default')))
    items.append((lambda: app.controller.removeFeed(feedObj), _('Remove')))
    return makeMenu(items)

def makeChannelFolderContextMenu(folderObj, templateName, view):
    return makeMenu([
        (folderObj.rename, _('Rename Channel Folder')),
        (lambda: app.controller.removeFeed(folderObj), _('Remove')),
    ])

def makePlaylistFolderContextMenu(folderObj, templateName, view):
    return makeMenu([
        (folderObj.rename, _('Rename Playlist Folder')),
        (lambda: app.controller.removePlaylist(folderObj), _('Remove')),
    ])

def makeGuideContextMenu(guideObj, templateName, view):
    menuItems = [
        (lambda: app.delegate.copyTextToClipboard(guideObj.getURL()),
            _('Copy URL to clipboard')),
    ]
    if not guideObj.getDefault():
        menuItems.append((lambda: app.controller.renameGuide(guideObj), _('Rename')))
        menuItems.append((lambda: app.controller.removeGuide(guideObj), _('Remove')))
    return makeMenu(menuItems)

def makeItemContextMenu(itemObj, templateName, view):
    if itemObj.isDownloaded():
        if templateName in ('playlist', 'playlist-folder'):
            label = _('Remove From Playlist')
        else:
            label = _('Remove From the Library')
        items = [
            (lambda: app.htmlapp.playView(view, itemObj.getID()), _('Play')),
            (lambda: app.htmlapp.playView(view, itemObj.getID(), True), 
                _('Play Just This Video')),
            (app.controller.addToNewPlaylist, _('Add to new playlist')),
            (app.controller.removeCurrentItems, label),
        ]
        if itemObj.getSeen():
            items.append((itemObj.markItemUnseen, _('Mark as Unwatched')))
        else:
            items.append((itemObj.markItemSeen, _('Mark as Watched')))
                            
        if itemObj.downloader and itemObj.downloader.getState() == 'finished' and itemObj.downloader.getType() == 'bittorrent':
            items.append((itemObj.startUpload, _('Restart Upload')))
    elif itemObj.getState() == 'downloading':
        items = [(itemObj.expire, _('Cancel Download')), (itemObj.pause, _('Pause Download'))]
    else:
        items = [(itemObj.download, _('Download'))]
    return makeMenu(items)

def makePlaylistContextMenu(playlistObj, templateName, view):
    return makeMenu([
        (playlistObj.rename, _('Rename Playlist')),
        (lambda: app.controller.removePlaylist(playlistObj), _('Remove')),
    ])

