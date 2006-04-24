import unittest
import resource
import os
import re
import time

from template import *
from database import *

HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)

class HTMLObject(DDBObject):
    def __init__(self,html):
        self.html = html
        DDBObject.__init__(self)

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

class SimpleTest(unittest.TestCase):
    def setUp(self):
        handle = file(resource.path("templates/unittest/simple"),"r")
        self.text = handle.read()
        handle.close()
        self.text = HTMLPattern.match(self.text).group(1)
    def test(self):
        (text, handle) = fillTemplate("unittest/simple",{},lambda x: '')
        text = HTMLPattern.match(text).group(1)
        self.assertEqual(text,self.text)

class ReplaceTest(unittest.TestCase):
    def setUp(self):
        handle = file(resource.path("templates/unittest/replace-result"),"r")
        self.text = handle.read()
        handle.close()
        self.text = HTMLPattern.match(self.text).group(1)
    def test(self):
        (text, handle) = fillTemplate("unittest/replace",{"replace":"<span>This is a database replace</span>"},lambda x: '')
        text = HTMLPattern.match(text).group(1)
        self.assertEqual(text,self.text)

class HideTest(unittest.TestCase):
    def setUp(self):
        handle = file(resource.path("templates/unittest/hide-result"),"r")
        self.text = handle.read()
        handle.close()
        self.text = HTMLPattern.match(self.text).group(1)
    def bool(self,x,y):
        self.assertEqual(y, "paramtest")
        return x
    def test(self):
        (text, handle) = fillTemplate("unittest/hide",{"replace":"<span>This is a database replace</span>","true":True, "false":False, "bool":self.bool},lambda x: '')
        text = HTMLPattern.match(text).group(1)
        self.assertEqual(text,self.text)

class ViewTest(unittest.TestCase):
    pattern = re.compile("^\n<h1>view test template</h1>\n<span id=\"([^\"]+)\"/>\n", re.S)
    doublePattern = re.compile("^\n<h1>view test template</h1>\n<span id=\"([^\"]+)\"/>\n<span id=\"([^\"]+)\"/>\n", re.S)

    itemPattern = re.compile("^<div id=\"(.*?)\">\n<span>&lt;span&gt;object&lt;/span&gt;</span>\n<span><span>object</span></span>\n<div style=\"display:none\">\nhideIfKey:true\n<span>This is an include</span>\n\n<span>This is a template include</span>\n\n<span>&lt;span&gt;This is a database replace&lt;/span&gt;</span>\n<span><span>This is a database replace</span></span>\n</div>\n<div>\nhideIfNotKey:true\n<span>This is an include</span>\n\n<span>This is a template include</span>\n\n<span>&lt;span&gt;This is a database replace&lt;/span&gt;</span>\n<span><span>This is a database replace</span></span>\n</div>\n<div>\nhideIfKey:false\n<span>This is an include</span>\n\n<span>This is a template include</span>\n\n<span>&lt;span&gt;This is a database replace&lt;/span&gt;</span>\n<span><span>This is a database replace</span></span>\n</div>\n<div style=\"display:none\">\nhideIfNotKey:flase\n<span>This is an include</span>\n\n<span>This is a template include</span>\n\n<span>&lt;span&gt;This is a database replace&lt;/span&gt;</span>\n<span><span>This is a database replace</span></span>\n</div>\n",re.S)

    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
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
        (text, handle) = fillTemplate("unittest/view",{"replace":"<span>This is a database replace</span>","true":True, "false":False, "bool":self.bool, "view":self.everything},self.domHandle)
        text = HTMLPattern.match(text).group(1)
        assert(self.pattern.match(text)) #span for template inserted
        id = self.pattern.match(text).group(1)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),2)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[1]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[0]['id'],id)
        self.assertEqual(self.domHandle.callList[1]['id'],id)
        match0 = self.itemPattern.match(self.domHandle.callList[0]['xml'])
        match1 = self.itemPattern.match(self.domHandle.callList[1]['xml'])
        self.assert_(match0)
        self.assert_(match1)
        self.assertNotEqual(match0.group(1),match1.group(1))

    def testTwoViews(self):
        (text, handle) = fillTemplate("unittest/view-double",{"replace":"<span>This is a database replace</span>","true":True, "false":False, "bool":self.bool, "view":self.everything},self.domHandle)
        text = HTMLPattern.match(text).group(1)
        assert(self.doublePattern.match(text)) #span for template inserted
        id = self.doublePattern.match(text).group(1)
        id2 = self.doublePattern.match(text).group(2)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),4)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[1]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[2]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[3]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[0]['id'],id)
        self.assertEqual(self.domHandle.callList[1]['id'],id)
        self.assertEqual(self.domHandle.callList[2]['id'],id2)
        self.assertEqual(self.domHandle.callList[3]['id'],id2)
        match = []
        match.append(self.itemPattern.match(self.domHandle.callList[0]['xml']))
        match.append(self.itemPattern.match(self.domHandle.callList[1]['xml']))
        match.append(self.itemPattern.match(self.domHandle.callList[2]['xml']))
        match.append(self.itemPattern.match(self.domHandle.callList[3]['xml']))
        for x in range(0,4):
            self.assert_(match[x])
            for y in range(x+1,4):
                self.assertNotEqual(match[x].group(1),match[y].group(1))
        self.x.beginChange()
        self.x.endChange()
        self.x.remove()
        self.assertEqual(len(self.domHandle.callList),8)
        self.assertEqual(self.domHandle.callList[4]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[5]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[6]['name'],'removeItem')
        self.assertEqual(self.domHandle.callList[7]['name'],'removeItem')
        self.assertEqual(self.domHandle.callList[4]['id'],match[1].group(1))
        self.assertEqual(self.domHandle.callList[5]['id'],match[3].group(1))
        self.assertEqual(self.domHandle.callList[6]['id'],match[1].group(1))
        self.assertEqual(self.domHandle.callList[7]['id'],match[3].group(1))

    def testSameTwice(self):
        (text, handle) = fillTemplate("unittest/view-sametwice",{"replace":"<span>This is a database replace</span>","true":True, "false":False, "bool":self.bool, "view":self.everything},self.domHandle)
        text = HTMLPattern.match(text).group(1)
        assert(self.doublePattern.match(text)) #span for template inserted
        id = self.doublePattern.match(text).group(1)
        id2 = self.doublePattern.match(text).group(2)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),4)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[1]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[2]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[3]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[0]['id'],id)
        self.assertEqual(self.domHandle.callList[1]['id'],id)
        self.assertEqual(self.domHandle.callList[2]['id'],id2)
        self.assertEqual(self.domHandle.callList[3]['id'],id2)
        match = []
        match.append(self.itemPattern.match(self.domHandle.callList[0]['xml']))
        match.append(self.itemPattern.match(self.domHandle.callList[1]['xml']))
        match.append(self.itemPattern.match(self.domHandle.callList[2]['xml']))
        match.append(self.itemPattern.match(self.domHandle.callList[3]['xml']))
        for x in range(0,4):
            self.assert_(match[x])
            for y in range(x+1,4):
                self.assertNotEqual(match[x].group(1),match[y].group(1))
        self.x.beginChange()
        self.x.endChange()
        self.x.remove()
        self.assertEqual(len(self.domHandle.callList),8)
        self.assertEqual(self.domHandle.callList[4]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[5]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[6]['name'],'removeItem')
        self.assertEqual(self.domHandle.callList[7]['name'],'removeItem')
        self.assertEqual(self.domHandle.callList[4]['id'],match[1].group(1))
        self.assertEqual(self.domHandle.callList[5]['id'],match[3].group(1))
        self.assertEqual(self.domHandle.callList[6]['id'],match[1].group(1))
        self.assertEqual(self.domHandle.callList[7]['id'],match[3].group(1))

    def testOutOfOrder(self):
        self.domHandle = ChangeDelayedDOMTracker()
        (text, handle) = fillTemplate("unittest/view",{"replace":"<span>This is a database replace</span>","true":True, "false":False, "bool":self.bool, "view":self.view},self.domHandle)
        handle.initialFillIn()
        self.x.beginChange()
        self.x.endChange()
        self.x.remove()
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[1]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[2]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[3]['name'],'removeItem')

    def testIndexSort(self):
        print "Index sort test"
        HTMLObject('<span>bogus</span>')
        HTMLObject('<span>bogus</span>')
        HTMLObject('<span>bogus</span>')
        self.domHandle = ChangeDelayedDOMTracker()
        (text, handle) = fillTemplate("unittest/ifsview",{"replace":"<span>This is a database replace</span>","true":True, "false":False, "bool":self.bool, "view":self.everything,"sort":self.sortFunc,"index":self.indexFunc,"value":'1',"filter":self.filterFunc},self.domHandle)
        handle.initialFillIn()
        HTMLObject('<span>bogus</span>')
        HTMLObject('<span>bogus</span>')
        HTMLObject('<span>bogus</span>')
        HTMLObject('<span>bogus</span>')
        HTMLObject('<span>bogus</span>')
        self.x.beginChange()
        self.x.endChange()
        self.x.remove()
        self.assertEqual(len(self.domHandle.callList),4)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[1]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[2]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[3]['name'],'removeItem')
        print "Done index sort test"

# FIXME Add test for evalKey
# FIXME Add test for database add, remove, change
# FIXME Test templates that use "this" and "thisView"
