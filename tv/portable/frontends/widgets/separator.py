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

from miro.plat.frontends.widgets.widgetset import DrawingArea

class Separator (DrawingArea):
    def __init__(self, color1=None, color2=None):
        DrawingArea.__init__(self)
        self.set_color1(color1)
        self.set_color2(color2)
    
    def set_color1(self, color):
        if color is None:
            self.color1 = (0.85, 0.85, 0.85)
        else:
            self.color1 = color

    def set_color2(self, color):
        if color is None:
            self.color2 = (0.95, 0.95, 0.95)
        else:
            self.color2 = color
        
class HSeparator (Separator):
    def draw(self, context, layout_manager):
        context.set_line_width(1)
        context.set_color(self.color1)
        context.move_to(0, 0.5)
        context.line_to(context.width, 0.5)
        context.stroke()
        context.set_color(self.color2)
        context.move_to(0, 1.5)
        context.line_to(context.width, 1.5)
        context.stroke()
    def size_request(self, layout):
        return (0, 2)
        
class VSeparator (Separator):
    def draw(self, context, layout_manager):
        context.set_line_width(1)
        context.set_color(self.color1)
        context.move_to(0.5, 0)
        context.line_to(0.5, context.height)
        context.stroke()
        context.set_color(self.color2)
        context.move_to(1.5, 0)
        context.line_to(1.5, context.height)
        context.stroke()
    def size_request(self, layout):
        return (2, 0)


class ThinSeparator (DrawingArea):
    def __init__(self, color):
        DrawingArea.__init__(self)
        self.color = color

class HThinSeparator (ThinSeparator):
    def draw(self, context, layout_manager):
        context.set_color(self.color)
        context.move_to(0, 0)
        context.line_to(context.width, 0)
        context.stroke()
    def size_request(self, layout):
        return (0, 1)

class VThinSeparator (ThinSeparator):
    def draw(self, context, layout_manager):
        context.set_color(self.color)
        context.move_to(0, 0)
        context.line_to(0, context.height)
        context.stroke()
    def size_request(self, layout):
        return (1, 0)
