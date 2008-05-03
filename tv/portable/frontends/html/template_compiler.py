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
# "Compiles" Miro templates to Python code
#

from miro.util import checkU

###############################################################################
#### Functions used in repeating templates                                 ####
###############################################################################

# These are functions that take in a file object name that will be
# written to in the output file, an optional id, prefix text, and an
# argument

# Simply returns text
def genRepeatText(varname, tid, prefix, text):
    checkU(text)
    return u'%s%s.write(%s)\n' % (prefix,varname, repr(text))

# Returns translated version of text
def genRepeatTranslate(varname, tid, prefix, args):
    (text, funcDict) = args
    checkU(text)
    # Convert to ascii, strip leading and trailing whitespace and
    # convert interior whitespace to spaces
    text = u' '.join(str(text).strip().split())

    if len(funcDict) == 0:
        return u'%s%s.write(_(%s))\n' % (prefix, varname, repr(text))
    else:
        dictName = generateId()
        out = u'%s%s = {}\n' % (prefix, dictName)
        for name in funcDict:
            temp = generateId()
            out = u'%s%s%s = StringIO()\n' % (out, prefix, temp)
            for (func, fargs) in funcDict[name]:
                val = func(temp, tid, prefix, fargs)
                checkU(val)
                out = u'%s%s' % (out, val)
            out = u'%s%s%s.seek(0)\n' % (out, prefix, temp)
            out = u'%s%s%s[%s] = %s.read()\n' % (out, prefix, dictName, repr(str(name)), temp)

        out = u'%s%s%s.write(Template(_(%s)).substitute(%s))\n' % (
            out, prefix, varname, repr(text), dictName)
        return out
# Returns text if function does not evaluate to true
def genRepeatTextHide(varname, tid, prefix, args):
    (ifValue, text) = args
    checkU(text)
    out = u'%sif not (%s):\n'%(prefix, ifValue)
    out = u'%s%s    %s.write(%s)\n' % (out, prefix, varname, repr(text))
    return out
        
def genQuoteAttr(varname, tid, prefix, value):
    return u'%s%s.write(quoteattr(urlencode(%s)))\n'%(
        prefix, varname, value)

def genRawAttr(varname, tid, prefix, value):
    return u'%s%s.write(quoteattr(%s))\n'%(prefix, varname, value)

# Adds a tid attribute to a tag and closes it
def genRepeatTID(varname, tid, prefix, args):
    return u'%s%s.write(quoteattr(tid))\n' % (prefix, varname)

# Evaluates key with data
def genRepeatEvalEscape(varname, tid, prefix, replace):
    return u'%s%s.write(escape(%s))\n' % (prefix, varname, replace)

# Evaluates key with data
def genRepeatEval(varname, tid, prefix, replace):
    return u'%s%s.write(%s)\n' % (prefix, varname, replace)

# Returns include iff function does not evaluate to true
def genRepeatIncludeHide(varname, tid, prefix, args):
    (ifValue, name) = args
    f = open(resource.path('templates/%s'%name),'r')
    text = f.read()
    f.close()
    out = u'%sif not (%s):\n'%(prefix, ifValue)
    out = u'%s%s    %s.write(%s)\n' % (out, prefix, varname, repr(text.decode('utf-8')))
    return out

def genHideSection(varname, tid, prefix, args):
    (ifValue, funcList) = args
    out = u'%sif not (%s):\n'%(prefix, ifValue)
    for (func, newargs) in funcList:
        val = func(varname,tid,prefix+'    ',newargs)
        checkU(val)
        out = u'%s%s' % (out, val)
    return out

def genQuoteAndFillAttr(varname, tid, prefix, value):
    checkU(value)
    return u'%s%s.write(quoteAndFillAttr(%s,locals()))\n'%(prefix,varname,repr(value))
    
def genUpdateHideOnView(varname, tid, prefix, args):
    (viewName, ifValue, attrs, nodeId) = args

    out = u'%s_hideFunc = lambda : %s\n' % (prefix, ifValue)
    out = u'%s%s_dynHide = _hideFunc()\n' % (out, prefix)
    out = u'%s%sif _dynHide:\n' % (out, prefix)
    out = u'%s%s    %s.write(u" style=\\\"display:none\\\">")\n' % (
        out, prefix, varname)
    out = u'%s%selse:\n%s    %s.write(u">")\n' % (
        out, prefix, prefix, varname)

    out = u'%s%shandle.addUpdateHideOnView(%s,%s,_hideFunc,_dynHide)\n' % (
        out, prefix, repr(nodeId), viewName)
    return out

def genInsertBodyTagExtra(varname, tid, prefix, args):
    return u'%s%s.write(u" " + bodyTagExtra)\n' % (prefix, varname)

def genExecuteTemplate(varname, tid, prefix, args):
    filename, methodArgs = args
    methodCall = u"fillStaticTemplate(%r, onlyBody=True" % filename
    for name, value in methodArgs.items():
        methodCall += u', %s=%s' % (name, value)
    methodCall += u')'
    return u'%s%s.write(%s)\n' % (prefix, varname, methodCall)

from xml import sax
from StringIO import StringIO # Oh! Why can't cStringIO support unicode?
from miro.frontends.html.templatehelper import HTMLPattern, attrPattern, resourcePattern, rawAttrPattern, generateId
from miro.util import quoteattr, escape
import re
import os
import stat

#Setup gettext
#gettext.install('dtv', 'resources/gettext')

# Limitations:
# - t:hideIf tags are only dynamically updated whenever there is dynamic
#   activity on a t:repeatForView in the document (easily fixed)
# - Style tags are overwritten for hidden nodes
# - id tags are inserted in appropriate places
# - An empty span is always created after a repeatForView, so we can't
#   use it inside of a table
# - Currently, we're using the translate and name attributes found on
#   this page to mark text for translation
#   http://www.zope.org/DevHome/Wikis/DevSite/Projects/ComponentArchitecture/ZPTInternationalizationSupport

# To Do:
# - Take a lock around the entire database while template is being filled
# - Improve error handling (currently some random exception is thrown if
#   the template is poorly structured)
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
def compileTemplate(inFile, *args, **kwargs):
    handle = MetaHandle()
    tcc = TemplateContentCompiler(handle, inFile, *args, **kwargs)
    p = sax.make_parser()
    p.setFeature(sax.handler.feature_external_ges, False)
    p.setContentHandler(tcc)
    p.parse(resource.path("templates/%s" % inFile))
    return (tcc, handle)      

# Returns a list of templates with URLs relative to the template
# resource directory
def findTemplates(tpath):
    templates = []
    folders = []
    for template in os.listdir(tpath):
        if (template.find('.svn') == -1 and
            template.find('_svn') == -1 and
            not (template.startswith('.') or template.startswith('#') or 
                 template.endswith('~') or template.endswith('.js') or 
                 template.endswith('.html'))):
            mode = os.stat(os.path.join(tpath,template))[stat.ST_MODE]
            if stat.S_ISDIR(mode):
                folders.append(template)
            else:
                templates.append(template)        
    return (folders, templates)

def modifiedTime(dir):
    maxTime = 0
    try:
        for (dirpath, dirnames, filenames) in os.walk(dir):
            for f in filenames:
                if -1 == dirpath.find('.svn') and -1 == dirpath.find('_svn'):
                    t = os.stat(os.path.join(dirpath, f)).st_mtime
                    if t > maxTime:
                        maxTime = t
        return maxTime
    except:
        return 0

def compiledTemplateDir():
    return resource.path(os.path.join('..','portable', 'frontends', 'html',
        'compiled_templates'))

def compileAllTemplates(root):
    setResourcePath(os.path.join(root,'resources'))
    source = resource.path('templates')
    sourceTime = modifiedTime(source)
    dest = compiledTemplateDir()
    if not os.path.isdir(dest):
        os.makedirs(dest)
    destTime = modifiedTime(dest)
    compilerTime = os.stat(resource.path(__file__)).st_mtime
    if (sourceTime > destTime) or (compilerTime > destTime):
        compileTemplates()

def compileTemplates(tpath = None):
    outdir = compiledTemplateDir()
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    indir = resource.path('templates')
    if tpath is not None:
        print "Compiling %s" % tpath
        outdir = os.path.join(outdir, tpath)
        try:
            os.makedirs(outdir)
        except:
            pass
        indir = os.path.join(indir, tpath)
    
    manifest = open(os.path.join(outdir,'__init__.py'),'wb')
    manifest.write('# This is a generated file. Do not edit.\n\n')

    (folders, templates) = findTemplates(indir)
    for template in templates:
        outFile = os.path.join(outdir,template.replace('-','_')+'.py')
        if tpath is None:
            sourceFile = template
        else:
            sourceFile = os.path.join(tpath, template)
        print "Compiling '%s' template to %s" % (sourceFile, outFile)
        (tcc, handle) = compileTemplate(sourceFile)
        f = open(outFile,"wb")
        f.write(tcc.getOutput().encode('utf-8'))
        f.close()
        manifest.write("import %s\n" % template.replace('/','.').replace('\\','.').replace('-','_'))
    for folder in folders:
        manifest.write("import %s\n" % folder.replace('/','.').replace('\\','.').replace('-','_'))
        compileTemplates(folder)
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
    def __init__(self, handle, name, debug = False, onlyBody = False,
            addIdToTopLevelElement=False):
        self.handle = handle
        self.debug = debug
        self.onlyBody = onlyBody
        self.addIdToTopLevelElement = addIdToTopLevelElement
        self.name = name
        self.isDynamic = False

    def getOperationList(self):
        return self.outputLists[0]
        
    def getOutput(self, data = None):
        fo = StringIO()
        self.render(fo)
        return fo.getvalue()

    def render(self, fileobj):
        fileobj.write(u'# This is a generated file. Do not edit.\n')
        fileobj.write(u'from StringIO import StringIO\n')
        fileobj.write(u'from string import Template\n')
        fileobj.write(u'from miro.xhtmltools import urlencode\n')
        fileobj.write(u'from miro.frontends.html.template import Handle, fillAttr, quoteAndFillAttr, fillStaticTemplate\n')
        fileobj.write(u'from miro.util import quoteattr, escape\n')
        fileobj.write(u'from miro import app\n')
        fileobj.write(u'from miro import views\n')
        fileobj.write(u'from miro import sorts\n')
        fileobj.write(u'from miro import indexes\n')
        fileobj.write(u'from miro import filters\n')
        fileobj.write(u'from miro.plat import resources\n')
        fileobj.write(u'from miro import gtcache\n')
        fileobj.write(u'_ = gtcache.gettext\n')
        fileobj.write(u'def fillTemplate(domHandler, dtvPlatform, eventCookie, bodyTagExtra, *args, **kargs):\n')
        self.handle.render(fileobj)
        fileobj.write(u'\n\n    out = StringIO()\n')
        
        if not self.onlyBody:
            fileobj.write(u'    out.write(u"<?xml version=\\\"1.0\\\" encoding=\\\"utf-8\\\"?>\\n<!DOCTYPE html PUBLIC \\\"-//W3C//DTD XHTML 1.0 Strict//EN\\\" \\\"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd\\\">\\n")\n')
            
        for count in range(len(self.outputLists[0])):
            (func, args) = self.outputLists[0][count]
            fileobj.write(func(u'out',u'',u'    ',args))

        fileobj.write(u'    out.seek(0)\n')
        fileobj.write(u'\n\n    return (out, handle)\n')

    def returnIf(self,bool,value):
        if bool:
            return value
        else:
            return ''

    def startDocument(self):
        print "Starting compile of %s" % self.name
        self.elementStack = []
        self.inInclude = False
        self.inRepeatView = False
        self.inRepeatWithTemplate = False
        self.inUpdateView = False
        self.inConfigUpdate = False
        self.inReplace = False
        self.inStaticReplace = False
        self.inExecOnUnload = False
        self.inExecOnLoad = False
        self.repeatDepth = 0
        self.hotspotDepth = -1
        self.hotspotTagName = ''
        self.replaceDepth = 0
        self.hiding = False
        self.hideDepth = []
        self.depth = 0
        self.bodyDepth = None
        self.repeatName = ''
        self.started = not self.onlyBody
        self.outputLists = [[]]
        self.outputText = []
        self.hidingParams = []
        self.translateDepth = []
        self.translateText = []
        self.translateDict = []
        self.translateName = []
        self.inRaw = False
        self.rawDepth = None
        

    def endDocument(self):
        print "Ending compile"
        self.endText()

    def startElement(self,name, attrs):
        self.depth = self.depth + 1
        if name == 'body':
            self.bodyDepth = self.depth

        if (len(self.translateDepth) > 0 and
                                   self.depth == self.translateDepth[-1]+1):
            if not attrs.has_key('i18n:name'):
                print "in raw for %s" % name
                self.inRaw = True
                self.rawDepth = self.depth
            else:
                self.translateName[-1] = attrs['i18n:name']
                self.translateText[-1] += u'${%s}' % self.translateName[-1]
                self.endText()
                self.outputLists.append([])

        if self.inRaw:
            self.translateText[-1] += u"<%s" % name
            for attr in attrs.keys():
                self.translateText[-1] += u' %s="%s"' % (attr, quoteattr(attrs[attr]))
            self.translateText[-1] += u'>'
        elif self.onlyBody and not self.started:
            if name == 'body':
                self.started = True
        elif not self.started:
            pass
        elif 't:repeatForView' in attrs.keys():
            if 't:containerDiv' in attrs.keys():
                self.inRepeatWithContainerDiv = True
                self.repeatContainerId = generateId()
                self.addElementStart('div', {'id': self.repeatContainerId})
            else:
                self.inRepeatWithContainerDiv = False
            self.startRepeat(attrs['t:repeatForView'])
            if not 't:repeatTemplate' in attrs.keys():
                self.addElementStart(name, attrs, addId=True)
                self.inRepeatWithTemplate = False
            else:
                name = attrs['t:repeatTemplate']
                self.addFillTemplate(name, addIdToTopLevelElement=True)
                # if t:repeatTemplate is set, there shouldn't be any children
                # of this element.  Create a new outputList to check this.
                self.outputLists.append([]) 
                self.inRepeatWithTemplate = True
        elif 't:updateForView' in attrs.keys():
            self.startUpdate(attrs['t:updateForView'])
            self.addElementStart(name, attrs, addId=True)
        elif 't:updateForConfigChange' in attrs.keys():
            self.startConfigUpdate()
            self.addElementStart(name, attrs, addId=True)
        elif 't:hideIf' in attrs.keys():
            ifValue = attrs['t:hideIf']
            if attrs.has_key('t:updateHideOnView'):
                if self.inRepeatView or self.inUpdateView:
                    print "Warning: t:updateHideOnView is unsupported inside a repeat view"
                self.addUpdateHideOnView(attrs['t:updateHideOnView'],name, ifValue, attrs)
            else:
                self.startHiding(ifValue)
                self.addElementStart(name, attrs)
                #FIXME: support i18n tags within a t:hideIf
        elif 't:showIf' in attrs.keys():
            ifValue = u"not (%s)" % attrs['t:showIf']
            if attrs.has_key('t:updateHideOnView'):
                if self.inRepeatView or self.inUpdateView:
                    print "Warning: t:updateHideOnView is unsupported inside a repeat view"
                self.addUpdateHideOnView(attrs['t:updateHideOnView'],name, ifValue, attrs)
            else:
                self.startHiding(ifValue)
                self.addElementStart(name, attrs)
                #FIXME: support i18n tags within a t:showIf
        elif 'i18n:translate' in attrs.keys():
            self.addElementStart(name, attrs)
            self.translateDepth.append(self.depth)
            self.translateText.append('')
            self.translateDict.append({})
            self.translateName.append('')
            
        elif name == 't:include':
            self.addInclude(attrs['filename'])

        elif 't:replace' in attrs.keys():
                self.addElementStart(name, attrs)
                replace = attrs['t:replace']
                self.addEvalEscape(replace)
                self.inReplace = True
                self.replaceDepth = self.depth      
        elif 't:replaceMarkup' in attrs.keys():
                self.addElementStart(name, attrs)
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
            self.addText(html.decode('utf-8'))
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
        elif name == 't:executeTemplate':
            args = dict(attrs.items())
            filename = args.pop('filename')
            self.addInstruction(genExecuteTemplate, (filename, args))
        elif name == 't:triggerActionOnLoad':
            self.handle.addTriggerActionURLOnLoad(attrs['url'])
        elif name == 't:triggerActionOnUnload':
            self.handle.addTriggerActionURLOnUnload(attrs['url'])
        elif 't:hotspot' in attrs.keys():
            self.addHotspot(name, attrs['t:hotspot'])
        else:
            self.addElementStart(name, attrs)

    def endElement(self,name):
        if not self.started:
            pass
        elif self.inRaw:
            self.translateText[-1] += u'</%s>' % name
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
        elif name == 't:executeTemplate':
            pass
        elif name == 't:triggerActionOnUnload':
            pass
        elif name == 't:triggerActionOnLoad':
            pass
        elif self.hiding and self.depth == self.hideDepth[-1]:
            self.addText(u'</%s>'%name)
            self.endHiding()
        elif self.inReplace and self.depth == self.replaceDepth:
            self.addText(u'</%s>'%name)
            self.inReplace = False
        elif self.inRepeatView and self.depth == self.repeatDepth:
            if self.inRepeatWithTemplate:
                self.endText()
                nestedOutputs = self.outputLists.pop()
                if nestedOutputs:
                    m = "Elements with t:repeatTemplate, can't have children"
                    raise ValueError(m)
            else:
                self.addText(u'</%s>'%name)
                self.endText()
            repeatList = self.endRepeat()
            if self.inRepeatWithContainerDiv:
                self.endElement('div')
                self.handle.addView(self.repeatContainerId, 'containerDiv', repeatList, self.repeatName)
            else:
                repeatId = generateId()
                self.addText(u'<span id="%s"/>'%quoteattr(repeatId))
                self.handle.addView(repeatId, 'nextSibling', repeatList, self.repeatName)
        elif self.inUpdateView and self.depth == self.repeatDepth:
            self.addText(u'</%s>'%name)
            self.endText()
            repeatList = self.endUpdate()
            repeatId = generateId()
            self.addText(u'<span id="%s"/>'%quoteattr(repeatId))
            self.handle.addUpdate(repeatId, 'nextSibling', repeatList, self.repeatName)
        elif self.inConfigUpdate and self.depth == self.repeatDepth:
            self.addText(u'</%s>'%name)
            self.endText()
            repeatList = self.endConfigUpdate()
            repeatId = generateId()
            self.addText(u'<span id="%s"/>'%quoteattr(repeatId))
            self.handle.addConfigUpdate(repeatId, 'nextSibling', repeatList)
        elif (len(self.translateDepth) > 0 and
                                     self.depth == self.translateDepth[-1]):
            self.addTranslation()
            self.addText(u'</%s>'%name)
        elif self.depth == self.hotspotDepth:
            self.addText(u"</%s><!-- HOT SPOT END -->" % self.hotspotTagName)
            self.hotspotDepth = -1
        elif name == 't:execOnUnload':
            self.inExecOnUnload = False
            self.handle.addExecOnUnload(self.code)
        elif name == 't:execOnLoad':
            self.inExecOnLoad = False
            self.handle.addExecOnLoad(self.code)
        else:
            self.addText(u'</%s>'%name)
        if (len(self.translateDepth) > 0 and
                                   self.depth == self.translateDepth[-1]+1):
            if self.inRaw:
                print "ending raw for %s" % name
                self.inRaw = False
            else:
                self.endText()
                self.translateDict[-1][self.translateName[-1]] = self.outputLists.pop()
        self.depth = self.depth - 1

    def characters(self,data):
        if not self.started:
            pass
        elif self.inReplace or self.inStaticReplace:
            pass
        elif ((len(self.translateDepth) > 0 and
                                      self.depth == self.translateDepth[-1]) or
                self.inRaw):
              self.translateText[-1] += data
        elif self.inExecOnUnload or self.inExecOnLoad:
            self.code += data
        else:
            self.addTextEscape(data)

    def skippedEntity(self, name):
        self.addText(u"&%s;" % name)

    def addTranslation(self):
        self.translateDepth.pop()
        self.translateName.pop()
        self.addInstruction(genRepeatTranslate, (self.translateText.pop(), self.translateDict.pop()))

    def addInclude(self, template):
        f = open(resource.path('templates/%s'%template),'r')
        html = f.read()
        f.close()
        self.addText(html)

    def addFillTemplate(self, name, *args, **kwargs):
        print "  compiling '%s' subtemplate" % name
        (tcc, handle) = compileTemplate(name, onlyBody=True, *args, **kwargs)
        if tcc.isDynamic:
            self.isDynamic = True
            if self.inUpdateView or self.inConfigUpdate or self.inRepeatView:
                raise TemplateError, "Nested Dynamic tags"
        self.handle.addSubHandle(handle)
        self.addInstructions(tcc.getOperationList())

    def addIdAndClose(self):
        self.addText(' id="')
        self.addInstruction(genRepeatTID,None)
        self.addText('">')

    def startRepeat(self, name):
        if self.inUpdateView or self.inConfigUpdate or self.inRepeatView:
            raise TemplateError, "Nested Dynamic tags"
        self.endText()
        self.inRepeatView = True
        self.isDynamic = True
        self.repeatDepth = self.depth
        self.repeatName = name
        self.outputLists.append([])

    def startUpdate(self, name):
        if self.inUpdateView or self.inConfigUpdate or self.inRepeatView:
            raise TemplateError, "Nested Dynamic tags"
        self.endText()
        self.inUpdateView = True
        self.isDynamic = True
        self.repeatDepth = self.depth
        self.repeatName = name
        self.outputLists.append([])

    def startConfigUpdate(self):
        if self.inUpdateView or self.inConfigUpdate or self.inRepeatView:
            raise TemplateError, "Nested Dynamic tags"
        self.endText()
        self.inConfigUpdate = True
        self.isDynamic = True
        self.repeatDepth = self.depth
        self.outputLists.append([])

    def endRepeat(self):
        self.inRepeatView = False
        return self.outputLists.pop()

    def endUpdate(self):
        self.inUpdateView = False
        return self.outputLists.pop()

    def endConfigUpdate(self):
        self.inConfigUpdate = False
        return self.outputLists.pop()

    def startHiding(self,ifValue):
        self.endText()
        self.hidingParams.append(ifValue)
        self.outputLists.append([])
        self.hideDepth.append(self.depth)
        self.hiding = True

    def endHiding(self):
        self.endText()
        ifValue = self.hidingParams.pop()
        funcList = self.outputLists.pop()
        self.hideDepth.pop()
        self.hiding = len(self.hideDepth) > 0
        self.addInstruction(genHideSection, (ifValue, funcList))

    def addText(self, text):
        self.outputText.append( text)

    def addElementStart(self, name, attrs, addId=False):
        if (self.bodyDepth is not None and self.depth == self.bodyDepth + 1
                and self.addIdToTopLevelElement):
            addId = True
        self.addText(u'<%s'%name)
        for key in attrs.keys():
            if (not (key.startswith('t:') or key.startswith('i18n:')) or
                    key == 't:contextMenu'):
                self.addAttr(key,attrs[key])
        if name.lower() == 'body':
            self.addInstruction(genInsertBodyTagExtra, None)
        if addId:
            self.addIdAndClose()
        else:
            self.addText(u'>')

    def addTextEscape(self, text):
        self.outputText.append( escape(text))

    def addUpdateHideOnView(self, viewName, name, ifValue, attrs):
        nodeId = generateId()
        self.addText(u"<%s" % name)
        for key in attrs.keys():
            if not key in ['t:hideIf','t:updateHideOnView','style']:
                self.addText(u" %s=" % key)
                self.addInstruction(genQuoteAndFillAttr, attrs[key])
        self.addText(u' id="%s"' % quoteattr(nodeId))
        self.addInstruction(genUpdateHideOnView,(viewName, ifValue, attrs, nodeId))

    def addAttr(self, attr, value):
        self.addText(u' %s="' % attr)
        self.addDynamicText(value)
        self.addText('"')

    def addDynamicText(self, value):
        match = attrPattern.match(value)
        if match:
            while match:
                self.addText(quoteattr(match.group(1)))
                self.addInstruction(genQuoteAttr,match.group(2))
                value = match.group(3)
                match = attrPattern.match(value)
            self.addText(u'%s' % quoteattr(value))
        else:
            match = rawAttrPattern.match(value)
            if match:
                while match:
                    self.addText(quoteattr(match.group(1)))
                    self.addInstruction(genRawAttr,match.group(2))
                    value = match.group(3)
                    match = rawAttrPattern.match(value)
                self.addText(u'%s' % quoteattr(value))
            else:
                match = resourcePattern.match(value)
                if match:
                    self.addInstruction(genRawAttr,u'resources.url(%s)'%repr(match.group(1)))
                else:
                    self.addText(quoteattr(value))

    def addHotspot(self, name, id):
        self.hotspotDepth = self.depth
        self.hotspotTagName = name
        self.addText(u"<!-- HOT SPOT ")
        self.addDynamicText(id)
        self.addText(u" -->")
        self.addElementStart(name, {'id': id})

    def addEval(self,replace):
        self.addInstruction(genRepeatEval,replace)

    def addEvalEscape(self,replace):
        self.addInstruction(genRepeatEvalEscape, replace)

    def endText(self):
        if len(self.outputText) > 0:
            self.addInstruction(genRepeatText,u''.join(self.outputText))
        self.outputText = []

    def addInstruction(self, instruction, args):
        if instruction != genRepeatText:
            self.endText()
        self.outputLists[-1].append((instruction,args))
        
    def addInstructions(self, instructions):
        self.endText()
        for (ins, arg) in instructions:
            self.addInstruction(ins, arg)

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
        self.configUpdateRegions = []
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
        # 'containerDiv' is like parentNode, except it's contained in an
        # auto-generated <div> element.  This allows for efficient changes
        # when the view is re-sorted.
        #
        # We take a private copy of 'node', so don't worry about modifying
        # it subsequent to calling this method.
        tv = (anchorId, anchorType, templateFuncs, name)
        self.trackedViews.append(tv)

    def addUpdate(self, anchorId, anchorType, templateFuncs, name):
        ur = (anchorId, anchorType, templateFuncs, name)
        self.updateRegions.append(ur)

    def addConfigUpdate(self, anchorId, anchorType, templateFuncs):
        ur = (anchorId, anchorType, templateFuncs)
        self.configUpdateRegions.append(ur)
    
    def addSubHandle(self, handle):
        self.subHandles.append(handle)

    def render(self, fileobj, varname = 'handle'):
        prefix = u'    '
        ending = u"\n"
        
        fileobj.write(u'%s# Start of handle%s%s' % (prefix, ending, ending))

        fileobj.write(u'%s# Start user code%s' % (prefix, ending))
        if self.execOnLoad is not None:
            for line in self.execOnLoad.splitlines():
                fileobj.write(u'%s%s%s' % (prefix, line, ending))
        if self.execOnUnload is not None:
            fileobj.write(u'%s%sdef _execOnUnload():%s' % (ending, prefix, ending))
            for line in self.execOnUnload.splitlines():
                fileobj.write(u'%s    %s%s' % (prefix, line, ending))
        fileobj.write(u'%s# End user code%s%s' % (prefix, ending, ending))

        fileobj.write(u'%slocalvars = locals()%s' % (prefix, ending))
        fileobj.write(u'%slocalvars.update(globals())%s' % (prefix, ending))
        if self.execOnUnload is not None:
            fileobj.write(u'%s%s = Handle(domHandler, localvars, onUnlink = _execOnUnload)%s%s' % (prefix, varname, ending, ending))
        else:
            fileobj.write(u'%s%s = Handle(domHandler, localvars, onUnlink = lambda:None)%s%s' % (prefix, varname, ending, ending))

        count = 0
        for ur in self.updateRegions:
            (anchorId, anchorType, templateFuncs, name) = ur
            upFunc = u"up_%s_%s" % (count, varname)
            fileobj.write(u'%sdef %s(viewName, view, tid):%s' % (prefix, upFunc,ending))
            fileobj.write(u'%s    out = StringIO()%s' % (prefix, ending))
            for count2 in range(len(templateFuncs)):
                (func, args) = templateFuncs[count2]
                fileobj.write(func(u'out',u'',prefix+u'    ',args))
            fileobj.write(u'%s    out.seek(0)%s' % (prefix, ending))
            fileobj.write(u'%s    return out%s' % (prefix, ending))

            fileobj.write(u'%s%s.addUpdate(%s,%s,%s,%s, %s)%s' % (prefix, varname, repr(anchorId),repr(anchorType),name,upFunc,repr(name),ending))
            count += 1

        for ur in self.configUpdateRegions:
            (anchorId, anchorType, templateFuncs) = ur
            upFunc = u"config_up_%s_%s" % (count, varname)
            fileobj.write(u'%sdef %s(tid):%s' % (prefix, upFunc, ending))
            fileobj.write(u'%s    out = StringIO()%s' % (prefix, ending))
            for count2 in range(len(templateFuncs)):
                (func, args) = templateFuncs[count2]
                fileobj.write(func('out','',prefix+'    ',args))
            fileobj.write(u'%s    out.seek(0)%s' % (prefix, ending))
            fileobj.write(u'%s    return out%s' % (prefix, ending))

            fileobj.write(u'%s%s.addConfigUpdate(%s,%s,%s)%s' % (prefix, varname, repr(anchorId),repr(anchorType),upFunc,ending))
            count += 1

        for tv in self.trackedViews:
            (anchorId, anchorType, templateFuncs, name) = tv
            repFunc = u"rep_%s_%s" % (count, varname)
            fileobj.write(u'%sdef %s(this, viewName, view, tid):%s' % (prefix, repFunc,ending))
            fileobj.write(u'%s    out = StringIO()%s' % (prefix, ending))
            for count2 in range(len(templateFuncs)):
                (func, args) = templateFuncs[count2]
                fileobj.write(func('out','',prefix+'    ',args))
            fileobj.write(u'%s    out.seek(0)%s' % (prefix, ending))
            fileobj.write(u'%s    return out%s' % (prefix, ending))

            fileobj.write(u'%s%s.addView(%s,%s,%s,%s, %s)%s' % (prefix, varname, repr(anchorId),repr(anchorType),name,repFunc,repr(name),ending))
            count += 1
            
        for action in self.triggerActionURLsOnLoad:
            fileobj.write(u'%s%s.addTriggerActionURLOnLoad(fillAttr(%s,locals()))%s' %
                          (prefix, varname, repr(action), ending))

        for action in self.triggerActionURLsOnUnload:
            fileobj.write(u'%s%s.addTriggerActionURLOnUnload(fillAttr(%s,locals()))%s' %
                          (prefix, varname, repr(action), ending))

        for subHandle in range(len(self.subHandles)):
            newVarName = u'%s_%d' % (varname, subHandle)
            self.subHandles[subHandle].render(fileobj, newVarName)
            fileobj.write(u'%s%s.addSubHandle(%s)%s'%
                          (prefix,varname,newVarName,ending))
            

def fillIfNotNone(obj):
    if obj is None:
        return repr(None)
    else:
        return u"fillAttr(%s,locals())" % repr(obj)
