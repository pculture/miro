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

import os
import weakref

from miro.frontends.widgets import widgetconst
from miro.plat import resources
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets import layoutmanager
from miro.plat.frontends.widgets.base import Widget
from miro.plat.frontends.widgets.helpers import NotificationForwarder

from miro import searchengines

class SizedControl(Widget):
    def set_size(self, size):
        if size == widgetconst.SIZE_NORMAL:
            self.view.cell().setControlSize_(NSRegularControlSize)
            font = NSFont.systemFontOfSize_(NSFont.systemFontSize())
        elif size == widgetconst.SIZE_SMALL:
            font = NSFont.systemFontOfSize_(NSFont.smallSystemFontSize())
            self.view.cell().setControlSize_(NSSmallControlSize)
        else:
            raise ValueError("Unknown size: %s" % size)
        self.view.setFont_(font)

class BaseTextEntry(SizedControl):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, initial_text=None):
        SizedControl.__init__(self)
        self.view = self.make_view()
        self.font = NSFont.systemFontOfSize_(NSFont.systemFontSize())
        self.height = self.font.pointSize() + self.font.leading()
        self.view.setFont_(self.font)
        self.view.setEditable_(YES)
        self.view.cell().setLineBreakMode_(NSLineBreakByClipping)
        self.sizer_cell = self.view.cell().copy()
        if initial_text:
            self.view.setStringValue_(initial_text)
            self.set_width(len(initial_text))
        else:
            self.set_width(10)

        self.notifications = NotificationForwarder.create(self.view)
        self.notifications.connect(self.on_changed, 'NSControlTextDidChangeNotification')

        self.create_signal('activate')
        self.create_signal('changed')
        self.create_signal('validate')

    def baseline(self):
        return -self.view.font().descender() + 2

    def on_changed(self, notification):
        self.emit('changed')

    def calc_size_request(self):
        size = self.sizer_cell.cellSize()
        return size.width, size.height

    def set_text(self, text):
        self.view.setStringValue_(text)
        self.emit('changed')

    def get_text(self):
        return self.view.stringValue()

    def set_width(self, chars):
        self.sizer_cell.setStringValue_('X' * chars)
        self.invalidate_size_request()

    def set_activates_default(self, setting):
        pass

    def enable_widget(self):
        SizedControl.enable_widget(self)
        self.view.setEnabled_(True)

    def disable_widget(self):
        SizedControl.disable_widget(self)
        self.view.setEnabled_(False)

class MiroTextField(NSTextField):
    def becomeFirstResponder(self):
        wrappermap.wrapper(self).emit('activate')
        return NSTextField.becomeFirstResponder(self)

class TextEntry(BaseTextEntry):
    def make_view(self):
        return MiroTextField.alloc().init()

class MiroSecureTextField(NSSecureTextField):
    def becomeFirstResponder(self):
        wrappermap.wrapper(self).emit('activate')
        return NSSecureTextField.becomeFirstResponder(self)

class SecureTextEntry(BaseTextEntry):
    def make_view(self):
        return MiroSecureTextField.alloc().init()

class MiroSearchTextField(NSSearchField):
    def becomeFirstResponder(self):
        wrappermap.wrapper(self).emit('activate')
        return NSSearchField.becomeFirstResponder(self)

class SearchTextEntry(BaseTextEntry):
    def make_view(self):
        return MiroSearchTextField.alloc().init()


class MiroButton(NSButton):
    
    def initWithSignal_(self, signal):
        self = super(MiroButton, self).init()
        self.signal = signal
        return self
    
    def sendAction_to_(self, action, to):
        # We override the Cocoa machinery here and just send it to our wrapper
        # widget.
        wrappermap.wrapper(self).emit(self.signal)
        return YES

class Checkbox(SizedControl):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, label):
        SizedControl.__init__(self)
        self.create_signal('toggled')
        self.label = label
        self.view = MiroButton.alloc().initWithSignal_('toggled')
        self.view.setButtonType_(NSSwitchButton)
        self.view.setTitle_(self.label)

    def calc_size_request(self):
        size = self.view.cell().cellSize()
        return (size.width, size.height)

    def baseline(self):
        return -self.view.font().descender() + 1

    def get_checked(self):
        return self.view.state() == NSOnState

    def set_checked(self, value):
        if value:
            self.view.setState_(NSOnState)
        else:
            self.view.setState_(NSOffState)

    def enable_widget(self):
        SizedControl.enable_widget(self)
        self.view.setEnabled_(True)

    def disable_widget(self):
        SizedControl.disable_widget(self)
        self.view.setEnabled_(False)

class Button(SizedControl):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, label, style='normal'):
        SizedControl.__init__(self)
        self.color = None
        self.title = label
        self.create_signal('clicked')
        self.view = MiroButton.alloc().initWithSignal_('clicked')
        self.view.setButtonType_(NSMomentaryPushInButton)
        self._set_title()
        self.setup_style(style)
        self.min_width = 0

    def set_text(self, label):
        self.title = label
        self._set_title()

    def set_color(self, color):
        self.color = self.make_color(color)
        self._set_title()

    def _set_title(self):
        if self.color is None:
            self.view.setTitle_(self.title)
        else:
            attributes = {
                NSForegroundColorAttributeName: self.color,
                NSFontAttributeName: self.view.font()
            }
            string = NSAttributedString.alloc().initWithString_attributes_(
                    self.title, attributes)
            self.view.setAttributedTitle_(string)

    def setup_style(self, style):
        if style == 'normal':
            self.view.setBezelStyle_(NSRoundedBezelStyle)
            self.pad_height = 0
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

    def baseline(self):
        return -self.view.font().descender() + 10 + self.pad_height

    def enable_widget(self):
        SizedControl.enable_widget(self)
        self.view.setEnabled_(True)

    def disable_widget(self):
        SizedControl.disable_widget(self)
        self.view.setEnabled_(False)

class MiroPopupButton(NSPopUpButton):

    def init(self):
        self = NSPopUpButton.init(self)
        self.setTarget_(self)
        self.setAction_('handleChange:')
        return self

    def handleChange_(self, sender):
        wrappermap.wrapper(self).emit('changed', self.indexOfSelectedItem())

class OptionMenu(SizedControl):
    def __init__(self, options):
        SizedControl.__init__(self)
        self.create_signal('changed')
        self.view = MiroPopupButton.alloc().init()
        self.options = options
        for option in options:
            self.view.addItemWithTitle_(option)

    def baseline(self):
        if self.view.cell().controlSize() == NSRegularControlSize:
            return -self.view.font().descender() + 6
        else:
            return -self.view.font().descender() + 5

    def calc_size_request(self):
        return self.view.cell().cellSize()

    def set_selected(self, index):
        self.view.selectItemAtIndex_(index)

    def get_selected(self):
        return self.view.indexOfSelectedItem()

    def enable_widget(self):
        SizedControl.enable_widget(self)
        self.view.setEnabled_(True)

    def disable_widget(self):
        SizedControl.disable_widget(self)
        self.view.setEnabled_(False)

class RadioButtonGroup:
    def __init__(self):
        self._buttons = []

    def handle_click(self, widget):
        self.set_selected(widget)

    def add_button(self, button):
        self._buttons.append(button)
        button.connect('clicked', self.handle_click)
        if len(self._buttons) == 1:
            button.view.setState_(NSOnState)
        else:
            button.view.setState_(NSOffState)

    def get_buttons(self):
        return self._buttons

    def get_selected(self):
        for mem in self._buttons:
            if mem.get_selected():
                return mem

    def set_selected(self, button):
        for mem in self._buttons:
            if button is mem:
                mem.view.setState_(NSOnState)
            else:
                mem.view.setState_(NSOffState)

# use a weakref so that we're not creating circular references between
# RadioButtons and RadioButtonGroups
radio_button_to_group_mapping = weakref.WeakValueDictionary()

class RadioButton(SizedControl):
    def __init__(self, label, group=None):
        SizedControl.__init__(self)
        self.create_signal('clicked')
        self.view = MiroButton.alloc().initWithSignal_('clicked')
        self.view.setButtonType_(NSRadioButton)
        self.view.setTitle_(label)

        if not group:
            group = RadioButtonGroup() 

        group.add_button(self)
        oid = id(self)
        radio_button_to_group_mapping[oid] = group

    def calc_size_request(self):
        size = self.view.cell().cellSize()
        return (size.width, size.height)

    def baseline(self):
        -self.view.font().descender() + 2

    def get_group(self):
        return radio_button_to_group_mapping[id(self)]

    def get_selected(self):
        return self.view.state() == NSOnState

    def set_selected(self):
        radio_button_to_group_mapping[id(self)].set_selected(self)

    def enable_widget(self):
        SizedControl.enable_widget(self)
        self.view.setEnabled_(True)

    def disable_widget(self):
        SizedControl.disable_widget(self)
        self.view.setEnabled_(False)


class VideoSearchTextEntry (SearchTextEntry):

    def make_view(self):
        return NSVideoSearchField.alloc().init()

    def selected_engine(self):
        return self.view.currentItem.representedObject()

class NSVideoSearchField (MiroSearchTextField):

    def init(self):
        self = MiroSearchTextField.init(self)
        self.currentItem = nil
        self.setTarget_(self)
        self.setAction_('search:')
        self.cell().setBezeled_(YES)
        self.cell().setSearchMenuTemplate_(self.makeSearchMenuTemplate())
        self.cell().setSendsWholeSearchString_(YES)
        self.cell().setSendsSearchStringImmediately_(NO)
        self.cell().setScrollable_(YES)
        self.initFromLastEngine()
        return self

    def makeSearchMenuTemplate(self):
        menu = NSMenu.alloc().initWithTitle_("Search Menu")
        for engine in reversed(searchengines.get_search_engines()):
            nsitem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(engine.title, 'selectEngine:', '')
            nsitem.setTarget_(self)
            nsitem.setImage_(_getEngineIcon(engine))
            nsitem.setRepresentedObject_(engine)
            menu.insertItem_atIndex_(nsitem, 0)
        return menu

    def selectEngine_(self, sender):
        if self.currentItem is not nil:
            self.currentItem.setState_(NSOffState)
        self.currentItem = sender
        sender.setState_(NSOnState)
        engine = sender.representedObject()
        self.cell().searchButtonCell().setImage_(_getSearchIcon(engine))

    def search_(self, sender):
        if self.stringValue() != "":
            wrappermap.wrapper(self).emit('validate')

    def initFromLastEngine(self):
        self.setStringValue_("")
        lastEngine = searchengines.get_last_engine()
        for engine in searchengines.get_search_engines():
            if engine.name == lastEngine.name:
                menu = self.searchMenuTemplate()
                index = menu.indexOfItemWithRepresentedObject_(engine)
                menu.performActionForItemAtIndex_(index)
                return

class VideoSearchFieldCell (NSSearchFieldCell):
    
    def searchButtonRectForBounds_(self, bounds):
        return NSRect(NSPoint(8.0, 3.0), NSSize(25.0, 16.0))
        
    def searchTextRectForBounds_(self, bounds):
        textBounds = NSSearchFieldCell.searchTextRectForBounds_(self, bounds)
        cancelButtonBounds = NSSearchFieldCell.cancelButtonRectForBounds_(self, bounds)
        searchButtonBounds = self.searchButtonRectForBounds_(bounds)

        x = searchButtonBounds.origin.x + searchButtonBounds.size.width + 4
        y = textBounds.origin.y
        width = bounds.size.width - x - cancelButtonBounds.size.width
        height = textBounds.size.height

        return ((x, y), (width, height))

NSVideoSearchField.setCellClass_(VideoSearchFieldCell)

def _getEngineIcon(engine):
    engineIconPath = resources.path('images/search_icon_%s.png' % engine.name)
    if not os.path.exists(engineIconPath):
        return nil
    return NSImage.alloc().initByReferencingFile_(engineIconPath)

searchIcons = dict()
def _getSearchIcon(engine):
    if engine.name not in searchIcons:
        searchIcons[engine.name] = _makeSearchIcon(engine)
    return searchIcons[engine.name]        

def _makeSearchIcon(engine):
    popupRectangle = NSImage.imageNamed_(u'search_popup_triangle')
    popupRectangleSize = popupRectangle.size()

    engineIconPath = resources.path('images/search_icon_%s.png' % engine.name)
    if not os.path.exists(engineIconPath):
        return nil
    engineIcon = NSImage.alloc().initByReferencingFile_(engineIconPath)
    engineIconSize = engineIcon.size()

    searchIconSize = (engineIconSize.width + popupRectangleSize.width + 2, engineIconSize.height)
    searchIcon = NSImage.alloc().initWithSize_(searchIconSize)
    
    searchIcon.lockFocus()
    try:
        engineIcon.compositeToPoint_operation_((0,0), NSCompositeSourceOver)
        popupRectangleX = engineIconSize.width + 2
        popupRectangleY = (engineIconSize.height - popupRectangleSize.height) / 2
        popupRectangle.compositeToPoint_operation_((popupRectangleX, popupRectangleY), NSCompositeSourceOver)
    finally:
        searchIcon.unlockFocus()

    return searchIcon
