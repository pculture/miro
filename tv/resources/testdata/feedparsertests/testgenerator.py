# Miro - an RSS based video player application
# Copyright (C) 2011
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
Generates feedparser tests.
"""
import sys

# even though we don't use unittest, we need this because it weirdly
# causes feedparser to use GMT instead of the local timezone.
import unittest
import pprint
import os

# hack to setup the miro module
sys.path.insert(0, os.path.join(os.pardir, os.pardir, os.pardir))
import lib
sys.modules['miro'] = lib
# hack to setup the miro.plat module.
# This assumes we're calling on linux, which is unfortunate, but I don't see a
# bette way to do this
sys.path.insert(0, os.path.join(os.pardir, os.pardir, os.pardir, 'linux'))
import plat
sys.modules['miro.plat'] = sys.modules['miro'].plat = plat

from time import struct_time

USAGE = "testgenerator.py <input-dir> <output-dir>"

def convert_datetime(elem):
    """Takes part of a FeedParserDict and converts any
    time.struct_time instances to appropriate timezone-agnostic
    strings.
    """
    if isinstance(elem, struct_time):
        return "DATETIME"
    if isinstance(elem, tuple):
        return tuple([convert_datetime(e) for e in elem])
    if isinstance(elem, list):
        return [convert_datetime(e) for e in elem]
    if isinstance(elem, dict):
        for key, val in elem.items():
            elem[key] = convert_datetime(val)
        return elem
    return elem

def run_parser(feedparser, inputdir, outputdir, mem):
    output = feedparser.parse(os.path.join(inputdir, mem))
    output = convert_datetime(output)
    f = open(os.path.join(outputdir, "%s.output" % mem), "w")
    if 'entries' in output:
        output = output['entries']
    f.write(pprint.pformat(output))
    f.close()

def main(argv):
    print "Feedparser test generator of awesome: version 1.0"
    if len(argv) < 2:
        print USAGE
        return 1

    inputdir = os.path.abspath(argv[0])
    outputdir = os.path.abspath(argv[1])

    from miro import feedparserutil

    inputfiles = os.listdir(inputdir)
    print "%s total input files" % len(inputfiles)
    outputfiles = os.listdir(outputdir)
    print "%s total output files" % len(outputfiles)

    print ""

    to_generate = [m for m in inputfiles if "%s.output" % m not in outputfiles]
    if not to_generate:
        print "No files to generate."
    else:
        print "Generating %s files:" % len(to_generate)
        for i, mem in enumerate(to_generate):
            print "%s: Generating output for %s" % (i, mem)
            run_parser(feedparserutil, inputdir, outputdir, mem)

    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
