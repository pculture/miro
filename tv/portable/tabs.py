import database
import app
import template
import views
import feed
import resource

from xml.dom.minidom import parse

###############################################################################
#### Tabs                                                                  ####
###############################################################################


# Database object representing a static (non-feed-associated) tab.
class StaticTab(database.DDBObject):
    def __init__(self, tabTemplateBase, contentsTemplate, order):
        self.tabTemplateBase = tabTemplateBase
        self.contentsTemplate = contentsTemplate
        self.order = order
        database.DDBObject.__init__(self)

class Tab:
    idCounter = 0

    def __init__(self, tabTemplateBase, contentsTemplate, sortKey, obj):
        self.tabTemplateBase = tabTemplateBase
        self.contentsTemplate = contentsTemplate
        self.sortKey = sortKey
        self.display = None
        self.id = "tab%d" % Tab.idCounter
        Tab.idCounter += 1
        self.obj = obj

    def start(self, frame, templateNameHint):
        app.controller.setTabListActive(True)
        self.display = app.TemplateDisplay(templateNameHint or self.contentsTemplate, frameHint=frame, areaHint=frame.mainDisplay)
        frame.selectDisplay(self.display, frame.mainDisplay)

    def markup(self):
        """Get HTML giving the visual appearance of the tab. 'state' is
        one of 'selected' (tab is currently selected), 'normal' (tab is
        not selected), or 'selected-inactive' (tab is selected but
        setTabListActive was called with a false value on the MainFrame
        for which the tab is being rendered.) The HTML should be returned
        as a xml.dom.minidom element or document fragment."""
        state = app.controller.getTabState(self.id)
        file = "%s-%s" % (self.tabTemplateBase, state)
        return template.fillStaticTemplate(file)

    # Returns "normal" "selected" or "selected-inactive"
    def getState(self):
        return  app.controller.getTabState(self.id)

    def redraw(self):
        # Force a redraw by sending a change notification on the underlying
        # DB object.
        self.obj.beginChange()
        self.obj.endChange()

    def isFeed(self):
        """True if this Tab represents a Feed."""
        return isinstance(self.obj, feed.Feed)

    def feedURL(self):
        """If this Tab represents a Feed, the feed's URL. Otherwise None."""
        if self.isFeed():
            return self.obj.getURL()
        else:
            return None

    def feedID(self):
        """If this Tab represents a Feed, the feed's ID. Otherwise None."""
        if self.isFeed():
            return self.obj.getID()
        else:
            return None

    def onDeselected(self, frame):
        self.display.onDeselect(frame)

# Remove all static tabs from the database
def removeStaticTabs():
    app.db.beginUpdate()
    try:
        for obj in views.staticTabs:
            obj.remove()
    finally:
        app.db.endUpdate()

# Reload the StaticTabs in the database from the statictabs.xml resource file.
def reloadStaticTabs():
    app.db.beginUpdate()
    try:
        # Wipe all of the StaticTabs currently in the database.
        removeStaticTabs()

        # Load them anew from the resource file.
        # NEEDS: maybe better error reporting?
        document = parse(resource.path('statictabs.xml'))
        for n in document.getElementsByTagName('statictab'):
            tabTemplateBase = n.getAttribute('tabtemplatebase')
            contentsTemplate = n.getAttribute('contentstemplate')
            order = int(n.getAttribute('order'))
            StaticTab(tabTemplateBase, contentsTemplate, order)
    finally:
        app.db.endUpdate()
