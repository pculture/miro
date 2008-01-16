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

"""frontendutil.py -- Utility functions for frontends.

This module contains utility functions that frontends can make use of.
Functions usually end up here instead of util.py because they depend on other
Miro modules.
"""

import logging

import app
import config
import httpclient
import prefs

sendingCrashReport = 0

def sendBugReport(report, description, send_database):
    global sendingCrashReport
    def callback(result):
        sendingCrashReport -= 1
        if result['status'] != 200 or result['body'] != 'OK':
            logging.warning(u"Failed to submit crash report. Server returned %r" % result)
        else:
            logging.info(u"Crash report submitted successfully")
    def errback(error):
        sendingCrashReport -= 1
        logging.warning(u"Failed to submit crash report %r" % error)

    backupfile = None
    if send_database:
        try:
            logging.info("Sending entire database")
            import database
            backupfile = database.defaultDatabase.liveStorage.backupDatabase()
        except:
            traceback.print_exc()
            logging.warning(u"Failed to backup database")

    description = description.encode("utf-8")
    postVars = {"description":description,
                "app_name": config.get(prefs.LONG_APP_NAME),
                "log": report}
    if backupfile:
        postFiles = {"databasebackup": {"filename":"databasebackup.zip", "mimetype":"application/octet-stream", "handle":open(backupfile, "rb")}}
    else:
        postFiles = None
    sendingCrashReport += 1
    httpclient.grabURL("http://participatoryculture.org/bogondeflector/index.php", callback, errback, method="POST", postVariables = postVars, postFiles = postFiles)
