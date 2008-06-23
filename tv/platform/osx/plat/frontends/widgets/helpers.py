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
import weakref 

from Foundation import *
from objc import nil

class WeakMethodReference:
    """Used to handle weak references to a method.

    We can't simply keep a weak reference to method itself, because there
    almost certainly aren't any other references to it.  Instead we keep a
    weak reference to the unbound method and the class that it's attached to.
    This gives us enough info to recreate the bound method when we need it.
    """

    def __init__(self, method):
        self.object = weakref.ref(method.im_self)
        self.func = weakref.ref(method.im_func)
        # don't create a weak refrence to the class.  That only works for
        # new-style classes.  It's highly unlikely the class will ever need to
        # be garbage collected anyways.
        self.cls = method.im_class

    def __call__(self):
        func = self.func()
        if func is None: return None
        object = self.object()
        if object is None: return None
        return func.__get__(object, self.cls)

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

        This class keeps a weak reference to callback.  This matches the Cocoa
        API and prevents circular references in the common use-case where a
        Widget creates an NotificationForwarder, then connects it's own
        methods with it.

        Only one callback for each notification name can be connected.
        """

        if name in self.callback_map:
            raise ValueError("%s already connected" % name)

        if hasattr(callback, 'im_self'):
            # object method
            ref = WeakMethodReference(callback)
        else:
            # just a plain function
            ref = weakref.ref(callback)

        self.callback_map[name] = ref
        self.center.addObserver_selector_name_object_(self, 'observe:', name,
                self.nsobject)

    def observe_(self, notification):
        name = notification.name()
        callback = self.callback_map[name]()
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
        self.center.removeObserver_(self)
