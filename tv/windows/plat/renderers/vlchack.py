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

"""vlchack.py -- Hack for #16987

Call the hack_window() method shortly after playback begins to try to make
sure that VLC's windows are sized properly.
"""

import logging
import ctypes

GetWindow = ctypes.windll.user32.GetWindow
MoveWindow = ctypes.windll.user32.MoveWindow
GetClientRect = ctypes.windll.user32.GetClientRect
PostMessage = ctypes.windll.user32.PostMessageA

GW_CHILD = 5

WM_WINDOWPOSCHANGED = 0x0047

class RECT(ctypes.Structure):
    _fields_ = [
            ("left", ctypes.c_ulong),
            ("top", ctypes.c_ulong),
            ("right", ctypes.c_ulong),
            ("bottom", ctypes.c_ulong)
    ];

def hack_window(hwnd):
    # get VLC's DirectX window
    child = GetWindow(hwnd, GW_CHILD)
    if child:
        # perturb the window my moving it 1px down, then back up.  This makes
        # VLC see a WM_WINDOWPOSCHANGED message and fix it's windows.
        rect = RECT()
        GetClientRect(child, ctypes.byref(rect))
        MoveWindow(child, 0, 1, rect.right, rect.bottom, 0)
        MoveWindow(child, 0, 0, rect.right, rect.bottom, 0)

