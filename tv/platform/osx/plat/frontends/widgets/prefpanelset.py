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

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro.frontends.widgets import imagepool

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets.rect import Rect

def get_platform_specific(name):
    pass

class PreferenceItem (NSToolbarItem):

    def setPanel_(self, panel):
        self.panel = panel

class ToolbarDelegate (NSObject):

    def initWithPanels_identifiers_window_(self, panels, identifiers, window):
        self = super(ToolbarDelegate, self).init()
        self.panels = panels
        self.identifiers = identifiers
        self.window = window
        return self

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return self.identifiers

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return self.identifiers

    def toolbarSelectableItemIdentifiers_(self, toolbar):
        return self.identifiers

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(self, toolbar, itemIdentifier, flag):
        panel = self.panels[itemIdentifier]
        item = PreferenceItem.alloc().initWithItemIdentifier_(itemIdentifier)
        item.setLabel_(panel[1])
        item.setImage_(NSImage.imageNamed_(u"pref_item_%s" % itemIdentifier))
        item.setAction_("switchPreferenceView:")
        item.setTarget_(self)
        item.setPanel_(panel[0])
        return item

    def validateToolbarItem_(self, item):
        return YES

    def switchPreferenceView_(self, sender):
        self.window.do_select_panel(sender.panel, YES)

class PreferencesWindow (widgetset.Window):

    def __init__(self, title):
        widgetset.Window.__init__(self, title, Rect(0, 0, 640, 440))
        self.panels = dict()
        self.identifiers = list()
        self.nswindow.setShowsToolbarButton_(NO)

    def get_style_mask(self):
        return NSTitledWindowMask | NSClosableWindowMask | NSMiniaturizableWindowMask
 
    def append_panel(self, name, panel, title, image_name):
        self.panels[name] = (panel, title)
        self.identifiers.append(name)

    def finish_panels(self):
        self.tbdelegate = ToolbarDelegate.alloc().initWithPanels_identifiers_window_(self.panels, self.identifiers, self)
        toolbar = NSToolbar.alloc().initWithIdentifier_(u"Preferences")
        toolbar.setAllowsUserCustomization_(NO)
        toolbar.setDelegate_(self.tbdelegate)

        self.nswindow.setToolbar_(toolbar)
       
    def select_panel(self, panel, all_panels):
        if panel is None:
            panel = self.identifiers[0]
        self.nswindow.toolbar().setSelectedItemIdentifier_(panel)
        self.do_select_panel(self.panels[panel][0], NO)

    def do_select_panel(self, panel, animate):
        wframe = self.nswindow.frame()
        vsize = list(panel.get_size_request())
        if vsize[0] < 500:
            vsize[0] = 500
        if vsize[1] < 200:
            vsize[1] = 200

        toolbarHeight = wframe.size.height - self.nswindow.contentView().frame().size.height
        wframe.origin.y += wframe.size.height - vsize[1] - toolbarHeight
        wframe.size = (vsize[0], vsize[1] + toolbarHeight)

        self.set_content_widget(panel)
        self.nswindow.setFrame_display_animate_(wframe, YES, animate)

    def show(self):
        self.nswindow.center()
        widgetset.Window.show(self)
