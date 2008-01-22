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

"""Startup code.

In general, frontends should do the following to handle startup.

    - (optional) call startup.installMoviesGoneHandler()
    - Call startup.initialize()
    - Wait for either the 'startup-success', or 'startup-failure' signal
"""

from gtcache import gettext as _
from string import Template
import logging
import platform
import os
import traceback

from clock import clock
import app
import autodler
import config
import database
import databaseupgrade
import downloader
import eventloop
import iconcache
import indexes
import item
import feed
import folder
import guide
import moviedata
import playlist
import prefs
import resources
import signals
import tabs
import theme
import util
import searchengines
import storedatabase
import views
import opml

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


def initialize():
    """Initialize Miro and schedule startup.
    
    This method starts up the config system and eventloop however it doesn't
    complete the startup process.  Instead, that gets scheduled to run in the
    event loop.

    Frontends should call this method, then wait for 1 of 2 system signals.
    "startup-success" is fired once the startup is done and the backend is
    ready to go.  "startup-failure" is fired if something bad happned
    """
    logging.info ("Starting up %s", config.get(prefs.LONG_APP_NAME))
    logging.info ("Version:    %s", config.get(prefs.APP_VERSION))
    logging.info ("Revision:   %s", config.get(prefs.APP_REVISION))
    logging.info ("Builder:    %s", config.get(prefs.BUILD_MACHINE))
    logging.info ("Build Time: %s", config.get(prefs.BUILD_TIME))
    util.print_mem_usage("Pre everything memory check")
    logging.info ("Loading preferences...")
    config.load()
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
    setupGuides()

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

    signals.system.startupSuccess()

def setupGlobalFeeds():
    setupGlobalFeed(u'dtv:manualFeed', initiallyAutoDownloadable=False)
    setupGlobalFeed(u'dtv:singleFeed', initiallyAutoDownloadable=False)
    setupGlobalFeed(u'dtv:search', initiallyAutoDownloadable=False)
    setupGlobalFeed(u'dtv:searchDownloads')
    setupGlobalFeed(u'dtv:directoryfeed')

def setupTabs():
    tabs.reloadStaticTabs()
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
    movies_dir = config.get(prefs.MOVIES_DIRECTORY)
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
    description = _("""
Miro can't find your primary video directory.  This may be because it's \
located on an external drive that is currently disconnected.""")
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

def setupGuides():
    _getThemeHistory()

def _getThemeHistory():
    if len(views.themeHistories) > 0:
        return views.themeHistories[0]
    else:
        return theme.ThemeHistory()


