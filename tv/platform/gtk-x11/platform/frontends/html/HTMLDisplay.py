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

from miro import app
from miro import config
import gobject
import gtk
import gtkmozembed
from miro import prefs
import tempfile
from xml.sax.saxutils import escape
from miro.platform.MozillaBrowser import MozillaBrowser
from miro.frontends.html.displaybase import Display
from miro.platform.frontends.html.gtk_queue import gtkAsyncMethod
from miro.util import quoteJS, checkU
from miro.platform.utils import confirmMainThread

import os
import re

# These are used by the channel guide. This platform uses the
# old-style 'magic URL' guide API, so we just return None. See
# ChannelGuideToDtvApi in the Trac wiki for the full writeup.
def getDTVAPICookie():
    return None
def getDTVAPIURL():
    return None
        
###############################################################################
#### HTML display                                                          ####
###############################################################################

# Decorator to make using execAfterLoad easier
def deferUntilAfterLoad(func):
    def schedFunc(self, *args, **kwargs):
        self.execAfterLoad(lambda: func(self, *args, **kwargs))
    return schedFunc

_impls = {}

def getImpl (area):
    if not _impls.has_key(area):
        _impls[area] = HTMLDisplayImpl()
    return _impls[area]

count = 0
class HTMLDisplay(Display):
    def __init__(self, html, frameHint=None, areaHint=None, baseURL=None):
        global count
        Display.__init__(self)
        checkU(html)
        self.html = html
        self.count = count
        count = count + 1
        self.impl = None
        self.deferred = []
        self.baseURL = baseURL

    def __getattr__ (self, attr):
        # Since this is for methods calling into HTMLDisplayImpl, we
        # handle the async here.
        @gtkAsyncMethod
        def maybe_defer (*args, **kwargs):
            if self.impl != None:
                if self.impl.display is self:
                    func = getattr (self.impl, attr)
                    func(*args, **kwargs)
                else:
                    pass
            else:
                self.deferred.append((attr, args, kwargs))
        return maybe_defer
        

    def __str__ (self):
        return str (self.count)

    def __repr__ (self):
        return str(self)

    def __nonzero__ (self):
        return True

    def __eq__ (self, other):
        return self is other

    def onSelected(self, frame):
        confirmMainThread()
        Display.onSelected(self, frame)
        self.impl.load_html (self)
        for deferment in self.deferred:
            (attr, args, kwargs) = deferment
            func = getattr (self.impl, attr)
            func(*args, **kwargs)
        self.deferred = []

    def getWidget(self, area = None):
        confirmMainThread()
        self.impl = getImpl (area)
        return self.impl.widget

    def getEventCookie(self):
        return ''

    def getDTVPlatformName(self):
        return 'gtk-x11-MozillaBrowser'

    def getBodyTagExtra(self):
        return ''

    def onURLLoad (self, url):
        # For overriding
        return True

class HTMLDisplayImpl:
    "Selectable Display that shows a HTML document."

    def __init__(self):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""

        confirmMainThread()

        self.initialLoadFinished = False
        self.execQueue = []
        self.widgetDestroyed = False

        self.mb = MozillaBrowser()
        self.display = None
        self.widget = self.mb.getWidget()
        self.widget.connect("net-stop", self.loadFinished)
        self.widget.connect("destroy", self.onBrowserDestroy)
        self.widget.connect("unrealize", self.onUnrealize)
        self.mb.setURICallBack(self.onURLLoad)
        self.mb.setContextMenuCallBack(self.onContextMenu)
        self.widget.show()
        self.in_load_html = False
        self.location = None

    def load_html(self, display):

        confirmMainThread()

        self.in_load_html = True
        self.initialLoadFinished = False
        self.execQueue = []
        self.display = display

        if (display.baseURL == app.controller.guideURL and
                display.baseURL is not None):
            self.removeFile = False
            self.location = os.path.join(config.get(prefs.SUPPORT_DIRECTORY),
                    'democracy-channel-guide.html')
            handle = open(self.location, 'w')
        else:
            self.removeFile = True
            (handle, self.location) = tempfile.mkstemp('.html')
            handle = os.fdopen(handle,"w")
        handle.write(display.html.encode('utf-8'))
        handle.close()

        # Translate path into URL.
        parts = re.split(r'/', self.location)
        self.urlToLoad = "file://" + '/'.join(parts)
        self.widget.load_url(self.urlToLoad)
        self.in_load_html = False

    @deferUntilAfterLoad
    def navigateToFragment(self, fragment):
        url = '%s#%s' % (self.urlToLoad, fragment)
        self.widget.load_url(url)

    def loadFinished(self, widget):
        confirmMainThread()

        if self.in_load_html:
            return
        if (not self.initialLoadFinished):
            try:
                # Execute any function calls we queued because the page load
                # hadn't completed
                for func in self.execQueue:
                    func()
                self.execQueue = []
            finally:
                self.initialLoadFinished = True
            if self.removeFile:
                try:
                    os.remove (self.location)
                except:
                    pass

            try:
                self.onInitialLoadFinished()
            except:
                pass

    # Call func() once the document has finished loading. If the
    # document has already finished loading, call it right away. But
    # in either case, the call is executed on the main thread, by
    # queueing an event, since WebViews are not documented to be
    # thread-safe, and we have seen crashes.
    def execAfterLoad(self, func):
        if not self.initialLoadFinished:
            self.execQueue.append(func)
        else:
            func()

# These functions are now only called from maybe_defer,
# onSelected_private, and loadFinished, so we don't have to worry
# about gtkAsyncMethod anymore.

    @deferUntilAfterLoad
    def execJS(self, js):
        self.widget.load_url('javascript:%s' % js)

    # DOM hooks used by the dynamic template code
    @deferUntilAfterLoad
    def addItemAtEnd(self, xml, id):
        if not self.widgetDestroyed:
            self.mb.addItemAtEnd(xml, id)

    @deferUntilAfterLoad
    def addItemBefore(self, xml, id):
        if not self.widgetDestroyed:
            self.mb.addItemBefore(xml, id)
    
    @deferUntilAfterLoad
    def removeItem(self, id):
        if not self.widgetDestroyed:
            self.mb.removeItem(id)
    
    @deferUntilAfterLoad
    def removeItems(self, ids):
        if not self.widgetDestroyed:
            for id in ids:
                try:
                    self.mb.removeItem(id)
                except:
                    pass

    @deferUntilAfterLoad
    def changeItem(self, id, xml, changeHint):
        if not self.widgetDestroyed:
            self._doChangeItem(id, xml, changeHint)

    def _doChangeItem(self, id, xml, changeHint):
        if changeHint is None or changeHint.changedInnerHTML is not None:
            self.mb.changeItem(id, xml)
        elif changeHint.changedAttributes:
            for name, value in changeHint.changedAttributes.items():
                if value is not None:
                    self.mb.changeAttribute(id, name, value)
                else:
                    self.mb.removeAttribute(id, name)

    @deferUntilAfterLoad
    def changeItems(self, listOfArgs):
        if not self.widgetDestroyed:
            for args in listOfArgs:
                self._doChangeItem(*args)

    @deferUntilAfterLoad
    def hideItem(self, id):
        if not self.widgetDestroyed:
            self.mb.hideItem(id)
        
    @deferUntilAfterLoad
    def showItem(self, id):
        if not self.widgetDestroyed:
            self.mb.showItem(id)

    def onURLLoad(self, url):
        """Called when this HTML browser attempts to load a URL (either
        through user action or Javascript.) The URL is provided as a
        string. Return true to allow the URL to load, or false to cancel
        the load (for example, because it was a magic URL that marks
        an item to be downloaded.) Implementation in HTMLDisplay always
        returns true; override in a subclass to implement special
        behavior."""
        retval = self.display.onURLLoad(url)
        return retval

    def onBrowserDestroy(self, widget):
        confirmMainThread()
        self.widgetDestroyed = True

    def onUnrealize (self, widget):
        confirmMainThread()
        for (key, value) in _impls.items():
            if value is self:
                del _impls[key]

    def onDocumentLoadFinished(self):
        pass

    @gtkAsyncMethod
    def onContextMenuItem(self, menuItem, url):
        self.widget.load_url(url)

    @gtkAsyncMethod
    def onContextMenu(self, menu):
        # onContextMenu handles the context menu callback from MozillaBrowser.
        # Menu is a string, where each line is either
        # "URL|description" or a blank lines for separators. 
        # On menu item click, we should load URL into this HTML area.
        popupMenu = gtk.Menu()
        for item in menu.split("\n"):
            if item == "":
                item = gtk.SeparatorMenuItem()
            else:
                url, description = item.split("|")
                item = gtk.MenuItem(description)
                item.connect("activate", self.onContextMenuItem, url)
            popupMenu.append(item)
            item.show()
        popupMenu.popup(None, None, None, 2, gtk.get_current_event_time())

    def unlink(self):
        pass

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
