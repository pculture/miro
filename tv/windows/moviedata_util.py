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

# Make sure we can load the modules that Py2exe bundles for us

# import sys
# exe = sys.executable
# exe_dir = exe[:exe.rfind('\\')]
# sys.path.append(exe_dir + '\\library.zip')

from plat.renderers import gst_extractor
import ctypes
import sys

SEM_FAILCRITICALERRORS = 0x0001
SEM_NOGPFAULTERRORBOX = 0x0002

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "moviedata_util <video_path> [thumbnail_path]"
        sys.exit(1)

    try:
        # disable annoying windows popup
        ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX |
                                            SEM_FAILCRITICALERRORS)

        sys.exit(gst_extractor.main(sys.argv))
    except Exception, e:
        import traceback
        traceback.print_exc()
        print "Miro-Movie-Data-Length: -1"
        print "Miro-Movie-Data-Thumbnail: Failure"
        print "Miro-Movie-Data-Type: other"
        sys.exit(1)
