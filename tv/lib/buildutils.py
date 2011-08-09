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

"""``miro.buildutils`` -- Utilities for building miro

This module stores functions that touch on the build system for miro.  This
includes setup.py files, files that process app.config, etc.

Since this module is used by setup.py on 3 different platforms, it should only
import from the python standard library.
"""

import re
import subprocess

CONFIG_LINE_RE = re.compile(r"^([^ ]+) *= *([^\r\n]*)[\r\n]*$")

def read_simple_config_file(path):
    """Parse a configuration file in a very simple format and return contents
    as a dict.

    Each line is either whitespace or "Key = Value".  Whitespace is ignored
    at the beginning of Value, but the remainder of the line is taken
    literally, including any whitespace.

    Note: There is no way to put a newline in a value.
    """
    ret = {}

    filep = open(path, "rt")
    for line in filep.readlines():
        # Skip blank lines
        if not line.strip():
            continue

        # Otherwise it'd better be a configuration setting
        match = CONFIG_LINE_RE.match(line)
        if not match:
            print ("WARNING: %s: ignored bad configuration directive '%s'" %
                   (path, line))
            continue

        key = match.group(1)
        value = match.group(2)
        if key in ret:
            print "WARNING: %s: ignored duplicate directive '%s'" % (path,
                                                                     line)
            continue

        ret[key] = value

    return ret

def write_simple_config_file(path, data):
    """Given a dict, write a configuration file in the format that
    read_simple_config_file reads.
    """
    filep = open(path, "wt")

    for k, v in data.iteritems():
        filep.write("%s = %s\n" % (k, v))

    filep.close()

def query_revision():
    """Called at build-time to ask git for the revision of this
    checkout.

    Returns the (url, revision) on success and None on failure.
    """
    url = "unknown"
    revision = "unknown"
    try:
        proc = subprocess.Popen(["git", "config", "--list"],
                             stdout=subprocess.PIPE)
        info = proc.stdout.read().splitlines()
        proc.stdout.close()
        origline = "remote.origin.url"
        info = [m for m in info if m.startswith(origline)]
        if info:
            url = info[0][len(origline)+1:].strip()

        proc = subprocess.Popen(["git", "rev-parse", "HEAD"],
                             stdout=subprocess.PIPE)
        info = proc.stdout.read()
        proc.stdout.close()
        revision = info[0:8]
        return (url, revision)
    except StandardError, exc:
        print "Exception thrown when querying revision: %s" % exc
    return (url, revision)
