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
import threading

from miro import app
from miro import config
from miro import downloader
from miro import eventloop
from miro import httpclient
from miro import iconcache
from miro import indexes
from miro import moviedata
from miro import prefs
from miro import signals
from miro import util
from miro import views
from miro import fileutil
from miro.plat.utils import exit

###############################################################################
#### The main application app.controller object, binding model to view     ####
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

    def get_global_feed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        rv = feedView[0]
        feedView.unlink()
        return rv

    @eventloop.asUrgent
    def shutdown(self):
        logging.info("Shutting down Downloader...")
        downloader.shutdownDownloader(self.downloaderShutdown)

    def downloaderShutdown(self):
        logging.info("Closing Database...")
        if app.db.liveStorage is not None:
            app.db.liveStorage.close()
        logging.info("Shutting down event loop")
        eventloop.quit()
        signals.system.shutdown()

    def onShutdown(self):
        try:
            eventloop.join()        
            logging.info("Saving preferences...")
            config.save()

            logging.info("Shutting down icon cache updates")
            iconcache.iconCacheUpdater.shutdown()
            logging.info("Shutting down movie data updates")
            moviedata.movieDataUpdater.shutdown()

            if self.idlingNotifier is not None:
                logging.info("Shutting down IdleNotifier")
                self.idlingNotifier.join()

            logging.info("Done shutting down.")
            logging.info("Remaining threads are:")
            for thread in threading.enumerate():
                logging.info("%s", thread)

        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            signals.system.failed_exn("while shutting down")
            exit(1)

    @eventloop.asUrgent
    def changeMoviesDirectory(self, newDir, migrate):
        oldDir = config.get(prefs.MOVIES_DIRECTORY)
        config.set(prefs.MOVIES_DIRECTORY, newDir)
        if migrate:
            views.remoteDownloads.confirmDBThread()
            for download in views.remoteDownloads:
                if download.isFinished():
                    logging.info("migrating %s", download.getFilename())
                    download.migrate(newDir)
            # Pass in case they don't exist or are not empty:
            try:
                fileutil.rmdir(os.path.join(oldDir, 'Incomplete Downloads'))
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
            try:
                fileutil.rmdir(oldDir)
            except (SystemExit, KeyboardInterrupt):
                raise
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
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                logging.exception("Failed to backup database")

        description = description.encode("utf-8")
        postVars = {"description": description,
                    "app_name": config.get(prefs.LONG_APP_NAME),
                    "log": report}
        if backupfile:
            postFiles = {"databasebackup": {
                            "filename": "databasebackup.zip", 
                            "mimetype": "application/octet-stream", 
                            "handle": open(backupfile, "rb")
                        }}
        else:
            postFiles = None
        self.sendingCrashReport += 1
        httpclient.grabURL("http://participatoryculture.org/bogondeflector/index.php", 
                callback, errback, method="POST", postVariables=postVars, postFiles=postFiles)
