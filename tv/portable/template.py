# template.py Copyright (c) 2005, 2006 Participatory Culture Foundation
#
# Contains runtime template code

import os
import eventloop
from templatehelper import quoteattr, escape, toUni, attrPattern, rawAttrPattern, resourcePattern, generateId
from xhtmltools import urlencode

if os.environ.has_key('DEMOCRACY_RECOMPILE_TEMPLATES'):
    import template_compiler
    import resource
    template_compiler.setResourcePath(resource.path(''))


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
def fillTemplate(filename, domHandler, platform, eventCookie, top = True, onlyBody = False):
    if os.environ.has_key('DEMOCRACY_RECOMPILE_TEMPLATES'):
        (tcc, handle) = template_compiler.compileTemplate(filename)
        exec tcc.getOutput() in locals()
        return fillTemplate(domHandler, platform, eventCookie)
    else:
        filename = filename.replace('/','.').replace('\\','.').replace('-','_')
        components = filename.split('.')
        mod = __import__("compiled_templates.%s"%filename)
        for comp in components:
            mod = getattr(mod,comp)
        return mod.fillTemplate(domHandler, platform, eventCookie)

# As fillTemplate, but no Javascript calls are made, and no template
# handle is returned, only the HTML or XML as a string. Effectively,
# you get a static snapshot of the page at the time the call is made.
def fillStaticTemplate(filename, platform, eventCookie):
    # This could be somewhat more efficient
    (tch, handle) = fillTemplate(filename, None, platform, eventCookie)
    handle.unlinkTemplate()
    return tch.getOutput()

class TemplateError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return self.message

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

        self.origView = view
        self.view = view.map(IDAssignmentInView(id(self)).mapper)
        self.templateFunc = templateFunc
        self.parent = parent
        self.name = name
        self.toAdd = []
        self.toAddSet = set()
        self.toChange = {}
        self.toRemove = {}
        self.idle_queued = False

    #
    # This is called after the HTML has been rendered to fill in the
    # data for each view and register callbacks to keep it updated
    def initialFillIn(self):
        self.view.confirmDBThread()
        #print "Filling in %d items" % self.view.len()
        #start = time.clock()
        xmls = []
        for x in self.view:
            xmls.append(self.currentXML(x))
        self.addHTMLAtEnd(''.join(xmls))
        self.view.addChangeCallback(self.onChange)
        self.view.addAddCallback(self.onAdd)
        self.view.addRemoveCallback(self.onRemove)
        #print "done (%f)" % (time.clock()-start)


    def currentXML(self, item):
        output = []
        output.append(self.templateFunc(item.object, self.name, item.tid).read())
        try:
#             print "-----"
#             print str(''.join(output))
#             print "-----"
            return ''.join(output)
        except UnicodeDecodeError:
            ret = ''
            for string in output:
                try:
                    ret = ret + string
                except:
                    pass
            return ret

    def callback (self):
        for id, obj in self.toAdd:
            self.doAdd(obj, id)
        for id in self.toChange:
            self.doChange(self.toChange[id], id)
        for id in self.toRemove:
            self.doRemove(self.toRemove[id], id)
        self.toAdd = []
        self.toAddSet = set()
        self.toChange = {}
        self.toRemove = {}
        self.idle_queued = False

    def addCallback(self):
        if not self.idle_queued:
            import frontend
            try:
                frontend.inMainThread(lambda:eventloop.addIdle(self.callback, "Update UI"))
            except:
                eventloop.addIdle(self.callback, "Update UI")
            self.idle_queued = True

    def onChange(self,obj,id):
        if id in self.toAddSet:
            for i in xrange (len(self.toAdd)):
                if self.toAdd[i][0] == id:
                    self.toAdd[i][1] = obj
                    return
        self.toChange[id] = obj
        self.addCallback()

    def onAdd(self, obj, id):
        self.toAdd.append ([id, obj])
        self.toAddSet.add (id)
        if id in self.toRemove:
            del self.toRemove[id]
        self.addCallback()

    def onRemove(self, obj, id):
        if id in self.toAddSet:
            for i in xrange (len(self.toAdd)):
                if self.toAdd[i][0] == id:
                    del self.toAdd[i]
                    break
            self.toAddSet.remove (id)
        if id in self.toChange:
            del self.toChange[id]
        self.toRemove[id] = obj
        self.addCallback()

    def doChange(self,obj,id):
        tid = obj.tid
        xmlString = self.currentXML(obj)
        if self.parent.domHandler:
            self.parent.domHandler.changeItem(tid, xmlString)

    def doAdd(self, obj, id):
        if self.parent.domHandler:
            next = self.view.getNextID(id) 
            if next == None:
                # Adding it at the end of the list. Must add it relative to
                # the anchor.
                if self.anchorType == 'parentNode':
                    self.parent.domHandler.addItemAtEnd(self.currentXML(obj), self.anchorId)
                if self.anchorType == 'nextSibling':
                    self.parent.domHandler.addItemBefore(self.currentXML(obj), self.anchorId)
            else:
                self.parent.domHandler.addItemBefore(self.currentXML(obj), self.view.getObjectByID(next).tid)

    def doRemove(self, obj, id):
        if self.parent.domHandler:
            self.parent.domHandler.removeItem(obj.tid)

    # Add the HTML for the item at newIndex in the view to the
    # display. It should only be called by initialFillIn()
    def addHTMLAtEnd(self, xml):
        if self.parent.domHandler:
            self.parent.domHandler.addItemBefore(xml, self.anchorId)

# Class used internally by Handle to track a t:updateForView clause.
class UpdateRegion:
    def __init__(self, anchorId, anchorType, view, templateFunc, parent, name):
        # arguments as Handle.addView(), plus 'parent', a pointer to the Handle
        # that is used to find domHandler and invoke checkHides
        self.anchorId = anchorId
        self.anchorType = anchorType

        self.view = view
        self.templateFunc = templateFunc
        self.parent = parent
        self.name = name
        self.tid = generateId()
        self.idle_queued = False

    #
    # This is called after the HTML has been rendered to fill in the
    # data for each view and register callbacks to keep it updated
    def initialFillIn(self):
        self.view.confirmDBThread()
        if self.parent.domHandler:
            self.parent.domHandler.addItemBefore(self.currentXML(), self.anchorId)
        self.view.addChangeCallback(self.onChange)
        self.view.addAddCallback(self.onChange)
        self.view.addRemoveCallback(self.onChange)


    def currentXML(self):
        output = []
        output.append(self.templateFunc(self.name, self.tid).read())
        try:
            return ''.join(output) 
        except UnicodeDecodeError:
            ret = ''
            for string in output:
                try:
                    ret = ret + string
                except:
                    pass
            return ret

    def onChange(self,obj=None,id=None):
        if not self.idle_queued:
            import frontend
            try:
                frontend.inMainThread(lambda:eventloop.addIdle(self.doChange, "Update UI"))
            except:
                eventloop.addIdle(self.doChange, "Update UI")
            self.idle_queued = True

    def doChange(self):
        xmlString = self.currentXML()
        if self.parent.domHandler:
            self.parent.domHandler.changeItem(self.tid, xmlString)
        self.idle_queued = False

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
        self.trackedHides[id] = (view, hideFunc, previous)

    def _checkHide(self, id):
        (view, hideFunc, previous) = self.trackedHides[id]
        if hideFunc() != previous:
            self.trackedHides[id] = (view, hideFunc, not previous)
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
        #
        # We take a private copy of 'node', so don't worry about modifying
        # it subsequent to calling this method.
        tv = TrackedView(anchorId, anchorType, view, templateFunc, self, name)
        self.trackedViews.append(tv)

    def addUpdate(self, anchorId, anchorType, view, templateFunc, name):
        ur = UpdateRegion(anchorId, anchorType, view, templateFunc, self, name)
        self.updateRegions.append(ur)

    def unlinkTemplate(self):
        # Stop delivering callbacks, allowing the handle to be released.
        self.domHandler = None
        try:
            self.document.unlink()
        except:
            pass
        self.document = None
        self.trackedViews = []
        self.updateRegions = []
        for handle in self.subHandles:
            handle.unlinkTemplate()
        self.onUnlink()

    def initialFillIn(self):
        for ur in self.updateRegions:
            ur.initialFillIn()
        for tv in self.trackedViews:
            tv.initialFillIn()
        for handle in self.subHandles:
            handle.initialFillIn()
        for id in self.trackedHides.keys():
            (view, hideFunc, previous) = self.trackedHides[id]
            self.addHideChecks(view, id)

    def addHideChecks(self, view, id):
        view.addChangeCallback(lambda x,y:self._checkHide(id))
        view.addAddCallback(lambda x,y:self._checkHide(id))
        view.addRemoveCallback(lambda x,y:self._checkHide(id))
        self._checkHide(id)

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



# View mapping function used to assign ID attributes to records so
# that we can find them in the page after we generate them if we need
# to update them.
class IDAssignment:
    def __init__(self, x, parentViewName):
        self.object = x
        self.tid = "objid-%s-%d" % (parentViewName, id(self.object))
        
class IDAssignmentInView:
    def __init__(self, name=""):
        self.viewName = name
    def mapper(self, obj):
        return IDAssignment(obj, self.viewName)


# Returns a quoted, filled version of attribute text
def quoteAndFillAttr(value, localVars):
    return ''.join(('"',quoteattr(fillAttr(value, localVars)),'"'))

# Returns a filled version of attribute text
# Important: because we expand resource: URLs here, instead of defining a
# URL handler (which is hard to do in IE), you must link to stylesheets via
# <link .../> rather than <style> @import ... </style> if they are resource:
# URLs.

# FIXME: we should parse the attribute values ahead of time
def fillAttr(_value, _localVars):
    match = attrPattern.match(_value)
    if match:
        result = eval(match.group(2), globals(), _localVars)
        return ''.join((match.group(1), urlencode(toUni(result)), match.group(3)))
    else:
        match = rawAttrPattern.match(_value)
        if match:
            result = eval(match.group(2), globals(), _localVars)
            return ''.join((match.group(1), toUni(result), match.group(3)))
        else:
            match = resourcePattern.match(_value)
            if match:
                return resource.url(match.group(1))
            else:
                return _value

# This has to be after Handle, so the compiled templates can get
# access to Handle
import compiled_templates
