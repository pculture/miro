# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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
FIXME
    - (optional) call startup.install_movies_gone_handler()
    - Call startup.initialize()
    - Wait for either the 'startup-success', or 'startup-failure' signal
"""

from miro.gtcache import gettext as _
import logging
import os
import config
import traceback
import threading
import time

from miro.clock import clock
from miro import app
from miro import autodler
from miro import autoupdate
from miro import commandline
from miro import crashreport
from miro import controller
from miro import extensionmanager
from miro import database
from miro import databaselog
from miro import databaseupgrade
from miro import dialogs
from miro import downloader
from miro import eventloop
from miro import fileutil
from miro import guide
from miro import httpauth
from miro import httpclient
from miro import iconcache
from miro import item
from miro import iteminfocache
from miro import feed
from miro import folder
from miro import messages
from miro import messagehandler
from miro import models
from miro import moviedata
from miro import playlist
from miro import prefs
import miro.plat.resources
from miro.plat.utils import setup_logging
from miro.plat import config as platformcfg
from miro import tabs
from miro import theme
from miro import util
from miro import search
from miro import searchengines
from miro import storedatabase
from miro import conversions
from miro import devices
from miro.plat import devicetracker

import miro.extensions

DEBUG_DB_MEM_USAGE = False
mem_usage_test_event = threading.Event()

class StartupError(Exception):
    def __init__(self, summary, description):
        self.summary = summary
        self.description = description

def startup_function(func):
    """Decorator for startup functions.  This decorator catches exceptions and
    turns them into StartupFailure messages.
    """
    def wrapped(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except StartupError, e:
            if e.summary is not None:
                m = messages.StartupFailure(e.summary, e.description)
            else:
                m = messages.FrontendQuit()
            m.send_to_frontend()
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception, exc:
            # we do this so that we only kick up the database error
            # if it's a database-related exception AND the app has a
            # db attribute
            if ((isinstance(exc, (database.DatabaseException,
                                  database.DatabaseStandardError,
                                  storedatabase.sqlite3.OperationalError))
                 and app.db is not None)):

                # somewhere in one of the startup functions, Miro
                # kicked up a database-related problem.  we don't know
                # where it happend, so we can't just start fresh and
                # keep going.  instead we have to start fresh, shut
                # miro down, and on the next run, maybe miro will
                # work.
                msg = exc.message
                if not msg:
                    msg = str(exc)
                logging.exception("Database error on startup:")
                m = messages.StartupDatabaseFailure(
                    _("Database Error"),
                    _("We're sorry, %(appname)s was unable to start up due "
                      "to a problem with the database:\n\n"
                      "Error: %(error)s\n\n"
                      "It's possible that your database file is corrupted and "
                      "cannot be used.\n\n"
                      "You can start fresh and your damaged database will be "
                      "removed, but you will have to re-add your feeds and "
                      "media files.  If you want to do this, press the "
                      "Start Fresh button and restart %(appname)s.\n\n"
                      "To help us fix problems like this in the future, "
                      "please file a bug report at %(url)s.",
                      {"appname": app.config.get(prefs.SHORT_APP_NAME),
                       "url": app.config.get(prefs.BUG_REPORT_URL),
                       "error": msg}
                      ))
                m.send_to_frontend()

            else:
                logging.warn(
                    "Unknown startup error: %s", traceback.format_exc())
                m = messages.StartupFailure(
                    _("Unknown Error"),
                    _("An unknown error prevented %(appname)s from startup.  "
                      "Please file a bug report at %(url)s.",
                      {"appname": app.config.get(prefs.SHORT_APP_NAME),
                       "url": app.config.get(prefs.BUG_REPORT_URL)}
                      ))
                m.send_to_frontend()
    return wrapped

def _movies_directory_gone_handler(callback):
    """Default _movies_directory_gone_handler.  The frontend should
    override this using the ``install_movies_directory_gone_handler``
    function.
    """
    logging.error("Movies directory is gone -- no handler installed!")
    eventloop.add_urgent_call(callback, "continuing startup")

def install_movies_directory_gone_handler(callback):
    global _movies_directory_gone_handler
    _movies_directory_gone_handler = callback

def _first_time_handler(callback):
    """Default _first_time_handler.  The frontend should override this
    using the ``install_first_time_handler`` function.
    """
    logging.error("First time -- no handler installed.")
    eventloop.add_urgent_call(callback, "continuing startup")

def install_first_time_handler(callback):
    global _first_time_handler
    _first_time_handler = callback

def setup_global_feed(url, *args, **kwargs):
    view = feed.Feed.make_view('origURL=?', (url,))
    view_count = view.count()
    if view_count == 0:
        logging.info("Spawning global feed %s", url)
        feed.Feed(url, *args, **kwargs)
    elif view_count > 1:
        allFeeds = [f for f in view]
        for extra in allFeeds[1:]:
            extra.remove()
        raise StartupError("Database inconsistent",
                "Too many db objects for %s" % url)

def initialize(themeName):
    """Initialize Miro.  This sets up things like logging and the config
    system and should be called as early as possible.
    """
    # set debugmode if it hasn't already been set
    if app.debugmode == None:
        app.debugmode = app.config.get(prefs.APP_VERSION).endswith("-git")

    # this is platform specific
    setup_logging()
    # this is portable general
    util.setup_logging()
    app.controller = controller.Controller()
    config.set_theme(themeName)

def startup():
    """Startup Miro.

    This method starts up the eventloop and schedules the rest of the startup
    to run in the event loop.

    Frontends should call this method, then wait for 1 of 2 messages

    StartupSuccess is sent once the startup is done and the backend is ready
    to go.

    StartupFailure is sent if something bad happened.

    initialize() must be called before startup().
    """
    logging.info("Starting up %s", app.config.get(prefs.LONG_APP_NAME))
    logging.info("Version:    %s", app.config.get(prefs.APP_VERSION))
    logging.info("Revision:   %s", app.config.get(prefs.APP_REVISION))
    logging.info("Builder:    %s", app.config.get(prefs.BUILD_MACHINE))
    logging.info("Build Time: %s", app.config.get(prefs.BUILD_TIME))
    logging.info("Debugmode:  %s", app.debugmode)
    eventloop.connect('thread-started', finish_startup)
    logging.info("Reading HTTP Password list")
    httpauth.init()
    httpauth.restore_from_file()
    logging.info("Starting libCURL thread")
    httpclient.init_libcurl()
    httpclient.start_thread()
    logging.info("Starting event loop thread")
    eventloop.startup()
    if DEBUG_DB_MEM_USAGE:
        mem_usage_test_event.wait()
    load_extensions()

@startup_function
def load_extensions():
    ext_dirs = miro.plat.resources.extension_roots()
    app.extension_manager = extensionmanager.ExtensionManager(ext_dirs)
    app.extension_manager.load_extensions()

@startup_function
def finish_startup(obj, thread):
    database.set_thread(thread)
    logging.info("Restoring database...")
    start = time.time()
    app.db = storedatabase.LiveStorage()
    try:
        app.db.upgrade_database()
    except databaseupgrade.DatabaseTooNewError:
        summary = _("Database too new")
        description = _(
            "You have a database that was saved with a newer version of "
            "%(appname)s. You must download the latest version of "
            "%(appname)s and run that.",
            {"appname": app.config.get(prefs.SHORT_APP_NAME)},
        )
        raise StartupError(summary, description)
    except storedatabase.UpgradeErrorSendCrashReport, e:
        send_startup_crash_report(e.report)
        return
    except storedatabase.UpgradeError:
        raise StartupError(None, None)
    database.initialize()
    end = time.time()
    logging.timing("Database upgrade time: %.3f", end - start)
    if app.db.startup_version != app.db.current_version:
        databaselog.info("Upgraded database from version %s to %s",
                app.db.startup_version, app.db.current_version)
    databaselog.print_old_log_entries()
    models.initialize()
    if DEBUG_DB_MEM_USAGE:
        util.db_mem_usage_test()
        mem_usage_test_event.set()
    app.item_info_cache = iteminfocache.ItemInfoCache()
    app.item_info_cache.load()

    logging.info("Loading video converters...")
    conversions.conversion_manager.startup()
    app.device_manager = devices.DeviceManager()
    app.device_tracker = devicetracker.DeviceTracker()

    searchengines.create_engines()
    setup_global_feeds()
    # call fix_database_inconsistencies() ASAP after the manual feed is set up
    fix_database_inconsistencies()
    logging.info("setup tabs...")
    setup_tabs()
    logging.info("setup theme...")
    setup_theme()
    install_message_handler()
    downloader.init_controller()

    eventloop.add_urgent_call(check_firsttime, "check first time")

def fix_database_inconsistencies():
    item.fix_non_container_parents()
    item.move_orphaned_items()
    playlist.fix_missing_item_ids()
    folder.fix_playlist_missing_item_ids()

@startup_function
def check_firsttime():
    """Run the first time wizard if need be.
    """
    callback = lambda: eventloop.add_urgent_call(check_movies_gone, "check movies gone")
    if is_first_time():
        logging.info("First time -- calling handler.")
        _first_time_handler(callback)
        return

    eventloop.add_urgent_call(check_movies_gone, "check movies gone")

@startup_function
def check_movies_gone():
    """Checks to see if the movies directory is gone.
    """
    callback = lambda: eventloop.add_urgent_call(fix_movies_gone,
                                               "fix movies gone")

    if is_movies_directory_gone():
        logging.info("Movies directory is gone -- calling handler.")
        _movies_directory_gone_handler(callback)
        return

    movies_dir = fileutil.expand_filename(app.config.get(prefs.MOVIES_DIRECTORY))
    # if the directory doesn't exist, create it.
    if not os.path.exists(movies_dir):
        try:
            os.makedirs(movies_dir)
        except OSError:
            logging.info("Movies directory can't be created -- calling handler")
            # FIXME - this isn't technically correct, but it's probably
            # close enough that a user can fix the issue and Miro can
            # run happily.
            _movies_directory_gone_handler(callback)
            return

    # make sure the directory is writeable
    if not os.access(movies_dir, os.W_OK):
        _movies_directory_gone_handler(callback)
        return
    eventloop.add_urgent_call(finish_backend_startup, "reconnect downloaders")

@startup_function
def fix_movies_gone():
    app.config.set(prefs.MOVIES_DIRECTORY, platformcfg.get(prefs.MOVIES_DIRECTORY))
    eventloop.add_urgent_call(finish_backend_startup, "reconnect downloaders")

@startup_function
def finish_backend_startup():
    """Last bit of startup required before we load the frontend.  """
    # Uncomment the next line to test startup error handling
    # raise StartupError("Test Error", "Startup Failed")
    reconnect_downloaders()
    guide.download_guides()
    feed.remove_orphaned_feed_impls()
    messages.StartupSuccess().send_to_frontend()

@eventloop.idle_iterator
def on_frontend_started():
    """Perform startup actions that should happen after the frontend is
    already up and running.
    """
    logging.info("Starting auto downloader...")
    autodler.start_downloader()
    yield None
    feed.expire_items()
    yield None
    moviedata.movie_data_updater.start_thread()
    yield None
    commandline.startup()
    yield None
    autoupdate.check_for_updates()
    yield None
    # Delay running high CPU/IO operations for a bit
    eventloop.add_timeout(5, downloader.startup_downloader,
            "start downloader daemon")
    eventloop.add_timeout(30, feed.start_updates, "start feed updates")
    eventloop.add_timeout(60, item.update_incomplete_movie_data,
            "update movie data")
    eventloop.add_timeout(90, clear_icon_cache_orphans, "clear orphans")

def setup_global_feeds():
    setup_global_feed(u'dtv:manualFeed', initiallyAutoDownloadable=False)
    setup_global_feed(u'dtv:search', initiallyAutoDownloadable=False)
    setup_global_feed(u'dtv:searchDownloads')
    setup_global_feed(u'dtv:directoryfeed')

def setup_tabs():
    def setup_tab_order(type):
        current_tab_orders = list(tabs.TabOrder.view_for_type(type))
        if len(current_tab_orders) == 0:
            logging.info("Creating %s tab order" % type)
            tab_order = tabs.TabOrder(type)
        else:
            current_tab_orders[0].restore_tab_list()
    setup_tab_order(u'site')
    setup_tab_order(u'channel')
    setup_tab_order(u'audio-channel')
    setup_tab_order(u'playlist')

def is_first_time():
    """Checks to see if this is the first time that Miro has been run.
    This is to do any first-time setup, show the user the first-time
    wizard, ...

    Returns True if yes, False if no.
    """
    return not app.config.get(prefs.STARTUP_TASKS_DONE)

def mark_first_time():
    app.config.set(prefs.STARTUP_TASKS_DONE, True)

def is_movies_directory_gone():
    """Checks to see if the MOVIES_DIRECTORY exists.

    Returns True if yes, False if no.
    """
    movies_dir = fileutil.expand_filename(app.config.get(prefs.MOVIES_DIRECTORY))
    if not movies_dir.endswith(os.path.sep):
        movies_dir += os.path.sep
    logging.info("Checking movies directory %r...", movies_dir)
    try:
        if os.path.exists(movies_dir):
            contents = os.listdir(movies_dir)
            if contents:
                # there's something inside the directory consider it
                # present (even if all our items are missing).
                return False

    except OSError:
        # we can't access the directory--treat it as if it's gone.
        logging.info("Can't access directory.")
        return True

    # at this point either there's no movies_dir or there is an empty
    # movies_dir.  we check to see if we think something is downloaded.
    for downloader_ in downloader.RemoteDownloader.make_view():
        if ((downloader_.is_finished()
             and downloader_.get_filename().startswith(movies_dir))):
            # we think something is downloaded, so it seems like the
            # movies directory is gone.
            logging.info("Directory there, but missing files.")
            return True

    # we have no content, so everything's fine.
    return False

def setup_theme():
    themeHistory = _get_theme_history()
    themeHistory.check_new_theme()

def install_message_handler():
    handler = messagehandler.BackendMessageHandler(on_frontend_started)
    messages.BackendMessage.install_handler(handler)

def _get_theme_history():
    current_themes = list(theme.ThemeHistory.make_view())
    if len(current_themes) > 0:
        return current_themes[0]
    else:
        return theme.ThemeHistory()

@eventloop.idle_iterator
def clear_icon_cache_orphans():
    # delete icon_cache rows from the database with no associated
    # item/feed/guide.
    removed_objs = []
    for ic in iconcache.IconCache.orphaned_view():
        logging.warn("No object for IconCache: %s.  Discarding", ic)
        ic.remove()
        removed_objs.append(str(ic.url))
    if removed_objs:
        databaselog.info("Removed IconCache objects without an associated "
                "db object: %s", ','.join(removed_objs))
    yield None

    # delete files in the icon cache directory that don't belong to IconCache
    # objects.

    cachedir = fileutil.expand_filename(app.config.get(prefs.ICON_CACHE_DIRECTORY))
    if not os.path.isdir(cachedir):
        return

    existingFiles = [os.path.normcase(os.path.join(cachedir, f))
            for f in os.listdir(cachedir)]
    yield None

    knownIcons = iconcache.IconCache.all_filenames()
    yield None

    knownIcons = [ os.path.normcase(fileutil.expand_filename(path)) for path in
            knownIcons]
    yield None

    for filename in existingFiles:
        if (os.path.exists(filename)
                and os.path.basename(filename)[0] != '.'
                and os.path.basename(filename) != 'extracted'
                and not filename in knownIcons):
            try:
                os.remove(filename)
            except OSError:
                pass
        yield None

def send_startup_crash_report(report):
    logging.info("Startup failed, waiting to send crash report")
    title = _("Submitting Crash Report")
    description = _(
        "%(appname)s will now submit a crash report to our crash "
        "database\n\n"
        "Do you want to include entire program database "
        "including all video and feed metadata with crash report? "
        "This will help us diagnose the issue.",
        {"appname": app.config.get(prefs.SHORT_APP_NAME)})
    d = dialogs.ChoiceDialog(title, description,
            dialogs.BUTTON_INCLUDE_DATABASE,
            dialogs.BUTTON_DONT_INCLUDE_DATABASE)
    choice = d.run_blocking()
    send_database = (choice == dialogs.BUTTON_INCLUDE_DATABASE)
    app.controller.send_bug_report(report, '', send_database, quit_after=True)

def reconnect_downloaders():
    for downloader_ in downloader.RemoteDownloader.orphaned_view():
        logging.warn("removing orphaned downloader: %s", downloader_.url)
        downloader_.remove()
    manualItems = item.Item.feed_view(feed.Feed.get_manual_feed().get_id())
    for item_ in manualItems:
        if item_.downloader is None and item_.__class__ == item.Item:
            logging.warn("removing cancelled external torrent: %s", item_)
            item_.remove()
