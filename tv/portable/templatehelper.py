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
from miro.xhtmltools import urlencode

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
