# Import Python C functions
cdef extern from "Python.h":
    cdef int PyList_GET_SIZE(object list)
    cdef int PyList_GET_ITEM(object list, int i)
    cdef void PyList_SET_ITEM(object PyList, int idx, object obj)
    cdef int PyList_SetSlice(object list, int low, int high, object itemlist)
    cdef int PyList_Append(object list, object item)

    cdef void* PyTuple_GET_ITEM(object list, int i)

    cdef void* PyDict_GetItem(object dict, object key)
    cdef int PyDict_SetItem(object dict, object key, object val)
    cdef int PyDict_SetItemString(object dict, char* key, object val)
    cdef int PyDict_Contains(object dict, object key)
    cdef int PyDict_Next(object dict, int *pos, void* key, void* value)
    cdef int PyDict_Check(object p)

    cdef object PyObject_CallObject(object callable, object args)
    cdef object PyObject_CallFunction(object callable, char *format,...)
    cdef void Py_INCREF(object x)
    cdef void Py_DECREF(object x)

    cdef object PyObject_CallMethod(object o, char *method, char *format)
    cdef int PyObject_HasAttr(object o, object name)
    cdef object PyObject_GetAttr(object o, object name)
    cdef object PyObject_GetAttrString(object o, char* name)
    cdef object PyObject_GetIter(object obj)

    cdef void* PyIter_Next(object obj)

    cdef int PyInstance_Check(object p)
    cdef int PyMethod_Check(object p)
    cdef int PyMethod_GET_FUNCTION(object m)

# A faster equivalent to PyList[idx] = obj
cdef int setListItem(object PyList, int idx, object obj) except -1:
    Py_INCREF(obj)
    PyList_SET_ITEM(PyList, idx, obj)

from xml.dom.minidom import parse, parseString
from xml import sax
from xhtmltools import urlencode
#from cStringIO import StringIO
from StringIO import StringIO
import time
import resource
import random
import copy
import re
import types
import traceback
import gettext
import templatehelper
from threading import Thread

#Setup gettext
gettext.install('dtv', 'resources/gettext')

# Limitations:
# - t:hideIf tags are only dynamically updated whenever there is dynamic
#   activity on a t:repeatForView in the document (easily fixed)
# - Style tags are overwritten for hidden nodes
# - id tags are inserted in appropriate places
# - An empty span is always created after a repeatForView, so we can't
#   use it inside of a table

# To Do:
# - Take a lock around the entire database while template is being filled
# - Improve error handling (currently some random exception is thrown if
#   the template is poorly structured)
# - Currently, we're using the translate and name attributes found on
#   this page to mark text for translation, but they're unhandled.
#   http://www.zope.org/DevHome/Wikis/DevSite/Projects/ComponentArchitecture/ZPTInternationalizationSupport
#
#    Eventually, we may add support for more attributes

cdef object HTMLPatter
cdef object attrPatter
cdef object rawAttrPattern

# Hmmm... Apparently escaping quotes in Pyrex is slightly different
# than in Python...

#HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)
HTMLPattern = re.compile("^.*<body.*?>(.*)</body\\s*>", re.S)
attrPattern = re.compile("^(.*)@@@(.*?)@@@(.*)$")
resourcePattern = re.compile("^resource:(.*)$")
#rawAttrPattern = re.compile("^(.*)\*\*\*(.*?)\*\*\*(.*)$")
rawAttrPattern = re.compile("^(.*)\\*\\*\\*(.*?)\\*\\*\\*(.*)$")

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
def fillTemplate(file, data, domHandler, top = True):
#     if top:
#         startTime = time.clock()
    handle = Handle(domHandler)
    tch = TemplateContentHandler(data,handle,True,domHandler=domHandler)
    p = sax.make_parser()
    p.setFeature(sax.handler.feature_external_ges, False)
    p.setContentHandler(tch)
    try:
        p.parse(resource.path("templates/%s" % file))
        #prof = hotshot.Profile("template.prof")
        #prof.runcall(p.parse,(resource.path("templates/%s" % file)))
        #prof.close()
    except:
        traceback.print_exc()        

    #print '-----\n%s\n-----'%tch.output
#     if top:
#         stopTime = time.clock()
#         print ("SAX Template for %s took about %s seconds to complete"%(file,str(stopTime-startTime)))
    return ''.join(('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n',tch.output)), handle
    #return (document.toxml(), handle)

# As fillTemplate, but no Javascript calls are made, and no template
# handle is returned, only the HTML or XML as a string. Effectively,
# you get a static snapshot of the page at the time the call is made.
def fillStaticTemplate(file, data):
    # This could be somewhat more efficient    
    (xml, handle) = fillTemplate(file, data, None)
    handle.unlinkTemplate()
    return xml

class TemplateError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return self.message

###############################################################################
#### Main template filling code                                            ####
###############################################################################

##
# SAX version of templating code
class TemplateContentHandler(sax.handler.ContentHandler):
    def __init__(self, data, handle, debug = False, domHandler = None):
        self.data = data
        self.handle = handle
        self.debug = debug
        self.domHandler = domHandler
        clearEvalCache()

    def returnIf(self,bool,value):
        if bool:
            return value
        else:
            return ''

    def fillTemplate(self,name,data):
        (html,handle) = fillTemplate(name,data,self.domHandler, False)
        
        html = HTMLPattern.match(html).group(1)
        self.handle.addSubHandle(handle)
        return html
        
    def startDocument(self):
        self.elementStack = []
        self.inDynamicViews = False
        self.inView = False
        self.inInclude = False
        self.inRepeatView = False
        self.inUpdateView = False
        self.inReplace = False
        self.inStaticReplace = False
        self.repeatDepth = 0
        self.replaceDepth = 0
        self.repeatView = None
        self.hiding = False
        self.hideDepth = 0
        self.outString = StringIO()
        self.depth = 0
        self.repeatName = ''

        # When we're in repeat mode, we store output as a set of
        # functions and arguments that, called given an object, tid,
        # and set of arguments return the correct output
        self.repeatList = []

    def endDocument(self):
        self.output = self.outString.getvalue()

    def startElement(self,name, attrs):
        self.depth = self.depth + 1
        if self.inReplace or self.inStaticReplace or self.hiding:
            pass
        elif 't:hideIfViewEmpty' in attrs.keys() or 't:hideIfViewNotEmpty' in attrs.keys():
            nodeId = generateId()
            if 't:hideIfViewEmpty' in attrs.keys():
                viewName = attrs['t:hideIfViewEmpty']
                ifInvert = False
            else:
                viewName = attrs['t:hideIfViewNotEmpty']
                ifInvert = True
            view = self.handle.findNamedView(viewName).getView()
            hide = (not ifInvert and view.len() == 0) or (ifInvert and view.len() > 0)

            self.outString.write('<')
            self.outString.write(name)
            for key in attrs.keys():
                if not key in ['t:hideIfViewEmpty','t:hideIfViewNotEmpty','style']:
                    self.outString.write(' ')
                    self.outString.write(key)
                    self.outString.write('=')
                    self.outString.write(quoteAndFillAttr(attrs[key],self.data))
            self.outString.write(' id=')
            self.outString.write(sax.saxutils.quoteattr(nodeId))
            if hide:
                self.outString.write(' style="display:none">')
            else:
                self.outString.write('>')
            self.handle.addHideIfEmpty(nodeId,viewName, ifInvert)
        elif 't:repeatForView' in attrs.keys():
            self.inRepeatView = True
            self.repeatDepth = self.depth
            self.repeatList = [(getRepeatText, '<%s'%name),]
            for key in attrs.keys():
                if key != 't:repeatForView':
                    addKey = key
                    PyList_Append(self.repeatList,(getRepeatAttr,(addKey,attrs[addKey])))
            PyList_Append(self.repeatList,(getRepeatAddIdAndClose,None))

            self.repeatView = self.handle.findNamedView(attrs['t:repeatForView']).getView()
            self.repeatName = attrs['t:repeatForView']

        elif 't:updateForView' in attrs.keys():
            self.inUpdateView = True
            self.repeatDepth = self.depth
            self.repeatList = [(getRepeatText, '<%s'%name),]
            for key in attrs.keys():
                if key != 't:updateForView':
                    addKey = key
                    PyList_Append(self.repeatList,(getRepeatAttr,(addKey,attrs[addKey])))
            PyList_Append(self.repeatList,(getRepeatAddIdAndClose,None))

            self.repeatView = self.handle.findNamedView(attrs['t:updateForView']).getView()
            self.repeatName = attrs['t:updateForView']

        elif self.inRepeatView or self.inUpdateView:
            if attrs.has_key('t:hideIfKey') or attrs.has_key('t:hideIfNotKey'):
                try:
                    ifKey = attrs['t:hideIfKey']
                    ifInvert = False
                except KeyError:
                    ifKey = attrs['t:hideIfNotKey']
                    ifInvert = True
                functionKey = attrs['t:hideFunctionKey']
                try:
                    parameter = attrs['t:hideParameter']
                except KeyError:
                    parameter = ''
                hide = True
            else:
                hide = False

            if name == 't:includeTemplate':
                if hide: 
                    PyList_Append(self.repeatList,(getRepeatFillTemplateHide,(functionKey,ifKey,parameter,ifInvert,attrs['filename'],self)))
                else:
                    PyList_Append(self.repeatList,(getRepeatFillTemplate,(attrs['filename'],self)))
            elif name == 't:include':
                if hide:
                    PyList_Append(self.repeatList,(getRepeatIncludeHide,(functionKey,ifKey,parameter,ifInvert,attrs['filename'],self)))
                else:
                    PyList_Append(self.repeatList,(getRepeatInclude,(attrs['filename'],self)))                
            else:
                PyList_Append(self.repeatList,(getRepeatText,'<%s'%name))
                for key in attrs.keys():
                    if not (key in ['t:replace','t:replaceMarkup','t:hideIfKey',
                               't:hideIfNotKey','t:hideFunctionKey',
                               't:hideParameter','style']):
                        PyList_Append(self.repeatList,(getRepeatAttr,(key,attrs[key])))

                if hide:
                    PyList_Append(self.repeatList,(getRepeatTextHide,(functionKey,ifKey,parameter,ifInvert,' style="display:none"')))

                PyList_Append(self.repeatList,(getRepeatText,'>'))
                try:
                    replace = attrs['t:replace']
                    PyList_Append(self.repeatList,(getRepeatEvalEscape,replace))
                    self.inReplace = True
                    self.replaceDepth = self.depth
                except KeyError:
                    pass
                try:
                    replace = attrs['t:replaceMarkup']
                    PyList_Append(self.repeatList,(getRepeatEval,replace))
                    self.inReplace = True
                    self.replaceDepth = self.depth
                except KeyError:
                    pass
        elif 't:hideIfKey' in attrs.keys() or 't:hideIfNotKey' in attrs.keys():
            try:
                ifKey = attrs['t:hideIfKey']
                ifInvert = False
            except KeyError:
                ifKey = attrs['t:hideIfNotKey']
                ifInvert = True
            functionKey = attrs['t:hideFunctionKey']
            try:
                parameter = attrs['t:hideParameter']
            except KeyError:
                parameter = ''

            function = evalKeyC(functionKey, self.data, None, True)
            hide = function(evalKeyC(ifKey, self.data, None, True), parameter)
            if ifInvert:
                hide = not hide

            if not hide:
                self.outString.write('<%s'%name)
                for key in attrs.keys():
                    if not (key in ['t:hideIfKey','t:hideIfNotKey','t:hideFunctionKey','t:hideParameter']):
                        self.outString.write(' %s=%s'%(key,quoteAndFillAttr(attrs[key],self.data)))
                self.outString.write('>')
            else:
                self.hiding = True
                self.hideDepth = self.depth

        elif 't:replace' in attrs.keys():
                self.outString.write('<%s'%name)
                for key in attrs.keys():
                    if key != 't:replace':
                        self.outString.write(' %s=%s'%(key,quoteAndFillAttr(attrs[key],self.data)))
                self.outString.write('>')
                replace = attrs['t:replace']
                self.outString.write(sax.saxutils.escape(unicode(evalKeyC(replace,self.data, None, True))))
                self.inReplace = True
                self.replaceDepth = self.depth      
        elif 't:replaceMarkup' in attrs.keys():
                self.outString.write('<%s'%name)
                for key in attrs.keys():
                    if key != 't:replaceMarkup':
                        self.outString.write(' %s=%s'%(key,quoteAndFillAttr(attrs[key],self.data)))
                self.outString.write('>')
                replace = attrs['t:replaceMarkup']
                self.outString.write(unicode(evalKeyC(replace,self.data,None, True)))
                self.inReplace = True
                self.replaceDepth = self.depth      
        elif name == 't:dynamicviews':
            self.inDynamicViews = True
        elif name == 't:view' and self.inDynamicViews:
            self.viewName = attrs['name']
            self.viewKey = attrs['key']
            self.viewIndex = None
            self.viewIndexValue = None
            self.filterKey = None
            self.filterInvert = False
            self.filterFunc = None
            self.filterParam = None
            self.sortKey = None
            self.sortFunc = None
            self.sortInvert = False
            self.inView = True
        elif name == 't:indexFilter' and self.inView:
            self.viewIndex = attrs['index']
            self.viewIndexValue = fillAttr(attrs['value'], self.data)
        elif name == 't:filter' and self.inView:
            try:
                self.filterKey = attrs['key']
            except KeyError:
                self.filterKey = ''
            try:
                self.filterInvert = not (attrs['invert'] in ['','false','0'])
            except KeyError:
                pass
            self.filterFunc = attrs['functionkey']
            self.filterParam = fillAttr(attrs['parameter'],self.data)
        elif name  == 't:sort' and self.inView:
            try:
                self.sortKey = attrs['key']
            except KeyError:
                self.sortKey = ''
            try:
                self.sortInvert = not (attrs['invert'] in ['','false','0'])
            except KeyError:
                pass
            self.sortFunc = attrs['functionkey']
        elif name == 't:include':
            f = open(resource.path('templates/%s'%attrs['filename']),'r')
            html = f.read()
            f.close()
            self.outString.write(html)
        elif name == 't:staticReplaceMarkup':
            replace = attrs['t:replaceData']
            self.outString.write(unicode(evalKeyC(replace,self.data,None, True)))
            self.inStaticReplace = True
        elif name == 't:staticReplace':
            replace = attrs['t:replaceData']
            self.outString.write(sax.saxutils.escape(unicode(evalKeyC(replace,self.data, None, True))))
            self.inStaticReplace = True
        elif name == 't:includeTemplate':
            self.outString.write(self.fillTemplate(attrs['filename'],self.data))
        elif name == 't:triggerActionOnLoad':
            self.handle.addTriggerActionURLOnLoad(fillAttr(attrs['url'],self.data))
        elif name == 't:triggerActionOnUnload':
            self.handle.addTriggerActionURLOnUnload(fillAttr(attrs['url'],self.data))
        else:
            self.outString.write('<%s'%name)
            for key in attrs.keys():
                self.outString.write(' %s=%s'%(key,quoteAndFillAttr(attrs[key],self.data)))
            self.outString.write('>')

    def endElement(self,name):
        if name == 't:include':
            pass
        elif name == 't:staticReplace':
            self.inStaticReplace = False
        elif name == 't:staticReplaceMarkup':
            self.inStaticReplace = False
        elif name == 't:filter':
            pass
        elif name == 't:sort':
            pass
        elif name == 't:includeTemplate':
            pass
        elif self.hiding:
            if self.depth == self.hideDepth:
                self.hiding = False
        elif self.inReplace and self.depth == self.replaceDepth:
            if self.inRepeatView or self.inUpdateView:
                PyList_Append(self.repeatList,(getRepeatText,'</%s>'%name))
            else:
                self.outString.write('</%s>'%name)
            self.inReplace = False
        elif self.inRepeatView and self.depth == self.repeatDepth:
            self.inRepeatView = False
            PyList_Append(self.repeatList,(getRepeatText,'</%s>'%name))

            repeatId = generateId()
            self.outString.write('<span id=%s/>'%sax.saxutils.quoteattr(repeatId))
            self.handle.addView(repeatId, 'nextSibling', self.repeatView, self.repeatList, self.data, self.repeatName)
        elif self.inUpdateView and self.depth == self.repeatDepth:
            self.inUpdateView = False
            PyList_Append(self.repeatList,(getRepeatText,'</%s>'%name))

            repeatId = generateId()
            self.outString.write('<span id=%s/>'%sax.saxutils.quoteattr(repeatId))
            self.handle.addUpdate(repeatId, 'nextSibling', self.repeatView, self.repeatList, self.data, self.repeatName)
        elif self.inRepeatView or self.inUpdateView:
            PyList_Append(self.repeatList,(getRepeatText,'</%s>'%name))
        elif name == 't:dynamicviews':
            self.inDynamicViews = False
        elif name == 't:view':
            self.inView = False
            self.handle.makeNamedView(self.viewName, self.viewKey,
                                 self.viewIndex, self.viewIndexValue,
                                 self.filterKey, self.filterFunc, 
                                 self.filterParam, self.filterInvert,
                                 self.sortKey, self.sortFunc, self.sortInvert,
                                 self.data)
        else:
            self.outString.write('</%s>'%name)
        self.depth = self.depth - 1

    def characters(self,data):
        if self.inReplace or self.inStaticReplace or self.hiding:
            pass
        elif self.inRepeatView or self.inUpdateView:
            PyList_Append(self.repeatList,(getRepeatTextEscape,data))
        else:
            self.outString.write(sax.saxutils.escape(data))

# Random utility functions 
def returnFalse(x):
    return False

def returnTrue(x):
    return True

def identityFunc(x):
    return x

def nullSort(x,y):
    return 0

# Class used internally by Handle to track a t:repeatForSet clause.
class TrackedView:
    def __init__(self, anchorId, anchorType, view, templateFuncs, templateData, parent, name):
        # arguments as Handle.addView(), plus 'parent', a pointer to the Handle
        # that is used to find domHandler and invoke checkHides
        self.anchorId = anchorId
        self.anchorType = anchorType

        self.origView = view
        self.view = view.map(idAssignment)
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
            for x in self.view:
                self.addHTMLAtEnd(x)
            self.view.addChangeCallback(self.onChange)
            self.view.addAddCallback(self.onAdd)
            self.view.addRemoveCallback(self.onRemove)
        finally:
            self.view.endRead()


    def currentXML(self, item):
        output = []
        data = copy.copy(self.templateData)
        data['this'] = item.object
        data['thisView'] = self.name
        for (func, args) in self.templateFuncs:
            output.append(func(data,item.tid,args))
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
            self.parent.domHandler.addItemBefore(self.currentXML(newObj), self.anchorId)

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
        data = copy.copy(self.templateData)
        data['this'] = self.view
        data['thisView'] = self.name
        for (func, args) in self.templateFuncs:
            output.append(func(data,self.tid,args))
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
        self.origView = evalKeyC(viewKey, data, None, True)

        if viewIndex is not None:
            self.indexFunc = evalKeyC(viewIndex, data, None, True)
            self.indexValue = evalKeyC(viewIndexValue, data, None, True)
            self.indexView = self.origView.filterWithIndex(self.indexFunc,self.indexValue)
        else:
            self.indexView = self.origView

        if filterKey is None:
            self.filter = returnTrue
        else:
            self.filter = templatehelper.makeFilter(filterKey, filterFunc, filterParameter, invertFilter,self.data)
        if sortKey is None:
            self.sort = nullSort
        else:
            self.sort = templatehelper.makeSort(sortKey, sortFunc, invertSort, self.data)

        self.filterView = self.indexView.filter(templatehelper.getFilterFunc(self))
        self.view = self.filterView.sort(templatehelper.getSortFunc(self))

    def setFilter(self, fieldKey, funcKey, parameter, invert):
        if not self.filter:
            raise TemplateError, "View '%s' was not declared with a filter, so it is not possible to change the filter parameters" % self.name
        self.filter = templatehelper.makeFilter(fieldKey, funcKey, parameter, invert,self.data)
        self.indexView.recomputeFilter(self.filterView)

    def setSort(self, fieldKey, funcKey, invert):
        if not self.sort:
            raise TemplateError, "View '%s' was not declared with a sort, so it is not possible to change the sort parameters." % self.name
        self.sort = templatehelper.makeSort(fieldKey, funcKey, invert, self.data)
        self.indexView.recomputeSort(self.filterView)

    def getView(self):
        # Internal use.
        return self.view

    def removeViewFromDB(self):
        if self.origView is self.indexView:
            self.origView.removeView(self.filterView)
        else:
            self.origView.removeView(self.indexView)

###############################################################################
#### Functions used in repeating templates                                 ####
###############################################################################

# These are functions that take in a dictionary to local data, an id,
# and an argument and return text to be added to the template

# Simply returns text
def getRepeatText(data, tid, text):
    return text

# Returns text, xml escaped
def getRepeatTextEscape(data, tid, text):
    return sax.saxutils.escape(text)

# Returns text if function does not evaluate to true
def getRepeatTextHide(data, tid, args):
    (functionKey,ifKey,parameter,invert, text) = args
    hide = evalKeyC(functionKey, data, None, True)(evalKeyC(ifKey, data, None, True), parameter)
    if (not invert and hide) or (invert and not hide):
        return text
    else:
        return ''

# Arg is a tuple of the name of the argument and it's value
def getRepeatAttr(data, tid, args):
    return " %s=%s" % (args[0],quoteAndFillAttr(args[1],data))

# Adds an id attribute to a tag and closes it
def getRepeatAddIdAndClose(data,tid,args):
    return ' id=%s>'%sax.saxutils.quoteattr(tid)

# Evaluates key with data
def getRepeatEvalEscape(data, tid, replace):
    return sax.saxutils.escape(unicode(evalKeyC(replace,data,None, True)))

# Evaluates key with data
def getRepeatEval(data, tid, replace):
    return unicode(evalKeyC(replace,data,None, True))

# Returns text of include
def getRepeatInclude(data, tid, args):
    f = open(resource.path('templates/%s'%args[0]),'r')
    html = f.read()
    f.close()
    return html

# Returns include iff function does not evaluate to true
def getRepeatIncludeHide(data,tid,args):
    (functionKey,ifKey,parameter,invert, name, self) = args
    hide = evalKeyC(functionKey, data, None, True)(evalKeyC(ifKey, data, None, True), parameter)
    if (not invert and hide) or (invert and not hide):
        return getRepeatInclude(data,tid,(name,self))
    else:
        return ''

# Evaluates template and returns it
def getRepeatFillTemplate(data,tid,args):
    (name, self) = args
    html = self.fillTemplate(name,data)
    return html

# Evaluates template and returns it iff function does not evaluate to true
def getRepeatFillTemplateHide(data,tid,args):
    (functionKey,ifKey,parameter,invert, name, self) = args
    hide = evalKeyC(functionKey, data, None, True)(evalKeyC(ifKey, data, None, True), parameter)
    if (not invert and hide) or (invert and not hide):
        return getRepeatFillTemplate(data,tid,(name,self))
    else:
        return ''
        
# Returns a quoted, filled version of attribute text
def quoteAndFillAttr(value,data):
    return sax.saxutils.quoteattr(fillAttr(value,data))

# Returns a filled version of attribute text
# Important: because we expand resource: URLs here, instead of defining a
# URL handler (which is hard to do in IE), you must link to stylesheets via
# <link .../> rather than <style> @import ... </style> if they are resource:
# URLs.
def fillAttr(value,data):
    while True:
        match = attrPattern.match(value)
        if not match:
            break
        value = ''.join((match.group(1), urlencode(unicode(evalKeyC(match.group(2), data, None, True))), match.group(3)))
    while True:
        match = rawAttrPattern.match(value)
        if not match:
            break
        value = ''.join((match.group(1), unicode(evalKeyC(match.group(2), data, None, True)), match.group(3)))
    match = resourcePattern.match(value)
    if match:
        value = resource.url(match.group(1))
    return value

# View mapping function used to assign ID attributes to records so
# that we can find them in the page after we generate them if we need
# to update them.
class idAssignment:
    def __init__(self, x):
        self.object = x
        self.tid = "objid%d" % id(self.object)

###############################################################################
#### Generating Javascript callbacks to keep document updated              ####
###############################################################################

# Object representing a set of registrations for Javascript callbacks when
# the contents of some set of database views change. One of these Handles
# is returned whenever you fill a template; when you no longer want to
# receive Javascript callbacks for a particular filled template, call
# this object's unlinkTemplate() method.
class Handle:
    def __init__(self, domHandler, document = None):
        # 'domHandler' is an object that will receive method calls when
        # dynamic page updates need to be made. 'document', if
        # non-None, is a (Python) DOM document objects that will be unlink()ed
        # when unlinkTemplate() is called on this handle.
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

###############################################################################
#### Utility routines                                                      ####
###############################################################################

cdef object evalCache
def clearEvalCache():
    global evalCache
    evalCache = {}

# 'key' is a key name in the template language. Resolve it relative to 'data.'
# For example, 'this feed name' might become data['this'].feed.name().
cdef object evalKeyC(object keyString, object data, object originalKey, int cache):
    cdef object keys
    cdef object key
    cdef int    count

    global evalCache

    if cache and PyDict_Contains(evalCache,keyString):
        return <object>PyDict_GetItem(evalCache,keyString)

#    print "eval %s against %s" % (str(key),str(data))
    # Save the original expression for use in error messages
    if originalKey is None:
        originalKey = key

    keys = PyObject_CallMethod(keyString,"split",<char*>NULL)

    for count from 0 <= count < PyList_GET_SIZE(keys):
        key = <object>PyList_GET_ITEM(keys,count)
        if PyDict_Check(data):
            if PyDict_Contains(data,key):
                data = <object>PyDict_GetItem(data,key)
            else:
                return 'Bad Key'
                #raise TemplateError, "Bad key '%s': dictionary '%s' does not contain an element '%s'." % (originalKey, data, key)

        elif PyInstance_Check(data):
            if PyObject_HasAttr(data,key):
                data = PyObject_GetAttr(data, key)
            else:
                return 'Bad Key'
                #raise TemplateError, "Bad key '%s': object '%s' does not have an attribute '%s'." % (originalKey, data, key)

            if PyMethod_Check(data):
                data = PyObject_CallFunction(data,NULL)
        else:
            # The template tried to index into something that we don't
            # consider a container for template filling purposes (eg,
            # 'this feed name contents')
            return 'Bad key'
            #raise TemplateError, "Bad key '%s': object '%s' has no subkeys. (Remainder of expression: '%s'." % (originalKey, data, key)
        
    if cache:
        PyDict_SetItem(evalCache,keyString,data)
    return data

#Python version of evalKeyC function for use in sub views
def evalKey(key, data, originalKey = None):
    return evalKeyC(key, data, originalKey, False)

# Perform escapes needed for Javascript string contents.
def quoteJS(x):
    x = re.compile("\\\\").sub("\\\\", x)  #       \ -> \\
    x = re.compile("\"").  sub("\\\"", x)  #       " -> \"
    x = re.compile("'").   sub("\\'", x)   #       ' -> \'
    x = re.compile("\n").  sub("\\\\n", x) # newline -> \n
    x = re.compile("\r").  sub("\\\\r", x) #      CR -> \r
    return x

# Generate an arbitrary string to use as an ID attribute.
def generateId():
    return "tmpl%08d" % random.randint(0,99999999)

###############################################################################
###############################################################################
