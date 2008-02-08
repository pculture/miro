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

"""frontendutil.py -- Utility functions for frontends.

This module contains utility functions that frontends can make use of.
Functions usually end up here instead of util.py because they depend on other
Miro modules.
"""

import logging

from miro import app
from miro import config
from miro import httpclient
from miro import prefs

sendingCrashReport = 0

def sendBugReport(report, description, send_database):
    global sendingCrashReport
    def callback(result):
        global sendingCrashReport
        sendingCrashReport -= 1
        if result['status'] != 200 or result['body'] != 'OK':
            logging.warning(u"Failed to submit crash report. Server returned %r" % result)
        else:
            logging.info(u"Crash report submitted successfully")
    def errback(error):
        global sendingCrashReport
        sendingCrashReport -= 1
        logging.warning(u"Failed to submit crash report %r" % error)

    backupfile = None
    if send_database:
        try:
            logging.info("Sending entire database")
            from miro import database
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
