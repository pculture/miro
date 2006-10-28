import re
from xml.sax.expatreader import ExpatParser
from xml.sax.handler import ContentHandler

hotspotMarkerPattern = re.compile("<!-- HOT SPOT ([^ ]*) -->")

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
            return [(self.id, self.html, attrDiff, newInnerHTML)]
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
    optimizes 2 cases:

      * If only the attributes of dom element change, then we only changes
        those attributes instead of updating the entire region (assuming the
        platform code supports this).
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
        old = self.elements[id]
        new = OptimizedElement(id, html)
        self.elements[id] = new
        return new.calcChanges(old)
