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

from miro.plat.utils import filenameToUnicode

def matchingItems(obj, searchString):
    """Returns items that match search
    """
    from miro import search
    if searchString is None:
        return True
    searchString = searchString.lower()
    title = obj.get_title() or u''
    desc = obj.get_raw_description() or u''
    filename = filenameToUnicode(obj.get_filename()) or u''
    if search.match(searchString, [title.lower(), desc.lower(), filename.lower()]):
        return True
    if not obj.isContainerItem:
        parent = obj.getParent()
        if parent != obj:
            return matchingItems(parent, searchString)
    return False

def downloadingItems(obj):
    return obj.get_state() == 'downloading'

def downloadingOrPausedItems(obj):
    return obj.get_state() in ('downloading', 'paused') or obj.is_uploading() or obj.is_uploading_paused()

def unwatchedItems(obj):
    return obj.get_state() == 'newly-downloaded' and not obj.is_nonvideo_file()

def expiringItems(obj):
    return obj.get_state() == 'expiring' and not obj.is_nonvideo_file()

def watchableItems(obj):
    return (obj.is_downloaded() and not obj.is_nonvideo_file() and
            not obj.isContainerItem and not obj.getFeedURL() == 'dtv:singleFeed')

def manualItems(obj):
    return obj.getFeedURL() == 'dtv:manualFeed' and not downloadingOrPausedItems(obj)

def searchItems(obj):
    return obj.getFeedURL() == 'dtv:search'

def allDownloadingItems(obj):
    return downloadingOrPausedItems(obj)

def autoUploadingDownloaders(obj):
    return obj.get_state() == 'uploading' and not obj.manualUpload

def notDeleted(obj):
    from miro import item
    return not (isinstance(obj, item.FileItem) and obj.deleted)

def newItems(obj):
    """This is "new" for the channel template
    """
    return not obj.get_viewed()

def newWatchableItems(obj):
    return (obj.is_downloaded() and not obj.is_nonvideo_file()
            and (obj.get_state() == u"newly-downloaded"))

def mappableToTab(obj):
    """Return True if a tab should be shown for obj in the frontend. The filter
    used on the database to get the list of tabs.
    """
    from miro import feed
    from miro import folder
    from miro import playlist
    from miro import guide
    return ((isinstance(obj, feed.Feed) and obj.isVisible()) or
            obj.__class__ in (
                folder.ChannelFolder, playlist.SavedPlaylist,
                folder.PlaylistFolder, guide.ChannelGuide))

def feedIsVisible(obj):
    return obj.isVisible()

def autoDownloads(item):
    return item.getAutoDownloaded() and downloadingOrPausedItems(item)

def manualDownloads(item):
    return not item.getAutoDownloaded() and not item.is_pending_manual_download() and item.get_state() == 'downloading'

def uniqueItems(item):
    try:
        return item.downloader.itemList[0] == item
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        return True

def watchedFolders(feed):
    return feed.url.startswith("dtv:directoryfeed:")
