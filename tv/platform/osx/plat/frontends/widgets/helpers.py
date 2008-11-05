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

"""helper classes."""

import logging
import traceback

from Foundation import *
from objc import nil

class NotificationForwarder(NSObject):
    """Forward notifications from a Cocoa object to a python class.  
    """

    def initWithNSObject_center_(self, nsobject, center):
        """Initialize the NotificationForwarder nsobject is the NSObject to
        forward notifications for.  It can be nil in which case notifications
        from all objects will be forwarded.

        center is the NSNotificationCenter to get notifications from.  It can
        be None, in which cas the default notification center is used.
        """
        self.nsobject = nsobject
        self.callback_map = {}
        if center is None:
            self.center = NSNotificationCenter.defaultCenter()
        else:
            self.center = center
        return self

    @classmethod
    def create(cls, object, center=None):
        """Helper method to call aloc() then initWithNSObject_center_()."""
        return cls.alloc().initWithNSObject_center_(object, center)

    def connect(self, callback, name):
        """Register to listen for notifications.
        Only one callback for each notification name can be connected.
        """

        if name in self.callback_map:
            raise ValueError("%s already connected" % name)

        self.callback_map[name] = callback
        self.center.addObserver_selector_name_object_(self, 'observe:', name,
                self.nsobject)

    def disconnect(self, name=None):
        if name is not None:
            self.center.removeObserver_name_object_(self, name, self.nsobject)
        else:
            self.center.removeObserver_(self)

    def observe_(self, notification):
        name = notification.name()
        callback = self.callback_map[name]
        if callback is None:
            logging.warn("Callback for %s is dead", name)
            self.center.removeObverser_name_object_(self, name, self.nsobject)
            return
        try:
            callback(notification)
        except:
            logging.warn("Callback for %s raised exception:%s\n", name,
                    traceback.format_exc())

    def __del__(self):
        self.disconnect()
