# templatehelper.py Copyright (c) 2005,2006 Participatory Culture Foundation
# Contains template utility code shared by template_compiler and template

# Distutils needs this in a .py file, so it knows they're required
# by the entension module. This place seems as good as any.
import cPickle #for database.pyx

import inspect
import shutil
import re
import traceback
import random
import types
from xhtmltools import toUTF8Bytes, urlencode
from xml.sax.expatreader import ExpatParser
from xml.sax.handler import ContentHandler

HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)
attrPattern = re.compile("^(.*?)@@@(.*?)@@@(.*)$")
resourcePattern = re.compile("^resource:(.*)$")
rawAttrPattern = re.compile("^(.*?)\*\*\*(.*?)\*\*\*(.*)$")

_unicache = {}
_escapecache = {}

def quoteattr(orig):
    return orig.replace('"','&quot;')

def escape(orig):
    global _escapecache
    try:
        return _escapecache[orig]
    except:
        _escapecache[orig] = orig.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        return _escapecache[orig]


def toUni(orig, encoding = None):
    global _unicache
    try:
        return _unicache[orig]
    except:
        if isinstance(orig, types.UnicodeType):
            # Let's not bother putting this in the cache.  Calculating
            # it is very fast, and since this is a very common case,
            # not caching here should help with memory usage.
            return orig
        elif not isinstance(orig, types.StringType):
            _unicache[orig] = unicode(orig)
        else:
            orig = toUTF8Bytes(orig, encoding)
            _unicache[orig] = unicode(orig,'utf-8')
        return _unicache[orig]

class SingleElementHandler(ContentHandler):
    def __init__(self):
        self.started = False
        ContentHandler.__init__(self)
    def startElement(self, name, attrs):
        self.name = name
        self.attrs = attrs
        self.started = True
    def reset(self):
        self.started = False


def breakXML(xml):
    """Take xml data and break it down into the outermost tag, and the
    inner xml.  
    Returns the tuple (<outermost-tag-name>, <outermost-tag-attrs>, <inner
    xml>)
    """

    parser = ExpatParser()
    handler = SingleElementHandler()
    parser.setContentHandler(handler)
    pos = 0
    while not handler.started:
        end_candidate = xml.find(">", pos)
        if end_candidate < 0:
            raise ValueError("Can't find start tag in %s" % xml)
        parser.feed(xml[pos:end_candidate+1])
        pos = end_candidate+1
    end_tag_pos = xml.rfind("</")
    innerXML = xml[pos:end_tag_pos]
    return handler.name, handler.attrs, innerXML

# Generate an arbitrary string to use as an ID attribute.
def generateId():
    return "tmplcomp%08d" % random.randint(0,99999999)

