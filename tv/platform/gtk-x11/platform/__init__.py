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

"""Miro platform package.  This exists mostly to hold platform-specific miro
code.

One annoying thing is that having this package means that code in the miro
package can't import the system module, "platform".  This is easy to fix
though, we just implement the parts of the API we need here.
"""

import os
import sys

def system():
    return "Linux"

def machine():
    system,node,release,version,machine = os.uname()
    return machine

def python_version():
    version = sys.version.split(' ')[0]
    while version.count('.') < 3:
        version += '.0'
    return version
