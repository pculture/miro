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

"""Contains widgets used in Miro."""

from miro.frontends.widgets.util import rounded_rectangle
from miro.plat.frontends.widgets.widgetset import Rect, Window, Browser, \
        VBox, HBox, Alignment, Splitter, ControlBox, ImageSurface, \
        CustomControl, ControlBackground

from miro.plat import resources

def make_browser(url):
    browser = Browser()
    browser.navigate(url)
    return browser

class ProgressTimeline(ControlBackground):
    def __init__(self):
        ControlBackground.__init__(self)
        self.alignment = Alignment()
        self.alignment.set_padding(8, 4, 30, 30)
        self.hbox = HBox()
        self.alignment.add(self.hbox)
        self.add(self.alignment)
        self.hbox.pack_start(PlayButton(), padding=10)
        self.hbox.pack_start(PlayButton(), padding=10)

    def draw(self, context, area):
        context.rectangle(area.x, area.y, area.width, area.height)
        context.clip()
        rounded_rectangle(context, 0, 0, self.width, self.height, 20)
        context.set_source_rgba(1.0, 0.4, 0.1, 0.3)
        context.fill()

class PlaybackControls(ControlBox):
    def __init__(self):
        ControlBox.__init__(self)
        self.image = ImageSurface(resources.path('wimages/wtexture.png'))
        self.image_inactive = \
                ImageSurface(resources.path('wimages/wtexture_inactive.png'))

        self.progress_background = ProgressTimeline()
        self.add(self.progress_background)

    def draw(self, context, area):
        context.rectangle(area.x, area.y, area.width, area.height)
        context.clip()
        if self.get_window().is_active():
            image = self.image
        else:
            image = self.image_inactive
        context.draw_image(image, 0, 0, self.width, self.height)

class PlayButton(CustomControl):
    def on_mouse_down(self, x, y):
        print 'mouse down: ', x, y
    def on_mouse_drag(self, x, y):
        print 'mouse drag: ', x, y
    def on_mouse_up(self, x, y):
        print 'mouse up: ', x, y

    def draw(self, context, area):
        context.set_source_rgba(0.4, 0.4, 1.0, 0.3)
        rounded_rectangle(context, area.x, area.y, area.width, area.height, 25)
        context.fill()

    def size_request(self):
        return 50, 50

# What is this ?!??! There's already a Miro window in frontends.widgets.window - luc
#class MiroWindow(Window):
#    def __init__(self, title, rect):
#        Window.__init__(self, title, rect)
#        self.connect('active-change', 
#                lambda window: controlbox.queue_redraw())
#        # self.splitter = Splitter()
#        # b1 = make_browser('http://google.com/')
#        # b2 = make_browser('http://getmiro.com/')
#        # controlbox = PlaybackControls()
#        # vbox = VBox()
#        # vbox.pack_start(b2, True)
#        # vbox.pack_start(controlbox)
#        # self.splitter.set_left(b1)
#        # self.splitter.set_right(vbox)
#        # self.set_content_widget(self.splitter)
