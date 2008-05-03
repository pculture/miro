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

#
# Contains runtime template code

import os
from miro import config
from miro import eventloop
from miro.frontends.html.templatehelper import attrPattern, rawAttrPattern, resourcePattern, generateId
from miro.frontends.html.templateoptimize import HTMLChangeOptimizer
from miro.xhtmltools import urlencode
from itertools import chain
import logging
from miro import util

from miro.plat.frontends.html.threads import inMainThread

# FIXME add support for onlyBody parameter for static templates so we
#       don't need to strip the outer HTML
import re
HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)

if os.environ.has_key('DEMOCRACY_RECOMPILE_TEMPLATES'):
    from miro.frontends.html import template_compiler
    from miro.plat import resources
    template_compiler.setResourcePath(resources.path(''))

###############################################################################
#### Public interface                                                      ####
###############################################################################

# Fill the template in the given file in the template directory using
# the information in the dictionary given by 'data'. If the template
# contains dynamic views, call update methods on the provided
# domHandler function object as necessary in the future, passing a
# string that should be executed in the context of the page to update
# it.  Returns a tuple: a string giving the HTML or XML that resulted
# from filling the template, and a "template handle" whose
# unlinkTemplate() method you should call when you no longer want to
# receive Javascript callbacks.
def fillTemplate(filename, domHandler, platform, eventCookie, bodyTagExtra="", top = True, onlyBody = False, *args, **kargs):
    # FIXME add support for "onlyBody"
    if os.environ.has_key('DEMOCRACY_RECOMPILE_TEMPLATES'):
        (tcc, handle) = template_compiler.compileTemplate(filename)
        exec tcc.getOutput() in locals()
        return fillTemplate(domHandler, platform, eventCookie, bodyTagExtra, *args, **kargs)
    else:
        modname = filename.replace('/','.').replace('\\','.').replace('-','_')
        mod = util.import_last("miro.frontends.html.compiled_templates.%s" % modname)
        return mod.fillTemplate(domHandler, platform, eventCookie, bodyTagExtra, *args, **kargs)

# As fillTemplate, but no Javascript calls are made, and no template
# handle is returned, only the HTML or XML as a string. Effectively,
# you get a static snapshot of the page at the time the call is made.
def fillStaticTemplate(filename, platform='', eventCookie='noCookie', bodyTagExtra="", onlyBody=False, *args, **kargs):
    (tch, handle) = fillTemplate(filename, None, platform, eventCookie, bodyTagExtra, *args, **kargs)
    handle.unlinkTemplate()
    rv = tch.read()
    if onlyBody: # FIXME we should support "onlyBody" in fillTemplate
        rv = HTMLPattern.match(rv).group(1)
    return rv

def queueDOMChange(func, name):
    """Queue function that does a bunch of DOM updates to a display.

    What happens is a little weird, we queue a call in the main gui thread
    loop, then we queue a second call in the backend loop.  If that call does
    any DOM updates like changeItems, addItemBefore, etc., those will almost
    certainly be queued back into the main loop.

    The rational for this is that if the main loop is busy it's better to wait
    for it to be idle if we have a bunch of changes.  That way we can group
    things together and have them happen all at once.  This may seem like it
    adds a bunch of latency, but this doesn't seem to be the case,
    addUrgentCall() happens quickly and if we are waiting on the gui thread,
    that means we're doing some other kind of gui update.
    """

    try:
       inMainThread(lambda:eventloop.addUrgentCall(func, name))
    except:
        eventloop.addIdle(func, name)

def queueSelectDisplay(frame, display, area):
    """Queue a call to MainFrame.selectDisplay using queueDOMChange.  This is
    useful if you want it to happen after template DOM updates (see
    selection.py for an example).
    """
    if area in toSelect:
        # There's already a display queued up. Dispose of it properly
        toSelect[area].unlink()
        
    toSelect[area] = display
    queueDOMChange(lambda: doSelectDisplay(frame, area), "Select display")

toSelect = {}
def doSelectDisplay(frame, area):
    if area in toSelect:
        frame.selectDisplay(toSelect.pop(area), area)
        
###############################################################################
#### template runtime code                                                 ####
###############################################################################

# Class used internally by Handle to track a t:repeatForSet clause.
class TrackedView:
    def __init__(self, anchorId, anchorType, view, templateFunc, parent, name):
        # arguments as Handle.addView(), plus 'parent', a pointer to the Handle
        # that is used to find domHandler and invoke checkHides
        self.anchorId = anchorId
        self.anchorType = anchorType

        self.view = view
        self.templateFunc = templateFunc
        self.parent = parent
        self.htmlChanger = parent.htmlChanger
        self.name = name
        self.toChange = {}
        self.toRemove = []
        self.toAdd = []
        self.addBefore = None
        self.idle_queued = False

    def tid(self, obj):
        return "objid-%s-%d" % (id(self), id(obj))

    #
    # This is called after the HTML has been rendered to fill in the
    # data for each view and register callbacks to keep it updated
    def initialFillIn(self):
        self.view.confirmDBThread()
        self.toChange = {}
        self.toRemove = []
        self.toAdd = []
        self.addBefore = None

        #print "Filling in %d items" % self.view.len()
        #start = time.clock()
        self.addObjects(self.view)
        self.view.addChangeCallback(self.onChange)
        self.view.addAddCallback(self.onAdd)
        self.view.addResortCallback(self.onResort)
        self.view.addRemoveCallback(self.onRemove)
        #print "done (%f)" % (time.clock()-start)

    def onUnlink(self):
        self.view.removeChangeCallback(self.onChange)
        self.view.removeAddCallback(self.onAdd)
        self.view.removeResortCallback(self.onResort)
        self.view.removeRemoveCallback(self.onRemove)

    def initialXML(self, item):
        xml = self.currentXML(item)
        self.htmlChanger.setInitialHTML(self.tid(item), xml)
        return xml

    def currentXML(self, item):
        xml = self.templateFunc(item, self.name, self.view, self.tid(item)).read()
        return xml

    def callback (self):
        if self.parent.domHandler:
            self.addObjects(self.toAdd)
            changes = []
            for id in self.toChange:
                obj = self.toChange[id]
                xml = self.currentXML(obj)
                changes.extend(self.htmlChanger.calcChanges(self.tid(obj), xml))
            if len(changes) > 0:
                self.parent.domHandler.changeItems(changes)

            tids = [self.tid(obj) for obj in self.toRemove]
            if len(tids) > 0:
                self.htmlChanger.removeElements(tids)
                self.parent.domHandler.removeItems(tids)
            
        self.toChange = {}
        self.toRemove = []
        self.toAdd = []
        self.addBefore = None
        self.idle_queued = False

    def addCallback(self):
        if not self.idle_queued:
            queueDOMChange(self.callback, "TrackedView DOM Change (%s)" % self.name)
            self.idle_queued = True

    def onResort (self):
        self.toChange = {}
        self.toRemove = []
        self.toAdd = []
        self.addBefore = None

        if self.anchorType == 'containerDiv':
            emptyXML = '<div id="%s"></div>' % (self.anchorId, )
            self.parent.domHandler.changeItem(self.anchorId, emptyXML, None)
        else:
            removeTids = [self.tid(obj) for obj in self.view]
            if len(removeTids) > 0:
                self.parent.domHandler.removeItems(removeTids)
        self.addObjects(self.view)

    def onChange(self,obj,id):
        if obj in self.toAdd:
            return
        self.toChange[id] = obj
        self.addCallback()

    def onAdd(self, obj, id):
        if len(self.toChange) > 0 or len(self.toRemove) > 0:
            self.callback()
        if self.parent.domHandler:
            next = self.view.getNextID(id) 
            if next is not None:
                nextTid = self.tid (self.view.getObjectByID(next))
            else:
                nextTid = None
            for i in range(len(self.toAdd)):
                if self.tid(self.toAdd[i]) == nextTid:
                    self.toAdd.insert(i, obj)
                    self.addCallback()
                    return
            if len(self.toAdd) > 0 and nextTid == self.addBefore:
                self.toAdd.append(obj)
                self.addCallback()
            else:
                self.callback()
                self.toAdd.append(obj)
                self.addBefore = nextTid
                self.addCallback()

    def addObjects(self, objects):
        """Insert the XML for a list of objects into the DOM tree."""

        if len(objects) == 0:
            # Web Kit treats adding the empty string like adding "&nbsp;", so
            # we don't add the HTML unless it's non-empty
            return
        xmls = [self.initialXML(x) for x in objects]
        # only render with 100 picees at a time, otherwise we can end up
        # trying to allocate huge strings (#8320)
        for xmls_part in util.partition(xmls, 100):
            self.addXML(''.join(xmls_part))

    def addXML(self, xml):
        # Adding it at the end of the list. Must add it relative to
        # the anchor.

        if self.addBefore:
            self.parent.domHandler.addItemBefore(xml, self.addBefore)
        else:
            if self.anchorType in ('parentNode', 'containerDiv'):
                self.parent.domHandler.addItemAtEnd(xml, self.anchorId)
            if self.anchorType == 'nextSibling':
                self.parent.domHandler.addItemBefore(xml, self.anchorId)

    def onRemove (self, obj, id):
        if obj in self.toAdd:
            self.toAdd.remove(obj)
            return
        if len (self.toAdd) > 0:
            self.callback()
        if id in self.toChange:
            del self.toChange[id]
        self.toRemove.append(obj)
        self.addCallback()

# UpdateRegion and ConfigUpdateRegion are used internally by Handle to track
# the t:updateForView and t:updateForConfigChange clauses.

class UpdateRegionBase:
    """Base class for UpdateRegion and ConfigUpdateRegion.  Subclasses must
    define renderXML, which returns a string representing the up-to-date XML
    for this region.  Also, hookupCallbacks() which hooks up any callbacks
    needed.  Subclasses can use onChange() as the handler for any callbacks.
    """

    def __init__(self, anchorId, anchorType, templateFunc, parent):
        # arguments as Handle.addView(), plus 'parent', a pointer to the Handle
        # that is used to find domHandler and invoke checkHides
        self.anchorId = anchorId
        self.anchorType = anchorType

        self.templateFunc = templateFunc
        self.parent = parent
        self.htmlChanger = self.parent.htmlChanger
        self.tid = generateId()
        self.idle_queued = False

    #
    # This is called after the HTML has been rendered to fill in the
    # data for each view and register callbacks to keep it updated
    def initialFillIn(self):
        if self.parent.domHandler:
            self.parent.domHandler.addItemBefore(self.initialXML(), self.anchorId)
        self.hookupCallbacks()

    def initialXML(self):
        xml = self.renderXML()
        self.htmlChanger.setInitialHTML(self.tid, xml)
        return xml

    def onChange(self, *args, **kwargs):
        if not self.idle_queued:
            queueDOMChange(self.doChange, "UpdateRegion DOM Change (%s)" % self.name)
            self.idle_queued = True

    def doChange(self):
        xml = self.renderXML()
        changes = self.parent.htmlChanger.calcChanges(self.tid, xml)
        if changes and self.parent.domHandler:
            self.parent.domHandler.changeItems(changes)
        self.idle_queued = False

class UpdateRegion(UpdateRegionBase):
    def __init__(self, anchorId, anchorType, view, templateFunc, parent, name):
        UpdateRegionBase.__init__(self, anchorId, anchorType, templateFunc, parent)
        self.view = view
        self.name = name

    def renderXML(self):
        return self.templateFunc(self.name, self.view, self.tid).read()

    def hookupCallbacks(self):
        self.view.addChangeCallback(self.onChange)
        self.view.addAddCallback(self.onChange)
        self.view.addRemoveCallback(self.onChange)
        self.view.addResortCallback(self.onChange)
        self.view.addViewChangeCallback(self.onChange)

    def onUnlink(self):
        self.view.removeChangeCallback(self.onChange)
        self.view.removeAddCallback(self.onChange)
        self.view.removeRemoveCallback(self.onChange)
        self.view.removeResortCallback(self.onChange)
        self.view.removeViewChangeCallback(self.onChange)

class ConfigUpdateRegion(UpdateRegionBase):
    def __init__(self, anchorId, anchorType, templateFunc, parent):
        UpdateRegionBase.__init__(self, anchorId, anchorType, templateFunc, parent)
        self.name = "ConfigUpdateRegion"
    def hookupCallbacks(self):
        config.addChangeCallback(self.onChange)

    def onUnlink(self):
        config.removeChangeCallback(self.onChange)

    def renderXML(self):
        return self.templateFunc(self.tid).read()

# Object representing a set of registrations for Javascript callbacks when
# the contents of some set of database views change. One of these Handles
# is returned whenever you fill a template; when you no longer want to
# receive Javascript callbacks for a particular filled template, call
# this object's unlinkTemplate() method.
#
# localVars is a dictionary of variables associated with this template
class Handle:
    def __init__(self, domHandler, templateVars, document = None, onUnlink = lambda : None):        
        # 'domHandler' is an object that will receive method calls when
        # dynamic page updates need to be made. 
        self.domHandler = domHandler
        self.templateVars = templateVars
        self.document = document
        self.trackedHides = {}
        self.trackedViews = []
        self.updateRegions = []
        self.subHandles = []
        self.triggerActionURLsOnLoad = []
        self.triggerActionURLsOnUnload = []
        self.onUnlink = onUnlink
        self.htmlChanger = HTMLChangeOptimizer()
        self.filled = False

    def addTriggerActionURLOnLoad(self,url):
        self.triggerActionURLsOnLoad.append(str(url))

    def addTriggerActionURLOnUnload(self, url):
        self.triggerActionURLsOnUnload.append(str(url))

    def getTriggerActionURLsOnLoad(self):
        return self.triggerActionURLsOnLoad

    def getTriggerActionURLsOnUnload(self):
        return self.triggerActionURLsOnUnload

    def getTemplateVariable(self, name):
        return self.templateVars[name]

    def addUpdateHideOnView(self, id, view, hideFunc, previous):
        checkFunc = lambda *args: self._checkHide(id)
        self.trackedHides[id] = (view, hideFunc, checkFunc, previous)
        if self.filled:
            self.addHideChecks(view, checkFunc)

    def _checkHide(self, id):
        (view, hideFunc, checkFunc, previous) = self.trackedHides[id]
        if hideFunc() != previous:
            self.trackedHides[id] = (view, hideFunc, checkFunc, not previous)
            if previous: # If we were hidden, show
                self.domHandler.showItem(id)
            else:        # If we were showing it, hide it
                self.domHandler.hideItem(id)


    def addView(self, anchorId, anchorType, view, templateFunc, name):
        # Register for JS calls to populate a t:repeatFor. 'view' is the
        # database view to track; 'node' is a DOM node representing the
        # template to fill; 'data' are extra variables to be used in expanding
        # the template. The 'anchor*' arguments tell where in the document
        # to place the expanded template nodes. If 'anchorType' is
        # 'nextSibling', 'anchorId' is the id attribute of the tag immediately
        # following the place the template should be expanded. If it is
        # 'parentNode', the template should be expanded so as to be the final
        # child in the node whose id attribute matches 'anchorId'.
        # 'containerDiv' is like parentNode, except it's contained in an
        # auto-generated <div> element.  This allows for efficient changes
        # when the view is re-sorted.
        #
        # We take a private copy of 'node', so don't worry about modifying
        # it subsequent to calling this method.
        tv = TrackedView(anchorId, anchorType, view, templateFunc, self, name)
        self.trackedViews.append(tv)

    def addUpdate(self, anchorId, anchorType, view, templateFunc, name):
        ur = UpdateRegion(anchorId, anchorType, view, templateFunc, self, name)
        self.updateRegions.append(ur)

    # This forces all "update for view" sections to update
    def forceUpdate(self):
        for ur in self.updateRegions:
            ur.onChange()
        for h in self.subHandles:
            h.forceUpdate()

    def addConfigUpdate(self, anchorId, anchorType, templateFunc):
        ur = ConfigUpdateRegion(anchorId, anchorType, templateFunc, self)
        self.updateRegions.append(ur)

    def unlinkTemplate(self, top = True):
        # Stop delivering callbacks, allowing the handle to be released.
        self.domHandler = None
        try:
            self.document.unlink()
        except:
            pass
        self.document = None
        for o in chain(self.trackedViews, self.updateRegions):
            o.onUnlink()
        self.trackedViews = []
        self.updateRegions = []
        if self.filled:
            for id in self.trackedHides.keys():
                (view, hideFunc, checkFunc, previous) = self.trackedHides[id]
                self.removeHideChecks(view, checkFunc)
        self.trackedHides = {}
        for handle in self.subHandles:
            handle.unlinkTemplate()
        self.subHandles = []
        self.templateVars.clear()
        self.onUnlink()

    def initialFillIn(self):
        for ur in self.updateRegions:
            ur.initialFillIn()
        for tv in self.trackedViews:
            tv.initialFillIn()
        for handle in self.subHandles:
            handle.initialFillIn()
        for id in self.trackedHides.keys():
            (view, hideFunc, checkFunc, previous) = self.trackedHides[id]
            self.addHideChecks(view, checkFunc)
        self.filled = True

    def addHideChecks(self, view, checkFunc):
        logging.debug ("Add hide checks: function %s on view %s", checkFunc, view)
        view.addChangeCallback(checkFunc)
        view.addAddCallback(checkFunc)
        view.addRemoveCallback(checkFunc)
        view.addResortCallback(checkFunc)
        view.addViewChangeCallback(checkFunc)
        checkFunc()

    def removeHideChecks(self, view, checkFunc):
        logging.debug ("Remove hide checks: function %s on view %s", checkFunc, view)
        view.removeChangeCallback(checkFunc)
        view.removeAddCallback(checkFunc)
        view.removeRemoveCallback(checkFunc)
        view.removeResortCallback(checkFunc)
        view.removeViewChangeCallback(checkFunc)

    def addSubHandle(self, handle):
        self.subHandles.append(handle)

# Random utility functions 
def returnFalse(x):
    return False

def returnTrue(x):
    return True

def identityFunc(x):
    return x

def nullSort(x,y):
    return 0

# Returns a quoted, filled version of attribute text
def quoteAndFillAttr(value, localVars):
    util.checkU(value)
    return ''.join(('"', util.quoteattr(fillAttr(value, localVars)),'"'))

# Returns a filled version of attribute text
# Important: because we expand resource: URLs here, instead of defining a
# URL handler (which is hard to do in IE), you must link to stylesheets via
# <link .../> rather than <style> @import ... </style> if they are resource:
# URLs.

# FIXME: we should parse the attribute values ahead of time
def fillAttr(_value, _localVars):
    util.checkU(_value)
    match = attrPattern.match(_value)
    if match:
        result = eval(match.group(2), globals(), _localVars)
        return ''.join((match.group(1), urlencode(result), match.group(3)))
    else:
        match = rawAttrPattern.match(_value)
        if match:
            result = eval(match.group(2), globals(), _localVars)
            return ''.join((match.group(1), result, match.group(3)))
        else:
            match = resourcePattern.match(_value)
            if match:
                return resources.url(match.group(1))
            else:
                return _value
