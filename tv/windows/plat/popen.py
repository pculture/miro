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

"""
Implements a platform specific Popen that hides all the platform
differences.
"""

import logging
import os
import subprocess

def cleanse_environment(env=None):
    """Given an environment dictionary, clean it by removing all traces
    of unicode types, as this is not supported on Windows when passing
    it via subprocesses.
    """
    source = env if env else os.environ.copy()
    env = source.copy()
    for k, v in source.iteritems():
        if isinstance(v, unicode):
            logging.debug('cleanse environment: %s in unicode with value %r.  '
                          'Removing.', k, v)
            del env[k]
    return env

def Popen(args, **kwargs):
    """Like subprocess.Popen but make sure we get rid of any platform
    quirks.  On Windows this means:

    Set STARTF_USESHOWWINDOW flag
    Clean environment any unicode types
    Remove close_fds argument (not supported)
    """
    startupinfo = subprocess.STARTUPINFO()
    # XXX temporary: STARTF_USESHOWWINDOW is in a different location
    # as of Python 2.6.6
    try:
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    except AttributeError:
        startupinfo.dwFlags |= subprocess._subprocess.STARTF_USESHOWWINDOW
    kwargs['startupinfo'] = startupinfo
    try:
        env = kwargs['env']
    except KeyError:
        env = None
    finally:
        kwargs['env'] = cleanse_environment(env)
    try:
        del kwargs['close_fds']    # not supported on Windows
    except KeyError:
        pass
    # Rules for quoting.
    # http://docs.python.org/library/subprocess.html
    # In section: #converting-argument-sequence 17.1.5.1
    #
    # In practical terms, it means if we are passing in a string type
    # then we should follow the quote rules, and if you pass in a
    # sequence type it should implement correct quoting.
    # I'm going to declare that this version of Popen only accepts
    # sequence types for the program argument (though implementing
    # correcting quoting is probably < 20 lines of code).

    return subprocess.Popen(args, **kwargs)
