# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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

import subprocess
import socket
import sys
import logging
import re
import shlex
import os


import bugzillalib

USAGE = "Usage: contributors.py <git-prev-rev> <git-rev> <bugzilla-milestone> [<output-file>]"

HELP = """
arguments:

   git-prev-rev
      The commit defining the start of the range of commits for this
      release.

   git-rev
      The commit defining the end of the range of commits for this
      release.

   bugzilla-milestone
      The Bugzilla milestone for all bugs in this release.

   output-file
      If not specified, this defaults to stdout.  If it is specified, then
      the list of contributors is saved to the file at this path.
"""

def execute(line):
    args = shlex.split(line)
    return subprocess.Popen(args, stdout=subprocess.PIPE).communicate()[0]

PARENS_RE = re.compile("\s*\\(.*\\)\s*")
BRACKETS_RE = re.compile("\s*\\[.*\\]\s*")

def clean_up_name(name):
    name = name.strip()
    name = PARENS_RE.sub("", name)
    name = BRACKETS_RE.sub("", name)
    return name

AUTHOR_RE = re.compile("^Author:\s+([^\<]+)")

def get_git_authors(prevrev, rev):
    logging.info("pulling git authors....")
    git_authors = {}
    
    revs = execute("git rev-list %s..%s" % (prevrev, rev))
    revs = revs.splitlines()
    for rev in revs:
        logging.info("... working on git rev %s", rev)
        summary = execute("git show --summary %s" % rev)
        summary = [mem for mem in summary.splitlines() if mem.startswith("Author: ")]
        if len(summary) != 1:
            logging.info("...summary has wrong number of authors--weird!")
            continue
        author = AUTHOR_RE.match(summary[0]).group(1)
        author = clean_up_name(author)
        author = (author, "code")
        git_authors[author] = git_authors.get(author, 0) + 1

    return git_authors

def get_name(item):
    name = ""
    if "name" in item.attrib:
        name = item.attrib["name"].strip()
    if not name:
        name = item.text.strip()
    if not name:
        name = "unknown"
    return name

def get_bugzilla_reporters(milestone):
    logging.info("pulling bugzilla reporters/commenters....")
    reporters = {}

    rows = bugzillalib.bz_query("bugzilla.pculture.org", [
        ("query_format", "advanced"),
        ("product", "Miro"),
        ("bug_status", "RESOLVED"),
        ("bug_status", "VERIFIED"),
        ("resolution", "FIXED"),
        ("target_milestone", milestone),
        ("ctype", "csv")
        ])

    bug_ids = [row["bug_id"] for row in rows]
    for bug_id in bug_ids:
        logging.info("... working on bug %s", bug_id)
        try:
            etree = bugzillalib.bz_query_bug_id("bugzilla.pculture.org", bug_id)
        except socket.error, se:
            logging.error("... error %s -- skipping", se)
        bug = etree.find("bug")
        reporter = bug.find("reporter")
        if reporter is None:
            logging.info("reporter is None")
            continue

        reporter = get_name(reporter)
        reporter = clean_up_name(reporter)
        reporter = (reporter, "bug reporter")
        reporters[reporter] = reporters.get(reporter, 0) + 1

        descs = bug.getiterator("long_desc")
        for desc in descs:
            commenter = desc.find("who")
            if commenter is None:
                logging.info("commenter is None")
                continue

            commenter = get_name(commenter)
            commenter = clean_up_name(commenter)
            commenter = (commenter, "bug reporter")
            reporters[commenter] = reporters.get(commenter, 0) + 1

    return reporters

def get_additional_contributors(fn):
    if not os.path.exists(fn):
        logging.error("additional.txt file does not exist--skipping.")
        return {}

    f = open(fn, "r")
    lines = f.readlines()
    f.close()

    lines = [line.strip() for line in lines if line.strip()]

    addtl = {}

    for mem in lines:
        mem = (clean_up_name(mem), "addtl")
        addtl[mem] = 1
    return addtl

html_escape_table = {
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    ">": "&gt;",
    "<": "&lt;",
    }

def html_escape(text):
    """Produce entities within text."""
    return "".join(html_escape_table.get(c,c) for c in text)

def name_to_key(name, kind):
    if kind == "funder":
        return name
    name = name.split(" ")
    if len(name) > 1:
        return name[-1]
    return name[0]

def print_stats(name, d):
    print name.upper()
    items = [(v, k) for k, v in d.items()]
    items.sort()
    items.reverse()
    for v, k in items:
        print "%5d - %s" % (v, k)
    
def main(argv):
    if not(argv):
        print USAGE
        print HELP
        return 0

    if len(argv) < 3:
        print USAGE
        return 0

    logging.basicConfig(level=logging.INFO)

    prevrev = argv[0]
    rev = argv[1]
    milestone = argv[2]

    git_authors = get_git_authors(prevrev, rev)
    reporters = get_bugzilla_reporters(milestone)
    addtl = get_additional_contributors("additional.txt")

    print_stats("git", git_authors)
    print_stats("bugzilla", reporters)
    print_stats("additional", addtl)

    everyone = addtl
    everyone.update(reporters)
    everyone.update(git_authors)

    everyone = everyone.keys()
    everyone.sort(key=lambda k: name_to_key(*k).lower())

    # FIXME should do a pass of uniquifying the list here

    output_file = open("for_credits", "w")
    for mem in everyone:
        output_file.write("* %s\n" % mem[0].encode("utf-8"))
    output_file.close()

    output_file = open("for_osx_credits_html", "w")
    for mem in everyone[:-1]:
        mem = html_escape(mem[0].encode("utf-8"))
        output_file.write("%s,\n" % mem)
    output_file.write("and %s.\n" % html_escape(everyone[-1][0].encode("utf-8")))
    output_file.close()

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
