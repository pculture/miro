# Democracy Player - an RSS based video player application
# Copyright (C) 2005-2006 Participatory Culture Foundation
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
import dbus.dbus_bindings

if getattr(dbus, 'version', (0,0,0)) >= (0,41,0):
    import dbus.glib

dbus_bindings_consts = {
    'REQUEST_NAME_REPLY_PRIMARY_OWNER' : 1,
    'REQUEST_NAME_REPLY_IN_QUEUE': 2,
    'REQUEST_NAME_REPLY_EXISTS': 3,
    'REQUEST_NAME_REPLY_ALREADY_OWNER': 4,
    'NAME_FLAG_DO_NOT_QUEUE' : 4
}
for key, value in dbus_bindings_consts.items():
    try:
        getattr(dbus.dbus_bindings, key)
    except AttributeError:
        setattr(dbus.dbus_bindings, key, value)

try:
    NameExistsException = dbus.NameExistsException
except AttributeError:
    class NameExistsException(dbus.DBusException):
        pass

class BusNameFlags(object):
    """A base class for exporting your own Named Services across the Bus
    """
    def __new__(cls, name, bus=None, flags=0):
        # get default bus
        if bus == None:
            bus = dbus.Bus()

        # otherwise register the name
        retval = dbus.dbus_bindings.bus_request_name(bus.get_connection(), name, flags=flags)

        # TODO: more intelligent tracking of bus name states?
        if retval == dbus.dbus_bindings.REQUEST_NAME_REPLY_PRIMARY_OWNER:
            pass
        elif retval == dbus.dbus_bindings.REQUEST_NAME_REPLY_IN_QUEUE:
            # queueing can happen by default, maybe we should
            # track this better or let the user know if they're
            # queued or not?
            pass
        elif retval == dbus.dbus_bindings.REQUEST_NAME_REPLY_EXISTS:
            raise NameExistsException(name)
        elif retval == dbus.dbus_bindings.REQUEST_NAME_REPLY_ALREADY_OWNER:
            # if this is a shared bus which is being used by someone
            # else in this process, this can happen legitimately
            pass
        else:
            raise RuntimeError('requesting bus name %s returned unexpected value %s' % (name, retval))

        # and create the object
        bus_name = object.__new__(cls)
        bus_name._bus = bus
        bus_name._name = name

        return bus_name

    # do nothing because this is called whether or not the bus name
    # object was retrieved from the cache or created new
    def __init__(self, *args, **keywords):
        pass

    # we can delete the low-level name here because these objects
    # are guaranteed to exist only once for each bus name
    def __del__(self):
        dbus_bindings.bus_release_name(self._bus.get_connection(), self._name)
        pass

    def get_bus(self):
        """Get the Bus this Service is on"""
        return self._bus

    def get_name(self):
        """Get the name of this service"""
        return self._name

    def __repr__(self):
        return '<dbus.service.BusName %s on %r at %#x>' % (self._name, self._bus, id(self))
    __str__ = __repr__

class OneTime (dbus.service.Object):
    def __init__(self):
        bus = dbus.SessionBus()
        bus_name = BusNameFlags('org.participatoryculture.dtv.onetime', bus=bus, flags=dbus.dbus_bindings.NAME_FLAG_DO_NOT_QUEUE)
        dbus.service.Object.__init__(self, bus_name, '/org/participatoryculture/dtv/OneTime')

    @dbus.service.method('org.participatoryculture.dtv.OneTimeIface')
    def HandleArgs (self, args):
        import singleclick
        import app
        import eventloop
        for i in xrange(len(args)):
            if args[i].startswith('file://'):
                args[i] = args[i][len('file://'):]
        eventloop.addIdle(lambda:singleclick.handleCommandLineArgs (args), "Open Files from dbus")
        app.controller.frame.widgetTree['main-window'].present()



