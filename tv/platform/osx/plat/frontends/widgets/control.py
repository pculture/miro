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

"""miro.plat.frontends.widgets.control - Controls."""

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets import layoutmanager
from miro.plat.frontends.widgets.base import Widget

def round_up(float):
    return int(round(float + 0.5))

class TextEntry(Widget):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, intial_text=None, hidden=False):
        Widget.__init__(self)
        self.font = NSFont.systemFontOfSize_(NSFont.systemFontSize())
        self.height = self.font.pointSize() + self.font.leading()
        if hidden:
            self.view = NSSecureTextField.alloc().init()
        else:
            self.view = NSTextField.alloc().init()
        self.view.setFont_(self.font)
        self.view.setEditable_(YES)
        self.sizer_cell = self.view.cell().copy()
        if intial_text:
            self.view.setStringValue_(intial_text)
            self.set_width(len(intial_text))
        else:
            self.set_width(10)

    def calc_size_request(self):
        size = self.sizer_cell.cellSize()
        return size.width, size.height

    def set_text(self, text):
        self.view.setStringValue_(text)

    def get_text(self):
        return self.view.stringValue()

    def set_width(self, chars):
        self.sizer_cell.setStringValue_('X' * chars)
        self.invalidate_size_request()

    def set_activates_default(self, setting):
        pass

    def enable_widget(self):
        self.view.setEnabled_(True)

    def disable_widget(self):
        self.view.setEnabled_(False)

class Checkbox(Widget):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, label):
        Widget.__init__(self)
        self.label = label
        self.view = NSButton.alloc().init()
        self.view.setButtonType_(NSSwitchButton)
        self.view.setTitle_(self.label)

    def calc_size_request(self):
        size = self.view.cell().cellSize()
        return (size.width, size.height)

    def get_checked(self):
        return self.view.state() == NSOnState

    def set_checked(self, value):
        if value:
            self.view.setState_(NSOnState)
        else:
            self.view.setState_(NSOffState)

    def enable_widget(self):
        self.view.setEnabled_(True)

    def disable_widget(self):
        self.view.setEnabled_(False)

class MiroButton(NSButton):
    def sendAction_to_(self, action, to):
        # We override the Cocoa machinery here and just send it to our wrapper
        # widget.
        wrappermap.wrapper(self).emit('clicked')
        return YES

class AttributedStringStyler(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.bold = False
        self.color = None
        self.scale = 1

    def set_bold(self, bold):
        self.bold = bold
        self.update_attributes()

    def set_size(self, scale):
        self.scale = scale
        self.update_attributes()

    def set_color(self, color):
        self.color = self.make_color(color)
        self.update_attributes()

    def update_attributes(self):
        font = layoutmanager.get_font(self.scale, bold=self.bold)
        attributes = { NSFontAttributeName: font }
        if self.color:
            attributes[NSForegroundColorAttributeName] = self.color
        self.handle_new_attributes(attributes)
        self.invalidate_size_request()

class Button(AttributedStringStyler):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, label, style='normal'):
        AttributedStringStyler.__init__(self)
        self.label = label
        self.create_signal('clicked')
        self.view = MiroButton.alloc().init()
        self.view.setButtonType_(NSMomentaryPushInButton)
        self.view.setTitle_(self.label)
        self.setup_style(style)
        self.min_width = 0

    def setup_style(self, style):
        if style == 'normal':
            self.view.setBezelStyle_(NSRoundedBezelStyle)
            self.pad_width = self.pad_height = 0
            self.pad_width = 10
            self.min_width = 112
        elif style == 'smooth':
            self.view.setBezelStyle_(NSRoundRectBezelStyle)
            self.pad_width = 0
            self.pad_height = 4
        self.paragraph_style = NSMutableParagraphStyle.alloc().init()
        self.paragraph_style.setAlignment_(NSCenterTextAlignment)

    def make_default(self):
        self.view.setKeyEquivalent_("\r")

    def calc_size_request(self):
        size = self.view.cell().cellSize()
        width = max(self.min_width, size.width + self.pad_width)
        height = size.height + self.pad_height
        return width, height

    def handle_new_attributes(self, attributes):
        attributes[NSParagraphStyleAttributeName] = self.paragraph_style
        string = NSAttributedString.alloc().initWithString_attributes_(
                self.label, attributes)
        self.view.setAttributedTitle_(string)

    def enable_widget(self):
        self.view.setEnabled_(True)

    def disable_widget(self):
        self.view.setEnabled_(False)

class OptionMenu(AttributedStringStyler):
    def __init__(self, *options):
        AttributedStringStyler.__init__(self)
        self.create_signal('changed')
        self.view = NSPopUpButton.alloc().init()
        self.options = options
        for option in options:
            self.view.addItemWithTitle_(option)

    def calc_size_request(self):
        return self.view.cell().cellSize()

    def select_option(self, index):
        self.view.selectItemAtIndex_(index)

    def handle_new_attributes(self, attributes):
        menu = self.view.menu()
        for i in xrange(menu.numberOfItems()):
            menu_item = menu.itemAtIndex_(i)
            string = NSAttributedString.alloc().initWithString_attributes_(
                    menu_item.title(), attributes)
            menu_item.setAttributedTitle_(string)
        self.view.setFont_(attributes[NSFontAttributeName])

    def enable_widget(self):
        self.view.setEnabled_(True)

    def disable_widget(self):
        self.view.setEnabled_(False)
