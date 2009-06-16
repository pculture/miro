# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
import tempfile
import locale
from random import randrange
from zipfile import ZipFile

from miro import app
from miro import config
from miro import downloader
from miro import eventloop
from miro import httpclient
from miro import iconcache
from miro import moviedata
from miro import prefs
from miro import signals
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

    @eventloop.asUrgent
    def shutdown(self):
        logging.info("Shutting down Downloader...")
        downloader.shutdown_downloader(self.downloader_shutdown)

    def downloader_shutdown(self):
        logging.info("Shutting down event loop")
        eventloop.quit()
        logging.info("Closing Database...")
        if app.db is not None:
            app.db.close()
        signals.system.shutdown()

    def on_shutdown(self):
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

    def send_bug_report(self, report, description, send_database):
        def callback(result):
            self.sendingCrashReport -= 1
            if result['status'] != 200 or result['body'] != 'OK':
                logging.warning(u"Failed to submit crash report.  Server returned %r" % result)
            else:
                logging.info(u"Crash report submitted successfully")

        def errback(error):
            self.sendingCrashReport -= 1
            logging.warning(u"Failed to submit crash report %r" % error)

        backupfile = None
        if send_database:
            try:
                logging.info("Sending entire database")
                backupfile = self._backup_support_dir()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                logging.exception("Failed to backup database")

        if isinstance(report, str):
            report = report.decode(locale.getpreferredencoding())
        report = report.encode("utf-8", "ignore")
        if isinstance(description, str):
            description = description.decode(locale.getpreferredencoding())
        description = description.encode("utf-8", "ignore")
        postVars = {"description": description,
                    "app_name": config.get(prefs.LONG_APP_NAME),
                    "log": report}
        if backupfile:
            postFiles = {"databasebackup":
                         {"filename": "databasebackup.zip",
                          "mimetype": "application/octet-stream",
                          "handle": open(backupfile, "rb")
                          }}
        else:
            postFiles = None
        self.sendingCrashReport += 1
        logging.info("Sending crash report....")
        httpclient.grabURL("http://participatoryculture.org/bogondeflector/index.php", 
                           callback, errback, method="POST",
                           postVariables=postVars, postFiles=postFiles)

    def _backup_support_dir(self):
        # backs up the support directories to a zip file
        # returns the name of the zip file
        logging.info("Attempting to back up support directory")
        app.db.close()
        try:
            tempfilename = os.path.join(tempfile.gettempdir(),
                                        ("%012ddatabasebackup.zip" % randrange(0, 999999999999)))
            zipfile = ZipFile(tempfilename, "w")
            for root, dirs, files in os.walk(config.get(prefs.SUPPORT_DIRECTORY)):
                if ((os.path.normpath(root) !=
                     os.path.normpath(config.get(prefs.ICON_CACHE_DIRECTORY)))
                    and not os.path.islink(root)):

                    relativeroot = root[len(config.get(prefs.SUPPORT_DIRECTORY)):]
                    while len(relativeroot) > 0 and relativeroot[0] in ['/', '\\']:
                        relativeroot = relativeroot[1:]
                    for filen in files:
                        if not os.path.islink(os.path.join(root, filen)):
                            zipfile.write(os.path.join(root, filen),
                                    os.path.join(relativeroot, filen).encode('ascii', 'replace'))
            zipfile.close()
            logging.info("Support directory backed up to %s" % tempfilename)
            return tempfilename
        finally:
            app.db.open_connection()
