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

"""crashreport.py -- Format crash reports."""

import logging
import sys
import threading
import time
import traceback

from miro import config
from miro import prefs
from miro import util

def format_crash_report(when, with_exception, details):
    header = ""
    header += "App:        %s\n" % config.get(prefs.LONG_APP_NAME)
    header += "Publisher:  %s\n" % config.get(prefs.PUBLISHER)
    header += "Platform:   %s\n" % config.get(prefs.APP_PLATFORM)
    header += "Python:     %s\n" % sys.version.replace("\r\n"," ").replace("\n"," ").replace("\r"," ")
    header += "Py Path:    %s\n" % repr(sys.path)
    header += "Version:    %s\n" % config.get(prefs.APP_VERSION)
    header += "Serial:     %s\n" % config.get(prefs.APP_SERIAL)
    header += "Revision:   %s\n" % config.get(prefs.APP_REVISION)
    header += "Builder:    %s\n" % config.get(prefs.BUILD_MACHINE)
    header += "Build Time: %s\n" % config.get(prefs.BUILD_TIME)
    header += "Time:       %s\n" % time.asctime()
    header += "When:       %s\n" % when
    header += "\n"

    if with_exception:
        header += "Exception\n---------\n"
        header += ''.join(traceback.format_exception(*sys.exc_info()))
        header += "\n"
    if details:
        header += "Details: %s\n" % (details, )
    header += "Call stack\n----------\n"
    try:
        stack = util.get_nice_stack()
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        stack = traceback.extract_stack()
    header += ''.join(traceback.format_list(stack))
    header += "\n"

    header += "Threads\n-------\n"
    header += "Current: %s\n" % threading.currentThread().getName()
    header += "Active:\n"
    for t in threading.enumerate():
        header += " - %s%s\n" % \
            (t.getName(),
             t.isDaemon() and ' [Daemon]' or '')

    # Combine the header with the logfile contents, if available, to
    # make the dialog box crash message. {{{ and }}} are Trac
    # Wiki-formatting markers that force a fixed-width font when the
    # report is pasted into a ticket.
    report = "{{{\n%s}}}\n" % header

    def read_log(logFile, logName="Log"):
        try:
            f = open(logFile, "rt")
            logContents = "%s\n---\n" % logName
            logContents += f.read()
            f.close()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logContents = ''
        return logContents

    logFile = config.get(prefs.LOG_PATHNAME)
    downloaderLogFile = config.get(prefs.DOWNLOADER_LOG_PATHNAME)
    if logFile is None:
        logContents = "No logfile available on this platform.\n"
    else:
        logContents = read_log(logFile)
    if downloaderLogFile is not None:
        if logContents is not None:
            logContents += "\n" + read_log(downloaderLogFile, "Downloader Log")
        else:
            logContents = read_log(downloaderLogFile)

    if logContents is not None:
        report += "{{{\n%s}}}\n" % util.stringify(logContents)

    # Dump the header for the report we just generated to the log, in
    # case there are multiple failures or the user sends in the log
    # instead of the report from the dialog box. (Note that we don't
    # do this until we've already read the log into the dialog
    # message.)
    logging.info ("----- CRASH REPORT (DANGER CAN HAPPEN) -----")
    logging.info (header)
    logging.info ("----- END OF CRASH REPORT -----")
    return report
