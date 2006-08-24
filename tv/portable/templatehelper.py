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
from xhtmltools import toUTF8Bytes, urlencode

HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)
attrPattern = re.compile("^(.*?)@@@(.*?)@@@(.*)$")
resourcePattern = re.compile("^resource:(.*)$")
rawAttrPattern = re.compile("^(.*)\*\*\*(.*?)\*\*\*(.*)$")

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
        if type(orig) is unicode:
            # Let's not bother putting this in the cache.  Calculating
            # it is very fast, and since this is a very common case,
            # not caching here should help with memory usage.
            return orig
        elif type(orig) in (int, long):
            _unicache[orig] = u"%d" % orig
        else:
            orig = toUTF8Bytes(orig, encoding)
            _unicache[orig] = unicode(orig,'utf-8')
        return _unicache[orig]

# Generate an arbitrary string to use as an ID attribute.
def generateId():
    return "tmplcomp%08d" % random.randint(0,99999999)

