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

# These are Python templates for string substitution, not at all
# related to our HTML based templates
from string import Template
import cgi
import logging
import os
import re
import threading
import traceback

from miro.clock import clock
from miro import dialogs
from miro.gtcache import gettext as _
from miro.plat.frontends.html.HTMLDisplay import HTMLDisplay
from miro import app
from miro import autodler
from miro import config
from miro import database
from miro import download_utils
from miro import eventloop
from miro import feed
from miro import folder
from miro import filetypes
from miro import guide
from miro import httpclient
from miro import indexes
from miro import item
import logging
from miro.plat.utils import unicodeToFilename
from miro import playlist
from miro import prefs
from miro import searchengines
from miro import signals
from miro import singleclick
from miro import sorts
from miro import subscription
from miro import tabs
from miro import util
from miro import views
from miro import xhtmltools
from miro.frontends.html import template

class TemplateDisplay(HTMLDisplay):
    """TemplateDisplay: a HTML-template-driven right-hand display panel."""

    def __init__(self, templateName, templateState, frameHint=None, areaHint=None, 
            baseURL=None, *args, **kargs):
        """'templateName' is the name of the inital template file.  'data' is
        keys for the template. 'templateState' is a string with the state of the
        template.
        """

        logging.debug ("Processing %s", templateName)
        self.templateName = templateName
        self.templateState = templateState
        (tch, self.templateHandle) = template.fillTemplate(templateName,
                self, self.getDTVPlatformName(), self.getEventCookie(),
                self.getBodyTagExtra(), templateState = templateState,
                                                           *args, **kargs)
        self.args = args
        self.kargs = kargs
        self.haveLoaded = False
        html = tch.read()

        self.actionHandlers = [
            ModelActionHandler(),
            HistoryActionHandler(self),
            GUIActionHandler(),
            TemplateActionHandler(self, self.templateHandle),
            ]

        loadTriggers = self.templateHandle.getTriggerActionURLsOnLoad()
        newPage = self.runActionURLs(loadTriggers)

        if newPage:
            self.templateHandle.unlinkTemplate()
            # FIXME - url is undefined here!
            self.__init__(re.compile(r"^template:(.*)$").match(url).group(1), frameHint, areaHint, baseURL)
        else:
            HTMLDisplay.__init__(self, html, frameHint=frameHint, areaHint=areaHint, baseURL=baseURL)

            self.templateHandle.initialFillIn()

    def __eq__(self, other):
        return (other.__class__ == TemplateDisplay and 
                self.templateName == other.templateName and 
                self.args == other.args and 
                self.kargs == other.kargs)

    def __str__(self):
        return "Template <%s> args=%s kargs=%s" % (self.templateName, self.args, self.kargs)

    def reInit(self, *args, **kargs):
        self.args = args
        self.kargs = kargs
        try:
            self.templateHandle.templateVars['reInit'](*args, **kargs)
        except:
            pass
        self.templateHandle.forceUpdate()
        
    def runActionURLs(self, triggers):
        newPage = False
        for url in triggers:
            if url.startswith('action:'):
                self.onURLLoad(url)
            elif url.startswith('template:'):
                newPage = True
                break
        return newPage

    def parseEventURL(self, url):
        match = re.match(r"[a-zA-Z]+:([^?]+)(\?(.*))?$", url)
        if match:
            path = match.group(1)
            argString = match.group(3)
            if argString is None:
                argString = u''
            argString = argString.encode('utf8')
            # argString is turned into a str since parse_qs will fail on utf8 that has been url encoded.
            argLists = cgi.parse_qs(argString, keep_blank_values=True)

            # argLists is a dictionary from parameter names to a list
            # of values given for that parameter. Take just one value
            # for each parameter, raising an error if more than one
            # was given.
            args = {}
            for key in argLists.keys():
                value = argLists[key]
                if len(value) != 1:
                    from miro import template_compiler
                    raise template_compiler.TemplateError, "Multiple values of '%s' argument passed to '%s' action" % (key, url)
                # Cast the value results back to unicode
                try:
                    args[key.encode('ascii','replace')] = value[0].decode('utf8')
                except:
                    args[key.encode('ascii','replace')] = value[0].decode('ascii', 'replace')
            return path, args
        else:
            raise ValueError("Badly formed eventURL: %s" % url)


    def onURLLoad(self, url):
        if self.checkURL(url):
            if not app.controller.guide: # not on a channel guide:
                return True
            # The first time the guide is loaded in the template, several
            # pages are loaded, so this shouldn't be called during that
            # first load.  After that, this shows the spinning circle to
            # indicate loading
            if not self.haveLoaded and (url ==
                    app.controller.guide.getLastVisitedURL()):
                self.haveLoaded = True
            elif self.haveLoaded:
                script = 'top.guideUnloaded()'
                if not url.endswith(script):
                    self.execJS(script)
            return True
        else:
            return False

    # Returns true if the browser should handle the URL.
    def checkURL(self, url):
        util.checkU(url)
        logging.info ("got %s", url)
        try:
            # Special-case non-'action:'-format URL
            if url.startswith (u"template:"):
                name, args = self.parseEventURL(url)
                self.dispatchAction('switchTemplate', name=name, **args)
                return False

            # Standard 'action:' URL
            if url.startswith (u"action:"):
                action, args = self.parseEventURL(url)
                self.dispatchAction(action, **args)
                return False
            
            # Let channel guide URLs pass through
            if (not subscription.isSubscribeLink(url) and
                app.controller.guide is not None and 
                app.controller.guide.isPartOfGuide(url) and
                not filetypes.isAllowedFilename(url) and
                not filetypes.isFeedFilename(url)):
                app.controller.setLastVisitedGuideURL(url)
                return True
            if url.startswith(u'file://'):
                path = download_utils.getFileURLPath(url)
                return os.path.exists(path)

            # If we get here, this isn't a DTV URL. We should open it
            # in an external browser.
            if (url.startswith(u'http://') or url.startswith(u'https://') or
                url.startswith(u'ftp://') or url.startswith(u'mailto:') or
                url.startswith(u'feed://')):
                self.handleCandidateExternalURL(url)
                return False

        except:
            signals.system.failedExn("while handling a request", 
                    details="Handling action URL '%s'" % (url, ))

        return True

    @eventloop.asUrgent
    def handleCandidateExternalURL(self, url):
        """Open a URL that onURLLoad thinks is an external URL.
        handleCandidateExternalURL does extra checks that onURLLoad can't do
        because it's happens in the gui thread and can't access the DB.
        """

        # check for subscribe.getdemocracy.com/subscribe.getmiro.com links
        type, subscribeURLs = subscription.findSubscribeLinks(url)


        normalizedURLs = []
        for url, additional in subscribeURLs:
            normalized = feed.normalizeFeedURL(url)
            if feed.validateFeedURL(normalized):
                normalizedURLs.append((normalized, additional))
        if normalizedURLs:
            if type == 'feed':
                for url, additional in normalizedURLs:
                    if feed.getFeedByURL(url) is None:
                        newFeed = feed.Feed(url)
                        newFeed.blink()
                        if 'trackback' in additional:
                            httpclient.grabURL(additional['trackback'],
                                               lambda x: None,
                                               lambda x: None)
            elif type == 'download':
                for url, additional in normalizedURLs:
                    singleclick.addDownload(url, additional)
            elif type == 'guide':
                for url, additional in normalizedURLs:
                    if guide.getGuideByURL (url) is None:
                        guide.ChannelGuide(url, [u'*'])
            else:
                raise AssertionError("Unknown subscribe type")
            return

        if url.startswith(u'feed://'):
            url = u"http://" + url[len(u"feed://"):]
            f = feed.getFeedByURL(url)
            if f is None:
                f = feed.Feed(url)
            f.blink()
            return

        if filetypes.isFeedFilename(url): # feed URL, ask to subscribe
            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_ADD:
                        singleclick.addDownload(url)
            title = _("File Download")
            text = _("""This link appears to be a feed.  Do you want to \
add it to your subscriptions?

%s""") % url
            dialog = dialogs.ChoiceDialog(title, text,
                                          dialogs.BUTTON_YES,
                                          dialogs.BUTTON_NO)
            dialog.run(callback)
        elif filetypes.isAllowedFilename(url): # media URL, download it
            singleclick.addDownload(url)
        else:
            app.delegate.openExternalURL(url)

    @eventloop.asUrgent
    def dispatchAction(self, action, **kwargs):
        called = False
        start = clock()
        for handler in self.actionHandlers:
            if hasattr(handler, action):
                getattr(handler, action)(**kwargs)
                called = True
                break
        end = clock()
        if end - start > 0.5:
            logging.timing ("dispatch action %s too slow (%.3f secs)", action, end - start)
        if not called:
            logging.warning ("Ignored bad action URL: action=%s", action)

    @eventloop.asUrgent
    def onDeselected(self, frame):
        unloadTriggers = self.templateHandle.getTriggerActionURLsOnUnload()
        self.runActionURLs(unloadTriggers)
        self.unlink()
        HTMLDisplay.onDeselected(self, frame)

    def unlink(self):
        self.templateHandle.unlinkTemplate()
        self.actionHandlers = []

###############################################################################
#### Handlers for actions generated from templates, the OS, etc            ####
###############################################################################

# Functions that are safe to call from action: URLs that do nothing
# but manipulate the database.
class ModelActionHandler:
    
    def setAutoDownloadMode(self, feed, mode):
        obj = app.db.getObjectByID(int(feed))
        obj.setAutoDownloadMode(mode)

    def setExpiration(self, feed, type, time):
        obj = app.db.getObjectByID(int(feed))
        obj.setExpiration(type, int(time))

    def requiresPositiveInteger(self, value):
        title = _("Invalid Value")
        description = _("%s is invalid.  You must enter a non-negative "
                "number.") % value
        dialogs.MessageBoxDialog(title, description).run()


    def setMaxNew(self, feed, maxNew):
        obj = app.db.getObjectByID(int(feed))
        obj.setMaxNew(int(maxNew))

    def setMaxOldItems(self, feed, maxOldItems):
        obj = app.db.getObjectByID(int(feed))
        obj.setMaxOldItems(int(maxOldItems))

    def cleanOldItems(self, feed):
        obj = app.db.getObjectByID(int(feed))
        obj.cleanOldItems()
        
    def startDownload(self, item):
        try:
            obj = app.db.getObjectByID(int(item))
            obj.download()
        except database.ObjectNotFoundError:
            pass

    def removeFeed(self, id):
        try:
            feed = app.db.getObjectByID(int(id))
            app.controller.removeFeed(feed)
        except database.ObjectNotFoundError:
            pass

    def removeCurrentFeed(self):
        app.controller.removeCurrentFeed()

    def removeCurrentPlaylist(self):
        app.controller.removeCurrentPlaylist()

    def removeCurrentItems(self):
        app.controller.removeCurrentItems()

    def mergeToFolder(self):
        tls = app.selection.tabListSelection
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
        selectedIDs = app.selection.calcSelection(area, int(id))
        selectedObjects = [app.db.getObjectByID(id) for id in selectedIDs]
        objType = selectedObjects[0].__class__

        if objType in (feed.Feed, folder.ChannelFolder):
            app.controller.removeFeeds(selectedObjects)
        elif objType in (playlist.SavedPlaylist, folder.PlaylistFolder):
            app.controller.removePlaylists(selectedObjects)
        elif objType == guide.ChannelGuide:
            if len(selectedObjects) != 1:
                raise AssertionError("Multiple guides selected in remove")
            app.controller.removeGuide(selectedObjects[0])
        elif objType == item.Item:
            pl = app.selection.getSelectedTabs()[0].obj
            pl.handleRemove(destObj, selectedIDs)
        else:
            logging.warning ("Can't handle type %s in remove()", objType)

    def rename(self, id):
        try:
            obj = app.db.getObjectByID(int(id))
        except:
            logging.warning ("tried to rename object that doesn't exist with id %d", int(feed))
            return
        if obj.__class__ in (playlist.SavedPlaylist, folder.ChannelFolder,
                folder.PlaylistFolder):
            obj.rename()
        else:
            logging.warning ("Unknown object type in remove() %s", type(obj))

    def updateFeed(self, feed):
        obj = app.db.getObjectByID(int(feed))
        obj.update()

    def copyFeedURL(self, feed):
        obj = app.db.getObjectByID(int(feed))
        url = obj.getURL()
        app.delegate.copyTextToClipboard(url)

    def markFeedViewed(self, feed):
        try:
            obj = app.db.getObjectByID(int(feed))
            obj.markAsViewed()
        except database.ObjectNotFoundError:
            pass

    def updateIcons(self, feed):
        try:
            obj = app.db.getObjectByID(int(feed))
            obj.updateIcons()
        except database.ObjectNotFoundError:
            pass

    def expireItem(self, item):
        try:
            obj = app.db.getObjectByID(int(item))
            obj.expire()
        except database.ObjectNotFoundError:
            logging.warning ("tried to expire item that doesn't exist with id %d", int(item))

    def expirePlayingItem(self, item):
        self.expireItem(item)
        app.htmlapp.playbackController.skip(1)

    def addItemToLibrary(self, item):
        obj = app.db.getObjectByID(int(item))
        manualFeed = util.getSingletonDDBObject(views.manualFeed)
        obj.setFeed(manualFeed.getID())

    def keepItem(self, item):
        obj = app.db.getObjectByID(int(item))
        obj.save()

    def stopUploadItem(self, item):
        obj = app.db.getObjectByID(int(item))
        obj.stopUpload()

    def pauseUploadItem(self, item):
        obj = app.db.getObjectByID(int(item))
        obj.pauseUpload()

    def resumeUploadItem(self, item):
        obj = app.db.getObjectByID(int(item))
        obj.startUpload()

    def toggleMoreItemInfo(self, item):
        obj = app.db.getObjectByID(int(item))
        obj.toggleShowMoreInfo()

    def revealItem(self, item):
        obj = app.db.getObjectByID(int(item))
        filename = obj.getFilename()
        if not os.path.exists(filename):
            basename = os.path.basename(filename)
            title = _("Error Revealing File")
            msg = _("The file \"%s\" was deleted from outside Miro.") % basename
            dialogs.MessageBoxDialog(title, msg).run()
        else:
            app.delegate.revealFile(filename)

    def clearTorrents (self):
        items = views.items.filter(lambda x: x.getFeed().url == u'dtv:manualFeed' and x.isNonVideoFile() and not x.getState() == u"downloading")
        for i in items:
            if i.downloader is not None:
                i.downloader.setDeleteFiles(False)
            i.remove()

    def pauseDownload(self, item):
        obj = app.db.getObjectByID(int(item))
        obj.pause()
        
    def resumeDownload(self, item):
        obj = app.db.getObjectByID(int(item))
        obj.resume()

    def pauseAll (self):
        autodler.pauseDownloader()
        for item in views.downloadingItems:
            item.pause()
        seeding_downloads = views.items.filter(
            lambda x: (x.downloader
                       and x.downloader.getState() == 'uploading' 
                       and not (x.getFeed().url == 'dtv:manualFee'
                       and x.isNonVideoFile())))
        for item in seeding_downloads:
            item.pauseUpload()

    def resumeAll (self):
        for item in views.pausedItems:
            item.resume()
        autodler.resumeDownloader()
        paused_seeding_downloads = views.items.filter(
            lambda x: (x.downloader
                       and x.downloader.getState() == 'uploading-paused'
                       and not (x.getFeed().url == 'dtv:manualFeed'
                       and x.isNonVideoFile())))
        for item in paused_seeding_downloads:
            item.startUpload()


    def toggleExpand(self, id):
        obj = app.db.getObjectByID(int(id))
        obj.setExpanded(not obj.getExpanded())

    def setRunAtStartup(self, value):
        value = (value == "1")
        app.delegate.setRunAtStartup(value)

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
        obj = app.db.getObjectByID(int(item))
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
        app.delegate.openExternalURL(url)

    # Race conditions:
    # We do the migration in the dl_daemon if the dl_daemon knows about it
    # so that we don't get a race condition.
    @eventloop.asUrgent
    def changeMoviesDirectory(self, newDir, migrate):
        if not util.directoryWritable(newDir):
            dialog = dialogs.MessageBoxDialog(
                    _("Error Changing Movies Directory"), 
                    _("You don't have permission to write to the directory you selected.  Miro will continue to use the old videos directory."))
            dialog.run()
            return
        app.controller.changeMoviesDirectory(newDir, migrate)

# Test shim for test* functions on GUIActionHandler
class printResultThread(threading.Thread):

    def __init__(self, format, func):
        self.format = format
        self.func = func
        threading.Thread.__init__(self)

    def run(self):
        print (self.format % (self.func(), ))

# Functions that change the history of a guide
class HistoryActionHandler:

    def __init__(self, display):
        self.display = display

    def gotoURL(self, newURL):
        self.display.execJS('top.miro_guide_frame.location="%s"' % newURL)

    def getGuide(self):
        guides = [t.obj for t in app.selection.getSelectedTabs()]
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

# Functions that are safe to call from action: URLs that can change
# the GUI presentation (and may or may not manipulate the database.)
class GUIActionHandler:

    def playUnwatched(self):
        app.htmlapp.playView(views.unwatchedItems)

    def openFile(self, path):
        singleclick.openFile(path)

    def addSearchFeed(self, term=None, style = dialogs.SearchChannelDialog.CHANNEL, location = None):
        def baseTitle(dialog):
            if dialog.style != dialogs.SearchChannelDialog.ENGINE:
                return None
            return "%s: %s" % (searchengines.getEngineTitle(dialog.location), dialog.term)

        def doAdd(dialog):
            if dialog.choice == dialogs.BUTTON_CREATE_CHANNEL:
                self.addFeed(dialog.getURL(), baseTitle=baseTitle(dialog))
        dialog = dialogs.SearchChannelDialog(term, style, location)
        if location == None:
            dialog.run(doAdd)
        else:
            self.addFeed(dialog.getURL(), baseTitle=baseTitle(dialog))

    def addChannelSearchFeed(self, id):
        feed = app.db.getObjectByID(int(id))
        self.addSearchFeed(feed.inlineSearchTerm, dialogs.SearchChannelDialog.CHANNEL, int(id))

    def addEngineSearchFeed(self, term, name):
        self.addSearchFeed(term, dialogs.SearchChannelDialog.ENGINE, name)
        
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
    def addFeed(self, url = None, showTemplate = None, selected = '1', baseTitle = None):
        if url:
            util.checkU(url)
        def doAdd (url):
            app.db.confirmDBThread()
            myFeed = feed.getFeedByURL (url)
            if myFeed is None:
                myFeed = feed.Feed(url)
                if baseTitle:
                    myFeed.setBaseTitle(baseTitle)
    
            if selected == '1':
                app.selection.selectTabByObject(myFeed)
            else:
                myFeed.blink()
        self.addURL (Template(_("$shortAppName - Add Channel")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the channel to add"), doAdd, url)

    def selectFeed(self, url):
        url = feed.normalizeFeedURL(url)
        app.db.confirmDBThread()
        # Find the feed
        myFeed = feed.getFeedByURL (url)
        if myFeed is None:
            logging.warning ("selectFeed: no such feed: %s", url)
            return
        app.selection.selectTabByObject(myFeed)
        
    def addGuide(self, url = None, selected = '1'):
        def doAdd(url):
            app.db.confirmDBThread()
            myGuide = guide.getGuideByURL (url)
            if myGuide is None:
                myGuide = guide.ChannelGuide(url, [u'*'])
    
            if selected == '1':
                app.selection.selectTabByObject(myGuide)
        self.addURL (Template(_("$shortAppName - Add Miro Guide")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the Miro Guide to add"), doAdd, url)

    def addDownload(self, url = None):
        def doAdd(url):
            app.db.confirmDBThread()
            singleclick.downloadURL(url)
        self.addURL (Template(_("$shortAppName - Download Video")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the video to download"), doAdd, url)

    def handleDrop(self, data, type, sourcedata):
        app.controller.handleDrop(data, type, sourcedata)

    def handleURIDrop(self, data, **kwargs):
        app.controller.handleURIDrop(data, **kwargs)

    def showHelp(self):
        app.delegate.openExternalURL(config.get(prefs.HELP_URL))

    def reportBug(self):
        app.delegate.openExternalURL(config.get(prefs.BUG_REPORT_URL))

# Functions that are safe to call from action: URLs that change state
# specific to a particular instantiation of a template, and so have to
# be scoped to a particular HTML display widget.
class TemplateActionHandler:
    
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
        template = TemplateDisplay(name, state, frameHint=app.htmlapp.frame,
                areaHint=app.htmlapp.frame.mainDisplay, baseURL=baseURL,
                *args, **kargs)
        app.htmlapp.frame.selectDisplay(template,
                app.htmlapp.frame.mainDisplay)
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
        app.htmlapp.playView(view, firstItemId)

    def playOneItem(self, viewName, itemID):
        try:
            view = self.templateHandle.getTemplateVariable(viewName)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable (%s) during playOneItem()" % (viewName,))
            return
        app.htmlapp.playView(view, itemID, justPlayOne=True)

    def playNewVideos(self, id):
        try:
            obj = app.db.getObjectByID(int(id))
        except database.ObjectNotFoundError:
            return

        def myUnwatchedItems(obj):
            return (obj.getState() == u'newly-downloaded' and
                    not obj.isNonVideoFile() and
                    not obj.isContainerItem)

        app.selection.selectTabByObject(obj, sendSignal=False)
        if isinstance(obj, feed.Feed):
            feedView = views.items.filterWithIndex(indexes.itemsByFeed,
                    obj.getID())
            view = feedView.filter(myUnwatchedItems,
                                   sortFunc=sorts.item)
            app.htmlapp.playView(view)
            view.unlink()
        elif isinstance(obj, folder.ChannelFolder):
            folderView = views.items.filterWithIndex(
                    indexes.itemsByChannelFolder, obj)
            view = folderView.filter(myUnwatchedItems,
                                     sortFunc=sorts.item)
            app.htmlapp.playView(view)
            view.unlink()
        elif isinstance(obj, tabs.StaticTab): # new videos tab
            view = views.unwatchedItems
            app.htmlapp.playView(view)
        else:
            raise TypeError("Can't get new videos for %s (type: %s)" % 
                    (obj, type(obj)))

    def playItemExternally(self, itemID):
        app.htmlapp.playbackController.playItemExternallyByID(itemID)
        
    def skipItem(self, itemID):
        app.htmlapp.playbackController.skip(1)
    
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

    def sortBy(self, by):
        try:
            self.templateHandle.getTemplateVariable('setSortBy')(by, self.templateHandle)
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
        app.selection.selectItem(area, view, int(id), shift, ctrl)

    def handleContextMenuSelect(self, id, area, viewName):
        from miro.frontends.html import contextmenu
        try:
            obj = app.db.getObjectByID(int(id))
        except:
            traceback.print_exc()
        else:
            try:
                view = self.templateHandle.getTemplateVariable(viewName)
            except KeyError, e: # user switched templates before we got this
                logging.warning ("KeyError in getTemplateVariable (%s) during handleContextMenuSelect()" % (viewName,))
                return
            if not app.selection.isSelected(area, view, int(id)):
                self.handleSelect(area, viewName, id, False, False)
            popup = contextmenu.makeContextMenu(self.currentName, view,
                    app.selection.getSelectionForArea(area), int(id))
            if popup:
                app.delegate.showContextMenu(popup)

    def __getSearchFeeds(self):
        searchFeed = app.controller.getGlobalFeed('dtv:search')
        assert searchFeed is not None
        
        searchDownloadsFeed = app.controller.getGlobalFeed('dtv:searchDownloads')
        assert searchDownloadsFeed is not None

        return (searchFeed, searchDownloadsFeed)

    # The Windows XUL port can send a setVolume or setVideoProgress at
    # any time, even when there's no video display around. We can just
    # ignore it
    def setVolume(self, level):
        pass
    def setVideoProgress(self, pos):
        pass

