import database
import app
import template
import views
import feed
import resource
import guide
import playlist

from xml.dom.minidom import parse
from gtcache import gettext as _

###############################################################################
#### Tabs                                                                  ####
###############################################################################


# Database object representing a static (non-feed-associated) tab.
class StaticTab(database.DDBObject):
    tabTitles = {
        'librarytab': _('My Collection'),
        'newtab': _('New Videos'),
        'searchtab': _('Search'),
        'downloadtab': _('Active Downloads'),
    }

    tabIcons = {
        'librarytab': 'collection-icon-tablist.png',
        'newtab': 'newvideos-icon-tablist.png',
        'searchtab': 'search-icon-tablist.png',
        'downloadtab': 'download-icon-tab.png',
    }

    def __init__(self, tabTemplateBase, contentsTemplate, order):
        self.tabTemplateBase = tabTemplateBase
        self.contentsTemplate = contentsTemplate
        self.order = order
        database.DDBObject.__init__(self)

    def getTitle(self):
        return self.tabTitles[self.tabTemplateBase]

    def getIconURL(self):
        return resource.url("images/%s" % self.tabIcons[self.tabTemplateBase])

    def getNumberColor(self):
        if self.tabTemplateBase == 'downloadtab':
            return 'orange'
        elif self.tabTemplateBase == 'newtab':
            return 'green'
        else:
            return None

    def getNumber(self):
        if self.tabTemplateBase == 'downloadtab':
            return views.downloadingItems.len()
        elif self.tabTemplateBase == 'newtab':
            return views.newlyDownloadedItems.len()
        else:
            return 0

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

    # Returns "normal" "selected" or "selected-inactive"
    def getState(self):
        return  app.controller.getTabState(self.id)

    def redraw(self):
        # Force a redraw by sending a change notification on the underlying
        # DB object.
        self.obj.signalChange()

    def isFeed(self):
        """True if this Tab represents a Feed."""
        return isinstance(self.obj, feed.Feed)

    def isGuide(self):
        """True if this Tab represents a Feed."""
        return isinstance(self.obj, guide.ChannelGuide)

    def isPlaylist(self):
        """True if this Tab represents a Playlist."""
        return isinstance(self.obj, playlist.SavedPlaylist)

    def feedURL(self):
        """If this Tab represents a Feed or a Guide, the URL. Otherwise None."""
        if self.isFeed() or self.isGuide():
            return self.obj.getURL()
        else:
            return None

    def objID(self):
        """If this Tab represents a Feed, the feed's ID. Otherwise None."""
        if isinstance (self.obj, database.DDBObject):
            return self.obj.getID()
        else:
            return None

    def onDeselected(self, frame):
        self.display.onDeselect(frame)

# Remove all static tabs from the database
def removeStaticTabs():
    app.db.confirmDBThread()
    for obj in views.staticTabsObjects:
        obj.remove()

# Reload the StaticTabs in the database from the statictabs.xml resource file.
def reloadStaticTabs():
    app.db.confirmDBThread()
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
