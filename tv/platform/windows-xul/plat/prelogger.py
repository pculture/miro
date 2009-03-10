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

"""
Handle logging before we are ready to write it out to disk.

This module defines the PreLogger class, which simply remembers logging
records instead of outputing them somewhere.  In plat.util.setup_logging(), we
retrieve records and write them out to disk after logging is setup.
"""

import logging

class PreLogger(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []

    def emit(self, record):
        self.records.append(record)

_handler = None

def install():
    """Install a logger to remember records before we have logging setup.
    """
    global _handler
    if _handler is not None:
        raise ValueError("Prelogger already installed")
    _handler = PreLogger()
    logging.getLogger('').addHandler(_handler)

def remove():
    """Remove the pre logger.  Return a list of records that it logged. """
    global _handler
    if _handler is None:
        raise ValueError("Prelogger not installed")
    logging.getLogger('').removeHandler(_handler)
    records = _handler.records
    _handler = None
    return records
