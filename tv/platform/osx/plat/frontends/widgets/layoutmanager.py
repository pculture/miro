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

"""textlayout.py -- Contains the LayoutManager class.  It handles laying text,
buttons, getting font metrics and other tasks that are required to size
things.
"""

import logging
import math
import weakref

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

INFINITE = 1000000 # size of an "infinite" dimension

def get_font(scale_factor, bold=False, italic=False):
    size = scale_factor * NSFont.systemFontSize()
    if bold:
        weight = 9
    else:
        weight = 5
    if italic:
        traits = NSItalicFontMask
    else:
        traits = 0
    return NSFontManager.sharedFontManager().fontWithFamily_traits_weight_size_('Lucida Grande', traits, weight, size)

class MiroLayoutManager(NSLayoutManager):
    """Overide NSLayoutManager to draw better underlines."""

    def drawUnderlineForGlyphRange_underlineType_baselineOffset_lineFragmentRect_lineFragmentGlyphRange_containerOrigin_(self, glyph_range, type, offset, line_rect, line_glyph_range, container_origin):
        container, _ = self.textContainerForGlyphAtIndex_effectiveRange_(glyph_range.location, None)
        rect = self.boundingRectForGlyphRange_inTextContainer_(glyph_range, container)
        x = container_origin.x + rect.origin.x
        y = (container_origin.y + rect.origin.y + rect.size.height - offset)
        underline_height, offset = self.calc_underline_extents(glyph_range)
        y = math.ceil(y + offset) + underline_height / 2.0
        path = NSBezierPath.bezierPath()
        path.setLineWidth_(underline_height)
        path.moveToPoint_(NSPoint(x, y))
        path.relativeLineToPoint_(NSPoint(rect.size.width, 0))
        path.stroke()

    def calc_underline_extents(self, line_glyph_range):
        index = self.characterIndexForGlyphAtIndex_(line_glyph_range.location)
        font, _ = self.textStorage().attribute_atIndex_effectiveRange_(NSFontAttributeName, index, None)
        # we use a couple of magic numbers that seems to work okay.  I (BDK)
        # got it from some old mozilla code.
        height = font.ascender() - font.descender()
        height = max(1.0, round(0.05 * height))
        offset = max(1.0, round(0.1 * height))
        return height, offset

class NSLayoutManagerPool(object):
    """Handles a pool of NSLayoutManager objects.  We monitor what objects are
    using them and when those objects die, we reclaim the NSLayoutManager for
    the pool.

    NSLayoutManager do a lot of caching, so it's useful to keep them around
    rather than destroying them.
    """
    POOL_SIZE = 5

    def __init__(self):
        self.used_layout_managers = {}
        self.available_layout_managers = []

    def get(self):
        """Get a NSLayoutManager, either from the pool or by creating a new
        one.
        """
        try:
            return self.available_layout_managers.pop()
        except IndexError:
            layout_manager = MiroLayoutManager.alloc().init()
            container = NSTextContainer.alloc().init()
            container.setLineFragmentPadding_(0)
            layout_manager.addTextContainer_(container)
            return layout_manager

    def release(self, layout_manager):
        """Release an NSLayoutManager"""
        self.available_layout_managers.append(layout_manager)

    def monitor_owner(self, owner, layout_manager):
        """Monitor the owner of an NSLayoutManager.  When the owner is garbage
        collected, the NSLayoutManager will go back to the pool.
        """
        ref = weakref.ref(owner, self.owner_dead)
        self.used_layout_managers[ref] = layout_manager

    def owner_dead(self, ref):
        layout_manager = self.used_layout_managers.pop(ref)
        self.release(layout_manager)

    def trim_pool(self):
        """Keep the pool to a reasonable size.
        """
        if len(self.used_layout_managers) > 0:
            # We have a simplistic view here.  We asume that by the time
            # trim_pool() is called, all the owners of NSLayoutManager have
            # been garbage collected.  There's no point in keeping a reference
            # to a TextBox around, so this seems okay for now.
            logging.warn("We're leaking NSLayoutManagers!")
        removing = len(self.available_layout_managers) - self.POOL_SIZE
        self.available_layout_managers = self.available_layout_managers[:self.POOL_SIZE]

nslayout_manager_pool = NSLayoutManagerPool()

class LayoutManager(object):
    def __init__(self):
        self.set_font(1.0)
        self.set_text_color((0, 0, 0))
        self.set_text_shadow(None)

    def font(self, scale_factor, bold=False, italic=False):
        return Font(get_font(scale_factor, bold, italic))

    def set_font(self, scale_factor, bold=False, italic=False):
        self.current_font = self.font(scale_factor, bold, italic)

    def set_text_color(self, color):
        self.text_color = color

    def set_text_shadow(self, shadow):
        self.shadow = shadow

    def textbox(self, text):
        layout_manager = nslayout_manager_pool.get()
        color = NSColor.colorWithDeviceRed_green_blue_alpha_(self.text_color[0], self.text_color[1], self.text_color[2], 1.0)
        textbox = TextBox(layout_manager, text, self.current_font, color, self.shadow)
        nslayout_manager_pool.monitor_owner(textbox, layout_manager)
        return textbox

    def button(self, text, pressed):
        return Button(text, self.current_font, pressed)

    def reset(self):
        nslayout_manager_pool.trim_pool()
        self.set_font(1.0)
        self.set_text_color((0, 0, 0))
        self.set_text_shadow(None)

class TextBox(object):
    def __init__(self, layout_manager, text, font, color, shadow=None):
        self.layout_manager = layout_manager
        self.font = font
        self.color = color
        self.shadow = shadow
        self.text_storage = NSTextStorage.alloc().init()
        self.text_storage.addLayoutManager_(self.layout_manager)
        self.text_container = layout_manager.textContainers()[0]
        self.text_container.setContainerSize_(NSSize(INFINITE, INFINITE))
        self.paragraph_style = NSMutableParagraphStyle.alloc().init()
        self.width = None
        self.text_storage.setFont_(font.nsfont)
        self.set_text(text)

    def make_attr_string(self, text, color, font, underline):
        attributes = { }
        if color is not None:
            nscolor = NSColor.colorWithDeviceRed_green_blue_alpha_(color[0], color[1], color[2], 1.0)
            attributes[NSForegroundColorAttributeName] = nscolor
        else:
            attributes[NSForegroundColorAttributeName] = self.color
        if font is not None:
            attributes[NSFontAttributeName] = font.nsfont
        else:
            attributes[NSFontAttributeName] = self.font.nsfont
        attributes[NSParagraphStyleAttributeName] = self.paragraph_style.copy()
        if underline:
            attributes[NSUnderlineStyleAttributeName] = NSUnderlineStyleSingle
        return NSAttributedString.alloc().initWithString_attributes_(text, attributes)

    def set_text(self, text, color=None, font=None, underline=False):
        string = self.make_attr_string(text, color, font, underline)
        self.text_storage.setAttributedString_(string)

    def append_text(self, text, color=None, font=None, underline=False):
        string = self.make_attr_string(text, color, font, underline)
        self.text_storage.appendAttributedString_(string)

    def set_width(self, width):
        if width is not None:
            self.text_container.setContainerSize_(NSSize(width, INFINITE))
        else:
            self.text_container.setContainerSize_(NSSize(INFINITE, INFINITE))
        self.width = width

    def update_paragraph_style(self):
        attr = NSParagraphStyleAttributeName
        value = self.paragraph_style.copy()
        rnge = NSMakeRange(0, self.text_storage.length())
        self.text_storage.addAttribute_value_range_(attr, value, rnge)

    def set_wrap_style(self, wrap):
        if wrap == 'word':
            self.paragraph_style.setLineBreakMode_(NSLineBreakByWordWrapping)
        elif wrap == 'char':
            self.paragraph_style.setLineBreakMode_(NSLineBreakByCharWrapping)
        else:
            raise ValueError("Unknown wrap value: %s" % wrap)
        self.update_paragraph_style()

    def set_alignment(self, align):
        if align == 'left':
            self.paragraph_style.setAlignment_(NSLeftTextAlignment)
        elif align == 'right':
            self.paragraph_style.setAlignment_(NSRightTextAlignment)
        elif align == 'center':
            self.paragraph_style.setAlignment_(NSCenterTextAlignment)
        else:
            raise ValueError("Unknown align value: %s" % align)
        self.update_paragraph_style()

#    def line_count(self):
#        glyph_count = self.layout_manager.numberOfGlyphs()
#        retval = 0
#        index = 0
#        while index < glyph_count:
#            _, glyph_range =  self.layout_manager.lineFragmentRectForGlyphAtIndex_effectiveRange_(index, None)
#            index = NSMaxRange(glyph_range)
#            retval += 1
#        return retval

#    def get_glyph_range_for_line(self, line):
#        glyph_count = self.layout_manager.numberOfGlyphs()
#        index = 0
#        for i in xrange(line + 1):
#            if index >= glyph_count:
#                raise IndexError("Not enough lines")
#            _, glyph_range = self.layout_manager.lineFragmentRectForGlyphAtIndex_effectiveRange_(index)
#            index = NSMaxRange(glyph_range)
#        return glyph_range

    def get_size(self):
        # The next line is there just to force cocoa to layout the text
        self.layout_manager.glyphRangeForTextContainer_(self.text_container)
        rect = self.layout_manager.usedRectForTextContainer_(self.text_container)
        return rect.size.width, rect.size.height

    def char_at(self, x, y):
        width, height = self.get_size()
        if 0 <= x < width and 0 <= y < height:
            index, _ = self.layout_manager.glyphIndexForPoint_inTextContainer_fractionOfDistanceThroughGlyph_(NSPoint(x, y), self.text_container)
            return index
        else:
            return None

    def draw(self, context, x, y, width, height):
        if self.shadow is not None:
            context.save()
            context.set_shadow(self.shadow.color, self.shadow.opacity, self.shadow.offset, self.shadow.blur_radius)
        self.width = width
        self.text_container.setContainerSize_(NSSize(width, height))
        glyph_range = self.layout_manager.glyphRangeForTextContainer_(self.text_container)
        self.layout_manager.drawGlyphsForGlyphRange_atPoint_(glyph_range, NSPoint(x, y))
        if self.shadow is not None:
            context.restore()
        context.path.removeAllPoints()

class Font(object):
    def __init__(self, nsfont):
        self.nsfont = nsfont

    def ascent(self):
        return self.nsfont.ascender()

    def descent(self):
        return -self.nsfont.descender()

    def line_height(self):
        layout_manager = nslayout_manager_pool.get()
        try:
            return layout_manager.defaultLineHeightForFont_(self.nsfont)
        finally:
            nslayout_manager_pool.release(layout_manager)

class Button(object):
    PAD_WIDTH = 0
    PAD_HEIGHT = 4

    def __init__(self, text, font, pressed):
        self.text = text
        self.font = font
        self.cell = NSButtonCell.alloc().init()
        self.cell.setTitle_(text)
        self.cell.setBezelStyle_(NSRoundRectBezelStyle)
        self.cell.setButtonType_(NSMomentaryPushInButton)
        self.cell.setFont_(font.nsfont)
        self.cell.setHighlighted_(pressed)
        self.min_width = 0

    def text_area(self):
        bounds = NSRect(NSZeroPoint, NSSize(*self.get_size()))
        return NSRectWrapper(self.cell.cellSizeForBounds_(bounds))

    def set_min_width(self, min_width):
        self.min_width = min_width

    def get_size(self):
        size = self.cell.cellSize()
        width = max(self.min_width, size.width + self.PAD_WIDTH)
        return width, size.height + self.PAD_HEIGHT

    def draw(self, context, x, y, width, height):
        rect = NSMakeRect(x, y, width, height)
        self.cell.drawWithFrame_inView_(rect, context.view)
        context.path.removeAllPoints()
