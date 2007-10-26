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

import dbus
import dbus.service

if getattr(dbus, 'version', (0,0,0)) >= (0,41,0):
    import dbus.glib

class OneTime (dbus.service.Object):
    """This makes sure we've only got one instance of Miro running at any given time.
    """
    def __init__(self):
        bus = dbus.SessionBus()
        bus_name = dbus.service.BusName('org.participatoryculture.dtv.onetime', bus=bus, do_not_queue = True)
        dbus.service.Object.__init__(self, bus_name, '/org/participatoryculture/dtv/OneTime')

    @dbus.service.method('org.participatoryculture.dtv.OneTimeIface')
    def HandleArgs (self, args):
        import singleclick
        import app
        import eventloop
        for i in xrange(len(args)):
            args[i] = args[i].encode('latin1')
            if args[i].startswith('file://'):
                args[i] = args[i][len('file://'):]
        eventloop.addIdle(lambda:singleclick.handleCommandLineArgs (args), "Open Files from dbus")
        app.controller.frame.widgetTree['main-window'].present()
