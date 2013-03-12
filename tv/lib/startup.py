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
    - (optional) call startup.install_movies_directory_gone_handler()
    - Call startup.initialize()
    - Wait for either the 'startup-success', or 'startup-failure' signal
"""

from miro.gtcache import gettext as _
import logging
import os
import config
import sys
import traceback
import threading
import time

from miro import api
from miro import app
from miro import autodler
from miro import autoupdate
from miro import commandline
from miro import controller
from miro import extensionmanager
from miro import database
from miro import databaselog
from miro import databaseupgrade
from miro import dbupgradeprogress
from miro import dialogs
from miro import donate
from miro import downloader
from miro import eventloop
from miro import fileutil
from miro import guide
from miro import httpauth
from miro import httpclient
from miro import iconcache
from miro import item
from miro import itemsource
from miro import feed
from miro import folder
from miro import messages
from miro import messagehandler
from miro import models
from miro import playlist
from miro import prefs
import miro.plat.resources
from miro.plat.utils import setup_logging, filename_to_unicode
from miro import tabs
from miro import theme
from miro import threadcheck
from miro import util
from miro import searchengines
from miro import storedatabase
from miro import conversions
from miro import devices
from miro import sharing
from miro import workerprocess
from miro.plat import devicetracker

DEBUG_DB_MEM_USAGE = False
mem_usage_test_event = threading.Event()

class StartupError(StandardError):
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
        except StandardError, exc:
            # we do this so that we only kick up the database error
            # if it's a database-related exception AND the app has a
            # db attribute
            if ((isinstance(exc, (database.DatabaseException,
                                  database.DatabaseStandardError,
                                  storedatabase.sqlite3.DatabaseError,
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
                      "removed, but you will have to re-add your podcasts and "
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

def setup_global_feed(url, *args, **kwargs):
    view = feed.Feed.make_view('orig_url=?', (url,))
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
        if app.config.get(prefs.APP_FINAL_RELEASE) == u"0":
            # if it's not a final release, then we're in debugmode
            app.debugmode = True
        else:
            # if it is a final release, then we're not in debugmode
            app.debugmode = False

    # this is platform specific
    setup_logging(app.config.get(prefs.LOG_PATHNAME),
                 main_process=True)
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
    eventloop.connect('thread-started', startup_for_frontend)
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
    core_ext_dirs = miro.plat.resources.extension_core_roots()
    user_ext_dirs = miro.plat.resources.extension_user_roots()
    app.extension_manager = extensionmanager.ExtensionManager(
        core_ext_dirs, user_ext_dirs)
    app.extension_manager.load_extensions()

@startup_function
def startup_for_frontend(obj, thread):
    """Run the startup code needed to get the frontend started

    This function should be kept as small as possible to ensure good startup
    times.
    """
    threadcheck.set_eventloop_thread(thread)
    logging.info("Installing deleted file checker...")
    item.setup_deleted_checker()
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
    downloader.reset_download_stats()
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

    dbupgradeprogress.upgrade_end()

    app.startup_timer.log_time("after db upgrade")

    app.icon_cache_updater = iconcache.IconCacheUpdater()
    setup_global_feeds()
    # call fix_database_inconsistencies() ASAP after the manual feed is set up
    fix_database_inconsistencies()
    logging.info("setup tabs...")
    setup_tabs()
    logging.info("setup theme...")
    setup_theme()
    install_message_handler()

    app.sharing_manager = sharing.SharingManager()
    app.download_state_manager = downloader.DownloadStateManager()
    item.setup_change_tracker()
    item.setup_metadata_manager()

    _startup_checker.run_checks()

def fix_database_inconsistencies():
    item.fix_non_container_parents()
    item.move_orphaned_items()
    playlist.fix_missing_item_ids()
    folder.fix_playlist_missing_item_ids()

class StartupChecker(object):
    """Handles various checks at startup.

    This class handles the first-time startup check and the movies directory
    gone check.

    This code is a bit weird because of the interplay between the frontend and
    the backend.  The checks run in the backend, but if they fail then the
    frontend needs to prompt the user to ask them what to do.  Also, neither
    side is totally started up at this point.
    """
    def run_checks(self):
        self.check_firsttime()

    @startup_function
    def check_firsttime(self):
        """Run the first time wizard if need be.
        """
        callback = lambda: eventloop.add_urgent_call(self.check_movies_gone,
                                                     "check movies gone")
        if is_first_time():
            logging.info("First time run -- calling handler.")
            self.first_time_handler(callback)
            return

        self.check_movies_gone()

    def first_time_handler(callback):
        """Default handler for first-time startup

        install_first_time_handler() replaces this method with the
        frontend-specific one.
        """
        logging.error("First time -- no handler installed.")
        eventloop.add_urgent_call(callback, "continuing startup")

    @startup_function
    def check_movies_gone(self, check_unmounted=True):
        """Checks to see if the movies directory is gone.
        """

        movies_dir = fileutil.expand_filename(app.config.get(
            prefs.MOVIES_DIRECTORY))
        movies_dir = filename_to_unicode(movies_dir)

        # if the directory doesn't exist, create it.
        if (not os.path.exists(movies_dir) and
                should_create_movies_directory(movies_dir)):
            try:
                fileutil.makedirs(movies_dir)
            except OSError:
                logging.info("Movies directory can't be created -- calling handler")
                # FIXME - this isn't technically correct, but it's probably
                # close enough that a user can fix the issue and Miro can
                # run happily.
                msg = _("Permissions error: %(appname)s couldn't "
                        "create the folder.",
                        {"appname": app.config.get(prefs.SHORT_APP_NAME)})
                self.movies_directory_gone_handler(msg, movies_dir)
                return

        # make sure the directory is writeable
        if not os.access(movies_dir, os.W_OK):
            logging.info("Can't write to movies directory -- calling handler")
            msg = _("Permissions error: %(appname)s can't "
                    "write to the folder.",
                    {"appname": app.config.get(prefs.SHORT_APP_NAME)})
            self.movies_directory_gone_handler(msg, movies_dir)
            return

        # make sure that the directory is populated if we've downloaded stuff to
        # it
        if check_unmounted and check_movies_directory_unmounted():
            logging.info("Movies directory is gone -- calling handler.")
            msg = _("The folder contains no files: "
                    "is it on a drive that's disconnected?")
            self.movies_directory_gone_handler(msg, movies_dir,
                                               allow_continue=True)
            return

        self.all_checks_done()

    def movies_directory_gone_handler(self, message, movies_dir,
                                      allow_continue=False):
        """Default movies_directory_gone_handler.

        This method simply quits when the movies directory is gone.
        install_movies_directory_gone_handler() replaces this method with the
        frontend-specific one.

        present them with the following options:
            - quit
            - change movies directory
            - continue with current directory (if allow_continue is True)

        After the user picks, the frontend should call either
        app.controller.shutdown() or startup.fix_movies_gone()
        """
        logging.error("Movies directory is gone -- no handler installed!")
        app.controller.shutdown()

    @startup_function
    def fix_movies_gone(self, new_movies_directory):
        """Called by the movies directory gone handler to fix the issue.

        :param new_movies_directory: new path for the movies directory, or
        None if we should continue with the current directory.
        """
        if new_movies_directory is not None:
            app.config.set(prefs.MOVIES_DIRECTORY, new_movies_directory)
        # do another check to make sure the selected directory works.  Here we
        # skip the unmounted check, since it's not exact and the user is
        # giving us a directory.
        self.check_movies_gone(check_unmounted=False)

    def all_checks_done(self):
        # Uncomment the next line to test startup error handling
        # raise StartupError("Test Error", "Startup Failed")
        app.startup_timer.log_time("sending StartupSuccess()")
        messages.StartupSuccess().send_to_frontend()

_startup_checker = StartupChecker()

def install_movies_directory_gone_handler(callback):
    """Install a function to handle the movies directory being gone

    The frontend should call this method and pass it a callback to handle this
    situation.  The signature is (message, movies_dir, allow_continue=False).
    The callback should present the user with the following options:
        - quit
        - change movies directory
        - continue with current directory (if allow_continue is True)

    After the user picks, the callback should call either
    app.controller.shutdown() or startup.fix_movies_gone()
    """
    _startup_checker.movies_directory_gone_handler = callback

def install_first_time_handler(callback):
    """Install a function to handle first-time startup

    If the frontend wants, it can pass a callback that shows a dialog to the
    user on first-time startup.  The function will be passed a single argument
    which is a callback function to call once the dialog completes.
    """
    _startup_checker.first_time_handler = callback

def fix_movies_gone(new_movies_directory):
    """Called by the movies directory gone handler to fix the issue.

    :param new_movies_directory: new path for the movies directory, or None if
    we should continue with the current directory.
    """
    eventloop.add_urgent_call(_startup_checker.fix_movies_gone,
                              "fix movies gone",
                              args=(new_movies_directory,))

@eventloop.idle_iterator
def on_frontend_started():
    """Perform startup actions that should happen after the frontend is
    already up and running.

    This function happens using an idle iterator.  Before/after code that
    could take a while to run, we yield to other eventloop callbacks.
    """
    conversions.conversion_manager.startup()

    app.sharing_tracker = sharing.SharingTracker()
    app.sharing_manager.startup()
    app.sharing_tracker.start_tracking()

    app.device_manager = devices.DeviceManager()
    app.device_tracker = devicetracker.DeviceTracker()
    app.device_tracker.start_tracking()

    reconnect_downloaders()
    guide.download_guides()
    feed.remove_orphaned_feed_impls()

    app.download_state_manager.init_controller()
    itemsource.setup_handlers()
    if app.frontend_name == 'widgets':
        app.donate_manager = donate.DonateManager()
    else:
        logging.warn("frontend is %s, not starting DonateManager()",
                     app.frontend_name)

    logging.info("Starting auto downloader...")
    autodler.start_downloader()
    app.icon_cache_updater.start_updates()
    yield None
    feed.expire_items()
    yield None
    commandline.startup()
    yield None
    autoupdate.check_for_updates()
    yield None
    app.local_metadata_manager.schedule_retry_net_lookup()
    # Delay running high CPU/IO operations for a bit
    eventloop.add_timeout(5, app.download_state_manager.startup_downloader,
            "start downloader daemon")
    eventloop.add_timeout(10, workerprocess.startup,
            "start worker process")
    eventloop.add_timeout(20, item.start_deleted_checker,
            "start checking deleted items")
    eventloop.add_timeout(30, feed.start_updates, "start feed updates")
    eventloop.add_timeout(60, item.update_incomplete_metadata,
            "update metadata data")
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
            logging.info("Creating %s tab order", type)
            tabs.TabOrder(type)
        else:
            current_tab_orders[0].restore_tab_list()
    setup_tab_order(u'site')
    setup_tab_order(u'channel')
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
    # we just bothered the user about importing media, don't do it again
    app.config.set(prefs.MUSIC_TAB_CLICKED, True)
    # make sure we save the config now, it's really annoying if a first-time
    # startup dialog pops up again
    app.config.save()

def should_create_movies_directory(path):
    """Figure out if we should create the movies directory if it's missing."""
    # We should only do this if the directory is the default directory.  This
    # avoids trying to create files on unmonted filesystems (#17826)
    return path == app.config.get_platform_default(prefs.MOVIES_DIRECTORY)

def check_movies_directory_unmounted():
    """Checks to see MOVIES_DIRECTORY has been unmounted.

    Our hueristic is to check if there are any files in the directory.  If
    it's totally empty, and we think that we should have a downloaded file in
    it, then we return True.
    """
    movies_dir = fileutil.expand_filename(app.config.get(
        prefs.MOVIES_DIRECTORY))
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

    cachedir = fileutil.expand_filename(app.config.get(
        prefs.ICON_CACHE_DIRECTORY))
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
        "including all video and podcast metadata with crash report? "
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
        if (item_.__class__ == item.Item and not item_.has_downloader() and
          not item_.pending_manual_download):
            logging.warn("removing cancelled external torrent: %s", item_)
            item_.remove()
