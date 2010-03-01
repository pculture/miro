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

import dbus
import dbus.service
import dbus.glib
from dbus.service import BusName

from miro import messages

class OneTime(dbus.service.Object):
    """This makes sure we've only got one instance of Miro running at
    any given time.
    """
    def __init__(self):
        bus = dbus.SessionBus()
        bus_name = BusName('org.participatoryculture.dtv.onetime',
                           bus=bus, do_not_queue=True)
        dbus.service.Object.__init__(
            self, bus_name=bus_name,
            object_path='/org/participatoryculture/dtv/OneTime')

    @dbus.service.method(
        dbus_interface='org.participatoryculture.dtv.OneTimeIFace',
        in_signature='as')
    def handle_args(self, args):
        from miro import singleclick
        from miro import eventloop
        for i, arg in enumerate(args):
            args[i] = arg.encode('latin1')
            if arg.startswith('file://'):
                args[i] = arg[len('file://'):]

        messages.OpenIndividualFiles(args).send_to_backend()
