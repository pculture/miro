# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import re
import logging

from xml.sax.expatreader import ExpatParser
from xml.sax.handler import ContentHandler

hotspotMarkerPattern = re.compile("<!-- HOT SPOT ([^ ]*) -->")

class ChangeItemHint:
    """Contains hints the frontend can use to optimize
    HTMLDisplay.changeItem().  Member attributes:


    changedInnerHTML -- The inner HTML of the element being changed.  If
        nothing changed inside the element this will be None.
    changedAttributes -- A dict containing the changes to the DOM element
        attributes.  Each attribute that changed will have an entry.  The key
        is the attribute name.  If the attribute was removed, the value will
        be None.
    """

    def __init__(self, changedAttributes, changedInnerHTML):
        self.changedAttributes = changedAttributes
        self.changedInnerHTML = changedInnerHTML

class SingleElementHandler(ContentHandler):
    """XML Content handler that just reads in the first elements tagname and
    attributes.
    """
    def __init__(self):
        self.started = False
        ContentHandler.__init__(self)
    def startElement(self, name, attrs):
        self.name = name
        self.attrs = attrs
        self.started = True
    def reset(self):
        self.started = False

class BrokenUpElement:
    """Breaks up an HTML element into it's outermost tag and inner html.
    
    Attributes:
      html -- original HTML
      name -- outermost tag name
      attrs -- outermost tag attributes
      innerHTML -- data inside the outermost tag.

    """

    parser = ExpatParser()
    handler = SingleElementHandler()
    parser.setContentHandler(handler)

    def __init__(self, id, html):
        self.id = id
        self.html = html
        innerHTMLStart = self.feedInFirstElement(html)
        innerHTMLEnd = html.rfind("</")
        self.innerHTML = html[innerHTMLStart:innerHTMLEnd]
        self.name = self.handler.name
        self.attrs = self.handler.attrs
        self.handler.reset()
        self.parser.reset()

    def feedInFirstElement(self, html):
        pos = 0
        while not self.handler.started:
            end_candidate = html.find(">", pos)
            if end_candidate < 0:
                raise ValueError("Can't find start tag in %s" % html)
            self.parser.feed(html[pos:end_candidate+1])
            pos = end_candidate+1
        return pos

    def calcChanges(self, older):
        """Calculate the changes between self and an older version of this
        element.  Return a list of changes to pass to HTMLArea.changeItems.
        """

        attrDiff = self.calcAttributeChanges(older.attrs, self.attrs)
        newInnerHTML = self.calcNewInnerHTML(older.innerHTML, self.innerHTML)
        if attrDiff or newInnerHTML:
            hint = ChangeItemHint(attrDiff, newInnerHTML)
            return [(self.id, self.html, hint)]
        else:
            return []

    def calcNewInnerHTML(self, oldInnerHTML, newInnerHTML):
        """Calculate the newInnerHTML argument to pass to HTMLArea.changeItem.
        """
        if oldInnerHTML != newInnerHTML:
            return newInnerHTML
        else:
            return None

    def calcAttributeChanges(self, oldAttrs, newAttrs):
        """Calculate the difference between two attribute dicts.  Returns a dict
        with entries for each key that has changed.  Keys that have been removed
        will have None values.
        """

        changes = dict(newAttrs)
        for key, value in oldAttrs.items():
            try:
                if changes[key] == value:
                    del changes[key] # attribute stayed the same
            except KeyError:
                changes[key] = None # attribute was removed
        return changes

class OptimizedElement:
    """Used by HTMLChangeOptimizer to calculate how an html element changed."""

    def __init__(self, id, html):
        self.brokenUp = BrokenUpElement(id, html)
        self.calcHotSpots()

    def calcHotSpots(self):
        self.hotspots = {}
        split = hotspotMarkerPattern.split(self.brokenUp.html)
        self.outerParts = [split[0]]
        i = 1
        while i < len(split):
            hotspotID, hotspotHTML, end, outerPart = split[i:i+4]
            self.hotspots[hotspotID] = BrokenUpElement(hotspotID, hotspotHTML)
            self.outerParts.append(hotspotID)
            self.outerParts.append(outerPart)
            i += 4

    def calcChanges(self, older):
        if len(self.outerParts) == 1 or self.outerParts != older.outerParts:
            return self.brokenUp.calcChanges(older.brokenUp)
        else:
            changes = []
            for id in self.hotspots:
                new = self.hotspots[id].calcChanges(older.hotspots[id])
                changes.extend(new)
            return changes

class HTMLChangeOptimizer:
    """Class that handles changing xml in an efficient way.  It currently
    optimizes a few cases:

      * If the html stays the same, we don't send anything to the frontend
        code.
      * We calculate a ChangeItemHint for each element that changes.  Smart
        frontends can use this to optimize the changeItem() call, especially
        when only the change is repeated element's attributes.
      * Child elements can be marked "hotspots" meaning they are more likely 
        change than other parts.  We only update the hotspot elements when we
        detect that other html hasn't changed.

    We mark a region as a hotspot by adding specially formatted comments like
    so:

    <!-- HOT SPOT hotspot-dom-id --><div id="hotspot-dom-id">
       blah blah blah
    </div><!-- HOT SPOT END -->
    """

    def __init__(self):
        self.elements = {}

    def setInitialHTML(self, id, html):
        """Set the initial HTML for a dom element.  This must be called before
        calcChanges() is called with id
        """
        self.elements[id] = OptimizedElement(id, html)

    def calcChanges(self, id, html):
        """Calculate a list of arguments to pass to HTMLArea.changeItems()."""
        try:
            old = self.elements[id]
        except KeyError:
            # this case shouldn't happen in the wild, but it was reported in
            # #8689.  Don't try to optimize anything.
            logging.warn("KeyError for element %s in "
                    "HTMLChangeOptimizer.calcChanges()", id)
            return [ (id, html, None) ]
        new = OptimizedElement(id, html)
        self.elements[id] = new
        return new.calcChanges(old)

    def removeElements(self, ids):
        for id in ids:
            if id in self.elements:
                del self.elements[id]
            else:
                logging.warn("Trying to remove an unknown element.")
