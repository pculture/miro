# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

"""clipboard.py.  Used to access the clipboard from python."""

from templatehelper import toUni
from ctypes import windll, c_char_p
CF_TEXT = 1

OpenClipboard = windll.user32.OpenClipboard
GetClipboardData = windll.user32.GetClipboardData
CloseClipboard = windll.user32.CloseClipboard
GlobalLock = windll.kernel32.GlobalLock
GlobalUnlock = windll.kernel32.GlobalUnlock

def getText():
     text = None
     if OpenClipboard(None):
         try:
             hClipMem = GetClipboardData(CF_TEXT)
             if hClipMem:
                 GlobalLock.restype = c_char_p
                 text = GlobalLock(hClipMem)
                 GlobalUnlock(hClipMem)
         finally:
             CloseClipboard()
     if text is not None:
         text = toUni(text)
     return text
