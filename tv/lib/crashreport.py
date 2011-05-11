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

"""crashreport.py -- Format crash reports."""

import logging
import os
import sys
import threading
import time
import traceback
import random

from miro import app
from miro import prefs
from miro import util
from miro import fileutil

END_HEADERS = "ENDHEADERS\n"

def format_crash_report(when, exc_info, details, log_report=True):
    header = ""
    header += "App:        %s\n" % app.config.get(prefs.LONG_APP_NAME)
    header += "Publisher:  %s\n" % app.config.get(prefs.PUBLISHER)
    header += "Platform:   %s\n" % app.config.get(prefs.APP_PLATFORM)
    header += "Python:     %s\n" % sys.version.replace("\r\n"," ").replace("\n"," ").replace("\r"," ")
    header += "Py Path:    %s\n" % repr(sys.path)
    header += "Version:    %s\n" % app.config.get(prefs.APP_VERSION)
    header += "Serial:     %s\n" % app.config.get(prefs.APP_SERIAL)
    header += "Revision:   %s\n" % app.config.get(prefs.APP_REVISION)
    header += "Builder:    %s\n" % app.config.get(prefs.BUILD_MACHINE)
    header += "Build Time: %s\n" % app.config.get(prefs.BUILD_TIME)
    header += "Time:       %s\n" % time.asctime()
    header += "When:       %s\n" % when
    header += "\n"

    header += "Exception\n---------\n"
    if exc_info:
        header += ''.join(traceback.format_exception(*exc_info))
        header += "\n"
        # Print out a stack trace too.  The exception stack only contains
        # calls between the try and the exception.
        try:
            stack = util.get_nice_stack()
        except StandardError:
            stack = traceback.extract_stack()
        header += "Call Stack\n---------\n"
        header += ''.join(traceback.format_list(stack))
        header += "\n"
    else:
        # fake an exception with our call stack
        try:
            stack = util.get_nice_stack()
        except StandardError:
            stack = traceback.extract_stack()
        header += ''.join(traceback.format_list(stack))
        header += 'UnknownError: %s\n' % details
        header += "\n"
    if details:
        header += "Details: %s\n" % (details, )

    header += "Threads\n-------\n"
    header += "Current: %s\n" % threading.currentThread().getName()
    header += "Active:\n"
    for t in threading.enumerate():
        isdaemon = t.isDaemon() and ' [Daemon]' or ''
        header += " - %s%s\n" % (t.getName(), isdaemon)

    header += END_HEADERS

    # Combine the header with the logfile contents, if available, to
    # make the dialog box crash message. {{{ and }}} are Trac
    # Wiki-formatting markers that force a fixed-width font when the
    # report is pasted into a ticket.
    report = "{{{\n%s}}}\n" % header

    def read_log(log_file, log_name="Log"):
        try:
            f = open(log_file, "rt")
            log_contents = "%s\n---\n" % log_name
            log_contents += f.read()
            f.close()
        except (IOError, OSError):
            log_contents = ''
        return log_contents

    log_file = app.config.get(prefs.LOG_PATHNAME)
    downloader_log_file = app.config.get(prefs.DOWNLOADER_LOG_PATHNAME)
    if log_file is None:
        log_contents = "No logfile available on this platform.\n"
    else:
        log_contents = read_log(log_file)
    if downloader_log_file is not None:
        if log_contents is not None:
            log_contents += "\n" + read_log(downloader_log_file, "Downloader Log")
        else:
            log_contents = read_log(downloader_log_file)

    if log_contents is not None:
        report += "{{{\n%s}}}\n" % util.stringify(log_contents)

    # Dump the header for the report we just generated to the log, in
    # case there are multiple failures or the user sends in the log
    # instead of the report from the dialog box. (Note that we don't
    # do this until we've already read the log into the dialog
    # message.)
    if log_report:
        logging.info("----- CRASH REPORT (DANGER CAN HAPPEN) -----")
        logging.info(header)
        logging.info("----- END OF CRASH REPORT -----")

    return report

def extract_headers(report):
    """Takes the headers out of the report which includes the log
    files.  This makes it easier to log the headers and only the
    headers so the log files don't grow exponentially.
    """
    if END_HEADERS in report:
        return report[:report.find(END_HEADERS)]
    return report

def save_crash_report(report):
    """Save a crash report to the support directory.

    :returns: filename we saved to, or None if the save failed
    """
    try:
        crash_dir = app.config.get(prefs.CRASH_PATHNAME)

        if not os.path.exists(crash_dir):
            fileutil.makedirs(crash_dir)

        # we use a timestamp so that crash reports are easy to identify
        # for users.
        # we add a random bit at the end to reduce the likelihood that
        # if Miro is being crash-tastic that one report will stomp on
        # another one.  we don't kill ourselves for file-name uniqueness
        # though since we're in the middle of a crash and it's better
        # to be simple about it.
        timestamp = time.strftime("%Y-%m-%d-%H%M%S", time.localtime())
        fn = os.path.join(
            crash_dir,
            "crashreport-%s-%s.txt" % (timestamp, random.randint(0, 10000)))

        logging.info("saving crash report file to: %s", fn)

        f = open(fn, "w")
        f.write(report)
        f.close()
    except (OSError, IOError):
        logging.exception("exception while saving crash report")
        return None
    return fn

def issue_failure_warning(when, details, with_exception):
    """Issue warnings about a failure that we were able to recover from.

    Use this function for cases when we crash, but we don't want to pop up a
    dialog box for the user.
    """
    logging.warn("soft failure when: %s details: %s", when, details)
    if with_exception:
        exc_info = sys.exc_info()
    else:
        exc_info = None
    report = format_crash_report(when, exc_info, details, log_report=False)
    save_crash_report(report)
