# Contains lambda functions that can't be rolled into Pyrex easily

import template

# Distutils needs these in a .py file, so it knows they're required
# by the entension module. This place seems as good as any.

#for database.pyx
import cPickle
#for template.pyx
import templatehelper
import gettext
import shutil


def makeFilter(fieldKey, funcKey, parameter, invert, data):
    func = template.evalKey(funcKey, data)
    if not invert:
        return lambda x: func(template.evalKey(fieldKey, x), parameter)
    else:
        return lambda x: not func(template.evalKey(fieldKey, x), parameter)

def makeSort(fieldKey, funcKey, invert,data):
    func = template.evalKey(funcKey, data)
    if not invert:
        return lambda x,y:  func(template.evalKey(fieldKey,x), template.evalKey(fieldKey,y)) 
    else:
        return lambda x,y: -func(template.evalKey(fieldKey,x), template.evalKey(fieldKey,y))

def getFilterFunc(templateApp):
    return lambda x: templateApp.filter(x)

def getSortFunc(templateApp):
    return lambda x: templateApp.sort(x)
