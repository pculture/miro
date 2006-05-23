import unittest
import resource
import os
import re
import time

from template import *
import database

from test.framework import DemocracyTestCase

HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)

class HTMLObject(database.DDBObject):
    def __init__(self,html):
        self.html = html
        database.DDBObject.__init__(self)

class DOMTracker:
    def __init__(self):
        self.callList = []
    def addItemAtEnd(self, xml, id):
        self.callList.append({'name':'addItemAtEnd','xml':xml,'id':id})
    def addItemBefore(self, xml, id):
        self.callList.append({'name':'addItemBefore','xml':xml,'id':id})
    def removeItem(self, id):
        self.callList.append({'name':'removeItem','id':id})
    def changeItem(self, id, xml):
        self.callList.append({'name':'changeItem','xml':xml,'id':id})
    def hideItem(self, id):
        self.callList.append({'name':'hideItem','id':id})
    def showItem(self, id):
        self.callList.append({'name':'showItem','id':id})

class ChangeDelayedDOMTracker(DOMTracker):
    def changeItem(self, id, xml):
        time.sleep(0.1)
        self.callList.append({'name':'changeItem','xml':xml,'id':id})

class SimpleTest(DemocracyTestCase):
    def setUp(self):
        handle = file(resource.path("templates/unittest/simple"),"r")
        self.text = handle.read()
        handle.close()
        self.text = HTMLPattern.match(self.text).group(1)
    def test(self):
        (tch, handle) = fillTemplate("unittest/simple",DOMTracker(),'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assertEqual(text,self.text)

class ReplaceTest(DemocracyTestCase):
    def setUp(self):
        handle = file(resource.path("testdata/replace-result"),"r")
        self.text = handle.read()
        handle.close()
        self.text = HTMLPattern.match(self.text).group(1)
    def test(self):
        (tch, handle) = fillTemplate("unittest/replace",DOMTracker(),'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assertEqual(text,self.text)

class HideTest(DemocracyTestCase):
    def setUp(self):
        handle = file(resource.path("testdata/hide-result"),"r")
        self.text = handle.read()
        handle.close()
        self.text = HTMLPattern.match(self.text).group(1)
    def test(self):
        (tch, handle) = fillTemplate("unittest/hide",DOMTracker(),'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assertEqual(text,self.text)

class ViewTest(DemocracyTestCase):
    pattern = re.compile("^\n<h1>view test template</h1>\n<span id=\"([^\"]+)\"/>\n", re.S)
    doublePattern = re.compile("^\n<h1>view test template</h1>\n<span id=\"([^\"]+)\"/>\n<span id=\"([^\"]+)\"/>\n", re.S)

    itemPattern = re.compile("^(<div id=\"(.*?)\">\n<span>&lt;span&gt;object&lt;/span&gt;</span>\n<span><span>object</span></span>\n\n<div>\nhideIf:False\n<span>This is an include</span>\n\n<span>This is a template include</span>\n\n<span>&lt;span&gt;This is a database replace&lt;/span&gt;</span>\n<span><span>This is a database replace</span></span>\n</div>\n</div>)+$",re.S)

    def setUp(self):
        self.everything = database.defaultDatabase
        self.x = HTMLObject('<span>object</span>')
        self.y = HTMLObject('<span>object</span>')
        self.view = self.everything.sort(self.sortFunc)
        self.everything.createIndex(self.indexFunc)
        self.domHandle = DOMTracker()
    def bool(self,x,y):
        self.assertEqual(y, "paramtest")
        return x
    def indexFunc(self,x):
        if x.getID() < self.x.getID()+3:
            return '1'
        else:
            return '0'
    def filterFunc(self,x,param):
        return x.getID() <= self.y.getID() or x.getID() >= self.x.getID()+3
    def sortFunc(self, x, y):
        x = x.getID()
        y = y.getID()
        if x < y:
            return -1
        elif x > y:
            return 1
        else:
            return 0

    def test(self):
        (tch, handle) = fillTemplate("unittest/view",self.domHandle,'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assert_(self.pattern.match(text)) #span for template inserted
        id = self.pattern.match(text).group(1)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),1)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        # FIXME: check that the ids are unique
        match = self.itemPattern.match(self.domHandle.callList[0]['xml'])
        self.assert_(match)

    def testTwoViews(self):
        (tch, handle) = fillTemplate("unittest/view-double",self.domHandle,'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        assert(self.doublePattern.match(text)) #span for template inserted
        id = self.doublePattern.match(text).group(2)
        id2 = self.doublePattern.match(text).group(2)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),2)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[1]['name'],'addItemBefore')
        match = []
        match.append(self.itemPattern.match(self.domHandle.callList[0]['xml']))
        match.append(self.itemPattern.match(self.domHandle.callList[1]['xml']))
        # FIXME: check that the ids are unique within the same insert
        for x in range(len(match)):
            self.assert_(match[x])
            for y in range(x+1,len(match)):
                self.assertNotEqual(match[x].group(2),match[y].group(2))
        self.x.beginChange()
        self.x.endChange()
        self.x.remove()
        self.assertEqual(len(self.domHandle.callList),6)
        self.assertEqual(self.domHandle.callList[2]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[3]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[4]['name'],'removeItem')
        self.assertEqual(self.domHandle.callList[5]['name'],'removeItem')
        # FIXME check that the correct ids are changed and removed

# FIXME Add test for database add, remove, change
# FIXME Test templates that use "thisView"
