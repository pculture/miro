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

import os
import re
import urllib
import logging

from objc import YES, NO, nil
from AppKit import *
from WebKit import *
from Foundation import *
from PyObjCTools import AppHelper

from miro import config
from miro import prefs
from miro import templatehelper
from miro.frontends.html import keyboard
from miro.frontends.html.displaybase import Display
from miro.platform import resources
from miro.platform.frontends.html.MainFrame import mapKey, handleKey
from miro.platform.frontends.html import threads

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

class HTMLDisplay (Display):
    "HTML browser that can be shown in a MainFrame's right-hand pane."

    # We don't need to override onSelected, onDeselected

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None, baseURL=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        self.readyToDisplayHook = None
        self.readyToDisplay = False
        self.html = html
        self.baseURL = baseURL
        if frameHint and areaHint:
            self.displaySizeHint = frameHint.getDisplaySizeHint(areaHint)
        else:
            self.displaySizeHint = None
        Display.__init__(self)
 
    # make web a lazily loaded property.  This is useful for the channel
    # guides because it makes the load happen after setGuideURL
    def get_web(self):
        try:
            return self._web
        except AttributeError:
            self._web = ManagedWebView.alloc().initWithInitialHTML_existinView_loadFinished_loadURL_sizeHint_baseURL_(
                            self.html, None, self.nowReadyToDisplay, lambda x:self.onURLLoad(unicode(x)), self.displaySizeHint, self.baseURL)
            return self._web
    web = property(get_web)

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
        try:
            self.web.execJS(js)
        except AttributeError:
            print "Couldn't exec javascript! Web view not initialized"
        #print "DISP: %s with %s" % (self.view, js)

    def navigateToFragment(self, fragment):
        self.web.navigateToFragment(fragment)

    # DOM hooks used by the dynamic template code -- do they need a 
    # try..except wrapper like the above?
    def addItemAtEnd(self, xml, id):
        return self.web.addItemAtEnd(xml, id)

    def addItemBefore(self, xml, id):
        return self.web.addItemBefore(xml, id)

    def removeItem(self, id):
        return self.web.removeItem(id)

    def removeItems(self, ids):
        return self.web.removeItems(ids)

    def changeItem(self, id, xml, changeHint):
        return self.web.changeItem(id, xml, changeHint)

    def changeItems(self, args):
        newArgs = []
        for id, xml, changeHint in args:
            newArgs.append((id, xml, changeHint))
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
        self.get_web() # make sure our ManagedWebView is loaded
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
            threads.warnIfNotOnMainThread('HTMLDisplay.unlink')
            webView.setHostWindow_(self.currentFrame.obj.window()) # not very pretty
    
    @threads.onMainThreadWaitingUntilDone
    def cancel(self):
        logging.debug("DTV: Canceling load of WebView %s" % self.web.getView())
        self.web.getView().stopLoading_(nil)
        self.readyToDisplay = False
        self.readyToDisplayHook = None

###############################################################################

class ManagedWebHTMLView (WebHTMLView):

    def keyDown_(self, event):
        key = mapKey(event)
        if key in (keyboard.UP, keyboard.DOWN):
            handleKey(event)
        else:
            super(ManagedWebHTMLView, self).keyDown_(event)

    def rightMouseDown_(self, event):
        # We want a right click to also select what's underneath so we intercept
        # the event here, force the left click handler first and reschedule the
        # right click handler.
        threads.callOnMainThread(self.mouseDown_, event)
        threads.callOnMainThreadAfterDelay(0.2, WebHTMLView.rightMouseDown_, self, event)

###############################################################################

class ManagedWebView (NSObject):

    WebView.registerViewClass_representationClass_forMIMEType_(ManagedWebHTMLView, WebHTMLRepresentation, u'text/html')

    def initWithInitialHTML_existinView_loadFinished_loadURL_sizeHint_baseURL_(
        self, initialHTML, existingView=nil, onInitialLoadFinished=None, onLoadURL=None, sizeHint=None, baseURL=None):
        self.onInitialLoadFinished = onInitialLoadFinished
        self.onLoadURL = onLoadURL
        self.initialLoadFinished = False
        self.view = existingView
        self.openPanelContextID = 1
        self.openPanelContext = dict()
        threads.callOnMainThreadAndWaitUntilDone(self.initWebView, initialHTML, sizeHint, baseURL)        
        return self

    def initWebView(self, initialHTML, sizeHint, baseURL):
        threads.warnIfNotOnMainThread('ManagedWebView.initWebView')
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
            self.view.setCustomUserAgent_(u"%s/%s (%s)" % \
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
            baseURL = NSURL.URLWithString_(unicode(baseURL))

        self.view.mainFrame().loadData_MIMEType_textEncodingName_baseURL_(data, u'text/html', u'utf-8', baseURL)        

    def isKeyExcludedFromWebScript_(self,key):
        return YES

    def isSelectorExcludedFromWebScript_(self, sel):
        return (str(sel) != 'eventURL')

    def eventURL(self,url):
        self.onLoadURL(url)

    def webView_contextMenuItemsForElement_defaultMenuItems_(self,webView,contextMenu,defaultMenuItems):
        event = NSApp().currentEvent()
        if event.type() == NSLeftMouseDown and (event.modifierFlags() & NSControlKeyMask):
            fake = NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
                           NSRightMouseDown, event.locationInWindow(), 0, 0, event.windowNumber(), nil, 0, 1, 0)
            NSApp().postEvent_atStart_(fake, YES)
        return nil

    # Generate callbacks when the initial HTML (passed in the constructor)
    # has been loaded
    def webView_didFinishLoadForFrame_(self, webview, frame):
        if (not self.initialLoadFinished) and (frame is self.view.mainFrame()):
            threads.warnIfNotOnMainThread('ManagedWebView.webView_didFinishLoadForFrame_')
            # Execute any function calls we queued because the page load
            # hadn't completed
            self.initialLoadFinished = True
            for func in self.execQueue:
                func()
            self.execQueue = []

            if self.onInitialLoadFinished:
                self.onInitialLoadFinished()

            scriptObj = self.view.windowScriptObject()
            scriptObj.setValue_forKey_(self, u'frontend')

    def webView_didFailProvisionalLoadWithError_forFrame_(self, webview, error, frame):
        urlError = (error.domain() == NSURLErrorDomain)
        certError = (error.code() in (NSURLErrorServerCertificateHasBadDate, 
                                      NSURLErrorServerCertificateHasUnknownRoot, 
                                      NSURLErrorServerCertificateUntrusted))

        if urlError and certError:
            request = frame.provisionalDataSource().request()
            if request is nil:
                request = frame.dataSource().request()
            url = request.URL()            
            allowed = [config.get(prefs.CHANNEL_GUIDE_URL), 
                       config.get(prefs.CHANNEL_GUIDE_FIRST_TIME_URL)]
            if url.absoluteString() in allowed:
                # The [NSURLRequest setAllowsAnyHTTPSCertificate:forHost:] selector is
                # not documented anywhere, so I assume it is not public. It is however 
                # a very clean and easy way to allow us to load our channel guide from
                # https, so let's use it here anyway :)
                NSURLRequest.setAllowsAnyHTTPSCertificate_forHost_(YES, url.host())
                # Now reload
                frame.loadRequest_(request)

    # Intercept navigation actions and give program a chance to respond
    def webView_decidePolicyForNavigationAction_request_frame_decisionListener_(self, webview, action, request, frame, listener):
        threads.warnIfNotOnMainThread('ManagedWebView.webView_decidePolicyForNavigationAction_request_frame_decisionListener_')
        method = request.HTTPMethod()
        url = unicode(request.URL())
        body = request.HTTPBody()
        ntype = action['WebActionNavigationTypeKey']
        #print "policy %d for url %s" % (ntype, url)
        # setting document.location.href in Javascript (our preferred
        # method of triggering an action) comes out as an
        # WebNavigationTypeOther.
        if ntype in (WebNavigationTypeLinkClicked, WebNavigationTypeFormSubmitted, WebNavigationTypeOther):
            # Make sure we have a real, bona fide Python string, not an
            # NSString. Unfortunately, == can tell the difference.
            if (not self.onLoadURL) or self.onLoadURL(url):
                listener.use()
            else:
                listener.ignore()
        else:
            listener.use()

    # Intercept external links requests
    def webView_decidePolicyForNewWindowAction_request_newFrameName_decisionListener_(self, webView, info, request, name, listener):
        url = info["WebActionOriginalURLKey"]
        NSWorkspace.sharedWorkspace().openURL_(url)
        listener.ignore()

    # Redirect resource: links to files in resource bundle
    def webView_resource_willSendRequest_redirectResponse_fromDataSource_(self, webview, resourceCookie, request, redirectResponse, dataSource):
        threads.warnIfNotOnMainThread('ManagedWebView.webView_resource_willSendRequest_redirectResponse_fromDataSource_')
        url = request.URL().absoluteString()

        match = templatehelper.resourcePattern.match(url)
        if match is not None:
            url = resources.url(match.group(1))
            urlObject = NSURL.URLWithString_(url)
            return NSURLRequest.requestWithURL_cachePolicy_timeoutInterval_(urlObject, NSURLRequestReloadIgnoringCacheData, 60)

        if isinstance(request, NSMutableURLRequest):
            language = os.environ['LANGUAGE'].split(':')[0].replace('_', '-')
            request.setValue_forHTTPHeaderField_(language, u'Accept-Language')
            request.setValue_forHTTPHeaderField_(u'1', u'X-Miro')
        
        return request

    def webView_runOpenPanelForFileButtonWithResultListener_(self, webview, listener):
        self.openPanelContextID += 1
        self.openPanelContext[self.openPanelContextID] = listener
        panel = NSOpenPanel.openPanel()
        panel.beginSheetForDirectory_file_types_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            NSHomeDirectory(),
            nil,
            nil,
            self.view.window(),
            self,
            'openPanelDidEnd:returnCode:contextInfo:',
            self.openPanelContextID)

    @AppHelper.endSheetMethod
    def openPanelDidEnd_returnCode_contextInfo_(self, panel, result, contextID):
        listener = self.openPanelContext[contextID]
        del self.openPanelContext[contextID]
        if result == NSOKButton:
            filenames = panel.filenames()
            listener.chooseFilename_(filenames[0])

    def webView_runJavaScriptAlertPanelWithMessage_(self, webview, message):
        logging.jsalert(message)

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
            threads.callOnMainThreadAndWaitUntilDone(func)

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

    def navigateToFragment(self, fragment):
        command = "var tab = document.getElementById(\"%s\"); tab.scrollIntoView(true);" % fragment
        self.execJS(command)

    ## DOM mutators called, ultimately, by dynamic template system ##

    def findElt(self, id):
        doc = self.view.mainFrame().DOMDocument()
        elt = doc.getElementById_(unicode(id))
        return elt

    def createElts(self, xml):
        parent = self.view.mainFrame().DOMDocument().createElement_(u"div")
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
    def changeItem(self, id, xml, changeHint):
        self._changeElement(id, xml, changeHint)

    @deferUntilAfterLoad
    def changeItems(self, args):
        for id, xml, changeHint in args:
            self._changeElement(id, xml, changeHint)

    def _changeElement(self, id, xml, changeHint):
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
