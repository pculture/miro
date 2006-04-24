# template_compiler.py Copyright (c) 2005,2006 Participatory Culture Foundation
#
# "Compiles" Democracy templates to Python


###############################################################################
#### Functions used in repeating templates                                 ####
###############################################################################

# These are functions that take in a dictionary to local data, an id,
# and an argument and return text to be added to the template

# Simply returns text
def genRepeatText(varname, tid, text):
    return '    %s.write(%s)\n' % (varname, repr(text))

# Returns text if function does not evaluate to true
def genRepeatTextHide(varname, tid, args):
    (functionKey,ifKey,parameter,invert, text) = args
    if invert:
        out = '    if not evalKey(%s, data)(evalKey(%s, data), %s):\n'%(
            repr(functionKey), repr(ifKey), repr(parameter))
    else:
        out = '    if evalKey(%s, data)(evalKey(%s, data), %s):\n'%(
            repr(functionKey), repr(ifKey), repr(parameter))
    out = '%s        %s.write(%s)\n' % (out, varname, repr(text))
    return out
        
def genQuoteAttr(varname, tid, value):
    return '    %s.write(quoteattr(urlencode(toUni(evalKey(%s,data)))))\n'%(
        varname, repr(value))

def genRawAttr(varname, tid, value):
    return '    %s.write(quoteattr(toUni(evalKey(%s,data))))\n'%(
        varname, repr(value))

# Adds an id attribute to a tag and closes it
def genRepeatAddIdAndClose(varname, tid, args):
    return '    %s.write(" id=\"%s\">")\n' % (varname, quoteattr(tid))

# Evaluates key with data
def genRepeatEvalEscape(varname, tid, replace):
    return '    %s.write(escape(evalKey(%s,data)))\n' % (
        varname, repr(replace))

# Evaluates key with data
def genRepeatEval(varname, tid, replace):
    return '    %s.write(toUni(evalKey(%s,data)))\n' % (
        varname, repr(replace))

# Returns include iff function does not evaluate to true
def genRepeatIncludeHide(varname, tid, args):
    (functionKey,ifKey,parameter,invert, name) = args
    f = open(resource.path('templates/%s'%name),'r')
    text = f.read()
    f.close()
    if invert:
        out = '    if not evalKey(%s, data)(evalKey(%s, data), %s):\n'%(
            repr(functionKey), repr(ifKey), repr(parameter))
    else:
        out = '    if evalKey(%s, data)(evalKey(%s, data), %s):\n'%(
            repr(functionKey), repr(ifKey), repr(parameter))
    out = '%s        %s.write(%s)\n' % (out, varname, repr(text))
    return out

def genHideIfEmpty(varname, tid, args):
    (viewName, name, invert, attrs) = args
    nodeId = generateId()
    
    out = '    %s.write("<%s")\n'%(varname,name)
    for key in attrs.keys():
        if not key in ['t:hideIfViewEmpty','t:hideIfViewNotEmpty','style']:
            out = '%s    %s.write(" %s=")\n'%(out,varname,key)
            out = '%s    %s.write(quoteAndFillAttr("%s",data))\n'%(out,varname,attrs[key])
    out = '%s    %s.write(" id=\\\"%s\\\"")\n'%(out,varname,quoteattr(nodeId))
    
    if invert:
        out = '%s    if handle.findNamedView("%s").getView().len() > 0:\n' % (
            out, viewName)
    else:
        out = '%s    if handle.findNamedView("%s").getView().len() == 0:\n' % (
            out, viewName)
    out = '%s        %s.write(" style=\\\"display:none\\\">")\n' % (
        out, varname)
    out = '%s    else:\n        %s.write(">")\n' % (
        out, varname)

    out = '%s    handle.addHideIfEmpty(%s,%s,%s)\n' % (
        out, repr(nodeId), repr(viewName), repr(invert))
    return out

def genHideSection(varname, tid, args):
    (functionKey,ifKey,parameter,invert, funcList) = args
    if invert:
        out = '    if evalKey(%s, data)(evalKey(%s, data), %s):\n'%(
            repr(functionKey), repr(ifKey), repr(parameter))
    else:
        out = '    if not evalKey(%s, data)(evalKey(%s, data), %s):\n'%(
            repr(functionKey), repr(ifKey), repr(parameter))
    out = '%s        for (func, args) in %s:\n' % (out, repr(funcList))
    out = '%s            %s.write(funcTable[func](data,%s,args))\n' % (out, varname, repr(tid))
    return out

def genQuoteAndFillAttr(varname, tid, value):
    return '    %s.write(quoteAndFillAttr(%s,data))\n' % (varname, repr(value))

compileTable = [genRepeatText,genRepeatTextHide,genQuoteAttr,genRepeatAddIdAndClose,genRepeatEvalEscape,genRepeatEval,genRepeatIncludeHide, genHideIfEmpty, genRawAttr, genHideSection, genQuoteAndFillAttr]

from xml import sax
from xhtmltools import toUTF8Bytes
from StringIO import StringIO
from templatehelper import quoteattr, escape, HTMLPattern, attrPattern, resourcePattern, rawAttrPattern, generateId, textFunc, textHideFunc, attrFunc, addIDFunc, evalEscapeFunc, evalFunc, includeHideFunc, hideIfEmptyFunc, rawAttrFunc, hideSectionFunc, quoteAndFillFunc
import re
import os

#Setup gettext
#gettext.install('dtv', 'resources/gettext')

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

class res:
    def path(self, rel_path):
        global resourcePath
        return os.path.join(resourcePath, rel_path)

resource = res()

def setResourcePath(path):
    global resourcePath
    resourcePath = path

###############################################################################
#### Public interface                                                      ####
###############################################################################

#
# Compile the template given in inFile to python code in outFile
#
def compileTemplate(inFile, top = True, onlyBody = False):
    handle = MetaHandle()
    tcc = TemplateContentCompiler(handle, onlyBody = onlyBody)
    p = sax.make_parser()
    p.setFeature(sax.handler.feature_external_ges, False)
    p.setContentHandler(tcc)
    p.parse(resource.path("templates/%s" % inFile))
    return (tcc, handle)      

# Returns a list of templates with URLs relative to the template
# resource directory
def findTemplates(root):
    templates = []
    tpath = os.path.join(root,'resources','templates')
    for r, dirs, files in os.walk(tpath):
        for template in files:
            # Find the path relative to the resource directory
            fullpath = os.path.join(r,template)
            template = fullpath[len(tpath)+1:]
            if (template.find('.svn') == -1 and
                not (template.startswith('#') or template.endswith('~') or
                     template.endswith('.js') or template.endswith('.html'))):
                templates.append(template)
    return templates

def compileAllTemplates(root):
    manifest = file(os.path.join(root,'portable','compiled_templates','__init__.py'),'wb')
    setResourcePath(os.path.join(root,'resources'))
    manifest = open(os.path.join(root,'portable','compiled_templates','__init__.py'),'wb')
    manifest.write('# This is a generated file. Do not edit.\n\n')
        
    for template in findTemplates(root):
        outFile = os.path.join(root,'portable','compiled_templates',template.replace('-','_')+'.py')
        print "Compiling %s template to %s" % (template, outFile)
        (tcc, handle) = compileTemplate(template)
        outDir = os.path.dirname(outFile)
        try:
            os.makedirs(outDir)
        except:
            pass

        try:
            open(os.path.join(outDir,'__init__.py'), "r")
        except:
            package = open(os.path.join(outDir,'__init__.py'), "wb")
            package.write('# This is a generated file. Do not edit.\n\n')
            package.close()
        f = open(outFile,"wb")
        f.write(tcc.getOutput())
        f.close()
        manifest.write("import %s\n" % template.replace('/','.').replace('\\','.').replace('-','_'))
    manifest.close()

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
class TemplateContentCompiler(sax.handler.ContentHandler):
    def __init__(self, handle, debug = False, onlyBody = False):
        self.handle = handle
        self.debug = debug
        self.onlyBody = onlyBody

    def getOperationList(self):
        return self.outputList
        
    def getOutput(self, data = None):
        fo = StringIO()
        self.render(fo)
        return fo.getvalue()

    def render(self, fileobj):
        fileobj.write('# This is a generated file. Do not edit.\n')
        fileobj.write('from template import Handle, fillAttr, quoteAndFillAttr, funcTable\n')
        fileobj.write('from IOBuffer import IOBuffer\n')
        fileobj.write('from xhtmltools import urlencode\n')
        fileobj.write('from templatehelper import quoteattr, escape, evalKey, toUni\n')
        fileobj.write('def fillTemplate(data, domHandler):\n')
        self.handle.render(fileobj)
        fileobj.write('\n\n    out = IOBuffer()\n')
        
        if not self.onlyBody:
            fileobj.write('    out.write("<?xml version=\\\"1.0\\\" encoding=\\\"UTF-8\\\"?>\\n<!DOCTYPE html PUBLIC \\\"-//W3C//DTD XHTML 1.0 Strict//EN\\\" \\\"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd\\\">\\n")\n')
            
        for count in range(len(self.outputList)):
            (func, args) = self.outputList[count]
            fileobj.write(compileTable[func]('out','',args))

        fileobj.write('    out.close()\n')        
        fileobj.write('\n\n    return (out, handle)\n')

    def returnIf(self,bool,value):
        if bool:
            return value
        else:
            return ''

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
        self.hiding = False
        self.hideDepth = []
        self.depth = 0
        self.repeatName = ''
        self.started = not self.onlyBody
        self.outputList = []
        self.outputText = []
        self.hidingList = []
        self.hidingParams = []

        # When we're in repeat mode, we store output as a set of
        # functions and arguments that, called given an object, tid,
        # and set of arguments return the correct output
        self.repeatList = []

        # We store repeat text here before turning it into an item in
        # repeatList. 
        self.repeatText = []

    def endDocument(self):
        self.endText()

    def startElement(self,name, attrs):
        self.depth = self.depth + 1
        if self.onlyBody and not self.started:
            if name == 'body':
                self.started = True
        elif not self.started:
            pass
        elif self.inReplace or self.inStaticReplace:
            pass
        elif 't:hideIfViewEmpty' in attrs.keys() or 't:hideIfViewNotEmpty' in attrs.keys():
            if 't:hideIfViewEmpty' in attrs.keys():
                viewName = attrs['t:hideIfViewEmpty']
                ifInvert = False
            else:
                viewName = attrs['t:hideIfViewNotEmpty']
                ifInvert = True
            self.addHideIfEmpty(viewName, name, ifInvert, attrs)
        elif 't:repeatForView' in attrs.keys():
            self.inRepeatView = True
            self.repeatDepth = self.depth
            self.resetRepeat()
            self.addRepeatText('<%s'%name)
            for key in attrs.keys():
                if key != 't:repeatForView':
                    self.addRepeatAttr(key,attrs[key])
            self.addRepeatAddIdAndClose()

            self.repeatName = attrs['t:repeatForView']

        elif 't:updateForView' in attrs.keys():
            self.inUpdateView = True
            self.repeatDepth = self.depth
            self.resetRepeat()
            self.addRepeatText('<%s'%name)
            for key in attrs.keys():
                if key != 't:updateForView':
                    self.addRepeatAttr(key,attrs[key])
            self.addRepeatAddIdAndClose()

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
                    self.addRepeatIncludeHide(functionKey,ifKey,parameter,ifInvert,attrs['filename'])
                else:
                    self.addRepeatFillTemplate(attrs['filename'])
            elif name == 't:include':
                if hide:
                    self.addRepeatIncludeHide(functionKey,ifKey,parameter,ifInvert,attrs['filename'])
                else:
                    self.addRepeatInclude(attrs['filename'])
            else:
                self.addRepeatText('<%s'%name)
                for key in attrs.keys():
                    if not (key in ['t:replace','t:replaceMarkup','t:hideIfKey',
                               't:hideIfNotKey','t:hideFunctionKey',
                               't:hideParameter','style']):
                        self.addRepeatAttr(key,attrs[key])

                if hide:
                    #self.addRepeatText(' style="display:none"')
                    self.addRepeatTextHide(functionKey,ifKey,parameter,ifInvert,' style="display:none"')

                self.addRepeatText('>')
                try:
                    replace = attrs['t:replace']
                    self.addRepeatEvalEscape(replace)
                    self.inReplace = True
                    self.replaceDepth = self.depth
                except KeyError:
                    pass
                try:
                    replace = attrs['t:replaceMarkup']
                    self.addRepeatEval(replace)
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
            self.startHiding(functionKey,ifKey,parameter,ifInvert)

            self.addText('<%s'%name)
            #self.addTextHide(functionKey,ifKey,parameter,ifInvert, ' style="display:none"')
            for key in attrs.keys():
                if not (key in ['t:hideIfKey','t:hideIfNotKey','t:hideFunctionKey','t:hideParameter']):
                    self.addAttr(key,attrs[key])
            self.addText('>')

        elif 't:replace' in attrs.keys():
                self.addText('<%s'%name)
                for key in attrs.keys():
                    if key != 't:replace':
                        self.addAttr(key,attrs[key])
                self.addText('>')
                replace = attrs['t:replace']
                self.addEvalEscape(replace)
                self.inReplace = True
                self.replaceDepth = self.depth      
        elif 't:replaceMarkup' in attrs.keys():
                self.addText('<%s'%name)
                for key in attrs.keys():
                    if key != 't:replaceMarkup':
                        self.addAttr(key,attrs[key])
                self.addText('>')
                replace = attrs['t:replaceMarkup']
                self.addEval(replace)
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
            self.viewIndexValue = attrs['value']
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
            f = open(resource.path('templates/%s'%attrs['filename']),'r')
            html = f.read()
            f.close()
            self.addText(html)
        elif name == 't:staticReplaceMarkup':
            replace = attrs['t:replaceData']
            self.addEval(replace)
            self.inStaticReplace = True
        elif name == 't:staticReplace':
            replace = attrs['t:replaceData']
            self.addEvalEscape(replace)
            self.inStaticReplace = True
        elif name == 't:includeTemplate':
            self.addFillTemplate(attrs['filename'])
        elif name == 't:triggerActionOnLoad':
            self.handle.addTriggerActionURLOnLoad(attrs['url']) # FIXME make sure this is filled
        elif name == 't:triggerActionOnUnload':
            self.handle.addTriggerActionURLOnUnload(attrs['url']) # FIXME make sure this is filled
        else:
            self.addText('<%s'%name)
            for key in attrs.keys():
                self.addAttr(key,attrs[key])
            self.addText('>')

    def endElement(self,name):
        if not self.started:
            pass
        elif self.onlyBody and name == 'body':
            self.started = False
        elif name == 't:include':
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
        elif self.hiding and self.depth == self.hideDepth[-1]:
            self.addText('</%s>'%name)
            self.endHiding()
        elif self.inReplace and self.depth == self.replaceDepth:
            if self.inRepeatView or self.inUpdateView:
                self.addRepeatText('</%s>'%name)
            else:
                self.addText('</%s>'%name)
            self.inReplace = False
        elif self.inRepeatView and self.depth == self.repeatDepth:
            self.inRepeatView = False
            self.addRepeatText('</%s>'%name)
            self.endRepeatText()
            repeatId = generateId()
            self.addText('<span id="%s"/>'%quoteattr(repeatId))
            self.handle.addView(repeatId, 'nextSibling', self.repeatList, self.repeatName)
        elif self.inUpdateView and self.depth == self.repeatDepth:
            self.inUpdateView = False
            self.addRepeatText('</%s>'%name)
            self.endRepeatText()
            
            repeatId = generateId()
            self.addText('<span id="%s"/>'%quoteattr(repeatId))
            self.handle.addUpdate(repeatId, 'nextSibling', self.repeatList, self.repeatName)
        elif self.inRepeatView or self.inUpdateView:
            self.addRepeatText('</%s>'%name)
        elif name == 't:dynamicviews':
            self.inDynamicViews = False
        elif name == 't:view':
            self.inView = False
            self.handle.makeNamedView(self.viewName, self.viewKey,
                                 self.viewIndex, self.viewIndexValue,
                                 self.filterKey, self.filterFunc, 
                                 self.filterParam, self.filterInvert,
                                 self.sortKey, self.sortFunc, self.sortInvert)
        else:
            self.addText('</%s>'%name)
        self.depth = self.depth - 1

    def characters(self,data):
        if not self.started:
            pass
        elif self.inReplace or self.inStaticReplace:
            pass
        elif self.inRepeatView or self.inUpdateView:
            self.addRepeatTextEscape(data)
        else:
            self.addTextEscape(data)

    def addRepeatText(self, text):
        self.repeatText.append(text)

    def addRepeatTextEscape(self, text):
        self.repeatText.append( escape(text))

    def addRepeatTextHide(self,functionKey,ifKey,parameter,invert, text):
        self.endRepeatText()
        self.repeatList.append((textHideFunc,(functionKey,ifKey,parameter,invert,text)))

    def addRepeatAttr(self, attr, value):
        match = attrPattern.match(value)
        if match:
            self.addRepeatText(' %s="' % attr)
            while match:
                self.addRepeatText(quoteattr(match.group(1)))
                self.endRepeatText()
                self.repeatList.append((attrFunc,match.group(2)))
                value = match.group(3)
                match = attrPattern.match(value)
            self.addRepeatText('%s"' % quoteattr(value))
        else:
            match = rawAttrPattern.match(value)
            if match:
                self.addRepeatText(' %s="' % attr)
                while match:
                    self.addRepeatText(quoteattr(match.group(1)))
                    self.endRepeatText()
                    self.repeatList.append((rawAttrFunc,match.group(2)))
                    value = match.group(3)
                    match = rawAttrPattern.match(value)
                self.addRepeatText('%s"' % quoteattr(value))
            else:
                self.addRepeatText(' %s=' % attr)
                self.addRepeatQuoteAndFill(value)

    def addRepeatQuoteAndFill(self, value):
        self.endRepeatText()
        self.repeatList.append((quoteAndFillFunc, value))

    def addRepeatInclude(self, template):
        f = open(resource.path('templates/%s'%template),'r')
        html = f.read()
        f.close()
        self.addRepeatText(html)

    def addRepeatIncludeHide(self,functionKey,ifKey,parameter,invert, name):
        self.endRepeatText()
        self.repeatList.append((includeHideFunc,(functionKey,ifKey,parameter,invert, name)))

    def addRepeatFillTemplate(self, name):
        self.endRepeatText()
        (tch, handle) = compileTemplate(name, False, True)
        self.handle.addSubHandle(handle)
        self.repeatList.extend(tch.getOperationList())

    def addRepeatAddIdAndClose(self):
        self.endRepeatText()
        self.repeatList.append((addIDFunc,None))

    def addRepeatEval(self,replace):
        self.endRepeatText()
        self.repeatList.append((evalFunc,replace))

    def addRepeatEvalEscape(self,replace):
        self.endRepeatText()
        self.repeatList.append((evalEscapeFunc,replace))

    def resetRepeat(self):
        self.repeatList = []
        self.repeatText = []

    def endRepeatText(self):
        if len(self.repeatText) > 0:
            self.repeatList.append((textFunc,''.join(self.repeatText)))
        self.repeatText = []

    def startHiding(self,functionKey,ifKey,parameter,ifInvert):
        self.endText()
        self.hidingParams.append((functionKey,ifKey,parameter,ifInvert))
        self.hidingList.append([])
        self.hideDepth.append(self.depth)
        self.hiding = True

    def endHiding(self):
        self.endText()
        (functionKey,ifKey,parameter,invert) = self.hidingParams.pop()
        funcList = self.hidingList.pop()
        self.hideDepth.pop()
        self.hiding = len(self.hidingList) > 0
        if self.hiding:
            self.hidingList[-1].append((hideSectionFunc, (functionKey, ifKey, parameter, invert, funcList)))
        else:
            self.outputList.append((hideSectionFunc, (functionKey, ifKey, parameter, invert, funcList)))

    def addText(self, text):
        self.outputText.append( text)

    def addTextEscape(self, text):
        self.outputText.append( escape(text))

    def addHideIfEmpty(self, view, name, invert, attrs):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append( (hideIfEmptyFunc,(view, name, invert, attrs)))
        else:
            self.outputList.append( (hideIfEmptyFunc,(view, name, invert, attrs)))


    def addAttr(self, attr, value):
        match = attrPattern.match(value)
        if match:
            self.addText(' %s="' % attr)
            while match:
                self.addText(quoteattr(match.group(1)))
                self.endText()
                if self.hiding:
                    self.hidingList[-1].append((attrFunc,match.group(2)))
                else:
                    self.outputList.append((attrFunc,match.group(2)))
                value = match.group(3)
                match = attrPattern.match(value)
            self.addText('%s"' % quoteattr(value))
        else:
            match = rawAttrPattern.match(value)
            if match:
                self.addText(' %s="' % attr)
                while match:
                    self.addText(quoteattr(match.group(1)))
                    self.endText()
                    if self.hiding:
                        self.hidingList[-1].append((rawAttrFunc,match.group(2)))
                    else:
                        self.outputList.append((rawAttrFunc,match.group(2)))
                    value = match.group(3)
                    match = rawAttrPattern.match(value)
                self.addText('%s"' % quoteattr(value))
            else:
                self.addText(' %s=' % attr)
                self.addQuoteAndFill(value)

    def addQuoteAndFill(self, value):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append((quoteAndFillFunc, value))
        else:
            self.outputList.append((quoteAndFillFunc, value))

    def addInclude(self, template):
        f = open(resource.path('templates/%s'%template),'r')
        html = f.read()
        f.close()
        self.addText(html)

    def addIncludeHide(self,functionKey,ifKey,parameter,invert, name):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append((includeHideFunc,(functionKey,ifKey,parameter,invert, name)))
        else:
            self.outputList.append((includeHideFunc,(functionKey,ifKey,parameter,invert, name)))

    def addFillTemplate(self, name):
        self.endText()
        (tch, handle) = compileTemplate(name, False, True)
        self.handle.addSubHandle(handle)
        if self.hiding:
            self.hidingList[-1].extend(tch.getOperationList())
        else:
            self.outputList.extend(tch.getOperationList())

    def addAddIdAndClose(self):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append((addIDFunc,None))
        else:
            self.outputList.append((addIDFunc,None))

    def addEval(self,replace):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append((evalFunc,replace))
        else:
            self.outputList.append((evalFunc,replace))

    def addEvalEscape(self,replace):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append((evalEscapeFunc,replace))
        else:
            self.outputList.append((evalEscapeFunc,replace))

    def endText(self):
        if len(self.outputText) > 0:
            if self.hiding:
                self.hidingList[-1].append((textFunc,''.join(self.outputText)))
            else:
                self.outputList.append((textFunc,''.join(self.outputText)))
        self.outputText = []



###############################################################################
#### Generating Javascript callbacks to keep document updated              ####
###############################################################################

# Object representing data needed to register Javascript callbacks
#
# This is used by TemplateContentCompiler to generate code to create a
# Handle
class MetaHandle:
    def __init__(self):
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
        self.hideConditions.append((id, name, invert))

    def makeNamedView(self, name, viewKey, viewIndex, viewIndexValue, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort):
        if self.namedViews.has_key(name):
            raise TemplateError, "More than one view was declared with the name '%s'. Each view must have a different name." % name
        nv = (viewKey, viewIndex, viewIndexValue, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort)
        self.namedViews[name] = nv

    def addView(self, anchorId, anchorType, templateFuncs, name):
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
        tv = (anchorId, anchorType, templateFuncs, name)
        self.trackedViews.append(tv)

    def addUpdate(self, anchorId, anchorType, templateFuncs, name):
        ur = (anchorId, anchorType, templateFuncs, name)
        self.updateRegions.append(ur)
    
    def addSubHandle(self, handle):
        self.subHandles.append(handle)

    def render(self, fileobj, varname = 'handle'):
        prefix = '    '
        ending = "\n"
        
        fileobj.write('%s# Start of handle%s' % (prefix, ending))
        fileobj.write('%s%s = Handle(domHandler)%s' % (prefix, varname, ending))
        for name in self.namedViews:
            (viewKey, viewIndex, viewIndexValue, filterKey, filterFunc, filterParameter, invertFilter, sortKey, sortFunc, invertSort) = self.namedViews[name]
            fileobj.write('%s%s.makeNamedView(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,data)%s' % (prefix, varname, repr(name),repr(viewKey),repr(viewIndex),fillIfNotNone(viewIndexValue),repr(filterKey),repr(filterFunc),fillIfNotNone(filterParameter),repr(invertFilter),repr(sortKey),repr(sortFunc),str(invertSort),ending))

        for tv in self.trackedViews:
            (anchorId, anchorType, templateFuncs, name) = tv
            fileobj.write('%s%s.addView(%s,%s,%s.findNamedView(%s).getView(),%s, data, %s)%s' % (prefix, varname, repr(anchorId),repr(anchorType),varname,repr(name),str(templateFuncs),repr(name),ending))

        for ur in self.updateRegions:
            (anchorId, anchorType, templateFuncs, name) = ur
            fileobj.write('%s%s.addUpdate(%s,%s,%s.findNamedView(%s).getView(),%s, data, %s)%s' % (prefix, varname, repr(anchorId),repr(anchorType),varname,repr(name),str(templateFuncs),repr(name),ending))
            
        for cond in self.hideConditions:
            (id, name, invert) = cond
            fileobj.write('%s%s.addHideIfEmpty(%s,%s,%s)%s' % (prefix, varname, repr(id), repr(name), repr(invert), ending))

        for action in self.triggerActionURLsOnLoad:
            fileobj.write('%s%s.addTriggerActionURLOnLoad(fillAttr(%s,data))%s' %
                          (prefix, varname, repr(action), ending))

        for action in self.triggerActionURLsOnUnload:
            fileobj.write('%s%s.addTriggerActionURLOnUnload(fillAttr(%s,data))%s' %
                          (prefix, varname, repr(action), ending))

        for subHandle in range(len(self.subHandles)):
            newVarName = '%s_%d' % (varname, subHandle)
            self.subHandles[subHandle].render(fileobj, newVarName)
            fileobj.write('%s%s.addSubHandle(%s)%s'%
                          (prefix,varname,newVarName,ending))
            

def fillIfNotNone(obj):
    if obj is None:
        return repr(None)
    else:
        return "fillAttr(%s,data)" % repr(obj)
