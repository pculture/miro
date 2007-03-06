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
import logging
from itertools import izip
from xhtmltools import urlencode

HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)
attrPattern = re.compile("^(.*?)@@@(.*?)@@@(.*)$")
resourcePattern = re.compile("^resource:(.*)$")
rawAttrPattern = re.compile("^(.*?)\*\*\*(.*?)\*\*\*(.*)$")

_unicache = {}
_escapecache = {}

def quoteattr(orig):
    orig = unicode(orig)
    return orig.replace(u'"',u'&quot;')

def escape(orig):
    global _escapecache
    orig = unicode(orig)
    try:
        return _escapecache[orig]
    except:
        _escapecache[orig] = orig.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        return _escapecache[orig]

# Takes a string and do whatever needs to be done to make it into a
# UTF-8 string. If a Unicode string is given, it is just encoded in
# UTF-8. Otherwise, if an encoding hint is given, first try to decode
# the string as if it were in that encoding; if that fails (or the
# hint isn't given), liberally (if necessary lossily) interpret it as
# defaultEncoding, as declared on the next line:
defaultEncoding = "iso-8859-1" # aka Latin-1
_utf8cache = {}

def toUTF8Bytes(string, encoding=None):
    global _utf8cache
    try:
        return _utf8cache[(string, encoding)]
    except KeyError:
        result = None
        # If we got a Unicode string, half of our work is already done.
        if isinstance(string, types.UnicodeType):
            result = string.encode('utf-8')
        elif not isinstance(string, types.StringType):
            string = str(string)
        if result is None and encoding is not None:
            # If we knew the encoding of the string, try that.
            try:
                decoded = string.decode(encoding,'replace')
            except (UnicodeDecodeError, ValueError, LookupError):
                pass
            else:
                result = decoded.encode('utf-8')
        if result is None:
            # Encoding wasn't provided, or it was wrong. Interpret provided string
            # liberally as a fixed defaultEncoding (see above.)
            result = string.decode(defaultEncoding, 'replace').encode('utf-8')

        _utf8cache[(string, encoding)] = result
        return _utf8cache[(string, encoding)]

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


# Generate an arbitrary string to use as an ID attribute.
def generateId():
    return "tmplcomp%08d" % random.randint(0,99999999)
