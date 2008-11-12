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

"""clipboard.py.  Used to access the clipboard from python."""

import logging

from miro.util import toUni
import ctypes
CF_TEXT = 1
GMEM_MOVEABLE = 0x2
GMEM_ZEROINIT = 0x40
GHND = (GMEM_MOVEABLE | GMEM_ZEROINIT)

OpenClipboard = ctypes.windll.user32.OpenClipboard
EmptyClipboard = ctypes.windll.user32.EmptyClipboard
GetClipboardData = ctypes.windll.user32.GetClipboardData
SetClipboardData = ctypes.windll.user32.SetClipboardData
CloseClipboard = ctypes.windll.user32.CloseClipboard
GlobalLock = ctypes.windll.kernel32.GlobalLock
GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
memcpy = ctypes.cdll.msvcrt.memcpy

def get_text():
    text = None
    if OpenClipboard(ctypes.c_int(0)):
        try:
            hClipMem = GetClipboardData(CF_TEXT)
            if hClipMem:
                GlobalLock.restype = ctypes.c_char_p
                text = GlobalLock(hClipMem)
                GlobalUnlock(hClipMem)
        finally:
            CloseClipboard()
    else:
        logging.warning("OpenClipboard(0) call failed.")

    if text is not None:
        text = toUni(text)
    return text

def set_text(text):
    buffer = ctypes.c_buffer(text)
    bufferSize = ctypes.sizeof(buffer)
    hGlobalMem = GlobalAlloc(GHND, bufferSize)
    GlobalLock.restype = ctypes.c_void_p
    lpGlobalMem = GlobalLock(hGlobalMem)
    memcpy(lpGlobalMem, ctypes.addressof(buffer), bufferSize)
    GlobalUnlock(hGlobalMem)

    if OpenClipboard(ctypes.c_int(0)):
        EmptyClipboard()
        SetClipboardData(CF_TEXT, hGlobalMem)
        CloseClipboard()

    else:
        logging.warning("OpenClipboard(0) call failed.")
