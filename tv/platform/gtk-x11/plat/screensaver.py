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

import os
import dbus
import gobject
import subprocess

class GnomeScreenSaverManager(object):
    def __init__(self):
        self.cookie = None

    def should_use(self):
        bus = dbus.SessionBus()
        return bus.name_has_owner('org.gnome.ScreenSaver')

    def disable(self):
        bus = dbus.SessionBus()
        obj = bus.get_object('org.gnome.ScreenSaver',
                             '/org/gnome/ScreenSaver')

        prog = "Miro"
        reason = "Playing a video"
        self.cookie = obj.Inhibit(prog, reason)

    def enable(self):
        if self.cookie is None:
            raise AssertionError("disable() must be called before enable()")
        bus = dbus.SessionBus()
        obj = bus.get_object('org.gnome.ScreenSaver',
                             '/org/gnome/ScreenSaver')

        obj.UnInhibit(self.cookie)
        self.cookie = None

class XScreenSaverManager(object):
    def __init__(self):
        self.timer = None

    def call_xss(self, command):
        rc = None
        devnull = open(os.devnull, 'w')
        try:
            rc = subprocess.call(['xscreensaver-command', command],
                                 stdout=devnull, stderr=devnull)
        except OSError:
            pass
        devnull.close()
        return rc == 0

    def should_use(self):
        return call_xss('-time')

    def deactivate(self):
        return call_xss('-deactivate')

    def disable(self):
        self.timer = gobject.timer_add(1000, self.deactivate)

    def enable(self):
        if self.timer is None:
            raise AssertionError("disable() must be called before enable()")
        gobject.source_remove(self.timer)
        self.timer = None

managers = [
    GnomeScreenSaverManager(),
    XScreenSaverManager(),
    # TODO: make a KDE3 version?
]

def create_manager():
    """Return an object that can disable/enable the screensaver."""
    for manager in managers:
        if manager.should_use():
            return manager
    return None
