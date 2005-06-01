from xml.dom.minidom import parse, parseString
from xml import sax
import time
import resource
import random
import copy
import re
import types
import traceback
import gettext

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


###############################################################################
#### Public interface                                                      ####
###############################################################################

# Fill the template in the given file in the template directory using
# the information in the dictionary given by 'data'. If the template
# contains dynamic views, call the provided execJS function as
# necessary in the future, passing a string that should be executed in
# the context of the page to update it.  Returns a tuple: a string
# giving the HTML or XML that resulted from filling the template, and
# a "template handle" whose unlinkTemplate() method you should call
# when you no longer want to receive Javascript callbacks.
def fillTemplate(file, data, execJS):
    startTime = time.clock()
    handle = Handle(execJS)
    tch = TemplateContentHandler(data,handle,True)
    p = sax.make_parser()
    p.setFeature(sax.handler.feature_external_ges, False)
    p.setContentHandler(tch)
    try:
        p.parse(resource.path("templates/%s" % file))
    except:
        traceback.print_exc()        
    x = ''.join(tch.output)
    #print '-----\n%s\n-----'%x
    stopTime = time.clock()
    print ("SAX Template for %s took about "%file)+str(stopTime-startTime)+" secs to complete"
    return x, handle
    #return (document.toxml(), handle)

# As fillTemplate, but no Javascript calls are made, and no template
# handle is returned, only the HTML or XML as a string. Effectively,
# you get a static snapshot of the page at the time the call is made.
def fillStaticTemplate(file, data):
    # This could be somewhat more efficient
    (xml, handle) = fillTemplate(file, data, lambda x: False)
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
    attrPattern = re.compile("^(.*)@@@(.*?)@@@(.*)$");
    def __init__(self, data, handle, debug = False):
        self.data = data
        self.handle = handle
        self.debug = debug

    def returnIf(self,bool,value):
        if bool:
            return value
        else:
            return ''

    # Returns a quoted, filled version of attribute text
    def quoteAndFillAttr(self,value,data):
        while True:
            match = self.attrPattern.match(value)
            if not match:
                break
            value = match.group(1) + str(evalKey(match.group(2), data)) + match.group(3)
        return sax.saxutils.quoteattr(value)
        
    def startDocument(self):
        self.elementStack = []
        self.inDynamicViews = False
        self.inView = False
        self.inInclude = False
        self.inRepeatView = False
        self.inReplace = False
        self.repeatDepth = 0
        self.replaceDepth = 0
        self.repeatView = None
        self.output = []
        self.depth = 0

        # When we're in repeat mode, we store output as a set of
        # functions that, given an object and tid return the correct
        # output
        self.repeatList = []

    def startElement(self,name, attrs):
        self.depth += 1
        if self.inReplace:
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

            self.output.append('<')
            self.output.append(name)
            for key in attrs.keys():
                if not key in ['t:hideIfViewEmpty','t:hideIfViewNotEmpty','style']:
                    self.output.append(' ')
                    self.output.append(key)
                    self.output.append('=')
                    self.output.append(self.quoteAndFillAttr(attrs[key],self.data))
            self.output.append(' id=')
            self.output.append(sax.saxutils.quoteattr(nodeId))
            if hide:
                self.output.append(' style="display:none">')
            else:
                self.output.append('>')
            if not ifInvert:
                self.handle.addHideCondition(nodeId, lambda:self.handle.findNamedView(viewName).getView().len()==0)
            else:
                self.handle.addHideCondition(nodeId, lambda:self.handle.findNamedView(viewName).getView().len()>0)
        elif 't:repeatForView' in attrs.keys():
            self.inRepeatView = True
            self.repeatDepth = self.depth
            self.repeatList = [lambda x,y: '<'+name,]
            for key in attrs.keys():
                if key != 't:repeatForView':
                    addKey = key
                    self.repeatList.append(lambda x,y:' '+addKey+'='+self.quoteAndFillAttr(attrs[addKey],x))
            self.repeatList.append(lambda x,y:' id='+sax.saxutils.quoteattr(y)+'>')

            self.repeatView = self.handle.findNamedView(attrs['t:repeatForView']).getView().map(idAssignment)
        elif self.inRepeatView:
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
                if ifInvert:
                    hideFunc = lambda x, y:not evalKey(functionKey, x)(evalKey(ifKey, x), parameter)
                else:
                    hideFunc = lambda x, y:evalKey(functionKey, x)(evalKey(ifKey, x), parameter)
                hide = True
            else:
                hide = False
                
            self.repeatList.append(lambda x,y:'<')
            self.repeatList.append(lambda x,y:name)
            for key in attrs.keys():
                if not (key in ['t:replace','t:replaceMarkup','t:hideIfKey',
                               't:hideIfNotKey','t:hideFunctionKey',
                               't:hideParameter','style']):
                    self.repeatList.append(self.makeReplaceFunc(key,attrs[key]))
            if hide:
                self.repeatList.append(lambda x, y:self.returnIf(hideFunc(x,y),' style="display:none"'))

            self.repeatList.append(lambda x,y: '>')
            try:
                replace = attrs['t:replace']
                self.repeatList.append(lambda x,y: sax.saxutils.escape(str(evalKey(replace,x))))
                self.inReplace = True
                self.replaceDepth = self.depth
            except KeyError:
                pass
            try:
                replace = attrs['t:replaceMarkup']
                self.repeatList.append(lambda x,y: str(evalKey(replace,x)))
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
            function = evalKey(functionKey, self.data)
            hide = function(evalKey(ifKey, self.data), parameter)
            if ifInvert:
                hide = not hide
            self.output.append('<'+name)
            for key in attrs.keys():
                if not (key in ['t:hideIfKey','t:hideIfNotKey','t:hideFunctionKey','t:hideParameter','style']):
                    self.output.append(' '+key+'='+self.quoteAndFillAttr(attrs[key],self.data))
            if hide:
                self.output.append(' style="display:none">')
            else:
                self.output.append('>')
                
        elif 't:replace' in attrs.keys():
                replace = attrs['t:replace']
                self.output.append(sax.saxutils.escape(str(evalKey(replace,self.data))))
                self.inReplace = True
                self.replaceDepth = self.depth      
        elif 't:replaceMarkup' in attrs.keys():
                replace = attrs['t:replaceMarkup']
                self.output.append(str(evalKey(replace,self.data)))
                self.inReplace = True
                self.replaceDepth = self.depth      
        elif name == 't:dynamicviews':
            self.inDynamicViews = True
        elif name == 't:view' and self.inDynamicViews:
            self.viewName = attrs['name']
            self.viewKey = attrs['key']
            self.filterKey = None
            self.filterInvert = False
            self.filterFunc = None
            self.filterParam = None
            self.sortKey = None
            self.sortFunc = None
            self.sortInvert = False
            self.inView = True
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
            self.filterParam = attrs['parameter']
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
            f = open(resource.path('templates/'+attrs['filename']),'r')
            html = f.read()
            f.close()
            self.output.append(html)
        else:
            self.output.append('<'+name)
            for key in attrs.keys():
                self.output.append(' '+key+'='+self.quoteAndFillAttr(attrs[key],self.data))
            self.output.append('>')

    def endElement(self,name):
        if self.inReplace and self.depth == self.replaceDepth:
            if self.inRepeatView:
                self.repeatList.append(lambda x,y: '</'+name+'>')
            else:
                self.output.append('</'+name+'>')
            self.inReplace = False
        elif self.inRepeatView and self.depth == self.repeatDepth:
            self.inRepeatView = False
            self.repeatList.append(lambda x,y: '</'+name+'>')

            #FIXME: This loop may be worth optimizing--we spend 40% of our time here
            startTime = time.clock()
            localData = copy.copy(self.data)
            for item in self.repeatView:
                localData['this'] = item.object
                self.output[len(self.output):] = map(lambda x:x(localData,item.tid),self.repeatList)
            endTime = time.clock()
            print "Repeat took "+str(endTime-startTime)
            repeatId = generateId()
            self.output.append('<span id='+sax.saxutils.quoteattr(repeatId)+'/>')
            repeatView = self.repeatView
            repeatList = self.repeatList
            localData = copy.copy(self.data)
            self.handle.addView(repeatId, 'nextSibling', repeatView, repeatList, localData)
        elif self.inRepeatView:
            self.repeatList.append(lambda x,y: '</'+name+'>')
        elif name == 't:dynamicviews':
            self.inDynamicViews = False
        elif name == 't:view':
            self.inView = False
            self.handle.makeNamedView(self.viewName, self.viewKey, 
                                 self.filterKey, self.filterFunc, 
                                 self.filterParam, self.filterInvert,
                                 self.sortKey, self.sortFunc, self.sortInvert,
                                 self.data)
        elif name == 't:include':
            pass
        elif name == 't:filter':
            pass
        elif name == 't:sort':
            pass
        else:
            self.output .append('</'+name+'>')
        self.depth -= 1

    def characters(self,data):
        if self.inReplace:
            pass
        elif self.inRepeatView:
            self.repeatList.append(lambda x,y: sax.saxutils.escape(data))
        else:
            self.output.append(sax.saxutils.escape(data))

    def makeReplaceFunc(self,key,value):
        return lambda x, y:' '+key+'='+self.quoteAndFillAttr(value,x)


# View mapping function used to assign ID attributes to records so
# that we can find them in the page after we generate them if we need
# to update them.
class idAssignment:
    def __init__(self, x):
        self.object = x
        self.tid = generateId()    

###############################################################################
#### Generating Javascript callbacks to keep document updated              ####
###############################################################################

# Object representing a set of registrations for Javascript callbacks when
# the contents of some set of database views change. One of these Handles
# is returned whenever you fill a template; when you no longer want to
# receive Javascript callbacks for a particular filled template, call
# this object's unlinkTemplate() method.
class Handle:
    def __init__(self, execJS, document = None):
        # 'execJS' is a function that will be called with a text
        # string to indicate Javascript to execute. 'document', if
        # non-None, is a DOM document objects that will be unlink()ed
        # when unlinkTemplate() is called on this handle.
        self.execJS = execJS
        self.document = document
        self.hideConditions = []
        self.namedViews = {}
        self.trackedViews = []

    def addHideCondition(self, id, predicate):
        # Make JS calls to hide and show the node with the give id when
        # predicate becomes true and false, respectively.
        self.hideConditions.append((id, predicate, predicate()))
        None

    def checkHides(self):
        # Internal use.
        if self.execJS:
            for i in range(0,len(self.hideConditions)):
                (id, predicate, previous) = self.hideConditions[i]
                current = predicate()
                if (current == True) != (previous == True):
                    self.hideConditions[i] = (id, predicate, current)
                    self.execJS("%sItem(\"%s\")" % (current and "hide" or "show", id))

    def makeNamedView(self, name, viewKey, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort, data):
        if self.namedViews.has_key(name):
            raise TemplateError, "More than one view was declared with the name '%s'. Each view must have a different name." % name
        nv = NamedView(name, viewKey, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort, data)
        self.namedViews[name] = nv
        return nv.getView()

    def findNamedView(self, name):
        if not self.namedViews.has_key(name):
            raise TemplateError, "A view named '%s' was referenced but not defined." % name
        return self.namedViews[name]

    def addView(self, anchorId, anchorType, view, templateFuncs, data):
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
        tv = TrackedView(anchorId, anchorType, view, templateFuncs, data, self)
        self.trackedViews.append(tv)
        None

    def unlinkTemplate(self):
        # Stop delivering callbacks, allowing the handle to be released.
        self.execJS = None
        try:
            self.document.unlink()
        except:
            pass
        self.document = None
        self.hideConditions = []
        self.trackedViews = []

# Class used by Handle to track the dynamically filterable, sortable
# views created by makeNamedView and identified by names. After
# creation, can be looked up with Handle.findNamedView and the filter
# and sort changed with setFilter and setSort.
class NamedView:
    def __init__(self, name, viewKey, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort, data):
        self.name = name
        self.data = data
        self.view = evalKey(viewKey, data)
        if filterKey != None:
            self.filter = self.makeFilter(filterKey, filterFunc, filterParameter, invertFilter)
            self.view = self.view.filter(lambda x: self.filter(x))
        if sortKey != None:
            self.sort = self.makeSort(sortKey, sortFunc, invertSort)
            self.view = self.view.sort(lambda x, y: self.sort(x, y))
        
    def setFilter(self, fieldKey, funcKey, parameter, invert):
        if not self.filter:
            raise TemplateError, "View '%s' was not declared with a filter, so it is not possible to change the filter parameters" % self.name
        self.filter = self.makeFilter(fieldKey, funcKey, parameter, invert)

    def setSort(self, fieldKey, funcKey, invert):
        if not self.sort:
            raise TemplateError, "View '%s' was not declared with a sort, so it is not possible to change the sort parameters." % self.name
        self.sort = self.makeSort(fieldKey, funcKey, invert)

    def makeFilter(self, fieldKey, funcKey, parameter, invert):
        # Internal use.
        func = evalKey(funcKey, self.data)
        if not invert:
            return lambda x: func(evalKey(fieldKey, x), parameter)
        else:
            return lambda x: not func(evalKey(fieldKey, x), parameter)

    def makeSort(self, fieldKey, funcKey, invert):
        # Internal use.
        func = evalKey(funcKey, self.data)
        if not invert:
            return lambda x,y:  func(evalKey(fieldKey,x), evalKey(fieldKey,y)) 
        else:
            return lambda x,y: -func(evalKey(fieldKey,x), evalKey(fieldKey,y))

    def getView(self):
        # Internal use.
        return self.view

# Class used internally by Handle to track a t:repeatForSet clause.
class TrackedView:
    def __init__(self, anchorId, anchorType, view, templateFuncs, templateData, parent):
        # arguments as Handle.addView(), plus 'parent', a pointer to the Handle
        # that is used to invoke execJS and checkHides
        self.anchorId = anchorId
        self.anchorType = anchorType
        # Map view through identity so that we get our own private
        # copy to attach our callbacks to, such that when we drop
        # our reference to the view the callbacks go away
        self.view = view.map(lambda x: x)
        self.templateFuncs = templateFuncs
        self.templateData = templateData
        self.parent = parent

        view.addChangeCallback(lambda index: self.onChange(index))
        view.addAddCallback(lambda newIndex: self.onAdd(newIndex))
        view.addRemoveCallback(lambda oldObject, oldIndex: self.onRemove(oldObject, oldIndex))

    def currentXML(self, index):
        output = []
        item = self.view[index]
        data = copy.copy(self.templateData)
        data['this'] = item.object
        for func in self.templateFuncs:
            output.append(func(data,item.tid))
        return ''.join(output)

    def onChange(self, index):
        if self.parent.execJS:
            self.parent.execJS("changeItem(\"%s\",\"%s\")" % (self.view[index].tid, quoteJS(self.currentXML(index))))
        self.parent.checkHides()

    def onAdd(self, newIndex):
        if self.parent.execJS:
            if newIndex + 1 == self.view.len():
                # Adding it at the end of the list. Must add it relative to
                # the anchor.
                if self.anchorType == 'parentNode':
                    self.parent.execJS("addItemAtEnd(\"%s\",\"%s\")" % (quoteJS(self.currentXML(newIndex)), self.anchorId))
                if self.anchorType == 'nextSibling':
                    self.parent.execJS("addItemBefore(\"%s\",\"%s\")" % (quoteJS(self.currentXML(newIndex)), self.anchorId))
            else:
                self.parent.execJS("addItemBefore(\"%s\",\"%s\")" % (quoteJS(self.currentXML(newIndex)), self.view[newIndex+1].tid))

        self.parent.checkHides()

    def onRemove(self, oldObject, oldIndex):
        if self.parent.execJS:
            self.parent.execJS("removeItem(\"%s\")" % oldObject.tid)
        self.parent.checkHides()

###############################################################################
#### Utility routines                                                      ####
###############################################################################

# Generate an arbitrary string to use as an ID attribute.
def generateId():
    return "tmpl%08d" % random.randint(0,99999999)

# Perform escapes needed for Javascript string contents.
def quoteJS(x):
    x = re.compile("\\\\").sub("\\\\", x)  #       \ -> \\
    x = re.compile("\"").  sub("\\\"", x)  #       " -> \"
    x = re.compile("'").   sub("\\'", x)   #       ' -> \'
    x = re.compile("\n").  sub("\\\\n", x) # newline -> \n
    x = re.compile("\r").  sub("\\\\r", x) #      CR -> \r
    return x

# 'key' is a key name in the template language. Resolve it relative to 'data.'
# For example, 'this feed name' might become data['this'].feed.name().
def evalKey(key, data, originalKey = None):
#    print "eval %s against %s" % (str(key),str(data))
    # Save the original expression for use in error messages
    if originalKey == None:
        originalKey = key

    keys = key.split()

    for key in keys:
        if type(data) == types.DictType:
            try:
                data = data[key]
            except KeyError:
                return 'Bad Key'
                #raise TemplateError, "Bad key '%s': dictionary '%s' does not contain an element '%s'." % (originalKey, data, key)

        elif type(data) == types.InstanceType:
            try:
                data = getattr(data, key)
            except AttributeError:
                return 'Bad Key'
                #raise TemplateError, "Bad key '%s': object '%s' does not have an attribute '%s'." % (originalKey, data, key)

            if type(data) == types.MethodType:
                data = data()
        else:
            # The template tried to index into something that we don't
            # consider a container for template filling purposes (eg,
            # 'this feed name contents')
            return 'Bad key'
            #raise TemplateError, "Bad key '%s': object '%s' has no subkeys. (Remainder of expression: '%s'." % (originalKey, data, key)

    return data

###############################################################################
###############################################################################
