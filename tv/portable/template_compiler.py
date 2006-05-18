# template_compiler.py Copyright (c) 2005,2006 Participatory Culture Foundation
#
# "Compiles" Democracy templates to Python code
#

###############################################################################
#### Functions used in repeating templates                                 ####
###############################################################################

# These are functions that take in a file object name that will be
# written to in the output file, an optional id, prefix text, and an
# argument

# FIXME: These can be optimized to eliminate redundancy

# Simply returns text
def genRepeatText(varname, tid, prefix, text):
    return '%s%s.write(%s)\n' % (prefix,varname, repr(text))

# Returns text if function does not evaluate to true
def genRepeatTextHide(varname, tid, prefix, args):
    (ifValue, text) = args
    out = '%sif not (%s):\n'%(prefix, ifValue)
    out = '%s%s    %s.write(%s)\n' % (out, prefix, varname, repr(text))
    return out
        
def genQuoteAttr(varname, tid, prefix, value):
    return '%s%s.write(quoteattr(urlencode(toUni(%s))))\n'%(
        prefix, varname, value)

def genRawAttr(varname, tid, prefix, value):
    return '%s%s.write(quoteattr(toUni(%s)))\n'%(prefix, varname, value)

# Adds an id attribute to a tag and closes it
def genRepeatAddIdAndClose(varname, tid, prefix, args):
    return '%s%s.write(" id=\\"")\n%s%s.write(quoteattr(tid))\n%s%s.write("\\">")\n' % (prefix, varname,prefix, varname,prefix, varname)

# Evaluates key with data
def genRepeatEvalEscape(varname, tid, prefix, replace):
    return '%s%s.write(escape(toUni(%s)))\n' % (prefix, varname, replace)

# Evaluates key with data
def genRepeatEval(varname, tid, prefix, replace):
    return '%s%s.write(toUni(%s))\n' % (prefix, varname, replace)

# Returns include iff function does not evaluate to true
def genRepeatIncludeHide(varname, tid, prefix, args):
    (ifValue, name) = args
    f = open(resource.path('templates/%s'%name),'r')
    text = f.read()
    f.close()
    out = '%sif not (%s):\n'%(prefix, ifValue)
    out = '%s%s    %s.write(%s)\n' % (out, prefix, varname, repr(text))
    return out

def genHideSection(varname, tid, prefix, args):
    (ifValue, funcList) = args
    out = '%sif not (%s):\n'%(prefix, ifValue)
    for (func, newargs) in funcList:
        out = '%s%s' % (out, func(varname,tid,prefix+'    ',newargs))
    return out

def genUpdateHideOnView(varname, tid, prefix, args):
    (viewName, name, ifValue, attrs) = args
    nodeId = generateId()
    
    out = '%s%s.write("<%s")\n'%(prefix, varname,name)
    for key in attrs.keys():
        if not key in ['t:hideIf','t:updateHideOnView','style']:
            out = '%s%s%s.write(" %s=")\n'%(out,prefix,varname,key)
            out = '%s%s%s.write(quoteAndFillAttr("%s",locals()))\n'%(out,prefix,varname,attrs[key])
    out = '%s%s%s.write(" id=\\\"%s\\\"")\n'%(out,prefix,varname,quoteattr(nodeId))

    out = '%s%s_hideFunc = lambda : %s\n' % (out, prefix, ifValue)
    out = '%s%s_dynHide = _hideFunc()\n' % (out, prefix)
    out = '%s%sif _dynHide:\n' % (out, prefix)
    out = '%s%s    %s.write(" style=\\\"display:none\\\">")\n' % (
        out, prefix, varname)
    out = '%s%selse:\n%s    %s.write(">")\n' % (
        out, prefix, prefix, varname)

    out = '%s%shandle.addUpdateHideOnView(%s,%s,_hideFunc,_dynHide)\n' % (
        out, prefix, repr(nodeId), viewName)
    return out

from distutils import dep_util
from xml import sax
from xhtmltools import toUTF8Bytes
from StringIO import StringIO
from templatehelper import quoteattr, escape, HTMLPattern, attrPattern, resourcePattern, rawAttrPattern, generateId
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
                not (template.startswith('.') or template.startswith('#') or 
                     template.endswith('~') or template.endswith('.js') or 
                     template.endswith('.html'))):
                templates.append(template)
    return templates

def compileAllTemplates(root):
    manifest = file(os.path.join(root,'portable','compiled_templates','__init__.py'),'wb')
    setResourcePath(os.path.join(root,'resources'))
    manifest = open(os.path.join(root,'portable','compiled_templates','__init__.py'),'wb')
    manifest.write('# This is a generated file. Do not edit.\n\n')
        
    for template in findTemplates(root):
        outFile = os.path.join(root,'portable','compiled_templates',template.replace('-','_')+'.py')
        sourceFile = resource.path("templates/%s" % template)
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

        if dep_util.newer(sourceFile, outFile):
            print "Compiling '%s' template to %s" % (template, outFile)
            (tcc, handle) = compileTemplate(template)
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
        fileobj.write('from template import Handle, fillAttr, quoteAndFillAttr\n')
        fileobj.write('from IOBuffer import IOBuffer\n')
        fileobj.write('from xhtmltools import urlencode\n')
        fileobj.write('from templatehelper import quoteattr, escape, toUni\n')
        fileobj.write('import app\n')
        fileobj.write('import views\n')
        fileobj.write('import sorts\n')
        fileobj.write('import indexes\n')
        fileobj.write('import filters\n')
        fileobj.write('import resource\n')
        fileobj.write('def fillTemplate(domHandler, dtvPlatform, eventCookie):\n')
        self.handle.render(fileobj)
        fileobj.write('\n\n    out = IOBuffer()\n')
        
        if not self.onlyBody:
            fileobj.write('    out.write("<?xml version=\\\"1.0\\\" encoding=\\\"UTF-8\\\"?>\\n<!DOCTYPE html PUBLIC \\\"-//W3C//DTD XHTML 1.0 Strict//EN\\\" \\\"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd\\\">\\n")\n')
            
        for count in range(len(self.outputList)):
            (func, args) = self.outputList[count]
            fileobj.write(func('out','','    ',args))

        fileobj.write('    out.close()\n')        
        fileobj.write('\n\n    return (out, handle)\n')

    def returnIf(self,bool,value):
        if bool:
            return value
        else:
            return ''

    def startDocument(self):
        print "Starting compile"
        self.elementStack = []
        self.inInclude = False
        self.inRepeatView = False
        self.inUpdateView = False
        self.inReplace = False
        self.inStaticReplace = False
        self.inExecOnUnload = False
        self.inExecOnLoad = False
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
        print "Ending compile"
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
        elif self.inRepeatView or self.inUpdateView:
            if attrs.has_key('t:hideIf'):
                ifValue = attrs['t:hideIf']

                if attrs.has_key('t:updateHideOnView'):
                    print "Warning: t:updateHideOnView is unsupported inside a repeat view"
                self.startHiding(ifValue)

            if name == 't:includeTemplate':
                self.addFillTemplate(attrs['filename'])
            elif name == 't:include':
                self.addInclude(attrs['filename'])
            else:
                self.addText('<%s'%name)
                for key in attrs.keys():
                    if not (key in ['t:replace','t:replaceMarkup','t:hideIf',
                                    'style']):
                        self.addAttr(key,attrs[key])

                self.addText('>')
                try:
                    replace = attrs['t:replace']
                    self.addEvalEscape(replace)
                    self.inReplace = True
                    self.replaceDepth = self.depth
                except KeyError:
                    pass
                try:
                    replace = attrs['t:replaceMarkup']
                    self.addEval(replace)
                    self.inReplace = True
                    self.replaceDepth = self.depth
                except KeyError:
                    pass
        elif 't:repeatForView' in attrs.keys():
            self.inRepeatView = True
            self.repeatDepth = self.depth
            self.resetRepeat()
            self.addText('<%s'%name)
            for key in attrs.keys():
                if key != 't:repeatForView':
                    self.addAttr(key,attrs[key])
            self.addIdAndClose()

            self.repeatName = attrs['t:repeatForView']

        elif 't:updateForView' in attrs.keys():
            self.inUpdateView = True
            self.repeatDepth = self.depth
            self.resetRepeat()
            self.addText('<%s'%name)
            for key in attrs.keys():
                if key != 't:updateForView':
                    self.addAttr(key,attrs[key])
            self.addIdAndClose()

            self.repeatName = attrs['t:updateForView']
        elif 't:hideIf' in attrs.keys():
            ifValue = attrs['t:hideIf']
            if attrs.has_key('t:updateHideOnView'):
                self.addUpdateHideOnView(attrs['t:updateHideOnView'],name, ifValue, attrs)
            else:
                self.startHiding(ifValue)

                self.addText('<%s'%name)

                for key in attrs.keys():
                    if (key not in ['t:hideIf']):
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
        elif name == 't:execOnUnload':
            self.inExecOnUnload = True
            self.code = ''
        elif name == 't:execOnLoad':
            self.inExecOnLoad = True
            self.code = ''
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
            self.handle.addTriggerActionURLOnLoad(attrs['url'])
        elif name == 't:triggerActionOnUnload':
            self.handle.addTriggerActionURLOnUnload(attrs['url'])
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
        elif name == 't:triggerActionOnUnload':
            pass
        elif name == 't:triggerActionOnLoad':
            pass
        elif self.hiding and self.depth == self.hideDepth[-1]:
            self.addText('</%s>'%name)
            self.endHiding()
        elif self.inReplace and self.depth == self.replaceDepth:
            self.addText('</%s>'%name)
            self.inReplace = False
        elif self.inRepeatView and self.depth == self.repeatDepth:
            self.addText('</%s>'%name)
            self.endText()
            self.inRepeatView = False
            repeatId = generateId()
            self.addText('<span id="%s"/>'%quoteattr(repeatId))
            self.handle.addView(repeatId, 'nextSibling', self.repeatList, self.repeatName)
        elif self.inUpdateView and self.depth == self.repeatDepth:
            self.addText('</%s>'%name)
            self.endText()
            self.inUpdateView = False
            repeatId = generateId()
            self.addText('<span id="%s"/>'%quoteattr(repeatId))
            self.handle.addUpdate(repeatId, 'nextSibling', self.repeatList, self.repeatName)
        elif name == 't:execOnUnload':
            self.inExecOnUnload = False
            self.handle.addExecOnUnload(self.code)
        elif name == 't:execOnLoad':
            self.inExecOnLoad = False
            self.handle.addExecOnLoad(self.code)
        else:
            self.addText('</%s>'%name)
        self.depth = self.depth - 1

    def characters(self,data):
        if not self.started:
            pass
        elif self.inReplace or self.inStaticReplace:
            pass
        elif self.inExecOnUnload or self.inExecOnLoad:
            self.code += data
        else:
            self.addTextEscape(data)

    def skippedEntity(self, name):
        self.addText("&%s;" % name)

    def addInclude(self, template):
        f = open(resource.path('templates/%s'%template),'r')
        html = f.read()
        f.close()
        self.addText(html)

    def addFillTemplate(self, name):
        self.endText()
        print "  compiling '%s' subtemplate" % name
        (tcc, handle) = compileTemplate(name, False, True)
        self.handle.addSubHandle(handle)
        if self.hiding:
            self.hidingList[-1].extend(tcc.getOperationList())
        elif self.inRepeatView or self.inUpdateView:
            self.repeatList.extend(tcc.getOperationList())
        else:
            self.outputList.extend(tcc.getOperationList())

    def addIdAndClose(self):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append((genRepeatAddIdAndClose,None))
        elif self.inRepeatView or self.inUpdateView:
            self.repeatList.append((genRepeatAddIdAndClose,None))
        else:
            self.outputList.append((genRepeatAddIdAndClose,None))

    def resetRepeat(self):
        self.repeatList = []
        self.repeatText = []

    def startHiding(self,ifValue):
        self.endText()
        self.hidingParams.append(ifValue)
        self.hidingList.append([])
        self.hideDepth.append(self.depth)
        self.hiding = True

    def endHiding(self):
        self.endText()
        ifValue = self.hidingParams.pop()
        funcList = self.hidingList.pop()
        self.hideDepth.pop()
        self.hiding = len(self.hidingList) > 0
        if self.hiding:
            self.hidingList[-1].append((genHideSection, (ifValue, funcList)))
        elif self.inRepeatView or self.inUpdateView:
            self.repeatList.append((genHideSection, (ifValue, funcList)))
        else:
            self.outputList.append((genHideSection, (ifValue, funcList)))

    def addText(self, text):
        if self.inRepeatView or self.inUpdateView:
            self.repeatText.append(text)
        else:
            self.outputText.append( text)

    def addTextHide(self,ifValue,text):
        if self.inRepeatView or self.inUpdateView:
            self.endText()
            if self.hiding:
                self.hidingList[-1].append((genRepeatTextHide,(ifValue,text)))
            else:
                self.repeatList.append((genRepeatTextHide,(ifValue,text)))
        else:
            self.endText()
            self.outputList.append((genRepeatTextHide,(ifValue,text)))

    def addTextEscape(self, text):
        if self.inRepeatView or self.inUpdateView:
            self.repeatText.append( escape(text))
        else:
            self.outputText.append( escape(text))

    def addUpdateHideOnView(self, viewName, name, ifValue, attrs):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append( (genUpdateHideOnView,(viewName, name, ifValue, attrs)))
        else:
            self.outputList.append( (genUpdateHideOnView,(viewName, name, ifValue, attrs)))

    def addAttr(self, attr, value):
        match = attrPattern.match(value)
        if match:
            self.addText(' %s="' % attr)
            while match:
                self.addText(quoteattr(match.group(1)))
                self.endText()
                if self.hiding:
                    self.hidingList[-1].append((genQuoteAttr,match.group(2)))
                elif self.inRepeatView or self.inUpdateView:
                    self.repeatList.append((genQuoteAttr,match.group(2)))
                else:
                    self.outputList.append((genQuoteAttr,match.group(2)))
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
                        self.hidingList[-1].append((genRawAttr,match.group(2)))
                    elif self.inRepeatView or self.inUpdateView:
                        self.repeatList.append((genRawAttr,match.group(2)))
                    else:
                        self.outputList.append((genRawAttr,match.group(2)))
                    value = match.group(3)
                    match = rawAttrPattern.match(value)
                self.addText('%s"' % quoteattr(value))
            else:
                self.addText(' %s="' % attr)
                match = resourcePattern.match(value)
                if match:
                    self.endText()
                    if self.hiding:
                        self.hidingList[-1].append((genRepeatEval,'resource.url(%s)'%repr(match.group(1))))
                    elif self.inRepeatView or self.inUpdateView:
                        self.repeatList.append((genRepeatEval,'resource.url(%s)'%repr(match.group(1))))
                    else:
                        self.outputList.append((genRepeatEval,'resource.url(%s)'%repr(match.group(1))))
                else:
                    self.addText(quoteattr(value))
                self.addText('"')

    def addEval(self,replace):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append((genRepeatEval,replace))
        elif self.inRepeatView or self.inUpdateView:
            self.repeatList.append((genRepeatEval,replace))
        else:
            self.outputList.append((genRepeatEval,replace))

    def addEvalEscape(self,replace):
        self.endText()
        if self.hiding:
            self.hidingList[-1].append((genRepeatEvalEscape,replace))
        elif self.inRepeatView or self.inUpdateView:
            self.repeatList.append((genRepeatEvalEscape,replace))
        else:
            self.outputList.append((genRepeatEvalEscape,replace))

    def endText(self):
        if self.inRepeatView or self.inUpdateView:
            if len(self.repeatText) > 0:
                if self.hiding:
                    self.hidingList[-1].append((genRepeatText,''.join(self.repeatText)))
                else:
                    self.repeatList.append((genRepeatText,''.join(self.repeatText)))
            self.repeatText = []
        else:
            if len(self.outputText) > 0:
                if self.hiding:
                    self.hidingList[-1].append((genRepeatText,''.join(self.outputText)))
                else:
                    self.outputList.append((genRepeatText,''.join(self.outputText)))
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
        self.trackedViews = []
        self.updateRegions = []
        self.subHandles = []
        self.triggerActionURLsOnLoad = []
        self.triggerActionURLsOnUnload = []
        self.execOnUnload = None
        self.execOnLoad = None
        
    def addTriggerActionURLOnLoad(self,url):
        self.triggerActionURLsOnLoad.append(str(url))

    def addTriggerActionURLOnUnload(self, url):
        self.triggerActionURLsOnUnload.append(str(url))

    def getTriggerActionURLsOnLoad(self):
        return self.triggerActionURLsOnLoad

    def getTriggerActionURLsOnUnload(self):
        return self.triggerActionURLsOnUnload

    def addExecOnUnload(self, code):
        self.execOnUnload = code

    def addExecOnLoad(self, code):
        self.execOnLoad = code

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
        
        fileobj.write('%s# Start of handle%s%s' % (prefix, ending, ending))

        fileobj.write('%s# Start user code%s' % (prefix, ending))
        if self.execOnLoad is not None:
            for line in self.execOnLoad.splitlines():
                fileobj.write('%s%s%s' % (prefix, line, ending))
        if self.execOnUnload is not None:
            fileobj.write('%s%sdef _execOnUnload():%s' % (ending, prefix, ending))
            for line in self.execOnUnload.splitlines():
                fileobj.write('%s    %s%s' % (prefix, line, ending))
        fileobj.write('%s# End user code%s%s' % (prefix, ending, ending))

        if self.execOnUnload is not None:
            fileobj.write('%s%s = Handle(domHandler, locals(), onUnlink = _execOnUnload)%s%s' % (prefix, varname, ending, ending))
        else:
            fileobj.write('%s%s = Handle(domHandler, locals(), onUnlink = lambda:None)%s%s' % (prefix, varname, ending, ending))
        count = 0
        for tv in self.trackedViews:
            (anchorId, anchorType, templateFuncs, name) = tv
            repFunc = "rep_%s_%s" % (count, varname)
            fileobj.write('%sdef %s(this, viewName, tid):%s' % (prefix, repFunc,ending))
            fileobj.write('%s    out = IOBuffer()%s' % (prefix, ending))
            for count2 in range(len(templateFuncs)):
                (func, args) = templateFuncs[count2]
                fileobj.write(func('out','',prefix+'    ',args))
            fileobj.write('%s    out.close()%s' % (prefix, ending))
            fileobj.write('%s    return out%s' % (prefix, ending))

            fileobj.write('%s%s.addView(%s,%s,%s,%s, %s)%s' % (prefix, varname, repr(anchorId),repr(anchorType),name,repFunc,repr(name),ending))
            count += 1

        for ur in self.updateRegions:
            (anchorId, anchorType, templateFuncs, name) = ur
            upFunc = "up_%s_%s" % (count, varname)
            fileobj.write('%sdef %s(viewName, tid):%s' % (prefix, upFunc,ending))
            fileobj.write('%s    out = IOBuffer()%s' % (prefix, ending))
            for count2 in range(len(templateFuncs)):
                (func, args) = templateFuncs[count2]
                fileobj.write(func('out','',prefix+'    ',args))
            fileobj.write('%s    out.close()%s' % (prefix, ending))
            fileobj.write('%s    return out%s' % (prefix, ending))

            fileobj.write('%s%s.addUpdate(%s,%s,%s,%s, %s)%s' % (prefix, varname, repr(anchorId),repr(anchorType),name,upFunc,repr(name),ending))
            count += 1
            
        for action in self.triggerActionURLsOnLoad:
            fileobj.write('%s%s.addTriggerActionURLOnLoad(fillAttr(%s,locals()))%s' %
                          (prefix, varname, repr(action), ending))

        for action in self.triggerActionURLsOnUnload:
            fileobj.write('%s%s.addTriggerActionURLOnUnload(fillAttr(%s,locals()))%s' %
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
        return "fillAttr(%s,locals())" % repr(obj)
