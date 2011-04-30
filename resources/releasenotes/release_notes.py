#!/usr/bin/python

# Miro - an RSS based video player application
# Copyright (C) 2010, 2011 Participatory Culture Foundation
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
http://bugzilla.pculture.org/buglist.cgi?query_format=simple&order=relevance+desc&product=Miro&bug_status=RESOLVED&resolution=FIXED&target_milestone=2.5.3&keywords_type=allwords&keywords=
"""

import optparse
import sys
import bugzillalib

BZ_HOST = "bugzilla.pculture.org"

def main(args):
    if len(args) < 1:
        print "Syntax: release_notes.py <milestone>"
        return 0

    milestone = args[0]
    
    rows = bugzillalib.bz_query(BZ_HOST, [
        ("query_format", "advanced"),
        ("product", "Miro"),
        ("bug_status", "RESOLVED"),
        ("bug_status", "VERIFIED"),
        ("resolution", "FIXED"),
        ("target_milestone", milestone),
        ("ctype", "csv")
        ])

    print "== Changes and bug fixes in Miro %s (pending) ==" % milestone
    print ""
    rows.sort(lambda x, y: cmp((x["op_sys"].lower(), int(x["bug_id"])), (y["op_sys"].lower(), int(y["bug_id"]))))

    enhancements = [r for r in rows if r["bug_severity"] == "enhancement"]
    bugfixes = [r for r in rows if r["bug_severity"] != "enhancement"]

    print "* New features"
    for row in enhancements:
        print "** [[bz:%s]] (%s) %s" % (row["bug_id"], row["op_sys"], row["short_desc"])
    print ""

    print "* Bug fixes"
    for row in bugfixes:
        print "** [[bz:%s]] (%s) %s" % (row["bug_id"], row["op_sys"], row["short_desc"])
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
