# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

"""Wrapper module for the downloader daemon.  This module just calls
SetDllDirectory() passing it the xulrunner directory.  This forces windows to
look there first before checking the system DLL directory.  This prevents bugs
when there is an incompatible DLL in there (#9756).
"""

import ctypes
import os
import sys

def appRoot():
    # This is exactly the same as resources.appRoot(), but with one extra call
    # to os.path.dirname(), since the downloader exe file is one level deeper
    # than Miro.exe.
    exe_path = unicode(sys.executable, sys.getfilesystemencoding())
    return os.path.dirname(os.path.dirname(os.path.dirname(exe_path)))


SetDllDirectory = ctypes.windll.kernel32.SetDllDirectoryW
SetDllDirectory(appRoot())

from miro.dl_daemon import Democracy_Downloader
Democracy_Downloader.launch()
