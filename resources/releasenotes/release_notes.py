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

import logging
import sys
import bugzillalib
import re
import socket
import csv

BZ_HOST = "bugzilla.pculture.org"

PARENS_RE = re.compile("\s*\\(.*\\)\s*")
BRACKETS_RE = re.compile("\s*\\[.*\\]\s*")

def clean_up_name(name):
    name = name.strip()
    name = PARENS_RE.sub("", name)
    name = BRACKETS_RE.sub("", name)
    return name

def get_name(item):
    name = ""
    if "name" in item.attrib:
        name = item.attrib["name"].strip()
    if not name:
        name = item.text.strip()
    if not name:
        name = "unknown"
    return name

def get_bugfixes(rows):

    bugs = dict((row["bug_id"], row) for row in rows)
    nixing = []

    for bug_id in bugs.keys():
        logging.info("... working on bug %s", bug_id)
        try:
            etree = bugzillalib.bz_query_bug_id("bugzilla.pculture.org", bug_id)
        except socket.error, se:
            logging.error("... error %s -- skipping", se)
        bug = etree.find("bug")
        version = bug.find("version")
        if version is None:
            logging.info("version is None")
            continue

        version = get_name(version)
        version = clean_up_name(version)
        if version in ("git-master", "unknown", "nightly build"):
            logging.info("... nixing %s", bug_id)
            nixing.append((bug_id, bugs[bug_id]["short_desc"]))
            del bugs[bug_id]
            continue

    logging.info("Writing nixing.csv....")
    with open("nixing.csv", "wb") as fp:
        writer = csv.writer(fp)
        writer.writerows(nixing)

    return bugs.values()


def main(args):
    if len(args) < 1:
        print "Syntax: release_notes.py <milestone>"
        return 0

    logging.basicConfig(level=logging.INFO)

    milestone = args[0]

    logging.info("Querying bugzilla....")
    
    rows = bugzillalib.bz_query(BZ_HOST, [
        ("query_format", "advanced"),
        ("product", "Miro"),
        ("bug_status", "RESOLVED"),
        ("bug_status", "VERIFIED"),
        ("resolution", "FIXED"),
        ("target_milestone", milestone),
        ("ctype", "csv")
        ])

    rows.sort(key=lambda x: (x["op_sys"], int(x["bug_id"])))

    logging.info("Calculating enhancements....")
    enhancements = [r for r in rows if r["bug_severity"] == "enhancement"]

    logging.info("Calculating bugfixes....")
    bugfixes = get_bugfixes([r for r in rows
                             if r["bug_severity"] != "enhancement"])

    logging.info("Creating output....")

    output = []

    output.append("== Changes and bug fixes in Miro %s (pending) ==" % (
            milestone))
    output.append("")

    output.append("* New features")
    for row in enhancements:
        output.append("** [[bz:%s]] (%s) %s" % (
                row["bug_id"], row["op_sys"], row["short_desc"]))
    output.append("")

    output.append("* Bug fixes")
    for row in bugfixes:
        output.append("** [[bz:%s]] (%s) %s" % (
                row["bug_id"], row["op_sys"], row["short_desc"]))

    logging.info("Writing releasenotes.txt....")
    with open("releasenotes.txt", "w") as fp:
        fp.write("\n".join(output))

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
