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

"""weakconnect.py -- Connect to a signal of a GObject using a weak method
reference.  This means that this connection will not keep the object alive.
This is a good thing because it prevents circular references between wrapper
widgets and the wrapped GTK widget.
"""

from miro import signals

class WeakSignalHandler(object):
    def __init__(self, method):
        self.method = signals.WeakMethodReference(method)

    def connect(self, obj, signal, *user_args):
        self.user_args = user_args
        self.signal_handle = obj.connect(signal, self.handle_callback)
        return self.signal_handle

    def handle_callback(self, obj, *args):
        real_method = self.method()
        if real_method is not None:
            return real_method(obj, *(args + self.user_args))
        else:
            obj.disconnect(self.signal_handle)

def weak_connect(gobject, signal, method, *user_args):
    handler = WeakSignalHandler(method)
    return handler.connect(gobject, signal, *user_args)
