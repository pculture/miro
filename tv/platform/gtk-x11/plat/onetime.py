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

import dbus
import dbus.service

if getattr(dbus, 'version', (0, 0, 0)) >= (0, 41, 0):
    import dbus.glib

# We do this crazy stuff so that Miro can run on platforms that have the
# older dbus-python bindings.  Dapper uses (0, 51, 0).  I think once we
# stop supporting Dapper, we can rip this whole section out.
# This section was re-written so that it doesn't trigger the dbus-python
# deprecation warning and is localized so we can just delete it and
# move on with our lives when the time comes. - willkahn-greene10-29-2007

# (0, 80, 0) is the first version that has do_not_queue
if getattr(dbus, 'version', (0, 0, 0)) >= (0, 80, 0):
    BusName = dbus.service.BusName
    NameExistsException = dbus.NameExistsException

else:
    import dbus.dbus_bindings

    class NameExistsException(dbus.DBusException):
        pass

    # these are in the dbus spec, so they're not going to change.
    REQUEST_NAME_REPLY_PRIMARY_OWNER = 1
    REQUEST_NAME_REPLY_IN_QUEUE = 2
    REQUEST_NAME_REPLY_EXISTS = 3
    REQUEST_NAME_REPLY_ALREADY_OWNER = 4
    NAME_FLAG_DO_NOT_QUEUE = 4
    
    class BusNameFlags(object):
        """A base class for exporting your own Named Services across the Bus
        """
        def __new__(cls, name, bus=None, flags=0, do_not_queue=False):
            if do_not_queue:
                flags = flags | NAME_FLAG_DO_NOT_QUEUE

            # get default bus
            if bus == None:
                bus = dbus.Bus()
    
            # otherwise register the name
            conn = bus.get_connection()
            retval = dbus.dbus_bindings.bus_request_name(conn, name, flags)
    
            # TODO: more intelligent tracking of bus name states?
            if retval == REQUEST_NAME_REPLY_PRIMARY_OWNER:
                pass
            elif retval == REQUEST_NAME_REPLY_IN_QUEUE:
                # queueing can happen by default, maybe we should
                # track this better or let the user know if they're
                # queued or not?
                pass
            elif retval == REQUEST_NAME_REPLY_EXISTS:
                raise NameExistsException(name)
            elif retval == REQUEST_NAME_REPLY_ALREADY_OWNER:
                # if this is a shared bus which is being used by someone
                # else in this process, this can happen legitimately
                pass
            else:
                raise RuntimeError('requesting bus name %s returned unexpected value %s' % (name, retval))
    
            # and create the object
            bus_name = object.__new__(cls)
            bus_name._bus = bus
            bus_name._name = name
            bus_name._conn = conn
    
            return bus_name
    
        # do nothing because this is called whether or not the bus name
        # object was retrieved from the cache or created new
        def __init__(self, *args, **keywords):
            pass
    
        # we can delete the low-level name here because these objects
        # are guaranteed to exist only once for each bus name
        def __del__(self):
            dbus.dbus_bindings.bus_release_name(self._bus.get_connection(), self._name)
    
        def get_bus(self):
            """Get the Bus this Service is on"""
            return self._bus
    
        def get_name(self):
            """Get the name of this service"""
            return self._name
    
        def get_connection(self): 
            """Get the connection for this service""" 
            return self._conn 
    
        def __repr__(self):
            return '<dbus.service.BusName %s on %r at %#x>' % (self._name, self._bus, id(self))
        __str__ = __repr__

    BusName = BusNameFlags

class OneTime(dbus.service.Object):
    """This makes sure we've only got one instance of Miro running at any given time.
    """
    def __init__(self):
        bus = dbus.SessionBus()
        bus_name = BusName('org.participatoryculture.dtv.onetime', bus=bus, do_not_queue=True)
        dbus.service.Object.__init__(self, bus_name, '/org/participatoryculture/dtv/OneTime')

    @dbus.service.method('org.participatoryculture.dtv.OneTimeIface')
    def handle_args(self, args):
        from miro import singleclick
        from miro import eventloop
        for i in xrange(len(args)):
            args[i] = args[i].encode('latin1')
            if args[i].startswith('file://'):
                args[i] = args[i][len('file://'):]

        eventloop.addIdle(lambda: singleclick.parse_command_line_args(args), "Open Files from dbus")
