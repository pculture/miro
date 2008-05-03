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

"""Startup code.

In general, frontends should do the following to handle startup.

    - (optional) call startup.installMoviesGoneHandler()
    - Call startup.initialize()
    - Wait for either the 'startup-success', or 'startup-failure' signal
"""

from miro.gtcache import gettext as _
from string import Template
import logging
import os
import traceback

from miro.clock import clock
from miro import app
from miro import autodler
from miro import config
from miro import controller
from miro import database
from miro import databaseupgrade
from miro import downloader
from miro import eventloop
from miro import fileutil
from miro import iconcache
from miro import indexes
from miro import item
from miro import feed
from miro import folder
from miro import guide
from miro import moviedata
from miro import plat
from miro import playlist
from miro import prefs
from miro import selection
from miro.plat import resources
from miro.plat.utils import setupLogging
from miro import signals
from miro import tabs
from miro import theme
from miro import util
from miro import searchengines
from miro import storedatabase
from miro import views
from miro import opml

class StartupError(Exception):
    def __init__(self, summary, description):
        self.summary = summary
        self.description = description

def startupFunction(func):
    """Decorator for startup functions.  This decorator catches exceptions and
    turns them into startup-failure signals.
    """

    def wrapped(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except StartupError, e:
            signals.system.startupFailure(e.summary, e.description)
        except:
            logging.warn("Unknown startup error: %s", traceback.format_exc())
            signals.system.startupFailure(_("Unknown Error"),
                    _("An unkown error prevented Miro from startup.  Please "
                        "file a bug report at %s") %
                    (config.get(prefs.BUG_REPORT_URL)))
    return wrapped

def setupGlobalFeed(url, *args, **kwargs):
    feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
    try:
        if feedView.len() == 0:
            logging.info ("Spawning global feed %s", url)
            # FIXME - variable d never gets used.
            d = feed.Feed(url, *args, **kwargs)
        elif feedView.len() > 1:
            allFeeds = [f for f in feedView]
            for extra in allFeeds[1:]:
                extra.remove()
            signals.system.failed("Too many db objects for %s" % url)
    finally:
        feedView.unlink()

def initialize(themeName):
    """Initialize Miro.  This sets up things like logging and the config
    system and should be called as early as possible.
    """
    setupLogging()
    util.setupLogging()
    app.db = database.defaultDatabase
    app.controller = controller.Controller()
    config.load(themeName)

def startup():
    """Startup Miro.
    
    This method starts up the eventloop and schedules the rest of the startup
    to run in the event loop.

    Frontends should call this method, then wait for 1 of 2 system signals.
    "startup-success" is fired once the startup is done and the backend is
    ready to go.  "startup-failure" is fired if something bad happned

    initialize() must be called before startup().
    """
    logging.info ("Starting up %s", config.get(prefs.LONG_APP_NAME))
    logging.info ("Version:    %s", config.get(prefs.APP_VERSION))
    logging.info ("Revision:   %s", config.get(prefs.APP_REVISION))
    logging.info ("Builder:    %s", config.get(prefs.BUILD_MACHINE))
    logging.info ("Build Time: %s", config.get(prefs.BUILD_TIME))
    util.print_mem_usage("Pre everything memory check")
    eventloop.connect('thread-started', 
            lambda obj, thread: database.set_thread(thread))
    logging.info ("Starting event loop thread")
    eventloop.startup()
    eventloop.addIdle(finishStartup, "finish startup")

@startupFunction
def finishStartup():
    views.initialize()
    util.print_mem_usage("Pre-database memory check:")
    logging.info ("Restoring database...")
    try:
        database.defaultDatabase.liveStorage = storedatabase.LiveStorage()
    except databaseupgrade.DatabaseTooNewError:
        summary = _("Database too new")
        description = Template(_("""\
You have a database that was saved with a newer version of $shortAppName. \
You must download the latest version of $shortAppName and run that.""")).substitute(shortAppName = config.get(prefs.SHORT_APP_NAME))
        raise StartupError(summary, description)
    database.defaultDatabase.recomputeFilters()

    if moviesDirectoryGone():
        global moviesGoneHandler
        moviesGoneHandler()
    else:
        eventloop.addUrgentCall(finalizeStartup, "finalizing startup")

@startupFunction
def finalizeStartup():
    downloader.startupDownloader()

    util.print_mem_usage("Post-downloader memory check")
    setupGlobalFeeds()
    setupTabs()
    searchengines.createEngines()
    setupTheme()

    # Start the automatic downloader daemon
    logging.info ("Spawning auto downloader...")
    autodler.startDownloader()

    item.reconnectDownloaders()
    feed.expireItems()

    starttime = clock()
    iconcache.clearOrphans()
    logging.timing ("Icon clear: %.3f", clock() - starttime)
    logging.info ("Starting movie data updates")
    moviedata.movieDataUpdater.startThread()

    app.selection = selection.SelectionHandler()

    signals.system.startupSuccess()

def setupGlobalFeeds():
    setupGlobalFeed(u'dtv:manualFeed', initiallyAutoDownloadable=False)
    setupGlobalFeed(u'dtv:singleFeed', initiallyAutoDownloadable=False)
    setupGlobalFeed(u'dtv:search', initiallyAutoDownloadable=False)
    setupGlobalFeed(u'dtv:searchDownloads')
    setupGlobalFeed(u'dtv:directoryfeed')

def setupTabs():
    try:
        channelTabOrder = util.getSingletonDDBObject(views.channelTabOrder)
    except LookupError:
        logging.info ("Creating channel tab order")
        tabs.TabOrder(u'channel')
    try:
        util.getSingletonDDBObject(views.playlistTabOrder)
    except LookupError:
        logging.info ("Creating playlist tab order")
        tabs.TabOrder(u'playlist')

def moviesDirectoryGone():
    movies_dir = fileutil.expand_filename(config.get(prefs.MOVIES_DIRECTORY))
    if not movies_dir.endswith(os.path.sep):
        movies_dir += os.path.sep
    try:
        contents = os.listdir(movies_dir)
    except OSError:
        # We can't access the directory.  Seems like it's gone.
        return True
    if contents != []:
        # There's something inside the directory consider it present  (even
        # if all our items are missing.
        return False
    # make sure that we have actually downloaded something into the movies
    # directory. 
    for downloader in views.remoteDownloads:
        if (downloader.isFinished() and
                downloader.getFilename().startswith(movies_dir)):
            return True
    return False

def defaultMoviesGoneHandler():
    summary = _("Video Directory Missing")
    description = Template(_("""
Miro can't find your primary video directory $moviesDirectory.  This may be because it's \
located on an external drive that is currently disconnected.  Please, connect the drive \
or create the directory, then start Miro again.""")).substitute(moviesDirectory = config.get(prefs.MOVIES_DIRECTORY))
    signals.system.startupFailure(summary, description)
moviesGoneHandler =  defaultMoviesGoneHandler

def installMoviesGoneHandler(callback):
    """Install a new movies gone handler.  This method handles the annoying
    case where we are trying to start up, but detect that the movies directory
    appears missing.  By default this causes us to fail starting up, but some
    frontends may want to allow the user to continue.  To do that, they must
    call startup.finalizeStartup().
    """

    global moviesGoneHandler
    moviesGoneHandler = callback

def setupTheme():
    themeHistory = _getThemeHistory()
    themeHistory.checkNewTheme()

def _getThemeHistory():
    if len(views.themeHistories) > 0:
        return views.themeHistories[0]
    else:
        return theme.ThemeHistory()


