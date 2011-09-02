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

"""screensaver.py -- Enable/Disable the screensaver."""

import os
import dbus
import gobject
import subprocess

class Gnome3ScreenSaverManager(object):
    """Screen saver manager for Gnome 3.x"""

    def __init__(self, toplevel_window):
        self.cookie = None
        self.toplevel_window = toplevel_window
        # keep a bus around for as long as this object is alive.  Gnome 3 docs
        # say that disconnecting from the bus will uninhibit the screen saver.
        self.bus = dbus.SessionBus()

    def should_use(self):
        # check to see if the DBus object exists
        if not self.bus.name_has_owner('org.gnome.SessionManager'):
            return False
        # check to see if it has the "Inhibit" method"
        # We use the Introspect() method to do this which returns an XML
        # string.  We could parse this, but it seems enough just to check if
        # the method name is present anywhere.
        obj = self.bus.get_object('org.gnome.SessionManager',
                             '/org/gnome/SessionManager')
        return 'Inhibit' in obj.Introspect()

    def _get_session_manager(self):
        return self.bus.get_object('org.gnome.SessionManager',
                             '/org/gnome/SessionManager')

    def disable(self):
        obj = self._get_session_manager()

        prog = "Miro"
        toplevel_xid = dbus.UInt32(self.toplevel_window.window.xid)
        reason = "Playing a video"
        flags = dbus.UInt32(8) # inhibit idle

        self.cookie = obj.Inhibit(prog, toplevel_xid, reason, flags)

    def enable(self):
        if self.cookie is None:
            raise AssertionError("disable() must be called before enable()")

        obj = self._get_session_manager()

        obj.Uninhibit(self.cookie)
        self.cookie = None

class Gnome2ScreenSaverManager(object):
    """Screen saver manager for Gnome 2.x"""

    def __init__(self, toplevel_window):
        self.cookie = None

    def should_use(self):
        bus = dbus.SessionBus()
        # first check if the screen saver dbus object exists
        if not bus.name_has_owner('org.gnome.ScreenSaver'):
            return False
        # check to see if it has the "Inhibit" method" (on Gnome 3 it doesn't)
        # We use the Introspect() method to do this which returns an XML
        # string.  We could parse this, but it seems enough just to check if
        # the method name is present anywhere.
        obj = bus.get_object('org.gnome.ScreenSaver',
                             '/org/gnome/ScreenSaver')
        return 'Inhibit' in obj.Introspect()

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
    def __init__(self, toplevel_window):
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
        return self.call_xss('-time')

    def deactivate(self):
        return self.call_xss('-deactivate')

    def disable(self):
        self.timer = gobject.timeout_add(1000, self.deactivate)

    def enable(self):
        if self.timer is None:
            raise AssertionError("disable() must be called before enable()")
        gobject.source_remove(self.timer)
        self.timer = None


MANAGER_CLASSES = [
    Gnome3ScreenSaverManager,
    Gnome2ScreenSaverManager,
    XScreenSaverManager,
    # TODO: make a KDE3 version?
]


def create_manager(toplevel_window):
    """Return an object that can disable/enable the screensaver."""
    for klass in MANAGER_CLASSES:
        manager = klass(toplevel_window)
        if manager.should_use():
            return manager
    return None
