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

"""commandline.py -- Command line getting/parsing functions."""

import ctypes

kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

kernel32.GetCommandLineW.restype = ctypes.c_wchar_p
shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)

def get_command_line_string():
    """Get the command line as a unicode string."""
    return kernel32.GetCommandLineW()

def parse_command_line_string(cmd_line):
    """Parse the command line and return a list of arguments."""
    num_args = ctypes.c_int()
    array = shell32.CommandLineToArgvW(cmd_line, ctypes.byref(num_args))
    rv = [array[i] for i in xrange(num_args.value)]
    kernel32.LocalFree(array)
    return rv

def get_command_line():
    return parse_command_line_string(get_command_line_string())
