from xml.dom.minidom import parse, parseString
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
# - If two tags with t:repeatForView appear as adjacent children of a node,
#   the results are undefined.

# To Do:
# - Take a lock around the entire database while template is being filled
# - Improve error handling (currently some random exception is thrown if
#   the template is poorly structured)

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
    document = parse(resource.path("templates/%s" % file))
    handle = Handle(execJS, document)
    transformDocument(document.documentElement, data, handle)
    #print "----\n%s----\n" % document.toxml()
    return (document.toxml(), handle)

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

def transformDocument(node, data, handle):
    # Pull the view declarations out of the headers. Create named views for
    # them.
    viewLists = node.getElementsByTagName("t:dynamicviews")
    if viewLists.length != 0:
	# Only one list is allowed per document
	if viewLists.length != 1:
	    raise TemplateError, "<t:dynamicviews> may occur only once in a template"
	viewList = viewLists.item(0)

	# Create each view
	for n in viewList.childNodes:
	    if n.nodeName == "t:view":
		# Get the name assigned to the view, and the key for
		# the actual database object it is supposed to show
		viewName = n.getAttribute("name")
		viewKey = n.getAttribute("key")
		if viewName == "" or viewKey == "":
		    raise TemplateError, "<t:view> requires a 'name' attribute"

		# Pull out filtering and sorting instructions
		filterKey = filterFunc = filterParameter = invertFilter = None
		sortKey = sortFunc = invertSort = None
		
		fs = n.getElementsByTagName("t:filter")
		if fs.length != 0:
		    if fs.length != 1:
			raise TemplateError, "<t:filter> may occur only once inside <t:view>"
		    f = fs.item(0)
		    filterKey = f.getAttribute("key")
		    filterFunc = f.getAttribute("functionkey")
		    filterParameter = f.getAttribute("parameter")
		    invertFilter = f.getAttribute("invert")
		    if filterFunc == "": # "" is a legal filterKey
			raise TemplateError, "<t:filter> requires 'functionkey' attribute"
		    invertFilter = invertFilter not in ["", "false", "0"]

		ss = n.getElementsByTagName("t:sort")
		if ss.length != 0:
		    if fs.length != 1:
			raise TemplateError, "<t:sort> may occur only once inside <t:view>"
		    s = ss.item(0)
		    sortKey = s.getAttribute("key")
		    sortFunc = s.getAttribute("functionkey")
		    invertSort = s.getAttribute("invert")
		    if sortFunc == "": # "" is a legal sortKey
			raise TemplateError, "<t:sort> requires a 'functionkey' attribute"
		    invertSort = invertSort not in ["", "false", "0"]
		    
		# Create the named view
		handle.makeNamedView(viewName, viewKey, filterKey, filterFunc,
				     filterParameter, invertFilter, sortKey,
				     sortFunc, invertSort, data)

	# Delete the declarations from the output document
	viewList.parentNode.removeChild(viewList)

    # Now that views are set up, fill the template
    transformTopNode(node, data, handle)

# View mapping function used to assign ID attributes to records so
# that we can find them in the page after we generate them if we need
# to update them.
class idAssignment:
    def __init__(self, x):
	self.object = x
	self.tid = generateId()

# 'node' is a DOM node that is not inside a t:repeatForView template. Modify
# the DOM tree in place according to processing instructions and record any
# dynamic event hooks in 'handle.' Transformation must be idempotent, because
# some nodes may get processed twice.
def transformTopNode(node, data, handle):
    if node.nodeType == node.ELEMENT_NODE:

	# Handle i18n translation
	#
	# For now, we're using the translate and name attributes found on this
	# page to handle translation. 
	# http://www.zope.org/DevHome/Wikis/DevSite/Projects/ComponentArchitecture/ZPTInternationalizationSupport
	#
	# Eventually, we may add support for more attributes
	if 'i18n:translate' in node.attributes.keys():

	    # Convert the node's children to a string, storing child
	    # elements for later
	    translateString = ''
	    children = {}
	    for child in node.childNodes:
		if child.nodeType == child.TEXT_NODE:
		    translateString += child.nodeValue
		if child.nodeType == child.ELEMENT_NODE and 'i18n:name' in child.attributes.keys():
		    translateString += '${'+child.getAttribute('i18n:name')+'}'
		    children[child.getAttribute('i18n:name')] = child.cloneNode(True)

	    # Remove all of the children
	    while len(node.childNodes)>0:
		node.removeChild(node.firstChild)

	    # Perform the actual translation
	    translation = _(translateString)

	    # Recreate the node's children based on the translation
	    nameReg = re.compile('^\$\{.*?\}$')
	    m = re.compile('(.*?)(\$\{.*?\})(.*?)').findall(translation)
	    for regMatch in m:
		for text in regMatch:
		    if None == nameReg.search(text) and len(text)>0:
			node.appendChild(node.ownerDocument.createTextNode(text))
		    elif len(text)>0:
			node.appendChild(children[text[2:-1]])
		
	# Handle t:include element
	if node.nodeName == "t:include":
	    newNode = parse(resource.path("templates/%s" % node.getAttribute('filename'))).documentElement
	    node.parentNode.replaceChild(newNode, node)
	    transformTopNode(newNode, data, handle)
	    return

	# Handle t:repeatForView attribute
	viewName = node.getAttribute('t:repeatForView')
	if viewName:
	    node.removeAttribute('t:repeatForView')
		
	    # Find the view by its name, and assign local unique IDs
	    # to each element
	    view = handle.findNamedView(viewName).getView().map(idAssignment)

	    # Determine if 'node' is the last sibling in its parent,
	    # neglecting a possible trailing text node comprised entirely
	    # of whitespace
	    atEnd = not node.nextSibling
	    if node.nextSibling and (node.nextSibling.nextSibling == None):
		n = node.nextSibling
		if n.nodeType == n.TEXT_NODE:
		    if re.compile("[ \n]+$").match(n.nodeValue):
			atEnd = True

	    # Find an adjacent node to use as a reference point
	    anchorNode = None
	    anchorType = None
	    if atEnd:
		anchorNode = node.parentNode
		anchorType = 'parentNode'
	    else:
		anchorNode = node.nextSibling
		anchorType = 'nextSibling'

		# Can't put an id on text elements; however, anywhere a
		# text element is legal, a span is probably legal, so make
		# a no-op span.
		if anchorNode.nodeType != anchorNode.ELEMENT_NODE:
		    span = anchorNode.ownerDocument.createElement("span")
		    anchorNode.parentNode.insertBefore(span, anchorNode)
		    anchorNode = span

	    # Make sure that node has a unique id
	    anchorId = generateId()
	    if anchorNode.getAttribute('id'):
		anchorId = anchorNode.getAttribute('id')
	    else:
		anchorNode.setAttribute('id', anchorId)

	    # Populate with initial contents
	    localData = copy.copy(data)
	    for index in range(0,view.len()):
		# Get a node for this item
		item = view[index]
		localData['this'] = item.object
		newNode = node.cloneNode(True)
		transformInnerNode(newNode, localData)
		newNode.setAttribute('id', item.tid)

		# Add to tree
		node.parentNode.insertBefore(newNode,node)

	    # Register for Javascript updates
	    handle.addView(anchorId, anchorType, view, node, data)

	    # Remove template node from document
	    node.parentNode.removeChild(node)
	    return

	# Handle dynamic hiding attributes
	hideName = "t:hideIfViewEmpty"
	hideInvert = False
	if not node.getAttribute(hideName):
	    hideName = "t:hideIfViewNotEmpty"
	    hideInvert = True
	if node.getAttribute(hideName):
	    viewName = node.getAttribute(hideName)
	    node.removeAttribute(hideName)
	    view = handle.findNamedView(viewName).getView()
	    basicFunc = lambda: view.len() == 0
	    # we need to do a name dance beause of how python binds in lambda
	    func = basicFunc 
	    if hideInvert:
		func = (lambda: not basicFunc())
	    id = generateId()
	    node.setAttribute('id',id)
	    handle.addHideCondition(id, func)
	    if func():
		if node.getAttribute('style'):
		    node.setAttribute("style","%; display:none" % node.getAttribute('style'))
		else:
		    node.setAttribute("style","display:none")

    # Handle t:Replace and @@@attribute value replacements@@@
    performSubstitutions(node, data)

    for child in node.childNodes:
	transformTopNode(child, data, handle)

# As transformTopNode, but perform only transformations that don't
# install JS hooks and thus are appropriate even if we are inside a
# t:repeatForSet template.
def transformInnerNode(node, data):
    # Handle t:include element inside template
    if node.nodeName == "t:include":
	newNode = parse(resource.path("templates/%s" % node.getAttribute('filename'))).documentElement
	node.parentNode.replaceChild(newNode, node)
	transformInnerNode(newNode, data)
	return

    # Handle t:Replace and @@@attribute value replacements@@@
    performSubstitutions(node, data)

    for child in node.childNodes:
	transformInnerNode(child, data)

# Common code (t:Replace and @@@-substitutions) between the two recursive
# transformation functions.
def performSubstitutions(node, data):
    if node.nodeType != node.ELEMENT_NODE:
	return

    # Handle t:Replace attribute
    replaceKey = node.getAttribute('t:replace')
    if replaceKey:
	node.removeAttribute('t:replace')
	for child in node.childNodes:
	    node.removeChild(child)
	node.appendChild(node.ownerDocument.createTextNode(str(evalKey(replaceKey, data))))

    # Handle t:ReplaceMarkup attribute
    replaceKey = node.getAttribute('t:replaceMarkup')
    if replaceKey:
	node.removeAttribute('t:replaceMarkup')
	for child in node.childNodes:
	    node.removeChild(child)
	markup = evalKey(replaceKey, data)
	try:
	    newDocument = parseString(markup)
	    newNode = newDocument.documentElement.cloneNode(True)
	    node.appendChild(newNode)
	except:
	    print "Invalid XHTML: "+markup
	    traceback.print_exc()

    # Substitute Replacements in attribute values
    attrs = node.attributes
    pattern = re.compile("^(.*)@@@(.*?)@@@(.*)$");
    if attrs:
	for index in range(0, attrs.length):
	    name = attrs.item(index).nodeName
	    value = attrs.item(index).nodeValue

	    while True:
		match = pattern.match(value)
		if not match:
		    break
		value = match.group(1) + str(evalKey(match.group(2), data)) + match.group(3)

	    node.setAttribute(name, value)

    # Handle t:hideIf and t:hideIfNot attributes
    # NEEDS: method for allowing null keys?
    ifName = "t:hideIfKey"
    ifInvert = False
    if not node.getAttribute(ifName):
	ifName = "t:hideIfNotKey"
	ifInvert = True
    ifKey = node.getAttribute(ifName)
    if ifKey:
	# Get arguments
	functionKey = node.getAttribute("t:hideFunctionKey")
	parameter = node.getAttribute("t:hideParameter")
	if functionKey == "": # "" is a legal parameter
	    raise TemplateError, "%s requires 't:hideFunctionKey' attribute" % ifName

	# Evaluate function to decide whether to hide the node
	function = evalKey(functionKey, data)
	hide = function(evalKey(ifKey, data), parameter)
	if ifInvert:
	    hide = not hide

	# If the result of the above is that the node should be hidden,
	# delete it.
	# NEEDS: Think through the interactions this may have with
	# other templating features. For example, could it happen that
	# a node gets deleted that has an 'id' attribute that we're
	# expecting to reference later?
	if hide:
	    node.parentNode.removeChild(node)
	else:
	    # Didn't need to delete it. Just strip off the processing
	    # instructions.
	    node.removeAttribute(ifName)
	    node.removeAttribute("t:hideFunctionKey")
	    if parameter:
		node.removeAttribute("t:hideParameter")

###############################################################################
#### Generating Javascript callbacks to keep document updated              ####
###############################################################################

# Object representing a set of registrations for Javascript callbacks when
# the contents of some set of database views change. One of these Handles
# is returned whenever you fill a template; when you no longer want to
# receive Javascript callbacks for a particular filled template, call
# this object's unlinkTemplate() method.
class Handle:
    def __init__(self, execJS, document):
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

    def addView(self, anchorId, anchorType, view, node, data):
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
	tv = TrackedView(anchorId, anchorType, view, node.cloneNode(True), data, self)
	self.trackedViews.append(tv)
	None

    def unlinkTemplate(self):
	# Stop delivering callbacks, allowing the handle to be released.
	self.execJS = None
	self.document.unlink()
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
    def __init__(self, anchorId, anchorType, view, templateNode, templateData, parent):
	# arguments as Handle.addView(), plus 'parent', a pointer to the Handle
	# that is used to invoke execJS and checkHides
	self.anchorId = anchorId
	self.anchorType = anchorType
	# Map view through identity so that we get our own private
	# copy to attach our callbacks to, such that when we drop
	# our reference to the view the callbacks go away
	self.view = view.map(lambda x: x)
	self.templateNode = templateNode
	self.templateData = templateData
	self.parent = parent

	view.addChangeCallback(lambda index: self.onChange(index))
	view.addAddCallback(lambda newIndex: self.onAdd(newIndex))
	view.addRemoveCallback(lambda oldObject, oldIndex: self.onRemove(oldObject, oldIndex))

    def currentXML(self, index):
	item = self.view[index]
	data = copy.copy(self.templateData)
	data['this'] = item.object
	node = self.templateNode.cloneNode(True)
	transformInnerNode(node, data)
	node.setAttribute('id', item.tid)
	return node.toxml()

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
    
    # Pull off the first word
    match = key and re.compile('^\s*([^\s]+)(\s.*)?$').match(key) or None
    if not match: # no non-space characters -- the end of the key
	return data
    thisKey = match.group(1)
    rest = match.group(2)

    # Resolve the key word relative to the value we have so far
    if type(data) == types.DictType:
	try:
	    value = data[thisKey]
	except KeyError:
	    raise TemplateError, "Bad key '%s': dictionary '%s' does not contain an element '%s'." % (originalKey, data, thisKey)
	return evalKey(rest, value, originalKey)

    elif type(data) == types.InstanceType:
	try:
	    attr = getattr(data, thisKey)
	except AttributeError:
	    raise TemplateError, "Bad key '%s': object '%s' does not have an attribute '%s'." % (originalKey, data, thisKey)

	if type(attr) == types.MethodType:
	    return evalKey(rest, attr(), originalKey)
	else:
	    return evalKey(rest, attr, originalKey)

    else:
	# The template tried to index into something that we don't
	# consider a container for template filling purposes (eg,
	# 'this feed name contents')
	raise TemplateError, "Bad key '%s': object '%s' has no subkeys. (Remainder of expression: '%s'." % (originalKey, data, key)

###############################################################################
###############################################################################
