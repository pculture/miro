# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""controller.py -- Contains Controller class.  It handles application
crashes and shutdown.
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
from miro.gtcache import gettext as _
from miro import httpclient
from miro import iconcache
from miro import messages
from miro import moviedata
from miro import prefs
from miro import signals
from miro import videoconversion
from miro.plat.utils import exit

BOGON_URL = "http://participatoryculture.org/bogondeflector/index.php"

class Controller:
    """The main application app.controller object, binding model to
    view.
    """
    def __init__(self):
        self.frame = None
        self.guide = None
        self.idling_notifier = None
        self.bug_report_senders = set()
        self._quit_after_bug_reports = False

    @eventloop.as_urgent
    def shutdown(self):
        logging.info("Shutting down video conversions manager")
        videoconversion.conversion_manager.shutdown()
        logging.info("Shutting down Downloader...")
        downloader.shutdown_downloader(self.downloader_shutdown)

    def downloader_shutdown(self):
        logging.info("Shutting down event loop")
        eventloop.shutdown()
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
            moviedata.movie_data_updater.shutdown()

            if self.idling_notifier is not None:
                logging.info("Shutting down IdleNotifier")
                self.idling_notifier.join()

            logging.info("Done shutting down.")
            logging.info("Remaining threads are:")
            for thread in threading.enumerate():
                logging.info("%s", thread)

        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            signals.system.failed_exn("while shutting down")
            exit(1)

    def is_sending_crash_report(self):
        return len(self.bug_report_senders) > 0

    def send_bug_report(self, report, description, send_database,
            quit_after=False):
        sender = BugReportSender(report, description, send_database)
        self.bug_report_senders.add(sender)
        sender.connect("finished", self._bug_report_sent)
        if quit_after:
            self._quit_after_bug_reports = True
            eventloop.add_timeout(0.5, self._start_send_bug_report_progress,
                    'bug report progress')

    def _bug_report_sent(self, sender):
        self.bug_report_senders.remove(sender)
        if (self._quit_after_bug_reports and not
                self.is_sending_crash_report()):
            messages.ProgressDialogFinished().send_to_frontend()
            messages.FrontendQuit().send_to_frontend()

    def _start_send_bug_report_progress(self):
        m = messages.ProgressDialogStart(_('Sending Crash Report'))
        m.send_to_frontend()
        self._send_bug_report_progress()

    def _send_bug_report_progress(self):
        current_sent = 0
        total_to_send = 0
        for sender in self.bug_report_senders:
            sent, to_send = sender.progress()
            if to_send == 0:
                # this sender doesn't know it's total data, we can't calculate
                # things.
                current_sent = total_to_send = 0
                break
            else:
                current_sent += sent
                total_to_send += to_send
        if total_to_send > 0:
            progress = float(current_sent) / total_to_send
        else:
            progress = -1
        text = '%s (%d%%)' % (_('Sending Crash Report'), progress * 100)
        messages.ProgressDialog(text, progress).send_to_frontend()
        eventloop.add_timeout(0.1, self._send_bug_report_progress,
                'bug report progress')

class BugReportSender(signals.SignalEmitter):
    """Helper class that sends bug reports."""
    def __init__(self, report, description, send_database):
        signals.SignalEmitter.__init__(self)
        self.create_signal('finished')

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
        post_vars = {"description": description,
                     "app_name": config.get(prefs.LONG_APP_NAME),
                     "log": report}
        if backupfile:
            post_files = {"databasebackup":
                              {"filename": "databasebackup.zip",
                               "mimetype": "application/octet-stream",
                               "handle": open(backupfile, "rb")
                               }}
        else:
            post_files = None
        logging.info("Sending crash report....")
        self.client = httpclient.grabURL(BOGON_URL,
                           self.callback, self.errback, method="POST",
                           postVariables=post_vars, postFiles=post_files)

    def callback(self, result):
        if result['status'] != 200 or result['body'] != 'OK':
            logging.warning(
                "Failed to submit crash report.  Server returned %r",
                result)
        else:
            logging.info("Crash report submitted successfully")
        self.emit("finished")

    def errback(self, error):
        logging.warning("Failed to submit crash report %r", error)
        self.emit("finished")

    def progress(self):
        return self.client.sendingProgress()

    def _backup_support_dir(self):
        # backs up the support directories to a zip file
        # returns the name of the zip file
        logging.info("Attempting to back up support directory")
        app.db.close()

        support_dir = config.get(prefs.SUPPORT_DIRECTORY)
        try:
            uniqfn = "%012databasebackup.zip" % randrange(0, 999999999999)
            tempfilename = os.path.join(tempfile.gettempdir(), uniqfn)
            zipfile = ZipFile(tempfilename, "w")
            iconcache_dir = config.get(prefs.ICON_CACHE_DIRECTORY)

            for root, dummy, files in os.walk(support_dir):
                if (((os.path.normpath(root) != os.path.normpath(iconcache_dir))
                     and not os.path.islink(root))):

                    relativeroot = root[len(support_dir):]
                    while (len(relativeroot) > 0 
                           and relativeroot[0] in ['/', '\\']):
                        relativeroot = relativeroot[1:]
                    for fn in files:
                        path = os.path.join(root, fn)
                        if not os.path.islink(path):
                            relpath = os.path.join(relativeroot, fn)
                            relpath = relpath.encode('ascii', 'replace')
                            zipfile.write(path, relpath)
            zipfile.close()
            logging.info("Support directory backed up to %s" % tempfilename)
            return tempfilename
        finally:
            app.db.open_connection()
