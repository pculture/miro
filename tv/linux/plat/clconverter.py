# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
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
Allows Miro on Linux to do command-line conversions.
"""

import os
import subprocess
import shutil
import sys

from miro.plat import resources, utils
from miro import conversions

USAGE = "usage: miro --convert [target] [inputfile [inputfile...]]"


class FakeInfo(object):
    """This implements just enough ItemInfo to get
    conversions going.
    """
    def __init__(self, video_path):
        self.name = unicode(os.path.basename(video_path))
        self.video_path = video_path


def convert(args):
    cm = conversions.ConverterManager()
    cm.load_converters(resources.path('conversions/*.conv'))

    if len(args) < 2:
        print USAGE
        print "Available targets:"
        for section, converters in cm.get_converters():
            print "  %s" % section
            for mem in converters:
                print "    %s - %s" % (mem.identifier, mem.name)
        return

    target = args[0]
    infiles = args[1:]

    try:
        converter_info = cm.lookup_converter(target)
    except KeyError:
        print "That target doesn't exist."
        return

    for mem in infiles:
        input_file = os.path.abspath(mem)
        if not os.path.exists(input_file):
            print "File %s does not exist.  Skipping." % input_file
            continue
        final_path, temp_path = conversions.build_output_paths(
            FakeInfo(input_file), os.getcwd(), converter_info)

        media_info = conversions.get_media_info(input_file)

        params = conversions.build_parameters(
            mem, temp_path, converter_info, media_info)
        if converter_info.executable == "ffmpeg":
            cmd = utils.get_ffmpeg_executable_path()
            params = utils.customize_ffmpeg_parameters(params)

        params.insert(0, cmd)

        print "\nCONVERTING %s -> %s\n" % (mem, final_path)
        print "ffmpeg command line:"
        print " ".join(params)
        print "\n"

        retcall = subprocess.call(params)
        if retcall == 0:
            shutil.move(temp_path, final_path)
            print "Success!  New file at %s." % final_path
