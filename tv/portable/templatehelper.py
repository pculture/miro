# templatehelper.py Copyright (c) 2005,2006 Participatory Culture Foundation
# Contains template utility code shared by template_compiler and template

# Distutils needs this in a .py file, so it knows they're required
# by the entension module. This place seems as good as any.
import cPickle #for database.pyx

import gettext
import inspect
import shutil
import re
import types
import traceback
import random
from xhtmltools import toUTF8Bytes, urlencode

HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)
attrPattern = re.compile("^(.*?)@@@(.*?)@@@(.*)$")
resourcePattern = re.compile("^resource:(.*)$")
rawAttrPattern = re.compile("^(.*)\*\*\*(.*?)\*\*\*(.*)$")
evalCache = {}

def quoteattr(orig):
    return orig.replace('"','&quot;')

def escape(orig):
    return unicode(orig).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def toUni(orig):
    if type(orig) == types.IntType:
        return "%d" % orig
    else:
        orig = toUTF8Bytes(orig)
        return unicode(orig,'utf-8')


# Generate an arbitrary string to use as an ID attribute.
def generateId():
    return "tmplcomp%08d" % random.randint(0,99999999)

