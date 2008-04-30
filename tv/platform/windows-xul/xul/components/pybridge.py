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

# This space is only for system import that we are *absolutely* sure will
# work.  If you think an import could possible fail, put it in the
# try...finally block below.
from gettext import gettext as _
from xpcom import components
import ctypes
import logging
import os
import shutil
import sys
import traceback
import _winreg

try:
    from miro.platform.xulhelper import makeService, makeComp, proxify
    from miro.platform.utils import initializeLocale, setupLogging, getLongPathName, makeURLSafe
    initializeLocale()
    setupLogging()
    from miro import gtcache
    gtcache.init()
    from miro import app
    from miro import controller
    from miro import eventloop
    from miro import config
    from miro import dialogs
    from miro.frontends.html import keyboard
    from miro import folder
    from miro import playlist
    from miro import prefs
    from miro import singleclick
    from miro import startup
    from miro import util
    from miro import menubar
    from miro import feed
    from miro import database
    from miro.platform.frontends.html import startup as platform_startup
    from miro.platform.frontends.html import HTMLDisplay
    from miro.platform.frontends.html.Application import Application
    from miro.platform.frontends.html.MainFrame import MainFrame
    from miro.eventloop import asUrgent, asIdle
    from miro import searchengines
    from miro import views
    from miro import moviedata
    from miro.platform import migrateappname
    from miro.platform import specialfolders
    from miro import signals
    from miro import u3info
    moviedata.RUNNING_MAX = 1
except:
    errorOnImport = True
    import traceback
    importErrorMessage = (_("Error importing modules:\n%s") %
            ''.join(traceback.format_exc()))

    # we need to make a fake asUrgent since we probably couldn't import
    # eventloop.
    def asUrgent(func):
        return func
    def asIdle(func):
        return func
else:
    errorOnImport = False
    # See http://www.xulplanet.com/tutorials/xultu/keyshort.html
    XUL_MOD_STRINGS = {menubar.CTRL : 'control',
                       menubar.ALT:   'alt',
                       menubar.SHIFT: 'shift'}
    XUL_KEY_STRINGS ={ menubar.RIGHT_ARROW: 'VK_RIGHT',
                       menubar.LEFT_ARROW:  'VK_LEFT',
                       menubar.UP_ARROW:    'VK_UP',
                       menubar.DOWN_ARROW:  'VK_DOWN',
                       menubar.SPACE : 'VK_SPACE',
                       menubar.ENTER: 'VK_ENTER',
                       menubar.DELETE: 'VK_DELETE',
                       menubar.BKSPACE: 'VK_BACK',
                       menubar.F1: 'VK_F1',
                       menubar.F2: 'VK_F2',
                       menubar.F3: 'VK_F3',
                       menubar.F4: 'VK_F4',
                       menubar.F5: 'VK_F5',
                       menubar.F6: 'VK_F6',
                       menubar.F7: 'VK_F7',
                       menubar.F8: 'VK_F8',
                       menubar.F9: 'VK_F9',
                       menubar.F10: 'VK_F10',
                       menubar.F11: 'VK_F11',
                       menubar.F12: 'VK_F12'}

# Extent the ShortCut class to include a XULString() function
def XULKey(shortcut):
    if isinstance(shortcut.key, int):
        return XUL_KEY_STRINGS[shortcut.key]
    else:
        return shortcut.key.upper()

def XULModifier(shortcut):
    if shortcut.key is None:
        return None
    output = []
    for modifier in shortcut.modifiers:
        output.append(XUL_MOD_STRINGS[modifier])
    return ' '.join(output)

def XULDisplayedShortcut(item):
    """Return the index of the default shortcut.  Normally items only have 1
    shortcut, which is an easy case.  If items have multiple shortcuts,
    normally we display the last one in the menus, however there are some
    special cases.

    Shortcut indicies are 1-based
    """

    if item.action.startswith("Remove"):
        return 1
    return len(item.shortcuts)

def createProxyObjects():
    """Creates the jsbridge and vlcrenderer xpcom components, then wraps them in
    a proxy object, then stores them in the frontend module.  By making them
    proxy objects, we ensure that the calls to them get made in the xul event
    loop.
    """

    app.jsBridge = makeService("@participatoryculture.org/dtv/jsbridge;1",
        components.interfaces.pcfIDTVJSBridge, True, False)
    app.vlcRenderer = makeService("@participatoryculture.org/dtv/vlc-renderer;1",  components.interfaces.pcfIDTVVLCRenderer, True, False)

def initializeProxyObjects(window):
    app.vlcRenderer.init(window)
    app.jsBridge.init(window)

def initializeHTTPProxy():
    xulprefs = makeService("@mozilla.org/preferences-service;1",components.interfaces.nsIPrefService, False)
    branch = xulprefs.getBranch("network.proxy.")

    if config.get(prefs.HTTP_PROXY_ACTIVE):                     
        branch.setIntPref("type",1)
        branch.setCharPref("http", config.get(prefs.HTTP_PROXY_HOST))
        branch.setCharPref("ssl", config.get(prefs.HTTP_PROXY_HOST))
        branch.setIntPref("http_port", config.get(prefs.HTTP_PROXY_PORT))
        branch.setIntPref("ssl_port", config.get(prefs.HTTP_PROXY_PORT))
        branch.setBoolPref("share_proxy_settings", True)
    else:
        branch.setIntPref("type",0)

def registerHttpObserver():
    observer = makeComp("@participatoryculture.org/dtv/httprequestobserver;1",
        components.interfaces.nsIObserver, False)
    observer_service = makeService("@mozilla.org/observer-service;1",
            components.interfaces.nsIObserverService, False)
    observer_service.addObserver(observer, "http-on-modify-request", False);
        
def getArgumentList(commandLine):
    """Convert a components.interfaces.nsICommandLine component to a list of
    arguments to pass to the singleclick module and a theme to load.

    Returns the tuple (args, theme)
    """

    theme = None
    args = [commandLine.getArgument(i) for i in range(commandLine.length)]
    # filter out the application.ini that gets included
    if len(args) > 0 and args[0].lower().endswith('application.ini'):
        args = args[1:]
    # Here's a massive hack to get command line parameters into config
    for x in range(len(args)-1):
        if args[x] == '--theme':
            theme = args[x+1]
            args[x:x+2] = []
            break
    args = [getLongPathName(path) for path in args]
    return args, theme

# Functions to convert menu information into XUL form
def XULifyLabel(label):
    return label.replace(u'_',u'')
def XULAccelFromLabel(label):
    parts = label.split(u'_')
    if len(parts) > 1:
        return parts[1][0]


def prefsChangeCallback(mapped, id):
    if isinstance (mapped.actualFeed, feed.DirectoryWatchFeedImpl):
        app.jsBridge.directoryWatchAdded (str(id), mapped.dir, mapped.visible);

def prefsRemoveCallback(mapped, id):
    if isinstance (mapped.actualFeed, feed.DirectoryWatchFeedImpl):
        app.jsBridge.directoryWatchRemoved (str(id));


@asIdle
def startPrefs():
    for f in views.feeds:
        if isinstance (f.actualFeed, feed.DirectoryWatchFeedImpl):
            app.jsBridge.directoryWatchAdded (str(f.getID()), f.dir, f.visible)
    views.feeds.addChangeCallback(prefsChangeCallback)
    views.feeds.addAddCallback(prefsChangeCallback)
    views.feeds.addRemoveCallback(prefsRemoveCallback)

@asIdle
def endPrefs():
    views.feeds.removeChangeCallback(prefsChangeCallback)
    views.feeds.removeAddCallback(prefsChangeCallback)
    views.feeds.removeRemoveCallback(prefsRemoveCallback)


class PyBridge:
    _com_interfaces_ = [components.interfaces.pcfIDTVPyBridge]
    _reg_clsid_ = "{F87D30FF-C117-401e-9194-DF3877C926D4}"
    _reg_contractid_ = "@participatoryculture.org/dtv/pybridge;1"
    _reg_desc_ = "Bridge into DTV Python core"

    def __init__(self):
        self.started = False
        self.cursorDisplayCount = 0
        if not errorOnImport:
            migrateappname.migrateSupport('Democracy Player', 'Miro')

    def getStartupError(self):
        if not errorOnImport:
            return ""
        else:
            return importErrorMessage

    def onStartup(self, window):
        if self.started:
            signals.system.failed(_("Loading window"), 
                details=_("onStartup called twice"))
            return
        else:
            self.started = True
        initializeProxyObjects(window)
        registerHttpObserver()
        initializeHTTPProxy()
        Application().run()

    @asUrgent
    def initializeViews(self):
        views.initialize()

    def onShutdown(self):
        app.vlcRenderer.stop()
        app.controller.onShutdown()

    def deleteVLCCache(self):
        if specialfolders.appDataDirectory:
            vlcCacheDir = os.path.join(specialfolders.appDataDirectory, 
                    "PCF-VLC")
            shutil.rmtree(vlcCacheDir, ignore_errors=True)

    def shortenDirectoryName(self, path):
        """Shorten a directory name by recognizing well-known nicknames, like
        "Desktop", and "My Documents"
        """

        tries = [ "My Music", "My Pictures", "My Videos", "My Documents",
            "Desktop", 
        ]

        for name in tries:
            virtualPath = specialfolders.getSpecialFolder(name)
            if virtualPath is None:
                continue
            if path == virtualPath:
                return name
            elif path.startswith(virtualPath):
                relativePath = path[len(virtualPath):]
                if relativePath.startswith("\\"):
                    return name + relativePath
                else:
                    return "%s\\%s" % (name, relativePath)
        return path


    # Preference setters/getters.
    #
    # NOTE: these are not in the mail event loop, so we have to be careful in
    # accessing data.  config.get and config.set are threadsafe though.
    #
    def getRunAtStartup(self):
        return config.get(prefs.RUN_AT_STARTUP)
    def setRunAtStartup(self, value):
        platform_startup.setRunAtStartup(value)
        config.set(prefs.RUN_AT_STARTUP, value)
    def getCheckEvery(self):
        return config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)
    def setCheckEvery(self, value):
        return config.set(prefs.CHECK_CHANNELS_EVERY_X_MN, value)
    def getAutoDownloadDefault(self):
        return config.get(prefs.CHANNEL_AUTO_DEFAULT)
    def setAutoDownloadDefault(self, value):
        return config.set(prefs.CHANNEL_AUTO_DEFAULT, value)
    def getMoviesDirectory(self):
        return config.get(prefs.MOVIES_DIRECTORY)
    def changeMoviesDirectory(self, path, migrate):
        app.controller.changeMoviesDirectory(path, migrate)
    def getLimitUpstream(self):
        return config.get(prefs.LIMIT_UPSTREAM)
    def setLimitUpstream(self, value):
        config.set(prefs.LIMIT_UPSTREAM, value)
    def getLimitUpstreamAmount(self):
        return config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
    def setLimitUpstreamAmount(self, value):
        return config.set(prefs.UPSTREAM_LIMIT_IN_KBS, value)
    def getLimitDownstream(self):
        return config.get(prefs.LIMIT_DOWNSTREAM_BT)
    def setLimitDownstream(self, value):
        config.set(prefs.LIMIT_DOWNSTREAM_BT, value)
    def getLimitDownstreamAmount(self):
        return config.get(prefs.DOWNSTREAM_BT_LIMIT_IN_KBS)
    def setLimitDownstreamAmount(self, value):
        return config.set(prefs.DOWNSTREAM_BT_LIMIT_IN_KBS, value)
    def getMaxManual(self):
        return config.get(prefs.MAX_MANUAL_DOWNLOADS)
    def setMaxManual(self, value):
        return config.set(prefs.MAX_MANUAL_DOWNLOADS, value)
    def getMaxAuto(self):
        return config.get(prefs.DOWNLOADS_TARGET)
    def setMaxAuto(self, value):
        return config.set(prefs.DOWNLOADS_TARGET, value)
    def startPrefs(self):
        startPrefs()
    def updatePrefs(self):
        endPrefs()
    def getPreserveDiskSpace(self):
        return config.get(prefs.PRESERVE_DISK_SPACE)
    def setPreserveDiskSpace(self, value):
        config.set(prefs.PRESERVE_DISK_SPACE, value)
    def getPreserveDiskSpaceAmount(self):
        return config.get(prefs.PRESERVE_X_GB_FREE)
    def setPreserveDiskSpaceAmount(self, value):
        return config.set(prefs.PRESERVE_X_GB_FREE, value)
    def getExpireAfter(self):
        return config.get(prefs.EXPIRE_AFTER_X_DAYS)
    def setExpireAfter(self, value):
        return config.set(prefs.EXPIRE_AFTER_X_DAYS, value)
    def getSinglePlayMode(self):
        return config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE)
    def setSinglePlayMode(self, value):
        return config.set(prefs.SINGLE_VIDEO_PLAYBACK_MODE, value)
    def getResumeVideosMode(self):
        return config.get(prefs.RESUME_VIDEOS_MODE)
    def setResumeVideosMode(self, value):
        return config.set(prefs.RESUME_VIDEOS_MODE, value)
    def getBTMinPort(self):
        return config.get(prefs.BT_MIN_PORT)
    def setBTMinPort(self, value):
        return config.set(prefs.BT_MIN_PORT, value)
    def getBTMaxPort(self):
        return config.get(prefs.BT_MAX_PORT)
    def setBTMaxPort(self, value):
        return config.set(prefs.BT_MAX_PORT, value)
    def getStartupTasksDone(self):
        if u3info.u3_active:
            config.set(prefs.STARTUP_TASKS_DONE, True)
        return config.get(prefs.STARTUP_TASKS_DONE)
    def setStartupTasksDone(self, value):
        return config.set(prefs.STARTUP_TASKS_DONE, value)
    def getWarnIfDownloadingOnQuit(self):
        return config.get(prefs.WARN_IF_DOWNLOADING_ON_QUIT)
    def setWarnIfDownloadingOnQuit(self, value):
        return config.set(prefs.WARN_IF_DOWNLOADING_ON_QUIT, value)
    def getUseUpnp(self):
        return config.get(prefs.USE_UPNP)
    def setUseUpnp(self, value):
        config.set(prefs.USE_UPNP, value)
    def getBitTorrentEncReq(self):
        return config.get(prefs.BT_ENC_REQ)
    def setBitTorrentEncReq(self, value):
        config.set(prefs.BT_ENC_REQ, value)
    def getBitTorrentLimitUploadRatio(self):
        return config.get(prefs.LIMIT_UPLOAD_RATIO)
    def setBitTorrentLimitUploadRatio(self, value):
        config.set(prefs.LIMIT_UPLOAD_RATIO, value)
    def getBitTorrentUploadRatio(self):
        return config.get(prefs.UPLOAD_RATIO)
    def setBitTorrentUploadRatio(self, value):
        config.set(prefs.UPLOAD_RATIO, value)

    def handleCommandLine(self, commandLine):
        args, theme = getArgumentList(commandLine)
        startup.initialize(theme)
        # Doesn't matter if this executes before the call to
        # parseCommandLineArgs in app.py. -clahey
        self._handleCommandLine(args)

    def handleSecondaryCommandLine(self, commandLine):
        """Handle a command line that was passed to Miro from a second
        instance (for example Miro was running, then the user opened a video
        file with miro).
        """

        args, theme = getArgumentList(commandLine)
        self._handleCommandLine(args)

    @asUrgent
    def _handleCommandLine(self, args):
        singleclick.handleCommandLineArgs(args)

    def pageLoadFinished(self, area, url):
        eventloop.addUrgentCall(HTMLDisplay.runPageFinishCallback, 
                "%s finish callback" % area, args=(area, url))

    @asUrgent
    def openFile(self, path):
        singleclick.openFile(getLongPathName(path))

    @asUrgent
    def setVolume(self, volume):
        volume = float(volume)
        config.set(prefs.VOLUME_LEVEL, volume)
        if hasattr(app.htmlapp, 'videoDisplay'):
            app.htmlapp.videoDisplay.setVolume(volume, moveSlider=False)

    @asUrgent
    def quit(self):
        if app.controller.finishedStartup:
            app.htmlapp.quit()

    @asUrgent
    def removeCurrentChannel(self):
        app.controller.removeCurrentFeed()

    @asUrgent
    def updateCurrentChannel(self):
        app.controller.updateCurrentFeed()

    @asUrgent
    def updateChannels(self):
        app.controller.updateAllFeeds()

    @asUrgent
    def showHelp(self):
        app.delegate.openExternalURL(config.get(prefs.HELP_URL))

    @asUrgent
    def reportBug(self):
        app.delegate.openExternalURL(config.get(prefs.BUG_REPORT_URL))

    @asUrgent
    def copyChannelLink(self):
        app.htmlapp.copyCurrentFeedURL()

    @asUrgent
    def handleContextMenu(self, index):
        app.delegate.handleContextMenu(index)

    @asUrgent
    def handleSimpleDialog(self, id, buttonIndex):
        app.delegate.handleDialog(id, buttonIndex)

    @asUrgent
    def handleCheckboxDialog(self, id, buttonIndex, checkbox_value):
        app.delegate.handleDialog(id, buttonIndex,
                checkbox_value=checkbox_value)
    @asUrgent
    def handleCheckboxTextboxDialog(self, id, buttonIndex, checkbox_value,
                                    textbox_value):
        app.delegate.handleDialog(id, buttonIndex,
                                   checkbox_value=checkbox_value,
                                   textbox_value=textbox_value)

    @asUrgent
    def handleHTTPAuthDialog(self, id, buttonIndex, username, password):
        app.delegate.handleDialog(id, buttonIndex, username=username,
                password=password)

    @asUrgent
    def handleTextEntryDialog(self, id, buttonIndex, text):
        app.delegate.handleDialog(id, buttonIndex, value=text)

    @asUrgent
    def handleSearchChannelDialog(self, id, buttonIndex, term, style, loc):
        app.delegate.handleDialog(id, buttonIndex, term=term, style=style, loc=loc)
    @asUrgent
    def handleFileDialog(self, id, pathname):
        app.delegate.handleFileDialog(id, pathname)

    @asUrgent
    def addChannel(self, url):
        app.htmlapp.addAndSelectFeed(url)

    @asUrgent
    def openURL(self, url):
        app.delegate.openExternalURL(url)

    @asUrgent
    def playPause(self):
        app.htmlapp.playbackController.playPause()

    @asUrgent
    def pause(self):
        if hasattr(app.controller, 'playbackController'):
            app.htmlapp.playbackController.pause()

    @asUrgent
    def stop(self):
        app.htmlapp.playbackController.stop()

    @asUrgent
    def skip(self, step):
        app.htmlapp.playbackController.skip(step)

    @asUrgent
    def skipPrevious(self):
        app.htmlapp.playbackController.skip(-1, allowMovieReset=False)

    @asUrgent
    def fastForward(self):
        keyboard.handleKey(keyboard.RIGHT, False, False)

    @asUrgent
    def rewind(self):
        keyboard.handleKey(keyboard.LEFT, False, False)

    @asUrgent
    def onMovieFinished(self):
        app.htmlapp.playbackController.onMovieFinished()

    @asUrgent
    def loadURLInBrowser(self, browserId, url):
        try:
            display = app.htmlapp.frame.selectedDisplays[browserId]
        except KeyError:
            print "No HTMLDisplay for %s in loadURLInBrowser: "% browserId
        else:
            display.onURLLoad(url)

    @asUrgent
    def performSearch(self, engine, query):
        app.htmlapp.performSearch(engine, query)

    # Returns a list of search engine titles and names
    # Should we just keep a map of engines to names?
    def getSearchEngineNames(self):
        out = []
        for engine in views.searchEngines:
            out.append(engine.name)
        return out
    def getSearchEngineTitles(self):
        out = []
        for engine in views.searchEngines:
            out.append(engine.title)
        return out

    def showCursor(self, display):
        # ShowCursor has an amazing API.  From Microsoft:
        #
        # This function sets an internal display counter that determines
        # whether the cursor should be displayed. The cursor is displayed
        # only if the display count is greater than or equal to 0. If a
        # mouse is installed, the initial display count is 0.  If no mouse
        # is installed, the display count is -1
        #
        # How do we get the initial display count?  There's no method.  We
        # assume it's 0 and the mouse is plugged in.
        if ((display and self.cursorDisplayCount >= 0) or
                (not display and self.cursorDisplayCount < 0)):
            return
        if display:
            arg = 1
        else:
            arg = 0
        self.cursorDisplayCount = ctypes.windll.user32.ShowCursor(arg)

    @asUrgent
    def createNewPlaylist(self):
        playlist.createNewPlaylist()

    @asUrgent
    def createNewPlaylistFolder(self):
        folder.createNewPlaylistFolder()

    @asUrgent
    def createNewSearchChannel(self):
        app.htmlapp.addSearchFeed()

    @asUrgent
    def createNewChannelFolder(self):
        folder.createNewChannelFolder()

    @asUrgent
    def handleDrop(self, dropData, dropType, sourceData):
        app.controller.handleDrop(dropData, dropType, sourceData)


    @asUrgent
    def removeCurrentSelection(self):
        app.controller.removeCurrentSelection()

    def checkForUpdates(self):
        app.htmlapp.checkForUpdates()

    @asUrgent
    def removeCurrentItems(self):
        app.controller.removeCurrentItems()

    @asUrgent
    def copyCurrentItemURL(self):
        app.htmlapp.copyCurrentItemURL()

    @asUrgent
    def selectAllItems(self):
        app.controller.selectAllItems()

    @asUrgent
    def createNewChannelFolder(self):
        folder.createNewChannelFolder()

    @asUrgent
    def createNewChannelGuide(self):
        app.htmlapp.addAndSelectGuide()

    @asUrgent
    def createNewDownload(self):
        app.htmlapp.newDownload()

    def importChannels(self):
        app.htmlapp.importChannels()

    def exportChannels(self):
        app.htmlapp.exportChannels()

    @asUrgent
    def addChannel(self):
        app.htmlapp.addAndSelectFeed()

    @asUrgent
    def renameCurrentChannel(self):
        app.controller.renameCurrentChannel()

    @asUrgent
    def recommendCurrentChannel(self):
        app.htmlapp.recommendCurrentFeed()

    @asUrgent
    def renameCurrentPlaylist(self):
        app.controller.renameCurrentPlaylist()

    @asUrgent
    def removeCurrentPlaylist(self):
        app.controller.removeCurrentPlaylist()

    def openDonatePage(self):
        app.delegate.openExternalURL(config.get(prefs.DONATE_URL))

    def openBugTracker(self):
        # This call could be coming as a result of a startup error, so we
        # have to assume as little as possible here.  It's possible the error
        # happened when importing some miro module.
        try:
            from miro import config
            from miro import prefs
            # If possible get the UIBackendDelegate from app, but maybe that
            # hasn't been set up yet.
            try:
                from miro import app
                delegate = app.delegate
            except:
                from miro.platform.frontends.html.UIBackendDelegate import UIBackendDelegate
                delegate = UIBackendDelegate()
            delegate = UIBackendDelegate()
            delegate.openExternalURL(config.get(prefs.BUG_TRACKER_URL))
        except:
            logging.warn("Error in openBugTracker():\n%s", 
                    ''.join(traceback.format_exc()))

    @asUrgent
    def saveVideoFile(self, path):
        if MainFrame.currentVideoPath is None:
            return
        app.controller.saveVideo(MainFrame.currentVideoPath, path)

    def startupDoSearch(self, path):
        if path.endswith(":"):
            path = path + "\\" # convert C: to C:\
        platform_startup.doSearch(path)

    def startupCancelSearch(self):
        platform_startup.cancelSearch()

    def getSpecialFolder(self, name):
        return specialfolders.getSpecialFolder(name)

    def extractFinish (self, duration, screenshot_success):
        app.htmlapp.videoDisplay.extractFinish(duration, screenshot_success)

    def createProxyObjects(self):
        createProxyObjects()

    def printOut(self, output):
        print output

    def addMenubar(self, document):
        menubarElement = document.getElementById("titlebar-menu")
        trayMenuElement = document.getElementById("traypopup")
        keysetElement = document.createElementNS(
         "http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","keyset")

        for menu in (menubar.menubar.menus + (menubar.traymenu,)):
            for item in menu.menuitems:
                if isinstance(item, menubar.MenuItem):
                    count = 0
                    for shortcut in item.shortcuts:
                        count += 1
                        keyElement = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","key")
                        keyElement.setAttribute("id", "%s-key%d" % (item.action, count))
                        if len(XULKey(shortcut)) == 1:
                            keyElement.setAttribute("key", XULKey(shortcut))
                        else:
                            keyElement.setAttribute("keycode", XULKey(shortcut))
                        if XULKey(shortcut) == 'VK_SPACE':
                            # spacebar doesn't get display text for some reason
                            keyElement.setAttribute('keytext', _('Spacebar'))
                        if len(shortcut.modifiers) > 0:
                            keyElement.setAttribute("modifiers", XULModifier(shortcut))
                        keyElement.setAttribute("command", item.action)
                        keysetElement.appendChild(keyElement)
        menubarElement.appendChild(keysetElement)

        for menu in menubar.menubar.menus:
            menuElement = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menu")
            menuElement.setAttribute("id", "menu-%s" % menu.action.lower())
            menuElement.setAttribute("label", XULifyLabel(menu.getLabel(menu.action)))
            if XULAccelFromLabel(menu.getLabel(menu.action)):
                menuElement.setAttribute("accesskey", XULAccelFromLabel(menu.getLabel(menu.action)))
            menupopup = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menupopup")

            menupopup.setAttribute("id", "menupopup-%s" % menu.action.lower())
            menuElement.appendChild(menupopup)
            menubarElement.appendChild(menuElement)
            for item in menu.menuitems:
                if isinstance(item, menubar.Separator):
                    menuitem = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menuseparator")
                else:
                    menuitem = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menuitem")
                    menuitem.setAttribute("id","menuitem-%s" % item.action.lower())
                    menuitem.setAttribute("label",XULifyLabel(menu.getLabel(item.action)))
                    menuitem.setAttribute("command", item.action)
                    if XULAccelFromLabel(item.label):
                        menuitem.setAttribute("accesskey",
                                          XULAccelFromLabel(item.label))
                    if len(item.shortcuts)>0:
                        menuitem.setAttribute("key","%s-key%d"%(item.action,
                            XULDisplayedShortcut(item)))
                        
                menupopup.appendChild(menuitem)

        for item in menubar.traymenu.menuitems:
            if isinstance(item, menubar.Separator):
                menuitem = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menuseparator")
            else:
                menuitem = document.createElementNS("http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul","menuitem")
                menuitem.setAttribute("id","traymenu-%s" % item.action.lower())
                menuitem.setAttribute("label",XULifyLabel(item.label))
                menuitem.setAttribute("command", item.action)
                if XULAccelFromLabel(item.label):
                    menuitem.setAttribute("accesskey",
                                          XULAccelFromLabel(item.label))
                if len(item.shortcuts)>0:
                    menuitem.setAttribute("key","%s-key%d"%(item.action,len(item.shortcuts)))
                        
            trayMenuElement.appendChild(menuitem)

    # Grab the database information, then throw it over the fence to
    # the UI thread
    @asIdle
    def updateTrayMenus(self):
        if views.initialized:
            numUnwatched = len(views.unwatchedItems)
            numDownloading = len(views.downloadingItems)
            numPaused = len(views.pausedItems)
        else:
            numPaused = numDownloading = numUnwatched = 0
        app.jsBridge.updateTrayMenus(numUnwatched, numDownloading, numPaused)

    # HACK ALERT - We should change this to take a dictionary instead
    # of all of the possible database variables. Since there's no
    # equivalent in XPCOM, it would be a pain, so we can wait. -- NN
    def getLabel(self,action,state,unwatched = 0,downloading = 0, paused = 0):
        variables = {}
        variables['numUnwatched'] = unwatched
        variables['numDownloading'] = downloading
        variables['numPaused'] = paused

        # Ih8XPCOM
        if len(state) == 0:
            state = None

        ret = XULifyLabel(menubar.menubar.getLabel(action,state,variables))
        if ret == action:
            ret = XULifyLabel(menubar.traymenu.getLabel(action,state, variables))
        return ret

    @asIdle
    def addDirectoryWatch(self, filename):
        feed.Feed (u"dtv:directoryfeed:%s" % (makeURLSafe(filename),))

    @asIdle
    def removeDirectoryWatch(self, id):
        try:
            obj = database.defaultDatabase.getObjectByID (int(id))
            app.controller.removeFeeds ([obj])
        except:
            pass

    @asIdle
    def toggleDirectoryWatchShown(self, id):
        try:
            obj = database.defaultDatabase.getObjectByID (int(id))
            obj.setVisible (not obj.visible)
        except:
            pass

    def playUnwatched(self):
        minimizer = makeService(
            "@participatoryculture.org/dtv/minimize;1",
            components.interfaces.pcfIDTVMinimize, False)
        if minimizer.isMinimized():
            minimizer.minimizeOrRestore()
        app.htmlapp.frame.mainDisplayCallback(u'action:playUnwatched')

    @asIdle
    def pauseDownloads(self):
        app.htmlapp.frame.mainDisplayCallback(u'action:pauseAll')

    @asIdle
    def resumeDownloads(self):
        app.htmlapp.frame.mainDisplayCallback(u'action:resumeAll')

    def minimizeToTray(self):
        return config.get(prefs.MINIMIZE_TO_TRAY)

    def setMinimizeToTray(self, newSetting):
        config.set(prefs.MINIMIZE_TO_TRAY, newSetting)

    def handleKeyPress(self, keycode, shiftDown, controlDown):
        keycode_to_portable_code = {
            37: keyboard.LEFT,
            38: keyboard.UP,
            39: keyboard.RIGHT,
            40: keyboard.DOWN,
        }
        if keycode in keycode_to_portable_code:
            key = keycode_to_portable_code[keycode]
            keyboard.handleKey(key, shiftDown, controlDown)

    def handleCloseButton(self):
        if not app.controller.finishedStartup:
            return
        if config.get(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE):
            self.askUserForCloseBehaviour()
        elif config.get(prefs.MINIMIZE_TO_TRAY):
            minimizer = makeService(
                    "@participatoryculture.org/dtv/minimize;1",
                    components.interfaces.pcfIDTVMinimize, False)
            minimizer.minimizeOrRestore()
        else:
            self.quit()

    def askUserForCloseBehaviour(self):
        title = _("Close to tray?")
        description = _("When you click the red close button, would you like Miro to close to the system tray or quit?  You can change this setting later in the Options.")

        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_CLOSE_TO_TRAY, dialogs.BUTTON_QUIT)
        def callback(dialog):
            if dialog.choice is None:
                return
            if dialog.choice == dialogs.BUTTON_CLOSE_TO_TRAY:
                config.set(prefs.MINIMIZE_TO_TRAY, True)
            else:
                config.set(prefs.MINIMIZE_TO_TRAY, False)
            config.set(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE, False)
            self.handleCloseButton()
        dialog.run(callback)
