# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""screensaver.py -- Enable/Disable the screensaver."""

import ctypes
import ctypes.wintypes
import _winreg

SystemParametersInfo = ctypes.windll.user32.SystemParametersInfoA

SPI_GETSCREENSAVEACTIVE = 16
SPI_SETSCREENSAVEACTIVE = 17


class WindowsScreenSaverManager(object):
    def __init__(self):
        self.was_active = None

    def check_screen_saver_disabled(self):
        # Workaround for a bug in windows 2000
        # (http://support.microsoft.com/kb/318781)
        handle = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, 
                "Control Panel\\Desktop", 0, _winreg.KEY_QUERY_VALUE)
        try:
            # We just try to query the value, if the key is missing then the
            # screensaver is disabled
            _winreg.QueryValueEx(handle, "SCRNSAVE.EXE")
        except WindowsError:
            rv = True
        else:
            rv = False
        handle.Close()
        return rv

    def check_screen_saver_active(self):
        if self.check_screen_saver_disabled():
            return False
        rv = ctypes.wintypes.BOOL()
        SystemParametersInfo(SPI_GETSCREENSAVEACTIVE, 0, ctypes.byref(rv), 0)
        return rv.value != 0

    def disable(self):
        if self.check_screen_saver_active():
            self.was_active = True
            SystemParametersInfo(SPI_SETSCREENSAVEACTIVE, 0, None, 0)
        else:
            self.was_active = False

    def enable(self):
        if self.was_active is None:
            raise AssertionError("disable() must be called before enable()")
        if self.was_active:
            SystemParametersInfo(SPI_SETSCREENSAVEACTIVE, 1, None, 0)
        self.was_active = None


def create_manager():
    """Return an object that can disable/enable the screensaver."""
    return WindowsScreenSaverManager()
