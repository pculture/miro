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

import os
import math

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

from miro.frontends.widgets import imagepool
from miro.frontends.widgets import widgetutil

def _get_image(name):
    path = resources.path(os.path.join('images', '%s.png' % name))
    return imagepool.get_surface(path)

class SegmentedButtonsRow(object):

    def __init__(self):
        self.buttons = list()
    
    def add_text_button(self, key, title, callback):
        self.buttons.append(TextButtonSegment(key, title, callback))
    
    def add_image_button(self, key, image_name, callback):
        self.buttons.append(ImageButtonSegment(key, image_name, callback))
    
    def make_widget(self):
        hbox = widgetset.HBox()
        count = len(self.buttons)
        for index in range(count):
            if index == 0:
                if count == 1:
                    segment_type = 'unique'
                else:
                    segment_type = 'left'
            elif index == count-1:
                segment_type =  'right'
            else:
                segment_type =  'middle'
            button = self.buttons[index].make_widget(segment_type)
            self.buttons[index] = button
            hbox.pack_start(button)
        return hbox
    
    def set_active(self, key):
        for button in self.buttons:
            if button.key == key:
                button.set_active(True)
            else:
                button.set_active(False)


class ButtonSegment(object):

    def __init__(self, key, callback):
        self.key = key
        self.callback = callback
        self.active = False
        
    def set_active(self, active):
        self.active = active

    def make_widget(self, segment_type):
        button = self.make_button_widget(segment_type)
        button.set_squish_width(True)
        button.connect('clicked', self.callback)
        button.set_active(self.active)
        return button


class TextButtonSegment(ButtonSegment):

    def __init__(self, key, title, callback):
        ButtonSegment.__init__(self, key, callback)
        self.title = title
    
    def make_button_widget(self, segment_type):
        return TextButtonSegmentWidget(self.key, self.title, segment_type)


class ImageButtonSegment(ButtonSegment):

    def __init__(self, key, image_name, callback):
        ButtonSegment.__init__(self, key, callback)
        self.image_name = image_name

    def make_button_widget(self, segment_type):
        return ImageButtonSegmentWidget(self.key, self.image_name, segment_type)


class ButtonSegmentWidget(widgetset.CustomButton):
    
    PARTS = {
        'off-far-left':     _get_image('segmented-off-far-left'),
        'off-middle-left':  _get_image('segmented-off-middle-left'),
        'off-center':       _get_image('segmented-off-center'),
        'off-middle-right': _get_image('segmented-off-middle-right'),
        'off-far-right':    _get_image('segmented-off-far-right'),
        'on-far-left':      _get_image('segmented-on-far-left'),
        'on-middle-left':   _get_image('segmented-on-middle-left'),
        'on-center':        _get_image('segmented-on-center'),
        'on-middle-right':  _get_image('segmented-on-middle-right'),
        'on-far-right':     _get_image('segmented-on-far-right')
    }

    def __init__(self, key, segment_type):
        widgetset.CustomButton.__init__(self)
        self.key = key
        self.segment_type = segment_type
        self.active = False

    def set_active(self, active):
        self.active = active
        self.queue_redraw()

    def draw(self, context, layout):
        if self.active:
            prefix = 'on'
        else:
            prefix = 'off'
        if self.segment_type in ('left', 'unique'):
            left = self.PARTS['%s-far-left' % prefix]
        else:
            left = self.PARTS['%s-middle-left' % prefix]
        center = self.PARTS['%s-center' % prefix]
        if self.segment_type in ('right', 'unique'):
            right = self.PARTS['%s-far-right' % prefix]
        else:
            right = self.PARTS['%s-middle-right' % prefix]
        surface = widgetutil.ThreeImageSurface()
        surface.set_images(left, center, right)
        surface.draw(context, 0, 0, context.width)


class TextButtonSegmentWidget(ButtonSegmentWidget):
    
    MARGIN = 12
    TEXT_COLOR = { True: (0.86, 0.86, 0.86), False: (0.4, 0.4, 0.4) }
    
    def __init__(self, key, title, segment_type):
        ButtonSegmentWidget.__init__(self, key, segment_type)
        self.title = title

    def size_request(self, layout):
        width, _ = self._get_textbox(layout).get_size()
        return math.ceil(width) + (2 * self.MARGIN), 20

    def draw(self, context, layout):
        ButtonSegmentWidget.draw(self, context, layout)
        layout.set_text_color(self.TEXT_COLOR[self.active])
        textbox = self._get_textbox(layout)
        _, height = textbox.get_size()
        y = int((context.height - height) / 2.0)
        textbox.draw(context, self.MARGIN, y, context.width - (2 * self.MARGIN), context.height)

    def _get_textbox(self, layout):
        layout.set_font(0.8)
        return layout.textbox(self.title)


class ImageButtonSegmentWidget(ButtonSegmentWidget):

    MARGIN = 7
    IMAGE_ALPHA = { True: 1.0, False: 0.4 }

    def __init__(self, key, image_name, segment_type):
        ButtonSegmentWidget.__init__(self, key, segment_type)
        self.image = _get_image(image_name)

    def size_request(self, layout):
        return self.image.width + (2 * self.MARGIN), 20

    def draw(self, context, layout):
        ButtonSegmentWidget.draw(self, context, layout)
        alpha = self.IMAGE_ALPHA[self.active]
        y = int((context.height - self.image.height) / 2.0)
        self.image.draw(context, self.MARGIN, y, self.image.width, self.image.height, alpha)
