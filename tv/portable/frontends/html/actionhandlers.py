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

"""frontends.html.actionhandlers.  
Handlers for actions generated from templates, the OS, etc.
"""

from gtcache import gettext as _
# These are Python templates for string substitution, not at all
# related to our HTML based templates
from string import Template

from frontends.html import dialogs
import config
import feed
import database
import frontends.html
import prefs
import util
db = database.defaultDatabase

class ModelActionHandler:
    """Functions that are safe to call from action: URLs that do nothing but
    manipulate the database.
    """
    
    def __init__(self, backEndDelegate):
        self.backEndDelegate = backEndDelegate
    
    def setAutoDownloadMode(self, feed, mode):
        obj = db.getObjectByID(int(feed))
        obj.setAutoDownloadMode(mode)

    def setExpiration(self, feed, type, time):
        obj = db.getObjectByID(int(feed))
        obj.setExpiration(type, int(time))

    def setMaxNew(self, feed, maxNew):
        obj = db.getObjectByID(int(feed))
        obj.setMaxNew(int(maxNew))

    def invalidMaxNew(self, value):
        title = _("Invalid Value")
        description = _("%s is invalid.  You must enter a non-negative "
                "number.") % value
        dialogs.MessageBoxDialog(title, description).run()

    def startDownload(self, item):
        try:
            obj = db.getObjectByID(int(item))
            obj.download()
        except database.ObjectNotFoundError:
            pass

    def removeFeed(self, id):
        try:
            feed = db.getObjectByID(int(id))
            frontends.html.app.removeFeed(feed)
        except database.ObjectNotFoundError:
            pass

    def removeCurrentFeed(self):
        frontends.html.app.removeCurrentFeed()

    def removeCurrentPlaylist(self):
        frontends.html.app.removeCurrentPlaylist()

    def removeCurrentItems(self):
        frontends.html.app.removeCurrentItems()

    def mergeToFolder(self):
        tls = frontends.html.app.selection.tabListSelection
        selectionType = tls.getType()
        childIDs = set(tls.currentSelection)
        if selectionType == 'channeltab':
            folder.createNewChannelFolder(childIDs)
        elif selectionType == 'playlisttab':
            folder.createNewPlaylistFolder(childIDs)
        else:
            logging.warning ("bad selection type %s in mergeToFolder",
                             selectionType)

    def remove(self, area, id):
        selectedIDs = frontends.html.app.selection.calcSelection(area, int(id))
        selectedObjects = [db.getObjectByID(id) for id in selectedIDs]
        objType = selectedObjects[0].__class__

        if objType in (feed.Feed, folder.ChannelFolder):
            frontends.html.app.removeFeeds(selectedObjects)
        elif objType in (playlist.SavedPlaylist, folder.PlaylistFolder):
            frontends.html.app.removePlaylists(selectedObjects)
        elif objType == guide.ChannelGuide:
            if len(selectedObjects) != 1:
                raise AssertionError("Multiple guides selected in remove")
            frontends.html.app.removeGuide(selectedObjects[0])
        elif objType == item.Item:
            pl = frontends.html.app.selection.getSelectedTabs()[0].obj
            pl.handleRemove(destObj, selectedIDs)
        else:
            logging.warning ("Can't handle type %s in remove()", objType)

    def rename(self, id):
        try:
            obj = db.getObjectByID(int(id))
        except:
            logging.warning ("tried to rename object that doesn't exist with id %d", int(feed))
            return
        if obj.__class__ in (playlist.SavedPlaylist, folder.ChannelFolder,
                folder.PlaylistFolder):
            obj.rename()
        else:
            logging.warning ("Unknown object type in remove() %s", type(obj))

    def updateFeed(self, feed):
        obj = db.getObjectByID(int(feed))
        obj.update()

    def copyFeedURL(self, feed):
        obj = db.getObjectByID(int(feed))
        url = obj.getURL()
        self.backEndDelegate.copyTextToClipboard(url)

    def markFeedViewed(self, feed):
        try:
            obj = db.getObjectByID(int(feed))
            obj.markAsViewed()
        except database.ObjectNotFoundError:
            pass

    def updateIcons(self, feed):
        try:
            obj = db.getObjectByID(int(feed))
            obj.updateIcons()
        except database.ObjectNotFoundError:
            pass

    def expireItem(self, item):
        try:
            obj = db.getObjectByID(int(item))
            obj.expire()
        except database.ObjectNotFoundError:
            logging.warning ("tried to expire item that doesn't exist with id %d", int(item))

    def expirePlayingItem(self, item):
        self.expireItem(item)
        frontends.html.app.playbackController.skip(1)

    def addItemToLibrary(self, item):
        obj = db.getObjectByID(int(item))
        manualFeed = util.getSingletonDDBObject(views.manualFeed)
        obj.setFeed(manualFeed.getID())

    def keepItem(self, item):
        obj = db.getObjectByID(int(item))
        obj.save()

    def stopUploadItem(self, item):
        obj = db.getObjectByID(int(item))
        obj.stopUpload()

    def toggleMoreItemInfo(self, item):
        obj = db.getObjectByID(int(item))
        obj.toggleShowMoreInfo()

    def revealItem(self, item):
        obj = db.getObjectByID(int(item))
        filename = obj.getFilename()
        if not os.path.exists(filename):
            basename = os.path.basename(filename)
            title = _("Error Revealing File")
            msg = _("The file \"%s\" was deleted from outside Miro.") % basename
            dialogs.MessageBoxDialog(title, msg).run()
        else:
            self.backEndDelegate.revealFile(filename)

    def clearTorrents (self):
        items = views.items.filter(lambda x: x.getFeed().url == u'dtv:manualFeed' and x.isNonVideoFile() and not x.getState() == u"downloading")
        for i in items:
            if i.downloader is not None:
                i.downloader.setDeleteFiles(False)
            i.remove()

    def pauseDownload(self, item):
        obj = db.getObjectByID(int(item))
        obj.pause()
        
    def resumeDownload(self, item):
        obj = db.getObjectByID(int(item))
        obj.resume()

    def pauseAll (self):
        autodler.pauseDownloader()
        for item in views.downloadingItems:
            item.pause()

    def resumeAll (self):
        for item in views.pausedItems:
            item.resume()
        autodler.resumeDownloader()

    def toggleExpand(self, id):
        obj = db.getObjectByID(int(id))
        obj.setExpanded(not obj.getExpanded())

    def setRunAtStartup(self, value):
        value = (value == "1")
        self.backEndDelegate.setRunAtStartup(value)

    def setCheckEvery(self, value):
        value = int(value)
        config.set(prefs.CHECK_CHANNELS_EVERY_X_MN,value)

    def setLimitUpstream(self, value):
        value = (value == "1")
        config.set(prefs.LIMIT_UPSTREAM,value)

    def setMaxUpstream(self, value):
        value = int(value)
        config.set(prefs.UPSTREAM_LIMIT_IN_KBS,value)

    def setPreserveDiskSpace(self, value):
        value = (value == "1")
        config.set(prefs.PRESERVE_DISK_SPACE,value)

    def setDefaultExpiration(self, value):
        value = int(value)
        config.set(prefs.EXPIRE_AFTER_X_DAYS,value)

    def videoBombExternally(self, item):
        obj = db.getObjectByID(int(item))
        paramList = {}
        paramList["title"] = obj.getTitle()
        paramList["info_url"] = obj.getLink()
        paramList["hookup_url"] = obj.getPaymentLink()
        try:
            rss_url = obj.getFeed().getURL()
            if (not rss_url.startswith(u'dtv:')):
                paramList["rss_url"] = rss_url
        except:
            pass
        thumb_url = obj.getThumbnailURL()
        if thumb_url is not None:
            paramList["thumb_url"] = thumb_url

        # FIXME: add "explicit" and "tags" parameters when we get them in item

        paramString = ""
        glue = '?'
       
        # This should be first, since it's most important.
        url = obj.getURL()
        url.encode('utf-8', 'replace')
        if (not url.startswith('file:')):
            paramString = "?url=%s" % xhtmltools.urlencode(url)
            glue = '&'

        for key in paramList.keys():
            if len(paramList[key]) > 0:
                paramString = "%s%s%s=%s" % (paramString, glue, key, xhtmltools.urlencode(paramList[key]))
                glue = '&'

        # This should be last, so that if it's extra long it 
        # cut off all the other parameters
        description = obj.getDescription()
        if len(description) > 0:
            paramString = "%s%sdescription=%s" % (paramString, glue,
                    xhtmltools.urlencode(description))
        url = config.get(prefs.VIDEOBOMB_URL) + paramString
        self.backEndDelegate.openExternalURL(url)

    def changeMoviesDirectory(self, newDir, migrate):
        changeMoviesDirectory(newDir, migrate == '1')

class HistoryActionHandler:
    """Functions that change the history of a guide"""

    def __init__(self, display):
        self.display = display

    def gotoURL(self, newURL):
        self.display.execJS('top.miro_guide_frame.location="%s"' % newURL)

    def getGuide(self):
        guides = [t.obj for t in frontends.html.app.selection.getSelectedTabs()]
        if len(guides) != 1:
            return
        if not isinstance(guides[0], guide.ChannelGuide):
            return
        return guides[0]

    def back(self):
        guide = self.getGuide()
        if guide is not None:
            newURL = guide.getHistoryURL(-1)
            if newURL is not None:
                self.gotoURL(newURL)

    def forward(self):
        guide = self.getGuide()
        if guide is not None:
            newURL = guide.getHistoryURL(1)
            if newURL is not None:
                self.gotoURL(newURL)

    def home(self):
        guide = self.getGuide()
        if guide is not None:
            newURL = guide.getHistoryURL(None)
            self.gotoURL(newURL)

class GUIActionHandler:
    """Functions that are safe to call from action: URLs that can change
    the GUI presentation (and may or may not manipulate the database.)
    """

    def playUnwatched(self):
        frontends.html.app.playView(views.unwatchedItems)

    def openFile(self, path):
        singleclick.openFile(path)

    def addSearchFeed(self, term=None, style = dialogs.SearchChannelDialog.CHANNEL, location = None):
        def doAdd(dialog):
            if dialog.choice == dialogs.BUTTON_CREATE_CHANNEL:
                self.addFeed(dialog.getURL())
        dialog = dialogs.SearchChannelDialog(term, style, location)
        if location == None:
            dialog.run(doAdd)
        else:
            self.addFeed(dialog.getURL())

    def addChannelSearchFeed(self, id):
        feed = db.getObjectByID(int(id))
        self.addSearchFeed(feed.inlineSearchTerm, dialogs.SearchChannelDialog.CHANNEL, int(id))

    def addEngineSearchFeed(self, term, name):
        self.addSearchFeed(term, dialogs.SearchChannelDialog.ENGINE, name)
        
    def testSearchFeedDialog(self):
        def finish(dialog):
            pass
        def thirdDialog(dialog):
            dialog = dialogs.SearchChannelDialog("Should select URL http://testurl/", dialogs.SearchChannelDialog.URL, "http://testurl/")
            dialog.run(finish)
        def secondDialog(dialog):
            dialog = dialogs.SearchChannelDialog("Should select YouTube engine", dialogs.SearchChannelDialog.ENGINE, "youtube")
            dialog.run(thirdDialog)
        dialog = dialogs.SearchChannelDialog("Should select third channel in list", dialogs.SearchChannelDialog.CHANNEL, -1)
        dialog.run(secondDialog)
        
    def addURL(self, title, message, callback, url = None):
        util.checkU(url)
        util.checkU(title)
        util.checkU(message)
        def createDialog(ltitle, lmessage, prefill = None):
            def prefillCallback():
                if prefill:
                    return prefill
                else:
                    return None
            dialog = dialogs.TextEntryDialog(ltitle, lmessage, dialogs.BUTTON_OK, dialogs.BUTTON_CANCEL, prefillCallback, fillWithClipboardURL=(prefill is None))
            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_OK:
                    doAdd(dialog.value)
            dialog.run(callback)
        def doAdd(url):
            normalizedURL = feed.normalizeFeedURL(url)
            if not feed.validateFeedURL(normalizedURL):
                ltitle = title + _(" - Invalid URL")
                lmessage = _("The address you entered is not a valid URL.\nPlease double check and try again.\n\n") + message
                createDialog(ltitle, lmessage, url)
                return
            callback(normalizedURL)
        if url is None:
            createDialog(title, message)
        else:
            doAdd(url)
        
    # NEEDS: name should change to addAndSelectFeed; then we should create
    # a non-GUI addFeed to match removeFeed. (requires template updates)
    def addFeed(self, url = None, showTemplate = None, selected = '1'):
        if url:
            util.checkU(url)
        def doAdd (url):
            db.confirmDBThread()
            myFeed = feed.getFeedByURL (url)
            if myFeed is None:
                myFeed = feed.Feed(url)
    
            if selected == '1':
                frontends.html.app.selection.selectTabByObject(myFeed)
            else:
                myFeed.blink()
        self.addURL (Template(_("$shortAppName - Add Channel")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the channel to add"), doAdd, url)

    def selectFeed(self, url):
        url = feed.normalizeFeedURL(url)
        db.confirmDBThread()
        # Find the feed
        myFeed = feed.getFeedByURL (url)
        if myFeed is None:
            logging.warning ("selectFeed: no such feed: %s", url)
            return
        frontends.html.app.selection.selectTabByObject(myFeed)
        
    def addGuide(self, url = None, selected = '1'):
        def doAdd(url):
            db.confirmDBThread()
            myGuide = guide.getGuideByURL (url)
            if myGuide is None:
                myGuide = guide.ChannelGuide(url)
    
            if selected == '1':
                frontends.html.app.selection.selectTabByObject(myGuide)
        self.addURL (Template(_("$shortAppName - Add Miro Guide")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the Miro Guide to add"), doAdd, url)

    def addDownload(self, url = None):
        def doAdd(url):
            db.confirmDBThread()
            singleclick.downloadURL(platformutils.unicodeToFilename(url))
        self.addURL (Template(_("$shortAppName - Download Video")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the video to download"), doAdd, url)

    def handleDrop(self, data, type, sourcedata):
        frontends.html.app.handleDrop(data, type, sourcedata)

    def handleURIDrop(self, data, **kwargs):
        frontends.html.app.handleURIDrop(data, **kwargs)

    def showHelp(self):
        delegate.openExternalURL(config.get(prefs.HELP_URL))

    def reportBug(self):
        delegate.openExternalURL(config.get(prefs.BUG_REPORT_URL))

class TemplateActionHandler:
    """Functions that are safe to call from action: URLs that change state
    specific to a particular instantiation of a template, and so have to
    be scoped to a particular HTML display widget.
    """
    
    def __init__(self, display, templateHandle):
        self.display = display
        self.templateHandle = templateHandle
        self.currentName = None

    def switchTemplate(self, name, state='default', baseURL=None, *args, **kargs):
        self.templateHandle.unlinkTemplate()
        # Switch to new template. It get the same variable
        # dictionary as we have.
        # NEEDS: currently we hardcode the display area. This means
        # that these links always affect the right-hand 'content'
        # area, even if they are loaded from the left-hand 'tab'
        # area. Actually this whole invocation is pretty hacky.
        template = TemplateDisplay(name, state, 
                frameHint=frontends.html.app.frame,
                areaHint=frontends.html.app.frame.mainDisplay, baseURL=baseURL,
                *args, **kargs)
        frontends.html.app.frame.selectDisplay(template, 
                frontends.html.app.frame.mainDisplay)
        self.currentName = name

    def setViewFilter(self, viewName, fieldKey, functionKey, parameter, invert):
        logging.warning ("setViewFilter deprecated")

    def setViewSort(self, viewName, fieldKey, functionKey, reverse="false"):
        logging.warning ("setViewSort deprecated")

    def setSearchString(self, searchString):
        try:
            self.templateHandle.getTemplateVariable('updateSearchString')(unicode(searchString))
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('updateSearchString')")

    def toggleDownloadsView(self):
        try:
            self.templateHandle.getTemplateVariable('toggleDownloadsView')(self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('toggleDownloadsView')")

    def toggleWatchableView(self):
        try:
            self.templateHandle.getTemplateVariable('toggleWatchableView')(self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('toggleWatchableView')")

    def toggleNewItemsView(self):
        try:
            self.templateHandle.getTemplateVariable('toggleNewItemsView')(self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('toggleNewItemsView')")            

    def toggleAllItemsMode(self):
        try:
            self.templateHandle.getTemplateVariable('toggleAllItemsMode')(self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('toggleAllItemsMode')")

    def pauseDownloads(self):
        try:
            view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('allDownloadingItems') during pauseDownloads()")
            return
        for item in view:
            item.pause()

    def resumeDownloads(self):
        try:
            view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('allDownloadingItems') during resumeDownloads()")
            return
        for item in view:
            item.resume()

    def cancelDownloads(self):
        try:
            view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('allDownloadingItems') during cancelDownloads()")
            return
        for item in view:
            item.expire()

    def playViewNamed(self, viewName, firstItemId):
        try:
            view = self.templateHandle.getTemplateVariable(viewName)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable (%s) during playViewNamed()" % (viewName,))
            return
        frontends.html.app.playView(view, firstItemId)

    def playOneItem(self, viewName, itemID):
        try:
            view = self.templateHandle.getTemplateVariable(viewName)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable (%s) during playOneItem()" % (viewName,))
            return
        frontends.html.app.playView(view, itemID, justPlayOne=True)

    def playNewVideos(self, id):
        try:
            obj = db.getObjectByID(int(id))
        except database.ObjectNotFoundError:
            return

        def myUnwatchedItems(obj):
            return (obj.getState() == u'newly-downloaded' and
                    not obj.isNonVideoFile() and
                    not obj.isContainerItem)

        frontends.html.app.selection.selectTabByObject(obj, 
                displayTabContent=False)
        if isinstance(obj, feed.Feed):
            feedView = views.items.filterWithIndex(indexes.itemsByFeed,
                    obj.getID())
            view = feedView.filter(myUnwatchedItems,
                                   sortFunc=sorts.item)
            frontends.html.app.playView(view)
            view.unlink()
        elif isinstance(obj, folder.ChannelFolder):
            folderView = views.items.filterWithIndex(
                    indexes.itemsByChannelFolder, obj)
            view = folderView.filter(myUnwatchedItems,
                                     sortFunc=sorts.item)
            frontends.html.app.playView(view)
            view.unlink()
        elif isinstance(obj, tabs.StaticTab): # new videos tab
            view = views.unwatchedItems
            frontends.html.app.playView(view)
        else:
            raise TypeError("Can't get new videos for %s (type: %s)" % 
                    (obj, type(obj)))

    def playItemExternally(self, itemID):
        frontends.html.app.playbackController.playItemExternally(itemID)
        
    def skipItem(self, itemID):
        frontends.html.app.playbackController.skip(1)
    
    def updateLastSearchEngine(self, engine):
        searchFeed, searchDownloadsFeed = self.__getSearchFeeds()
        if searchFeed is not None:
            searchFeed.lastEngine = engine
    
    def updateLastSearchQuery(self, query):
        searchFeed, searchDownloadsFeed = self.__getSearchFeeds()
        if searchFeed is not None:
            searchFeed.lastQuery = query
        
    def performSearch(self, engine, query):
        util.checkU(engine)
        util.checkU(query)
        searchFeed, searchDownloadsFeed = self.__getSearchFeeds()
        if searchFeed is not None and searchDownloadsFeed is not None:
            searchFeed.preserveDownloads(searchDownloadsFeed)
            searchFeed.lookup(engine, query)

    def resetSearch(self):
        searchFeed, searchDownloadsFeed = self.__getSearchFeeds()
        if searchFeed is not None and searchDownloadsFeed is not None:
            searchFeed.preserveDownloads(searchDownloadsFeed)
            searchFeed.reset()

    def sortBy(self, by, section):
        try:
            self.templateHandle.getTemplateVariable('setSortBy')(by, section, self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('setSortBy')")

    def handleSelect(self, area, viewName, id, shiftDown, ctrlDown):
        try:
            view = self.templateHandle.getTemplateVariable(viewName)
        except KeyError, e: # user switched templates before we got this
            logging.warning ("KeyError in getTemplateVariable (%s) during handleSelect()" % (viewName,))
            return
        shift = (shiftDown == '1')
        ctrl = (ctrlDown == '1')
        frontends.html.app.selection.selectItem(area, view, int(id), shift, ctrl)

    def handleContextMenuSelect(self, id, area, viewName):
        from frontends.html import contextmenu
        try:
            obj = db.getObjectByID(int(id))
        except:
            traceback.print_exc()
        else:
            try:
                view = self.templateHandle.getTemplateVariable(viewName)
            except KeyError, e: # user switched templates before we got this
                logging.warning ("KeyError in getTemplateVariable (%s) during handleContextMenuSelect()" % (viewName,))
                return
            if not frontends.html.app.selection.isSelected(area, view, int(id)):
                self.handleSelect(area, viewName, id, False, False)
            popup = contextmenu.makeContextMenu(self.currentName, view,
                    frontends.html.app.selection.getSelectionForArea(area), int(id))
            if popup:
                delegate.showContextMenu(popup)

    def __getSearchFeeds(self):
        searchFeed = frontends.html.app.getGlobalFeed('dtv:search')
        assert searchFeed is not None
        
        searchDownloadsFeed = frontends.html.app.getGlobalFeed('dtv:searchDownloads')
        assert searchDownloadsFeed is not None

        return (searchFeed, searchDownloadsFeed)

    # The Windows XUL port can send a setVolume or setVideoProgress at
    # any time, even when there's no video display around. We can just
    # ignore it
    def setVolume(self, level):
        pass
    def setVideoProgress(self, pos):
        pass
