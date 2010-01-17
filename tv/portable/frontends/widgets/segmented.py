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

    def __init__(self, label=None, behavior='radio'):
        self.buttons_list = list()
        self.buttons_map = dict()
        self.label = label
        self.behavior = behavior
    
    def add_text_button(self, key, title, callback):
        self.add_button(key, TextButtonSegment(key, title, callback))
    
    def add_image_button(self, key, image_name, callback):
        self.add_button(key, ImageButtonSegment(key, image_name, callback))

    def add_button(self, key, button):
        self.buttons_list.append(button)
        self.buttons_map[key] = button
    
    def make_widget(self):
        hbox = widgetset.HBox()
        if self.label is not None:
            label = widgetset.Label(self.label)
            label.set_size(-2)
            label.set_color((0.9, 0.9, 0.9))
            hbox.pack_start(widgetutil.align_middle(label))
        count = len(self.buttons_list)
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
            button = self.buttons_list[index]
            button.set_segment_type(segment_type)
            hbox.pack_start(button)
        return hbox
    
    def get_button(self, key):
        return self.buttons_map[key]
    
    def is_active(self, key):
        return self.buttons_map[key].active
    
    def set_active(self, key, active=True):
        # When using the radio behavior the passed active state is ignored and
        # considered True.
        if self.behavior == 'radio':
            for button in self.buttons_list:
                if button.key == key:
                    button.set_active(True)
                else:
                    button.set_active(False)
        else:
            self.buttons_map[key].set_active(active)

    def toggle(self, key):
        button = self.buttons_map[key]
        button.set_active(not button.active)

class ButtonSegment(widgetset.CustomButton):
    
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

    def __init__(self, key, callback):
        widgetset.CustomButton.__init__(self)
        self.key = key
        self.segment_type = None
        self.active = False
        self.set_squish_width(True)
        self.connect('clicked', callback)

    def set_segment_type(self, segment_type):
        self.segment_type = segment_type

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


class TextButtonSegment(ButtonSegment):
    
    MARGIN = 12
    TEXT_COLOR = { True: (0.86, 0.86, 0.86), False: (0.5, 0.5, 0.5) }
    
    def __init__(self, key, title, callback):
        ButtonSegment.__init__(self, key, callback)
        self.title = title

    def size_request(self, layout):
        width, _ = self._get_textbox(layout).get_size()
        return math.ceil(width) + (2 * self.MARGIN), 20

    def draw(self, context, layout):
        ButtonSegment.draw(self, context, layout)
        layout.set_text_color(self.TEXT_COLOR[self.active])
        textbox = self._get_textbox(layout)
        _, height = textbox.get_size()
        y = int((context.height - height) / 2.0)
        textbox.draw(context, self.MARGIN, y, context.width - (2 * self.MARGIN), context.height)

    def _get_textbox(self, layout):
        layout.set_font(0.8)
        return layout.textbox(self.title)


class ImageButtonSegment(ButtonSegment):

    MARGIN = 7
    IMAGE_ALPHA = { True: 1.0, False: 0.4 }

    def __init__(self, key, image_name, callback):
        ButtonSegment.__init__(self, key, callback)
        self.image = _get_image(image_name)

    def size_request(self, layout):
        return self.image.width + (2 * self.MARGIN), 20

    def draw(self, context, layout):
        ButtonSegment.draw(self, context, layout)
        alpha = self.IMAGE_ALPHA[self.active]
        y = int((context.height - self.image.height) / 2.0)
        self.image.draw(context, self.MARGIN, y, self.image.width, self.image.height, alpha)
