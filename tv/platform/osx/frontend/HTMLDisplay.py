import re

from objc import YES, NO, nil
from AppKit import *
from WebKit import *
from Foundation import *

import app
import prefs
import config
import resources
import platformutils

###############################################################################
# These are used by the channel guide. This platform uses the
# old-style 'magic URL' guide API, so we just return None. See
# ChannelGuideToDtvApi in the Trac wiki for the full writeup.
###############################################################################

def getDTVAPICookie():
    return None

def getDTVAPIURL():
    return None

###############################################################################

class HTMLDisplay (app.Display):
    "HTML browser that can be shown in a MainFrame's right-hand pane."

#    sharedWebView = None

    # We don't need to override onSelected, onDeselected

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None, baseURL=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        self.readyToDisplayHook = None
        self.readyToDisplay = False

        # The template system currently generates UTF-8. For now, we
        # just convert that back to unicode as necessary. See #3708
        html = html.decode('utf-8')

        self.web = ManagedWebView.alloc().init(html, None, self.nowReadyToDisplay, lambda x:self.onURLLoad(x), frameHint and areaHint and frameHint.getDisplaySizeHint(areaHint) or None, baseURL)
        app.Display.__init__(self)

    def getEventCookie(self):
        return ''
    def getDTVPlatformName(self):
        return 'webkit'
    def getBodyTagExtra(self):
        return 'ondragstart="handleDragStart(event);" ondragover="return handleDragOver(event);" ondragleave="return handleDragLeave(event);" ondrop="return handleDrop(event);" '

    def getView(self):
        return self.web.getView()

    def execJS(self, js):
        """Execute the given Javascript code (provided as a string) in the
        context of this HTML document."""
        js = js.decode('utf-8')
        try:
            self.web.execJS(js)
        except AttributeError:
            print "Couldn't exec javascript! Web view not initialized"
        #print "DISP: %s with %s" % (self.view, js)

    # DOM hooks used by the dynamic template code -- do they need a 
    # try..except wrapper like the above?
    def addItemAtEnd(self, xml, id):
        xml = xml.decode('utf-8')
        return self.web.addItemAtEnd(xml, id)

    def addItemBefore(self, xml, id):
        xml = xml.decode('utf-8')
        return self.web.addItemBefore(xml, id)

    def removeItem(self, id):
        return self.web.removeItem(id)

    def removeItems(self, ids):
        return self.web.removeItems(ids)

    def changeItem(self, id, xml, changedAttrs, newInnerHTML):
        xml = xml.decode('utf-8')
        return self.web.changeItem(id, xml, changedAttrs, newInnerHTML)

    def changeItems(self, args):
        newArgs = []
        for id, xml, changedAttrs, newInnerHTML in args:
            newArgs.append((id, xml.decode('utf-8'), changedAttrs, newInnerHTML))
        return self.web.changeItems(newArgs)

    def hideItem(self, id):
        return self.web.hideItem(id)

    def showItem(self, id):
        return self.web.showItem(id)

    def onURLLoad(self, url):
        """Called when this HTML browser attempts to load a URL (either
        through user action or Javascript.) The URL is provided as a
        string. Return true to allow the URL to load, or false to cancel
        the load (for example, because it was a magic URL that marks
        an item to be downloaded.) Implementation in HTMLDisplay always
        returns true; override in a subclass to implement special
        behavior."""
        # For overriding
        pass

    def callWhenReadyToDisplay(self, hook):
        if self.readyToDisplay:
            hook()
        else:
            assert self.readyToDisplayHook == None
            self.readyToDisplayHook = hook

    # Called (via callback established in constructor)
    def nowReadyToDisplay(self):
        self.readyToDisplay = True
        if self.readyToDisplayHook:
            hook = self.readyToDisplayHook
            self.readyToDisplayHook = None
            hook()

    def unlink(self):
        webView = self.web.getView()
        if webView is not nil:
            platformutils.warnIfNotOnMainThread('HTMLDisplay.unlink')
            webView.setHostWindow_(self.currentFrame.obj.window()) # not very pretty
    
    @platformutils.onMainThreadWaitingUntilDone
    def cancel(self):
        print "DTV: Canceling load of WebView %s" % self.web.getView()
        self.web.getView().stopLoading_(nil)
        self.readyToDisplay = False
        self.readyToDisplayHook = None
                        

###############################################################################

class ManagedWebHTMLView (WebHTMLView):

    def rightMouseDown_(self, event):
        # We want a right click to also select what's underneath so we intercept
        # the event here, force the left click handler first and reschedule the
        # right click handler.
        platformutils.callOnMainThread(self.mouseDown_, event)
        platformutils.callOnMainThreadAfterDelay(0.2, WebHTMLView.rightMouseDown_, self, event)

###############################################################################

class ManagedWebView (NSObject):

    WebView.registerViewClass_representationClass_forMIMEType_(ManagedWebHTMLView, WebHTMLRepresentation, 'text/html')

    def init(self, initialHTML, existingView=nil, onInitialLoadFinished=None, onLoadURL=None, sizeHint=None, baseURL=None):
        self.onInitialLoadFinished = onInitialLoadFinished
        self.onLoadURL = onLoadURL
        self.initialLoadFinished = False
        self.view = existingView
        platformutils.callOnMainThreadAndWaitUntilDone(self.initWebView, initialHTML, sizeHint, baseURL)        
        return self

    def initWebView(self, initialHTML, sizeHint, baseURL):
        platformutils.warnIfNotOnMainThread('ManagedWebView.initWebView')
        if not self.view:
            self.view = WebView.alloc().init()
            #print "***** Creating new WebView %s" % self.view
            if sizeHint:
                # We have an estimate of the size that will be assigned to
                # the view when it is actually inserted in the MainFrame.
                # Use this to size the view we just created so the HTML
                # is hopefully rendered to the correct dimensions, instead
                # of having to be corrected after being displayed.
                self.view.setFrame_(sizeHint)
            self.view.setCustomUserAgent_("%s/%s (%s)" % \
                                          (config.get(prefs.SHORT_APP_NAME),
                                           config.get(prefs.APP_VERSION),
                                           config.get(prefs.PROJECT_URL),))
        else:
            #print "***** Using existing WebView %s" % self.view
            if sizeHint:
                self.view.setFrame_(sizeHint)
        self.execQueue = []
        self.view.setPolicyDelegate_(self)
        self.view.setResourceLoadDelegate_(self)
        self.view.setFrameLoadDelegate_(self)
        self.view.setUIDelegate_(self)

        html = NSString.stringWithString_(unicode(initialHTML))
        data = html.dataUsingEncoding_(NSUTF8StringEncoding)
        if baseURL is not None:
            baseURL = NSURL.URLWithString_(baseURL)

        self.view.mainFrame().loadData_MIMEType_textEncodingName_baseURL_(data, 'text/html', 'utf-8', baseURL)        

    def isKeyExcludedFromWebScript_(self,key):
        return YES

    def isSelectorExcludedFromWebScript_(self,sel):
        if (str(sel) == 'eventURL'):
            return NO
        else:
            return YES

    def eventURL(self,url):
        self.onLoadURL(str(url))

    def webView_contextMenuItemsForElement_defaultMenuItems_(self,webView,contextMenu,defaultMenuItems):
        return nil

    # Generate callbacks when the initial HTML (passed in the constructor)
    # has been loaded
    def webView_didFinishLoadForFrame_(self, webview, frame):
        if (not self.initialLoadFinished) and (frame is self.view.mainFrame()):
            platformutils.warnIfNotOnMainThread('ManagedWebView.webView_didFinishLoadForFrame_')
            # Execute any function calls we queued because the page load
            # hadn't completed
            self.initialLoadFinished = True
            for func in self.execQueue:
                func()
            self.execQueue = []

            if self.onInitialLoadFinished:
                self.onInitialLoadFinished()

            scriptObj = self.view.windowScriptObject()
            scriptObj.setValue_forKey_(self,'frontend')

    # Intercept navigation actions and give program a chance to respond
    def webView_decidePolicyForNavigationAction_request_frame_decisionListener_(self, webview, action, request, frame, listener):
        platformutils.warnIfNotOnMainThread('ManagedWebView.webView_decidePolicyForNavigationAction_request_frame_decisionListener_')
        method = request.HTTPMethod()
        url = request.URL()
        body = request.HTTPBody()
        type = action['WebActionNavigationTypeKey']
        #print "policy %d for url %s" % (type, url)
        # setting document.location.href in Javascript (our preferred
        # method of triggering an action) comes out as an
        # WebNavigationTypeOther.
        if type == WebNavigationTypeLinkClicked or type == WebNavigationTypeFormSubmitted or type == WebNavigationTypeOther:
            # Make sure we have a real, bona fide Python string, not an
            # NSString. Unfortunately, == can tell the difference.
            if (not self.onLoadURL) or self.onLoadURL('%s' % url):
                listener.use()
            else:
                listener.ignore()
        else:
            listener.use()

    # Redirect resource: links to files in resource bundle
    def webView_resource_willSendRequest_redirectResponse_fromDataSource_(self, webview, resourceCookie, request, redirectResponse, dataSource):
        platformutils.warnIfNotOnMainThread('ManagedWebView.webView_resource_willSendRequest_redirectResponse_fromDataSource_')
        url = "%s" % request.URL() # Make sure it's a Python string
        match = re.compile("resource:(.*)$").match(url)
        if match:
            path = resources.path(match.group(1))
            urlObject = NSURL.fileURLWithPath_(path)
            return NSURLRequest.requestWithURL_(urlObject)
        return request

    # Return the actual WebView that we're managing
    def getView(self):
        return self.view

    # Call func() once the document has finished loading. If the
    # document has already finished loading, call it right away. But
    # in either case, the call is executed on the main thread, by
    # queueing an event, since WebViews are not documented to be
    # thread-safe, and we have seen crashes.
    def execAfterLoad(self, func):
        if not self.initialLoadFinished:
            self.execQueue.append(func)
        else:
            platformutils.callOnMainThreadAndWaitUntilDone(func)

    # Decorator to make using execAfterLoad easier
    def deferUntilAfterLoad(func):
        def runFunc(*args, **kwargs):
            func(*args, **kwargs)
        def schedFunc(self, *args, **kwargs):
            rf = lambda: runFunc(self, *args, **kwargs)
            self.execAfterLoad(rf)
        return schedFunc

    # Execute given Javascript string in context of the HTML document
    @deferUntilAfterLoad
    def execJS(self, js):
        self.view.stringByEvaluatingJavaScriptFromString_(js)

    ## DOM mutators called, ultimately, by dynamic template system ##

    def findElt(self, id):
        doc = self.view.mainFrame().DOMDocument()
        elt = doc.getElementById_(id)
        return elt

    def createElts(self, xml):
        parent = self.view.mainFrame().DOMDocument().createElement_("div")
        if len(xml) == 0:
            parent.setInnerHTML_("&nbsp;")
        else:
            parent.setInnerHTML_(xml)
        eltlist = []
        for child in range(parent.childNodes().length()):
            eltlist.append(parent.childNodes().item_(child))
        return eltlist
        
    @deferUntilAfterLoad
    def addItemAtEnd(self, xml, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: addItemAtEnd: missing element %s" % id
        else:
            #print "add item %s at end of %s" % (elt.getAttribute_("id"), id)
            #print xml[0:79]
            newElts = self.createElts(xml)
            for newElt in newElts:
                elt.insertBefore__(newElt, None)

    @deferUntilAfterLoad
    def addItemBefore(self, xml, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: addItemBefore: missing element %s" % id
        else:
            newElts = self.createElts(xml)
            for newElt in newElts:
                #print "add item %s before %s" % (newelt.getAttribute_("id"), id)
                elt.parentNode().insertBefore__(newElt, elt)

    @deferUntilAfterLoad
    def removeItem(self, id):
        self._removeElement(id)

    @deferUntilAfterLoad
    def removeItems(self, ids):
        for id in ids:
            self._removeElement(id)

    def _removeElement(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: removeItem: missing element %s" % id
        else:
            #print "remove item %s" % id
            elt.parentNode().removeChild_(elt)

    @deferUntilAfterLoad
    def changeItem(self, id, xml, changedAttrs, newInnerHTML):
        self._changeElement(id, xml, changedAttrs, newInnerHTML)

    @deferUntilAfterLoad
    def changeItems(self, args):
        for id, xml, changedAttrs, newInnerHTML in args:
            self._changeElement(id, xml, changedAttrs, newInnerHTML)

    def _changeElement(self, id, xml, changedAttrs, newInnerHTML):
        elt = self.findElt(id)
        if not elt:
            print "warning: changeItem: missing element %s" % id
        else:
            #print "change item %s (new id %s)" % (id, elt.getAttribute_("id"))
            #print xml[0:79]
            #if id != elt.getAttribute_("id"):
            #    raise Exception
            #elt = self.findElt(id)
            #if not elt:
            #    print "ERROR ELEMENT LOST %s" % id
            elt.setOuterHTML_(xml)

    @deferUntilAfterLoad
    def hideItem(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: hideItem: missing element %s" % id
        else:
            #print "hide item %s (new style '%s')" % (id, elt.getAttribute_("style"))
            elt.setAttribute__("style", "display:none")

    @deferUntilAfterLoad
    def showItem(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: showItem: missing element %s" % id
        else:
            #print "show item %s (new style '%s')" % (id, elt.getAttribute_("style"))
            elt.setAttribute__("style", "")

###############################################################################
