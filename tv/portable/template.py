# template.py Copyright (c) 2005, 2006 Participatory Culture Foundation
#
# Contains runtime template code

from templatehelper import quoteattr, escape, evalKey, toUni, clearEvalCache, attrPattern, rawAttrPattern, resourcePattern, generateId, textFunc, textHideFunc, attrFunc, addIDFunc, evalEscapeFunc, evalFunc, includeHideFunc, hideIfEmptyFunc, rawAttrFunc, hideSectionFunc, quoteAndFillFunc
import resource
from xhtmltools import urlencode

###############################################################################
#### Functions used in repeating templates                                 ####
###############################################################################

# These are functions that take in a dictionary to local data, an id,
# and an argument and return text to be added to the template

# Simply returns text
def getRepeatText(data, tid, text):
    return text

# Returns text if function does not evaluate to true
def getRepeatTextHide(data, tid, args):
    (functionKey,ifKey,parameter,invert, text) = args
    hide = evalKey(functionKey, data, None, True)(evalKey(ifKey, data, None, True), parameter)
    if (not invert and hide) or (invert and not hide):
        return text
    else:
        return ''

def getQuoteAttr(data, tid, value):
    return quoteattr(urlencode(toUni(evalKey(value, data, None, True))))

def getRawAttr(data, tid, value):
    return quoteattr(toUni(evalKey(value, data, None, True)))

# Adds an id attribute to a tag and closes it
def getRepeatAddIdAndClose(data, tid, args):
    return ' id="%s">'%quoteattr(tid)

# Evaluates key with data
def getRepeatEvalEscape(data, tid, replace):
    return escape(evalKey(replace,data,None, True))

# Evaluates key with data
def getRepeatEval(data, tid, replace):
    return toUni(evalKey(replace,data,None, True))

# Returns include iff function does not evaluate to true
def getRepeatIncludeHide(data, tid, args):
    (functionKey,ifKey,parameter,invert, name) = args
    hide = evalKey(functionKey, data, None, True)(evalKey(ifKey, data, None, True), parameter)
    if (not invert and hide) or (invert and not hide):
        f = open(resource.path('templates/%s'%name),'r')
        html = f.read()
        f.close()
        return html
    else:
        return ''

def getHideIfEmpty(data, tid, args):
    (self, viewName, name, invert, attrs) = args
    nodeId = generateId()
    view = self.handle.findNamedView(viewName).getView()
    hide = (not invert and view.len() == 0) or (invert and view.len() > 0)

    output = ['<%s'%name]
    for key in attrs.keys():
        if not key in ['t:hideIfViewEmpty','t:hideIfViewNotEmpty','style']:
            PyList_Append(output, ' %s=%s'%(key,quoteAndFillAttr(attrs[key],data)))
    PyList_Append(output,' id="')
    PyList_Append(output,quoteattr(nodeId))
    PyList_Append(output,'"')
    if hide:
        PyList_Append(output,' style="display:none">')
    else:
        PyList_Append(output,'>')
    self.handle.addHideIfEmpty(nodeId,viewName, invert)
    return ''.join(output)


def getHideSection(data, tid, args):
    output = []
    (functionKey,ifKey,parameter,invert, funcList) = args
    hide = evalKey(functionKey, data, None, True)(evalKey(ifKey, data, None, True), parameter)
    if (invert and hide) or (not invert and not hide):
        for count in range(len(funcList)):
            (func, args) = funcList[count]
            output.append(funcTable[func](data,tid,args))
    return ''.join(output)

def getQuoteAndFillAttr(data, tid, value):
    return quoteAndFillAttr(value, data)

funcTable = [getRepeatText, getRepeatTextHide, getQuoteAttr, getRepeatAddIdAndClose, getRepeatEvalEscape, getRepeatEval, getRepeatIncludeHide, getHideIfEmpty, getRawAttr, getHideSection, getQuoteAndFillAttr]

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
def fillTemplate(filename, data, domHandler, top = True, onlyBody = False):
    filename = filename.replace('/','.').replace('\\','.').replace('-','_')
    mod = __import__("compiled_templates.%s"%filename)
    mod = getattr(mod,filename)
    return mod.fillTemplate(data, domHandler)

# As fillTemplate, but no Javascript calls are made, and no template
# handle is returned, only the HTML or XML as a string. Effectively,
# you get a static snapshot of the page at the time the call is made.
def fillStaticTemplate(filename, data):
    # This could be somewhat more efficient
    (tch, handle) = fillTemplate(filename, data, None)
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
    def __init__(self, anchorId, anchorType, view, templateFuncs, templateData, parent, name):
        # arguments as Handle.addView(), plus 'parent', a pointer to the Handle
        # that is used to find domHandler and invoke checkHides
        self.anchorId = anchorId
        self.anchorType = anchorType

        self.origView = view
        self.view = view.map(IDAssignmentInView(id(self)).mapper)
        self.templateFuncs = templateFuncs
        self.templateData = templateData
        self.parent = parent
        self.name = name

    #
    # This is called after the HTML has been rendered to fill in the
    # data for each view and register callbacks to keep it updated
    def initialFillIn(self):
        self.view.beginRead()
        try:
            #print "Filling in %d items" % self.view.len()
            #start = time.clock()
            for x in self.view:
                self.addHTMLAtEnd(x)
            self.view.addChangeCallback(self.onChange)
            self.view.addAddCallback(self.onAdd)
            self.view.addRemoveCallback(self.onRemove)
            #print "done (%f)" % (time.clock()-start)
        finally:
            self.view.endRead()


    def currentXML(self, item):
        output = []
        data = self.templateData
        data['this'] = item.object
        data['thisView'] = self.name
        for (func, args) in self.templateFuncs:
            output.append(funcTable[func](data,item.tid,args))
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

    def onChange(self,obj,id):
        clearEvalCache()
        tid = obj.tid
        xmlString = self.currentXML(obj)
        if self.parent.domHandler:
            self.parent.domHandler.changeItem(tid, xmlString)
        self.parent.checkHides()

    def onAdd(self, obj, id):
        clearEvalCache()
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

        self.parent.checkHides()

    def onRemove(self, obj, id):
        clearEvalCache()
        if self.parent.domHandler:
            self.parent.domHandler.removeItem(obj.tid)
        self.parent.checkHides()

    # Add the HTML for the item at newIndex in the view to the
    # display. It should only be called by initialFillIn()
    def addHTMLAtEnd(self, newObj):
        clearEvalCache()
        if self.parent.domHandler:
            xml = self.currentXML(newObj)
            self.parent.domHandler.addItemBefore(xml, self.anchorId)

# Class used internally by Handle to track a t:updateForView clause.
class UpdateRegion:
    def __init__(self, anchorId, anchorType, view, templateFuncs, templateData, parent, name):
        # arguments as Handle.addView(), plus 'parent', a pointer to the Handle
        # that is used to find domHandler and invoke checkHides
        self.anchorId = anchorId
        self.anchorType = anchorType

        self.view = view
        self.templateFuncs = templateFuncs
        self.templateData = templateData
        self.parent = parent
        self.name = name
        self.tid = generateId()

    #
    # This is called after the HTML has been rendered to fill in the
    # data for each view and register callbacks to keep it updated
    def initialFillIn(self):
        self.view.beginRead()
        try:
            clearEvalCache()
            if self.parent.domHandler:
                self.parent.domHandler.addItemBefore(self.currentXML(), self.anchorId)
            self.view.addChangeCallback(self.onChange)
            self.view.addAddCallback(self.onChange)
            self.view.addRemoveCallback(self.onChange)
        finally:
            self.view.endRead()


    def currentXML(self):
        output = []
        data = self.templateData
        data['this'] = self.view
        data['thisView'] = self.name
        for (func, args) in self.templateFuncs:
            output.append(funcTable[func](data,self.tid,args))
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
        clearEvalCache()
        xmlString = self.currentXML()
        if self.parent.domHandler:
            self.parent.domHandler.changeItem(self.tid, xmlString)
        self.parent.checkHides()

# Class used by Handle to track the dynamically filterable, sortable
# views created by makeNamedView and identified by names. After
# creation, can be looked up with Handle.findNamedView and the filter
# and sort changed with setFilter and setSort.
class NamedView:
    def __init__(self, name, viewKey, viewIndex, viewIndexValue, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort, data):
        self.name = name
        self.data = data
        self.origView = evalKey(viewKey, data, None, True)

        if viewIndex is not None:
            self.indexFunc = evalKey(viewIndex, data, None, True)
            self.indexValue = viewIndexValue
            self.indexView = self.origView.filterWithIndex(self.indexFunc,self.indexValue)
        else:
            self.indexView = self.origView

        if filterKey is None:
            self.filter = returnTrue
        else:
            self.filter = makeFilter(filterKey, filterFunc, filterParameter, invertFilter,self.data)
        if sortKey is None:
            self.sort = nullSort
        else:
            self.sort = makeSort(sortKey, sortFunc, invertSort, self.data)

        self.filterView = self.indexView.filter(lambda x:self.filter(x))

        self.view = self.filterView.sort(lambda x, y:self.sort(x,y))

    def setFilter(self, fieldKey, funcKey, parameter, invert):
        if not self.filter:
            raise TemplateError, "View '%s' was not declared with a filter, so it is not possible to change the filter parameters" % self.name
        self.filter = makeFilter(fieldKey, funcKey, parameter, invert,self.data)
        self.indexView.recomputeFilter(self.filterView)

    def setSort(self, fieldKey, funcKey, invert):
        if not self.sort:
            raise TemplateError, "View '%s' was not declared with a sort, so it is not possible to change the sort parameters." % self.name
        self.sort = makeSort(fieldKey, funcKey, invert, self.data)
        self.indexView.recomputeSort(self.filterView)

    def getView(self):
        # Internal use.
        return self.view

    def removeViewFromDB(self):
        if self.origView is self.indexView:
            self.origView.removeView(self.filterView)
        else:
            self.origView.removeView(self.indexView)

# Object representing a set of registrations for Javascript callbacks when
# the contents of some set of database views change. One of these Handles
# is returned whenever you fill a template; when you no longer want to
# receive Javascript callbacks for a particular filled template, call
# this object's unlinkTemplate() method.
class Handle:
    def __init__(self, domHandler, document = None):
        # 'domHandler' is an object that will receive method calls when
        # dynamic page updates need to be made. 
        self.domHandler = domHandler
        self.document = document
        self.hideConditions = []
        self.namedViews = {}
        self.trackedViews = []
        self.updateRegions = []
        self.subHandles = []
        self.triggerActionURLsOnLoad = []
        self.triggerActionURLsOnUnload = []
        
    def addTriggerActionURLOnLoad(self,url):
        self.triggerActionURLsOnLoad.append(str(url))

    def addTriggerActionURLOnUnload(self, url):
        self.triggerActionURLsOnUnload.append(str(url))

    def getTriggerActionURLsOnLoad(self):
        return self.triggerActionURLsOnLoad

    def getTriggerActionURLsOnUnload(self):
        return self.triggerActionURLsOnUnload

    def addHideIfEmpty(self, id, name, invert):
        # Make JS calls to hide and show the node with the give id when
        # the given view becomes true and false, respectively.
        if invert:
            self.hideConditions.append((id, name, invert, not self.viewIsEmpty(name)))
        else:
            self.hideConditions.append((id, name, invert, self.viewIsEmpty(name)))

    def viewIsEmpty(self, viewName):
        return self.findNamedView(viewName).getView().len()==0

    def checkHides(self):
        # Internal use.
        if self.domHandler:
            for i in range(0,len(self.hideConditions)):
                (id, name, invert, previous) = self.hideConditions[i]
                if invert:
                    current = not self.viewIsEmpty(name)
                else:
                    current = self.viewIsEmpty(name)
                if (current == True) != (previous == True):
                    self.hideConditions[i] = (id, name, invert, current)
                    if current:
                        self.domHandler.hideItem(id)
                    else:
                        self.domHandler.showItem(id)
                        
    def makeNamedView(self, name, viewKey, viewIndex, viewIndexValue, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort, data):
        if self.namedViews.has_key(name):
            raise TemplateError, "More than one view was declared with the name '%s'. Each view must have a different name." % name
        nv = NamedView(name, viewKey, viewIndex, viewIndexValue, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort, data)
        self.namedViews[name] = nv
        return nv.getView()

    def findNamedView(self, name):
        if self.namedViews.has_key(name):
            return self.namedViews[name]
        else:
            for sh in self.subHandles:
                try:
                    return sh.findNamedView(name)
                except TemplateError:
                    pass
        raise TemplateError, "A view named '%s' was referenced but not defined." % name

    def addView(self, anchorId, anchorType, view, templateFuncs, data, name):
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
        tv = TrackedView(anchorId, anchorType, view, templateFuncs, data, self, name)
        self.trackedViews.append(tv)

    def addUpdate(self, anchorId, anchorType, view, templateFuncs, data, name):
        ur = UpdateRegion(anchorId, anchorType, view, templateFuncs, data, self, name)
        self.updateRegions.append(ur)

    def unlinkTemplate(self):
        # Stop delivering callbacks, allowing the handle to be released.
        self.domHandler = None
        try:
            self.document.unlink()
        except:
            pass
        self.document = None
        self.hideConditions = []
        self.trackedViews = []
        self.updateRegions = []
        for handle in self.subHandles:
            handle.unlinkTemplate()
        for view in self.namedViews.values():
            view.removeViewFromDB()
    
    def initialFillIn(self):
        for tv in self.trackedViews:
            tv.initialFillIn()
        for ur in self.updateRegions:
            ur.initialFillIn()
        for handle in self.subHandles:
            handle.initialFillIn()

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


def makeFilter(fieldKey, funcKey, parameter, invert, data):
    func = evalKey(funcKey, data)
    if not invert:
        return lambda x: func(evalKey(fieldKey, x), parameter)
    else:
        return lambda x: not func(evalKey(fieldKey, x), parameter)

def makeSort(fieldKey, funcKey, invert,data):
    func = evalKey(funcKey, data)
    if not invert:
        return lambda x,y:  func(evalKey(fieldKey,x), evalKey(fieldKey,y)) 
    else:
        return lambda x,y: -func(evalKey(fieldKey,x), evalKey(fieldKey,y))

# Returns a quoted, filled version of attribute text
def quoteAndFillAttr(value,data):
    return ''.join(('"',quoteattr(fillAttr(value,data)),'"'))

# Returns a filled version of attribute text
# Important: because we expand resource: URLs here, instead of defining a
# URL handler (which is hard to do in IE), you must link to stylesheets via
# <link .../> rather than <style> @import ... </style> if they are resource:
# URLs.
def fillAttr(value, data):
    match = attrPattern.match(value)
    if match:
        return ''.join((match.group(1), urlencode(toUni(evalKey(match.group(2), data, None, True))), match.group(3)))
    else:
        match = rawAttrPattern.match(value)
        if match:
            return ''.join((match.group(1), toUni(evalKey(match.group(2), data, None, True)), match.group(3)))
        else:
            match = resourcePattern.match(value)
            if match:
                return resource.url(match.group(1))
            else:
                return value

# This has to be after Handle, so the compiled templates can get
# access to Handle
import compiled_templates
