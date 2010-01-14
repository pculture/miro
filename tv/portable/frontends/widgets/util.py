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

"""``miro.frontends.widgets.util`` -- Utility functions.
"""

def rounded_rectangle(context, x, y, width, height, xradius, yradius=None):
    """Create a path using a rounded rectangle.  xradius and yradius specifies
    how far away from the normal rectangle corner the rounded edge will start.

    yradius defaults to xradius.
    """

    if yradius is None:
        yradius = xradius
    xradius = min(xradius, width/2.0)
    yradius = min(xradius, height/2.0)
    inner_width = width - xradius*2
    inner_height = height - yradius*2
    context.move_to(x+xradius, y)
    context.rel_line_to(inner_width, 0)
    # Our basic strategy for the corners is to make a curve with the
    # control points at the corner where a non-round rectangle would be
    context.rel_curve_to(xradius, 0, xradius, 0, xradius, yradius)
    context.rel_line_to(0, inner_height)
    context.rel_curve_to(0, yradius, 0, yradius, -xradius, yradius)
    context.rel_line_to(-inner_width, 0)
    context.rel_curve_to(-xradius, 0, -xradius, 0, -xradius, -yradius)
    context.rel_line_to(0, -inner_height)
    context.rel_curve_to(0, -yradius, 0, -yradius, xradius, -yradius)

