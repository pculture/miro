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

"""frontends.html.display.  Display classes."""

import cgi
import logging
import os
import re

from clock import clock
from frontends.html import actionhandlers
from frontends.html.displaybase import Display
import download_utils
import eventloop
import frontend
import frontends.html
import signals
import subscription
import template
import util
import views

class TemplateDisplay(frontend.HTMLDisplay):
    """TemplateDisplay: a HTML-template-driven right-hand display panel. """

    def __init__(self, templateName, templateState, frameHint=None, areaHint=None, 
            baseURL=None, *args, **kargs):
        """'templateName' is the name of the inital template file.  'data' is
        keys for the template. 'templateState' is a string with the state of the
        template.
        """

        logging.debug ("Processing %s", templateName)
        self.templateName = templateName
        self.templateState = templateState
        (tch, self.templateHandle) = template.fillTemplate(templateName,
                self, self.getDTVPlatformName(), self.getEventCookie(),
                self.getBodyTagExtra(), templateState = templateState,
                                                           *args, **kargs)
        self.args = args
        self.kargs = kargs
        self.haveLoaded = False
        html = tch.read()

        self.actionHandlers = [
            actionhandlers.ModelActionHandler(frontends.html.app.delegate),
            actionhandlers.HistoryActionHandler(self),
            actionhandlers.GUIActionHandler(),
            actionhandlers.TemplateActionHandler(self, self.templateHandle),
            ]

        loadTriggers = self.templateHandle.getTriggerActionURLsOnLoad()
        newPage = self.runActionURLs(loadTriggers)

        if newPage:
            self.templateHandle.unlinkTemplate()
            # FIXME - url is undefined here!
            self.__init__(re.compile(r"^template:(.*)$").match(url).group(1), frameHint, areaHint, baseURL)
        else:
            frontend.HTMLDisplay.__init__(self, html, frameHint=frameHint, areaHint=areaHint, baseURL=baseURL)

            self.templateHandle.initialFillIn()

    def __eq__(self, other):
        return (other.__class__ == TemplateDisplay and 
                self.templateName == other.templateName and 
                self.args == other.args and 
                self.kargs == other.kargs)

    def __str__(self):
        return "Template <%s> args=%s kargs=%s" % (self.templateName, self.args, self.kargs)

    def reInit(self, *args, **kargs):
        self.args = args
        self.kargs = kargs
        try:
            self.templateHandle.templateVars['reInit'](*args, **kargs)
        except:
            pass
        self.templateHandle.forceUpdate()
        
    def runActionURLs(self, triggers):
        newPage = False
        for url in triggers:
            if url.startswith('action:'):
                self.onURLLoad(url)
            elif url.startswith('template:'):
                newPage = True
                break
        return newPage

    def parseEventURL(self, url):
        match = re.match(r"[a-zA-Z]+:([^?]+)(\?(.*))?$", url)
        if match:
            path = match.group(1)
            argString = match.group(3)
            if argString is None:
                argString = u''
            argString = argString.encode('utf8')
            # argString is turned into a str since parse_qs will fail on utf8 that has been url encoded.
            argLists = cgi.parse_qs(argString, keep_blank_values=True)

            # argLists is a dictionary from parameter names to a list
            # of values given for that parameter. Take just one value
            # for each parameter, raising an error if more than one
            # was given.
            args = {}
            for key in argLists.keys():
                value = argLists[key]
                if len(value) != 1:
                    import template_compiler
                    raise template_compiler.TemplateError, "Multiple values of '%s' argument passed to '%s' action" % (key, url)
                # Cast the value results back to unicode
                try:
                    args[key.encode('ascii','replace')] = value[0].decode('utf8')
                except:
                    args[key.encode('ascii','replace')] = value[0].decode('ascii', 'replace')
            return path, args
        else:
            raise ValueError("Badly formed eventURL: %s" % url)


    def onURLLoad(self, url):
        print "URL LOAD %r %r" % (url, frontends.html.app.guide)
        if self.checkURL(url):
            if not frontends.html.app.guide: # not on a channel guide:
                return True
            # The first time the guide is loaded in the template, several
            # pages are loaded, so this shouldn't be called during that
            # first load.  After that, this shows the spinning circle to
            # indicate loading
            if not self.haveLoaded and (url ==
                    frontends.html.app.guide.getLastVisitedURL()):
                self.haveLoaded = True
            elif self.haveLoaded:
                script = 'top.miro_navigation_frame.guideUnloaded()'
                if not url.endswith(script):
                    self.execJS('top.miro_navigation_frame.guideUnloaded()')
            return True
        else:
            return False

    # Returns true if the browser should handle the URL.
    def checkURL(self, url):
        util.checkU(url)
        logging.info ("got %s", url)
        try:
            # Special-case non-'action:'-format URL
            if url.startswith (u"template:"):
                name, args = self.parseEventURL(url)
                self.dispatchAction('switchTemplate', name=name, **args)
                return False

            # Standard 'action:' URL
            if url.startswith (u"action:"):
                action, args = self.parseEventURL(url)
                self.dispatchAction(action, **args)
                return False

            # Let channel guide URLs pass through
            if frontends.html.app.guide is not None and \
                   frontends.html.app.guide.isPartOfGuide(url):
                frontends.html.app.setLastVisitedGuideURL(url)
                return True
            if url.startswith(u'file://'):
                path = download_utils.getFileURLPath(url)
                return os.path.exists(path)

            # If we get here, this isn't a DTV URL. We should open it
            # in an external browser.
            if (url.startswith(u'http://') or url.startswith(u'https://') or
                url.startswith(u'ftp://') or url.startswith(u'mailto:') or
                url.startswith(u'feed://')):
                self.handleCandidateExternalURL(url)
                return False

        except:
            signals.system.failedExn("while handling a request", 
                    details="Handling action URL '%s'" % (url, ))

        return True

    @eventloop.asUrgent
    def handleCandidateExternalURL(self, url):
        """Open a URL that onURLLoad thinks is an external URL.
        handleCandidateExternalURL does extra checks that onURLLoad can't do
        because it's happens in the gui thread and can't access the DB.
        """

        # check for subscribe.getdemocracy.com links
        type, subscribeURLs = subscription.findSubscribeLinks(url)

        # check if the url that came from a guide, but the user switched tabs
        # before it went through.
        if len(subscribeURLs) == 0:
            for guideObj in views.guides:
                if guideObj.isPartOfGuide(url):
                    return

        normalizedURLs = []
        for url in subscribeURLs:
            normalized = feed.normalizeFeedURL(url)
            if feed.validateFeedURL(normalized):
                normalizedURLs.append(normalized)
        if normalizedURLs:
            if type == 'feed':
                for url in normalizedURLs:
                    if feed.getFeedByURL(url) is None:
                        newFeed = feed.Feed(url)
                        newFeed.blink()
            elif type == 'download':
                for url in normalizedURLs:
                    filename = platformutils.unicodeToFilename(url)
                    singleclick.downloadURL(filename)
            elif type == 'guide':
                for url in normalizedURLs:
                    if guide.getGuideByURL (url) is None:
                        guide.ChannelGuide(url)
            else:
                raise AssertionError("Unkown subscribe type")
            return

        if url.startswith(u'feed://'):
            url = u"http://" + url[len(u"feed://"):]
            f = feed.getFeedByURL(url)
            if f is None:
                f = feed.Feed(url)
            f.blink()
            return

        frontends.html.app.delegate.openExternalURL(url)

    @eventloop.asUrgent
    def dispatchAction(self, action, **kwargs):
        called = False
        start = clock()
        for handler in self.actionHandlers:
            if hasattr(handler, action):
                getattr(handler, action)(**kwargs)
                called = True
                break
        end = clock()
        if end - start > 0.5:
            logging.timing ("dispatch action %s too slow (%.3f secs)", action, end - start)
        if not called:
            logging.warning ("Ignored bad action URL: action=%s", action)

    @eventloop.asUrgent
    def onDeselected(self, frame):
        unloadTriggers = self.templateHandle.getTriggerActionURLsOnUnload()
        self.runActionURLs(unloadTriggers)
        self.unlink()
        frontend.HTMLDisplay.onDeselected(self, frame)

    def unlink(self):
        self.templateHandle.unlinkTemplate()
        self.actionHandlers = []
