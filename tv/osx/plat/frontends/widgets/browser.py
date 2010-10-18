# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""miro.plat.frontends.widgets.browser -- Web Browser widget. """

import os
import logging

from AppKit import *
from Foundation import *
from WebKit import *
from objc import YES, NO, nil
from PyObjCTools import AppHelper

from miro import app
from miro import prefs
from miro.plat.frontends.widgets.base import Widget

class Browser(Widget):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        Widget.__init__(self)
        self.url = None
        self.create_signal('net-start')
        self.create_signal('net-stop')
        self.delegate = BrowserDelegate.alloc().initWithBrowser_(self)
        self.view = MiroWebView.alloc().initWithFrame_(NSRect((0,0), self.calc_size_request()))
        self.view.setMaintainsBackForwardList_(YES)
        self.view.setApplicationNameForUserAgent_("%s/%s (%s)" % \
                                      (app.config.get(prefs.SHORT_APP_NAME),
                                       app.config.get(prefs.APP_VERSION),
                                       app.config.get(prefs.PROJECT_URL),))

    def _set_webkit_delegates(self, delegate):
        self.view.setPolicyDelegate_(delegate)
        self.view.setResourceLoadDelegate_(delegate)
        self.view.setFrameLoadDelegate_(delegate)
        self.view.setUIDelegate_(delegate)


    def viewport_created(self):
        Widget.viewport_created(self)
        self._set_webkit_delegates(self.delegate)

    def remove_viewport(self):
        self._hack_remove_viewport()
        self._set_webkit_delegates(nil)

    def _hack_remove_viewport(self):
        # This was stolen from Widget.remove_viewport() and modified just move
        # the viewport to a hidden spot.
        # This works, but it's pretty ugly.  Let's fix for 4.0
        if self.viewport is not None:
            offscreen_rect = NSRect((-5000, -5000), self.view.frame().size)
            self.viewport.reposition(offscreen_rect)
            # When we re-show the view, miro will just position it back to the
            # correct place.  Therefore, don't remove from wrappermap because
            # miro won't call wrappermap.add() back
            #if self.CREATES_VIEW:
                #wrappermap.remove(self.view)

    def viewport_repositioned(self):
        # gets called when we need to re-show our view after
        # _hack_remove_viewport()
        self._set_webkit_delegates(self.delegate)

    def calc_size_request(self):
        return (200, 100) # Seems like a reasonable minimum size

    def navigate(self, url):
        self.url = url
        request = NSURLRequest.requestWithURL_(NSURL.URLWithString_(url))
        self.view.mainFrame().loadRequest_(request)

    def get_current_url(self):
        return self.view.mainFrameURL()

    def get_current_title(self):
        return self.view.mainFrameTitle()

    def forward(self):
        self.view.goForward()

    def back(self):
        self.view.goBack()

    def reload(self):
        self.view.reload_(nil)

    def stop(self):
        self.view.stopLoading_(nil)

    def can_go_back(self):
        return self.view.canGoBack()

    def can_go_forward(self):
        return self.view.canGoForward()

###############################################################################

class MiroWebView (WebView):
    def performDragOperation_(self, sender):
        return NO
        
###############################################################################

class BrowserDelegate (NSObject):

    def initWithBrowser_(self, browser):
        self = super(BrowserDelegate, self).init()
        self.browser = browser
        self.openPanelContextID = 1
        self.openPanelContext = dict()
        return self

    def webView_didStartProvisionalLoadForFrame_(self, webview, frame):
        self.browser.emit('net-start')

    def webView_didFinishLoadForFrame_(self, webview, frame):
        self.browser.emit('net-stop')

    def webView_decidePolicyForMIMEType_request_frame_decisionListener_(self, webview, mtype, request, frame, listener):
        url = unicode(request.URL())
        if self.browser.should_load_url(url, mtype):
            listener.use()
        else:
            listener.ignore()        

    # Intercept external links requests
    def webView_decidePolicyForNewWindowAction_request_newFrameName_decisionListener_(self, webView, info, request, name, listener):
        url = info["WebActionOriginalURLKey"]
        NSWorkspace.sharedWorkspace().openURL_(url)
        listener.ignore()

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
            allowed = [app.config.get(prefs.CHANNEL_GUIDE_URL), 
                       app.config.get(prefs.CHANNEL_GUIDE_FIRST_TIME_URL)]
            if url.absoluteString() in allowed:
                # The [NSURLRequest setAllowsAnyHTTPSCertificate:forHost:] selector is
                # not documented anywhere, so I assume it is not public. It is however 
                # a very clean and easy way to allow us to load our channel guide from
                # https, so let's use it here anyway :)
                NSURLRequest.setAllowsAnyHTTPSCertificate_forHost_(YES, url.host())
                # Now reload
                frame.loadRequest_(request)

    def webView_createWebViewWithRequest_(self, webView, request):
        global jsOpened
        webView = WebView.alloc().init()
        webView.setFrameLoadDelegate_(jsOpened)
        webView.mainFrame().loadRequest_(request)
        return webView

    def webView_resource_willSendRequest_redirectResponse_fromDataSource_(self, webview, resourceCookie, request, redirectResponse, dataSource):
        url = request.URL().absoluteString()
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
            webview.window(),
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

    def webView_addMessageToConsole_(self, webview, message):
        logging.jsalert(message)

    def webView_runJavaScriptAlertPanelWithMessage_(self, webview, message):
        logging.jsalert(message)

###############################################################################

class JSOpened (NSObject):
    
    def webView_willPerformClientRedirectToURL_delay_fireDate_forFrame_(self, webView, url, delay, fireDate, frame):
        webView.stopLoading_(nil)
        NSWorkspace.sharedWorkspace().openURL_(url)

jsOpened = JSOpened.alloc().init()
