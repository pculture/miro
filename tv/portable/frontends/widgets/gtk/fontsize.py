# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""fontsize.py set a pango font description to a size in pixels."""

import gtk
import pango

# Figure out how to set a font to a pixel size
if gtk.pygtk_version >= (2, 10):
    # Yeah, we can just use set_absolute_size()
    def set_font_pixel_size(font_description, size):
        font_description.set_absolute_size(size * pango.SCALE)
else:
    # Boo, we have to calculate it manually.
    #
    # The formula we use is
    # pangos/pixel == (pangos/point) * (points/inch) * (inches/mm) * (mm/pixels)
    # Where:
    # pangos/point == pango.SCALE
    # points/inch == 72
    # inches/mm == 0.0394
    # mm/pixel == (screen_height_mm() / screen_height())
    PANGO_SCALE_PIXELS = int(round(pango.SCALE * 72 * 0.0394 * 
            gtk.gdk.screen_height_mm() / gtk.gdk.screen_height()))
    def set_font_pixel_size(font_description, size):
        font_description.set_size(size * PANGO_SCALE_PIXELS)
