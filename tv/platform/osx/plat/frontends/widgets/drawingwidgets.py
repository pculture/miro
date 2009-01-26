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

"""drawingviews.py -- views that support custom drawing."""

from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets import drawing
from miro.plat.frontends.widgets.base import Widget, SimpleBin, FlippedView
from miro.plat.frontends.widgets.layoutmanager import LayoutManager

class DrawingView(FlippedView):
    def init(self):
        FlippedView.init(self)
        self.layout_manager = LayoutManager()
        return self

    def isOpaque(self):
        return wrappermap.wrapper(self).is_opaque()

    def drawRect_(self, rect):
        context = drawing.DrawingContext(self, self.bounds(), rect)
        context.style = drawing.DrawingStyle()
        wrappermap.wrapper(self).draw(context, self.layout_manager)

class DrawingArea(drawing.DrawingMixin, Widget):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        Widget.__init__(self)
        self.view = DrawingView.alloc().init()

class Background(drawing.DrawingMixin, SimpleBin):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        SimpleBin.__init__(self)
        self.view = DrawingView.alloc().init()

    def calc_size_request(self):
        drawing_size = drawing.DrawingMixin.calc_size_request(self)
        container_size = SimpleBin.calc_size_request(self)
        return (max(container_size[0], drawing_size[0]), 
                max(container_size[1], drawing_size[1]))
