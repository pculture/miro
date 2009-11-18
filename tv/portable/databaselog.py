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

"""Log events having to do with the database.

The purpose of this module is to help us keep track of the history of a user's
database.  See #12419 for more info.

Note: We should try hard not to let loops fill up the log file with too much
junk, or infinitely.  Take a look at item.move_orphaned_items() for one
technique to avoid this.
"""

import time
import logging

from miro.database import DDBObject

# log levels
DEBUG = 10
INFO = 20

class DBLogEntry(DDBObject):
    def setup_new(self, priority, description):
        self.priority = priority
        self.description = description
        self.timestamp = time.time()

    @classmethod
    def notable_entries(cls):
        return cls.make_view('priority > ?', (DEBUG,), order_by='timestamp')

def _log(priority, message, *args):
    try:
        description = unicode(message) % args
    except UnicodeError:
        logging.warn("Unicode error when creating database log entry %s %s" %
                (message, args))
        return
    entry = DBLogEntry(priority, description)
    logging.dblog(description)

def info(message, *args):
    """Log a message to the database, using the 'info' priority.

    This should be used for entries that are fairly notable.  These entries
    will be printed out every time the user starts up Miro.
    """
    _log(INFO, message, *args)

def debug(message, *args):
    """Log a message to the database, using the 'debug' priority.

    This should be used for entries that are there for debugging purposes.
    These will be only printed out to the current log file.
    """
    _log(DEBUG, message, *args)

def print_old_log_entries():
    """Printout old log entries to the log file."""
    old_entries = list(DBLogEntry.notable_entries())
    if not old_entries:
        return
    logging.dblog("-- re-printing old log entries --")
    for entry in old_entries:
        logging.dblog(entry.description)
    logging.dblog("-- done --")
