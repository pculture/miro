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

"""Execute a callback and trap exceptions.
"""

from miro.clock import clock
import logging
from miro import signals

def trap_call(when, function, *args, **kwargs):
    """Make a call to a function, but trap any exceptions and convert them int
    error signals.  Return True if the function successfully completed, False
    if it threw an exception
    """
    try:
        function(*args, **kwargs)
        return True
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        signals.system.failed_exn(when)
        return False

# Turn the next flag on to track the cumulative time for each when argument to
# time_trap_call().  Don't do this for production builds though!  Since we never
# clean up the entries in the cumulative dict, turning this on amounts to a
# memory leak.
TRACK_CUMULATIVE = False 
cumulative = {}
cancel = False

def time_trap_call(when, function, *args, **kwargs):
    global cancel
    cancel = False
    start = clock()
    retval = trap_call(when, function, *args, **kwargs)
    end = clock()
    if cancel:
        return retval
    if end-start > 1.0:
        logging.timing("WARNING: %s too slow (%.3f secs)", when, end-start)
    if TRACK_CUMULATIVE:
        try:
            total = cumulative[when]
        except KeyError:
            total = 0
        total += end - start
        cumulative[when] = total
        if total > 5.0:
            logging.timing("%s cumulative is too slow (%.3f secs)", when, total)
            cumulative[when] = 0
        return retval
    cancel = True
    return retval
