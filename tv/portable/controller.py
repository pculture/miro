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

"""controller.py -- Contains Controller class.  It handles high-level control
of Miro.
"""

import logging
import os
import shutil
import threading
import traceback
import urllib

# FIXME - this is icky
from miro import dialogs
from miro.frontends.widgets import dialogs as dialogsnew
from miro.frontends.widgets.displays import FeedDisplay

from miro.gtcache import gettext as _
from miro import app
from miro import config
from miro import database
from miro import downloader
from miro import download_utils
from miro import eventloop
from miro import feed
from miro import folder
from miro import guide
from miro import httpclient
from miro import iconcache
from miro import indexes
from miro import item
from miro import moviedata
from miro import playlist
from miro import prefs
from miro import signals
from miro import singleclick
from miro import util
from miro import views
from miro import databasehelper
from miro import fileutil
from miro.plat.utils import exit, osFilenameToFilenameType

from miro import messages

###############################################################################
#### The main application app.controller object, binding model to view         ####
###############################################################################
class Controller:
    def __init__(self):
        self.frame = None
        self.inQuit = False
        self.guideURL = None
        self.guide = None
        self.finishedStartup = False
        self.idlingNotifier = None
        self.gatheredVideos = None
        self.librarySearchTerm = None
        self.newVideosSearchTerm = None
        self.sendingCrashReport = 0

    def getGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        rv = feedView[0]
        feedView.unlink()
        return rv

    def removeGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        feedView.resetCursor()
        nextfeed = feedView.getNext()
        feedView.unlink()
        if nextfeed is not None:
            logging.info ("Removing global feed %s", url)
            nextfeed.remove()

    def selectAllItems(self):
        app.selection.itemListSelection.selectAll()
        app.selection.setTabListActive(False)

    def importChannels(self):
        # FIXME - implement me
        logging.info("FIXME - need a filechooser dialog")

    def exportChannels(self):
        # FIXME - implement me
        logging.info("FIXME - need a filechooser dialog")

    def mailChannel(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed' and len(channel_infos) == 1:
            ci = channel_infos[0]
            query = urllib.urlencode({"url": ci.base_href, "title": ci.name})
            emailfriend_url = config.get(prefs.EMAILFRIEND_URL)
            if not emailfriend_url.endswith("?"):
                emailfriend_url += "?"
            app.widgetapp.open_url(emailfriend_url + query)

    def copyChannelURL(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed' and len(channel_infos) == 1:
            ci = channel_infos[0]
            app.widgetapp.copy_text_to_clipboard(ci.base_href)

    def addNewChannel(self):
        title = _('Add Channel')
        description = _("Enter the URL of the channel to add:")
        text = app.widgetapp.get_clipboard_text()
        if text is not None and feed.validateFeedURL(text):
            text = feed.normalizeFeedURL(text)
        else:
            text = ""

        while 1:
            text = dialogsnew.ask_for_string(title, description, initial_text=text)
            if text == None:
                return

            normalized_url = feed.normalizeFeedURL(text)
            if feed.validateFeedURL(normalized_url):
                break

            title = _('Add Channel - Invalid URL')
            description = _("The address you entered is not a valid url.\nPlease check the URL and try again.\n\nEnter the URL of the channel to add:")

        messages.NewChannel(normalized_url).send_to_backend()

    def addNewChannelFolder(self):
        title = _('Create Channel Folder')
        description = _("Enter a name for the new channel folder:")

        name = dialogsnew.ask_for_string(title, description)
        if name:
            messages.NewChannelFolder(name).send_to_backend()

    def addNewPlaylist(self):
        # FIXME - this is really brittle.  this violates the Law of Demeter
        # in ways that should make people cry.
        try:
            t = app.display_manager.current_display
            if isinstance(t, FeedDisplay):
                t = t.view
                t = t.full_view
                t = t.item_list
                selection = [t.model[i][0] for i in t.get_selection()]
                ids = [s.id for s in selection if s.downloaded]
            else:
                ids = []
        except:
            logging.exception("addNewPlaylist exception.")
            ids = []

        title = _('Create Playlist')
        description = _("Enter a name for the new playlist")

        name = dialogsnew.ask_for_string(title, description)
        if name:
            messages.NewPlaylist(name, ids).send_to_backend()

    def addNewPlaylistFolder(self):
        title = _('Create Playlist Folder')
        description = _("Enter a name for the new playlist folder")

        name = dialogsnew.ask_for_string(title, description)
        if name:
            messages.NewPlaylistFolder(name).send_to_backend()

    def removeCurrentSelection(self):
        if app.selection.tabListActive:
            selection = app.selection.tabListSelection
        else:
            selection = app.selection.itemListSelection
        seltype = selection.getType()
        if seltype == 'channeltab':
            self.removeCurrentFeed()
        elif seltype == 'addedguidetab':
            self.removeCurrentGuide()
        elif seltype == 'playlisttab':
            self.removeCurrentPlaylist()
        elif seltype == 'item':
            self.removeCurrentItems()

    def removeCurrentFeed(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed':
            self.removeFeeds(channel_infos)

    def removeCurrentGuide(self):
        if app.selection.tabListSelection.getType() == 'addedguidetab':
            guides = [t.obj for t in app.selection.getSelectedTabs()]
            if len(guides) != 1:
                raise AssertionError("Multiple guides selected")
            self.removeGuide(guides[0])

    def removeCurrentPlaylist(self):
        t, infos = app.tab_list_manager.get_selection()
        if t == 'playlist':
            self.removePlaylists(infos)

    def removeCurrentItems(self):
        if app.selection.itemListSelection.getType() != 'item':
            return
        selected = app.selection.getSelectedItems()
        if app.selection.tabListSelection.getType() != 'playlisttab':
            removable = [i for i in selected if (i.isDownloaded() or i.isExternal()) ]
            if removable:
                item.expireItems(removable)
        else:
            playlist = app.selection.getSelectedTabs()[0].obj
            for i in selected:
                playlist.removeItem(i)

    def renameSomething(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        ci = channel_infos[0]

        if t == 'feed' and ci.is_folder:
            t = 'feed-folder'
        elif t == 'playlist' and ci.is_folder:
            t = 'playlist-folder'

        if t == 'feed-folder':
            title = _('Rename Channel Folder')
            description = _('Enter a new name for the channel folder %s') % \
                            ci.name

        elif t == 'feed' and not ci.is_folder:
            title = _('Rename Channel')
            description = _('Enter a new name for the channel %s') % \
                            ci.name

        elif t == 'playlist':
            title = _('Rename Playlist')
            description = _('Enter a new name for the playlist %s') % \
                            ci.name

        elif t == 'playlist-folder':
            title = _('Rename Playlist Folder')
            description = _('Enter a new name for the playlist folder %s') % \
                            ci.name

        else:
            return

        name = dialogsnew.ask_for_string(title, description,
                                         initial_text=ci.name)
        if name:
            messages.RenameObject(t, ci.id, name).send_to_backend()
 

    def renameCurrentTab(self, typeCheckList=None):
        selected = app.selection.getSelectedTabs()
        if len(selected) != 1:
            return
        obj = selected[0].obj
        if typeCheckList is None:
            typeCheckList = (playlist.SavedPlaylist, folder.ChannelFolder,
                folder.PlaylistFolder, feed.Feed)
        if obj.__class__ in typeCheckList:
            obj.rename()
        else:
            logging.warning ("Bad object type in renameCurrentTab() %s", obj.__class__)

    def renameCurrentChannel(self):
        # FIXME - i think this can be removed
        self.renameCurrentTab(typeCheckList=[feed.Feed, folder.ChannelFolder])

    def renameCurrentPlaylist(self):
        # FIXME - i think this can be removed
        self.renameCurrentTab(typeCheckList=[playlist.SavedPlaylist,
                folder.PlaylistFolder])

    def downloadCurrentItems(self):
        selected = app.selection.getSelectedItems()
        downloadable = [i for i in selected if i.isDownloadable() ]
        for item in downloadable:
            item.download()

    def stopDownloadingCurrentItems(self):
        selected = app.selection.getSelectedItems()
        downloading = [i for i in selected if i.getState() == 'downloading']
        for item in downloading:
            item.expire()

    def pauseDownloadingCurrentItems(self):
        selected = app.selection.getSelectedItems()
        downloading = [i for i in selected if i.getState() == 'downloading']
        for item in downloading:
            item.pause()

    def updateSelectedChannels(self):
        t, channel_infos = app.tab_list_manager.get_selection()
        if t == 'feed':
            channel_infos = [ci for ci in channel_infos if not ci.is_folder]
            for ci in channel_infos:
                messages.UpdateChannel(ci.id).send_to_backend()

    def updateAllChannels(self):
        messages.UpdateAllChannels().send_to_backend()

    def renameGuide(self, guide):
        if guide.getDefault():
            logging.warning ("attempt to rename default guide")
            return
        def callback(dialog):
            if dialog.choice == dialogs.BUTTON_OK:
                guide.setTitle(dialog.value)
        dialogs.TextEntryDialog(_('Rename Site'), _('Enter a new name for the Web Site %s') % guide.getURL(), 
                dialogs.BUTTON_OK, dialogs.BUTTON_CANCEL).run(callback)

    def removeGuide(self, guide):
        if guide.getDefault():
            logging.warning ("attempt to remove default guide")
            return
        title = _('Remove %s') % guide.getTitle()
        description = _("Are you sure you want to remove the guide %s?") % (guide.getTitle(),)
        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_YES, dialogs.BUTTON_NO)
        def dialogCallback(dialog):
            if guide.idExists() and dialog.choice == dialogs.BUTTON_YES:
                guide.remove()
        dialog.run(dialogCallback)

    def removePlaylist(self, playlist_info):
        return self.removePlaylists([playlist_info])

    def removePlaylists(self, playlist_infos):
        if len(playlist_infos) == 1:
            title = _('Remove %s') % playlist_infos[0].name
            description = _("Are you sure you want to remove %s") % \
                    playlist_infos[0].name
        else:
            title = _('Remove %s playlists') % len(playlist_infos)
            description = \
                    _("Are you sure you want to remove these %s playlists") % \
                    len(playlist_infos)

        ret = dialogsnew.show_choice_dialog(title, description,
                                            [dialogs.BUTTON_YES,
                                             dialogs.BUTTON_NO])

        if ret == dialogs.BUTTON_YES:
            for pi in playlist_infos:
                messages.DeletePlaylist(pi.id, pi.is_folder).send_to_backend()

    def removeFeed(self, channel_info):
        return self.removeFeeds([channel_info])

    def removeFeeds(self, channel_infos):
        # FIXME - this doesn't look right.  i would think we'd want to ask
        # a bunch of appropriate questions and then flip through the items
        # one by one.
        downloads = False
        downloading = False
        allDirectories = True
        for ci in channel_infos:
            if not ci.is_folder:
                allDirectories = False
                if ci.unwatched > 0:
                    downloads = True
                    break
                if ci.has_downloading:
                    downloading = True

        if downloads:
            self.removeFeedsWithDownloads(channel_infos)
        elif downloading:
            self.removeFeedsWithDownloading(channel_infos)
        elif allDirectories:
            self.removeDirectoryFeeds(channel_infos)
        else:
            self.removeFeedsNormal(channel_infos)

    def removeFeedsWithDownloads(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Remove %s') % channel_infos[0].name
            description = _("""\
What would you like to do with the videos in this channel that you've \
downloaded?""")
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _("""\
What would you like to do with the videos in these channels that you've \
downloaded?""")

        ret = dialogsnew.show_choice_dialog(title, description,
                                            [dialogs.BUTTON_KEEP_VIDEOS, 
                                             dialogs.BUTTON_DELETE_VIDEOS,
                                             dialogs.BUTTON_CANCEL])

        if ret == dialogs.BUTTON_KEEP_VIDEOS:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, True).send_to_backend()

        elif ret == dialogs.BUTTON_DELETE_VIDEOS:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def removeFeedsWithDownloading(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Remove %s') % channel_infos[0].name
            description = _("""\
Are you sure you want to remove %s?  Any downloads in progress will \
be canceled.""") % channel_infos[0].name
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _("""\
Are you sure you want to remove these %s channels?  Any downloads in \
progress will be canceled.""") % len(channel_infos)

        ret = dialogsnew.show_choice_dialog(title, description,
                                            [dialogs.BUTTON_YES, 
                                             dialogs.BUTTON_NO])

        if ret == dialogs.BUTTON_YES:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def removeFeedsNormal(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Remove %s') % channel_infos[0].name
            description = _("""\
Are you sure you want to remove %s?""") % channel_infos[0].name
        else:
            title = _('Remove %s channels') % len(channel_infos)
            description = _("""\
Are you sure you want to remove these %s channels?""") % len(channel_infos)

        ret = dialogsnew.show_choice_dialog(title, description,
                                            [dialogs.BUTTON_YES, 
                                             dialogs.BUTTON_NO])
        if ret == dialogs.BUTTON_YES:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def removeDirectoryFeeds(self, channel_infos):
        if len(channel_infos) == 1:
            title = _('Stop watching %s') % channel_infos[0].name
            description = _("""\
Are you sure you want to stop watching %s?""") % channel_infos[0].name
        else:
            title = _('Stop watching %s directories') % len(channel_infos)
            description = _("""\
Are you sure you want to stop watching these %s directories?""") % len(channel_infos)
        ret = dialogsnew.show_choice_dialog(title, description,
                                            [dialogs.BUTTON_YES, 
                                             dialogs.BUTTON_NO])
        if ret == dialogs.BUTTON_YES:
            for ci in channel_infos:
                messages.DeleteChannel(ci.id, ci.is_folder, False).send_to_backend()

    def shutdown(self):
        logging.info ("Shutting down Downloader...")
        downloader.shutdownDownloader(self.downloaderShutdown)

    def downloaderShutdown(self):
        logging.info ("Closing Database...")
        if app.db.liveStorage is not None:
            app.db.liveStorage.close()
        logging.info ("Shutting down event loop")
        eventloop.quit()
        signals.system.shutdown()

    @eventloop.asUrgent
    def setGuideURL(self, guideURL):
        """Change the URL of the current channel guide being displayed.  If no
        guide is being display, pass in None.

        This method must be called from the onSelectedTabChange in the
        platform code.  URLs are legal within guideURL will be allow
        through in onURLLoad().
        """
        self.guide = None
        if guideURL is not None:
            self.guideURL = guideURL
            for guideObj in views.guides:
                if guideObj.getURL() == app.controller.guideURL:
                    self.guide = guideObj
        else:
            self.guideURL = None

    @eventloop.asIdle
    def setLastVisitedGuideURL(self, url):
        selectedTabs = app.selection.getSelectedTabs()
        selectedObjects = [t.obj for t in selectedTabs]
        if (len(selectedTabs) != 1 or 
                not isinstance(selectedObjects[0], guide.ChannelGuide)):
            logging.warn("setLastVisitedGuideURL called, but a channelguide "
                    "isn't selected.  Selection: %s" % selectedObjects)
            return
        if selectedObjects[0].isPartOfGuide(url) and (
            url.startswith(u"http://") or url.startswith(u"https://")):
            selectedObjects[0].lastVisitedURL = url
            selectedObjects[0].extendHistory(url)
        else:
            logging.warn("setLastVisitedGuideURL called, but the guide is no "
                    "longer selected")

    def onShutdown(self):
        try:
            eventloop.join()        
            logging.info ("Saving preferences...")
            config.save()

            logging.info ("Shutting down icon cache updates")
            iconcache.iconCacheUpdater.shutdown()
            logging.info ("Shutting down movie data updates")
            moviedata.movieDataUpdater.shutdown()

            if self.idlingNotifier is not None:
                logging.info ("Shutting down IdleNotifier")
                self.idlingNotifier.join()

            logging.info ("Done shutting down.")
            logging.info ("Remaining threads are:")
            for thread in threading.enumerate():
                logging.info ("%s", thread)

        except:
            signals.system.failedExn("while shutting down")
            exit(1)

    def handleURIDrop(self, data, **kwargs):
        """Handle an external drag that contains a text/uri-list mime-type.
        data should be the text/uri-list data, in escaped form.

        kwargs is thrown away.  It exists to catch weird URLs, like
        javascript: which sometime result in us getting extra arguments.
        """

        lastAddedFeed = None
        data = urllib.unquote(data)
        for url in data.split(u"\n"):
            url = url.strip()
            if url == u"":
                continue
            if url.startswith(u"file://"):
                filename = download_utils.getFileURLPath(url)
                filename = osFilenameToFilenameType(filename)
                eventloop.addIdle (singleclick.openFile,
                    "Open Dropped file", args=(filename,))
            elif url.startswith(u"http:") or url.startswith(u"https:"):
                url = feed.normalizeFeedURL(url)
                if feed.validateFeedURL(url) and not feed.getFeedByURL(url):
                    lastAddedFeed = feed.Feed(url)

        if lastAddedFeed:
            app.selection.selectTabByObject(lastAddedFeed)

    def handleDrop(self, dropData, type, sourceData):
        try:
            destType, destID = dropData.split("-")
            if destID == 'END':
                destObj = None
            elif destID == 'START':
                if destType == 'channel':
                    tabOrder = util.getSingletonDDBObject(views.channelTabOrder)
                else:
                    tabOrder = util.getSingletonDDBObject(views.playlistTabOrder)
                for tab in tabOrder.getView():
                    destObj = tab.obj
                    break
            else:
                destObj = app.db.getObjectByID(int(destID))
            sourceArea, sourceID = sourceData.split("-")
            sourceID = int(sourceID)
            draggedIDs = app.selection.calcSelection(sourceArea, sourceID)
        except:
            logging.exception ("error parsing drop (%r, %r, %r)",
                               dropData, type, sourceData)
            return

        if destType == 'playlist' and type == 'downloadeditem':
            # dropping an item on a playlist
            destObj.handleDNDAppend(draggedIDs)
        elif ((destType == 'channelfolder' and type == 'channel') or
                (destType == 'playlistfolder' and type == 'playlist')):
            # Dropping a channel/playlist onto a folder
            obj = app.db.getObjectByID(int(destID))
            obj.handleDNDAppend(draggedIDs)
        elif (destType in ('playlist', 'playlistfolder') and 
                type in ('playlist', 'playlistfolder')):
            # Reording the playlist tabs
            tabOrder = util.getSingletonDDBObject(views.playlistTabOrder)
            tabOrder.handleDNDReorder(destObj, draggedIDs)
        elif (destType in ('channel', 'channelfolder') and
                type in ('channel', 'channelfolder')):
            # Reordering the channel tabs
            tabOrder = util.getSingletonDDBObject(views.channelTabOrder)
            tabOrder.handleDNDReorder(destObj, draggedIDs)
        elif destType == "playlistitem" and type == "downloadeditem":
            # Reording items in a playlist
            playlist = app.selection.getSelectedTabs()[0].obj
            playlist.handleDNDReorder(destObj, draggedIDs)
        else:
            logging.info ("Can't handle drop. Dest type: %s Dest id: %s Type: %s",
                          destType, destID, type)

    def addToNewPlaylist(self):
        selected = app.selection.getSelectedItems()
        childIDs = [i.getID() for i in selected if i.isDownloaded()]
        playlist.createNewPlaylist(childIDs)

    def startUploads(self):
        selected = app.selection.getSelectedItems()
        for i in selected:
            i.startUpload()

    @eventloop.asUrgent
    def saveVideo(self, currentPath, savePath):
        logging.info("saving video %s to %s" % (currentPath, savePath))
        try:
            shutil.copyfile(currentPath, savePath)
        except:
            title = _('Error Saving Video')
            name = os.path.basename(currentPath)
            text = _('An error occured while trying to save %s.  Please check that the file has not been deleted and try again.') % util.clampText(name, 50)
            dialogs.MessageBoxDialog(title, text).run()
            logging.warn("Error saving video: %s" % traceback.format_exc())

    @eventloop.asUrgent
    def changeMoviesDirectory(self, newDir, migrate):
        oldDir = config.get(prefs.MOVIES_DIRECTORY)
        config.set(prefs.MOVIES_DIRECTORY, newDir)
        if migrate:
            views.remoteDownloads.confirmDBThread()
            for download in views.remoteDownloads:
                if download.isFinished():
                    logging.info ("migrating %s", download.getFilename())
                    download.migrate(newDir)
            # Pass in case they don't exist or are not empty:
            try:
                fileutil.rmdir(os.path.join (oldDir, 'Incomplete Downloads'))
            except:
                pass
            try:
                fileutil.rmdir(oldDir)
            except:
                pass
        util.getSingletonDDBObject(views.directoryFeed).update()

    def sendBugReport(self, report, description, send_database):
        def callback(result):
            self.sendingCrashReport -= 1
            if result['status'] != 200 or result['body'] != 'OK':
                logging.warning(u"Failed to submit crash report. Server returned %r" % result)
            else:
                logging.info(u"Crash report submitted successfully")
        def errback(error):
            self.sendingCrashReport -= 1
            logging.warning(u"Failed to submit crash report %r" % error)

        backupfile = None
        if send_database:
            try:
                logging.info("Sending entire database")
                from miro import database
                backupfile = database.defaultDatabase.liveStorage.backupDatabase()
            except:
                traceback.print_exc()
                logging.warning(u"Failed to backup database")

        description = description.encode("utf-8")
        postVars = {"description":description,
                    "app_name": config.get(prefs.LONG_APP_NAME),
                    "log": report}
        if backupfile:
            postFiles = {"databasebackup": {"filename":"databasebackup.zip", "mimetype":"application/octet-stream", "handle":open(backupfile, "rb")}}
        else:
            postFiles = None
        self.sendingCrashReport += 1
        httpclient.grabURL("http://participatoryculture.org/bogondeflector/index.php", callback, errback, method="POST", postVariables = postVars, postFiles = postFiles)
