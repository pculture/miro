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

"""Custom controls that we use."""

from miro.frontends.widgets import imagepool
from miro.plat.frontends.widgets import widgetset
from miro.plat import resources

class ImageButtonMixin(object):
    def __init__(self, image_name):
        self.set_image(image_name)
        if (self.image.width != self.pressed_image.width or
                self.image.height != self.pressed_image.height):
            raise ValueError("Image sizes don't match")
    
    def set_image(self, image_name):
        path = resources.path('wimages/%s.png' % image_name)
        self.image = imagepool.get_surface(path)
        pressed_path = resources.path('wimages/%s_active.png' % image_name)
        self.pressed_image = imagepool.get_surface(pressed_path)
    
    def size_request(self, layout):
        return self.image.width, self.image.height

    def draw(self, context, layout):
        if self.state == 'pressed':
            self.pressed_image.draw(context, 0, 0, self.image.width,
                    self.image.height)
        else:
            self.image.draw(context, 0, 0, self.image.width, self.image.height)

class ImageButton(ImageButtonMixin, widgetset.CustomButton):
    def __init__(self, image_name):
        widgetset.CustomButton.__init__(self)
        ImageButtonMixin.__init__(self, image_name)

class ContinuousImageButton(ImageButtonMixin, widgetset.ContinuousCustomButton):
    def __init__(self, image_name):
        widgetset.ContinuousCustomButton.__init__(self)
        ImageButtonMixin.__init__(self, image_name)
