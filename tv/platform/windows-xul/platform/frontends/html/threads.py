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

"""miro.platform.frontends.html.threading -- Call functions in the XUL
thread.
"""

def inMainThread(function, args=None, kwargs=None):
    # TODO: IMPLEMENT THIS CORRECTLY (Currently calling on the same thread)
    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}
    return function(*args, **kwargs)
