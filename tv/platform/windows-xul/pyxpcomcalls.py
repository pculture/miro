# Miro - an RSS based video player application
# Copyright (C) 2008 Participatory Culture Foundation
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


# Create and store python callbacks so we can call them from XPCOM land

from xpcom import components
from xulhelper import makeComp
from util import random_string
from eventloop import asIdle

_callbacks = {}

def XPCOMifyCallback(callback):
    global _callbacks
    # This assumes that n/(52^50) == 0 when n is small
    idstring = random_string(50)
    _callbacks[idstring] = callback
    c = makeComp("@participatoryculture.org/dtv/pycallback;1",
                 components.interfaces.pcfIDTVPyCallback, True, False)
    c.setCallbackId(idstring)
    return c

@asIdle
def makeCallback(idstring, value):
    _callbacks[idstring](value)
    del _callbacks[idstring]
