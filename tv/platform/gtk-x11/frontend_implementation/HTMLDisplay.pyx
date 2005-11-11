import frontend
import app
import gtkmozembed
import tempfile
from xml.sax.saxutils import escape
from frontend_implementation.HTMLDisplayHelper import deferUntilAfterLoad

import os
import re
import threading
import time

cdef extern from "HTMLDisplay.h":
    ctypedef struct GtkMozEmbed
    ctypedef struct GObject 
    ctypedef struct PyGObject:
        GObject * obj
    ctypedef int gint
    ctypedef unsigned long gulong
    ctypedef char gchar
    ctypedef void * gpointer
    ctypedef void * GCallback
    cdef gulong g_signal_connect( gpointer *object, gchar *name, GCallback func, gpointer func_data )

def quoteJS(x):
    x = re.compile("\\\\").sub("\\\\", x)  #       \ -> \\
    x = re.compile("\"").  sub("\\\"", x)  #       " -> \"
    x = re.compile("'").   sub("\\'", x)   #       ' -> \'
    x = re.compile("\n").  sub("\\\\n", x) # newline -> \n
    x = re.compile("\r").  sub("\\\\r", x) #      CR -> \r
    return x

cdef class MozillaBrowser:
    cdef GtkMozEmbed *cWidget
    cdef object widget, URICallBack, finishedCallBack
    
    def __new__(self):
        self.widget = gtkmozembed.MozEmbed()
        self.cWidget = self.pygtkmozembed_to_c(self.widget)

    def __init__(self):
        self.URICallBack = None
        self.finishedCallBack = None
        g_signal_connect(<gpointer *>self.cWidget, "open_uri", <void *>open_uri_cb, <gpointer>self)
        g_signal_connect(<gpointer *>self.cWidget, "net_stop", <void *>load_finished_cb, <gpointer>self)

    def getWidget(self):
        return self.widget

    def setURICallBack(self, callback):
        self.URICallBack = callback

    def getURICallBack(self):
        return self.URICallBack

    def setFinishedCallBack(self, callback):
        self.finishedCallBack = callback

    def getFinishedCallBack(self):
        return self.finishedCallBack
        
    cdef GtkMozEmbed *pygtkmozembed_to_c(MozillaBrowser self, object pygtkmoz):
        cdef PyGObject *tempObj
        cdef GObject *temp
        tempObj = <PyGObject *>pygtkmoz
        temp = tempObj.obj
        return <GtkMozEmbed *>temp
cdef gint open_uri_cb (GtkMozEmbed *embed, char *uri, object self):
    URICallBack = self.getURICallBack()
    if URICallBack is None:
        return 0
    else:
        if URICallBack(uri):
            return 0
        else:
            return 1
cdef void load_finished_cb (GtkMozEmbed *embed, object self):
    finishedCallBack = self.getFinishedCallBack()
    if finishedCallBack is None:
        return
    else:
        finishedCallBack()
        
###############################################################################
#### HTML display                                                          ####
###############################################################################

class HTMLDisplay(app.Display):
    "Selectable Display that shows a HTML document."

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        app.Display.__init__(self)

        self.initialLoadFinished = False
        self.execQueue = []

        (handle, location) = tempfile.mkstemp('.html')
        handle = os.fdopen(handle,"w")
        handle.write(html)
        handle.close()
        self.deleteOnLoadFinished = location
        # For debugging generated HTML, you could uncomment the next
        # two lines.
        #print "Logged HTML to %s" % location
        #self.deleteOnLoadFinished = None

        # Translate path into URL.
        parts = re.split(r'/', location)
        url = "file:///" + '/'.join(parts)

        userAgent = "DTV/pre-release (http://participatoryculture.org/)"

        #self.widget.connect('open_uri',self.onOpenURI)
        self.mb = MozillaBrowser()
        self.mb.setURICallBack(self.onURLLoad)
        self.mb.setFinishedCallBack(self.loadFinished)
        self.widget = self.mb.getWidget()
        self.widget.load_url(url)
        self.widget.show()

    def getWidget(self):
        return self.widget

    def loadFinished(self):
        if (not self.initialLoadFinished):
            # Execute any function calls we queued because the page load
            # hadn't completed
            # NEEDS: there should be a lock here, preventing execAfterLoad
            # from dropping something in the queue just after we have finished
            # processing it
            for func in self.execQueue:
                func()
            self.execQueue = []
            self.initialLoadFinished = True

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

    def onSelected(self, *args):
        # Give focus whenever the display is installed. Probably the best
        # of several not especially attractive options.
        app.Display.onSelected(self, *args)

    def execJS(self, js):
        self.widget.load_url('javascript:%s' % js)
    execJS = deferUntilAfterLoad(execJS)

    # DOM hooks used by the dynamic template code
    def addItemAtEnd(self, xml, id):
        print "Adding at end (%s)" % id
        self.widget.load_url("javascript:addItemAtEnd(\"%s\",\"%s\")" %
                             (quoteJS(xml),
                              quoteJS(id)))
    addItemAtEnd = deferUntilAfterLoad(addItemAtEnd)

    def addItemBefore(self, xml, id):
        print "Adding item before %s" % id
        self.widget.load_url("javascript:addItemBefore(\"%s\",\"%s\")" %
                             (quoteJS(xml),
                              quoteJS(id)))
    addItemBefore = deferUntilAfterLoad(addItemBefore)
    
    def removeItem(self, id):
        print "Removing %s" % id
        self.widget.load_url("javascript:removeItem(\"%s\")" %
                             (quoteJS(id),))
    removeItem = deferUntilAfterLoad(removeItem)
    
    def changeItem(self, id, xml):
        print "changing %s" % id
        self.widget.load_url("javascript:changeItem(\"%s\",\"%s\")" %
                             (quoteJS(id),
                              quoteJS(xml)))
    changeItem = deferUntilAfterLoad(changeItem)
        
    def hideItem(self, id):
        print "hiding %s" % id
        self.widget.load_url("javascript:hideItem(\"%s\")" %
                             (quoteJS(id),))
    hideItem = deferUntilAfterLoad(hideItem)
        
    def showItem(self, id):
        print "showing %s" % id
        self.widget.load_url("javascript:showItem(\"%s\")" %
                             (quoteJS(id),))
    showItem = deferUntilAfterLoad(showItem)
    
    def onURLLoad(self, url):
        """Called when this HTML browser attempts to load a URL (either
        through user action or Javascript.) The URL is provided as a
        string. Return true to allow the URL to load, or false to cancel
        the load (for example, because it was a magic URL that marks
        an item to be downloaded.) Implementation in HTMLDisplay always
        returns true; override in a subclass to implement special
        behavior."""
        # For overriding
        return True

    def onDocumentLoadFinished(self):
        pass
        
    def unlink(self):
        pass

    def __del__(self):
        self.unlink()

    # NEEDS: right-click menu.
    # Protocol: if type(getContextClickMenu) == "function", call it and
    # pass the DOM node that was clicked on. That returns "URL|description"
    # with blank lines for separators. On a click, force navigation of that
    # frame to that URL, maybe by setting document.location.href.

###############################################################################
###############################################################################
