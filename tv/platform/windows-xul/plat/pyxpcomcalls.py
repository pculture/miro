# Miro - an RSS based video player application
# Copyright (C) 2008-2009 Participatory Culture Foundation
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


# Create and store python callbacks so we can call them from XPCOM land

from xpcom import components

from miro.eventloop import asIdle
from miro.plat.xulhelper import makeComp
from miro.util import random_string

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
