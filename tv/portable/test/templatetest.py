import unittest
from miro.plat import resources
import os
import re
import time
import copy
from miro import feedparser
from miro import feed
from miro import item
from miro import app
from miro import maps

from miro.frontends.html.template import *
from miro.frontends.html import templateoptimize
from time import time
from miro import database
import gettext
from miro.frontends.html import compiled_templates

from miro.test.framework import DemocracyTestCase

# FIXME: Add tests for DOM Handles without changeItems or deprecate
#        the old changeItem API

ranOnUnload = 0

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
    def removeItems(self, ids):
        self.callList.append({'name':'removeItems','ids':ids})
    def changeItem(self, id, xml, changeHint):
        self.callList.append({'name':'changeItem','xml':xml,'id':id,
            'changeHint': changeHint })
    def changeItems(self, pairs):
        self.callList.append({'name':'changeItems','pairs':pairs})
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
        DemocracyTestCase.setUp(self)
        handle = file(resources.path("templates/unittest/simple"),"r")
        self.text = handle.read()
        handle.close()
        self.text = HTMLPattern.match(self.text).group(1)
    def test(self):
        (tch, handle) = fillTemplate("unittest/simple",DOMTracker(),'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assertEqual(text,self.text)
    def testExecuteTemplate(self):
        (tch, handle) = fillTemplate("unittest/execute-template",DOMTracker(),'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        testRE = re.compile(r'^\s+<span>foo</span>\s+<span>BAR</span>\s+$')
        self.assert_(testRE.match(text))

class TranslationTest(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        handle = file(resources.path("testdata/translation-result"),"r")
        self.text = handle.read()
        handle.close()
        self.text = HTMLPattern.match(self.text).group(1)
        self.oldgettext = gettext.gettext
    def tearDown(self):
        compiled_templates.unittest.translationtest._ = self.oldgettext
        DemocracyTestCase.tearDown(self)
    def test(self):
        compiled_templates.unittest.translationtest._ = lambda x : '!%s!' % x
        (tch, handle) = fillTemplate("unittest/translationtest",DOMTracker(),'gtk-x11-MozillaBrowser','platform')
        compiled_templates.unittest.translationtest._ = self.oldgettext
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assertEqual(text,self.text)

class ReplaceTest(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        handle = file(resources.path("testdata/replace-result"),"r")
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
        DemocracyTestCase.setUp(self)
        handle = file(resources.path("testdata/hide-result"),"r")
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
    containerPattern = re.compile("^\n<h1>view test template</h1>\n<div id=\"([^\"]+)\"></div>\n", re.S)
    doublePattern = re.compile("^\n<h1>view test template</h1>\n<span id=\"([^\"]+)\"/>\n<span id=\"([^\"]+)\"/>\n", re.S)
    updatePattern = re.compile("^\n<h1>update test template</h1>\n<span id=\"([^\"]+)\"/>\n", re.S)
    hidePattern = re.compile("^\n<h1>update hide test template</h1>\n<div class=\"foo\" id=\"([^\"]+)\"", re.S)
    itemPattern = re.compile("<div id=\"(.*?)\">\n<span>testview\d*</span>\n<span>&lt;span&gt;object&lt;/span&gt;</span>\n<span><span>object</span></span>\n\n<div>\nhideIf:False\n<span>This is an include</span>\n\n<span>This is a template include</span>\n\n<span>&lt;span&gt;This is a database replace&lt;/span&gt;</span>\n<span><span>This is a database replace</span></span>\n</div>\n</div>",re.S)

    def setUp(self):
        global ranOnUnload
        ranOnUnload = 0
        DemocracyTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.x = HTMLObject('<span>object</span>')
        self.y = HTMLObject('<span>object</span>')
        self.domHandle = DOMTracker()

    def test(self):
        (tch, handle) = fillTemplate("unittest/view",self.domHandle,'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assert_(self.pattern.match(text)) #span for template inserted
        id = self.pattern.match(text).group(1)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),1)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[0]['id'],id)
        match = self.itemPattern.findall(self.domHandle.callList[0]['xml'])
        self.assertEqual(len(match),2)
        self.assertNotEqual(match[0], match[1])
        self.assertEqual(ranOnUnload, 0)
        handle.unlinkTemplate()
        self.assertEqual(ranOnUnload, 1)

    def testContainerDiv(self):
        (tch, handle) = fillTemplate("unittest/view-container-div",self.domHandle,'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assert_(self.containerPattern.match(text)) #span for template inserted
        id = self.containerPattern.match(text).group(1)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),1)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemAtEnd')
        self.assertEqual(self.domHandle.callList[0]['id'],id)
        initialXML = self.domHandle.callList[0]['xml']
        match = self.itemPattern.findall(initialXML)
        self.assertEqual(len(match),2)
        self.assertNotEqual(match[0], match[1])
        handle.trackedViews[0].onResort()
        self.assertEqual(len(self.domHandle.callList),3)
        self.assertEqual(self.domHandle.callList[1]['name'],'changeItem')
        self.assertEqual(self.domHandle.callList[1]['id'],id)
        self.assertEqual(self.domHandle.callList[1]['xml'],
                '<div id="%s"></div>' % id)
        self.assertEqual(self.domHandle.callList[2]['name'],'addItemAtEnd')
        self.assertEqual(self.domHandle.callList[2]['id'],id)
        self.assertEqual(self.domHandle.callList[2]['xml'], initialXML)

    def testUpdate(self):
        (tch, handle) = fillTemplate("unittest/update",self.domHandle,'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assert_(self.updatePattern.match(text)) #span for template inserted
        id = self.updatePattern.match(text).group(1)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),1)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[0]['id'],id)
        match = self.itemPattern.findall(self.domHandle.callList[0]['xml'])
        self.assertEqual(len(match),1)

        # This should do nothing, since the HTML didn't change
        self.x.signalChange()
        handle.updateRegions[0].doChange()
        self.assertEqual(len(self.domHandle.callList),1)
        
        # Now, we get a callback
        self.x.html = '<span>changes object</span>'
        self.x.signalChange()
        handle.updateRegions[0].doChange()
        self.assertEqual(len(self.domHandle.callList),2)

        self.assertEqual(self.domHandle.callList[1]['name'],'changeItems')
        self.assertEqual(self.domHandle.callList[1]['pairs'][0][0],match[0])
        temp = HTMLObject('<span>object</span>')
        handle.updateRegions[0].doChange()
        self.assertEqual(len(self.domHandle.callList),3)
        self.assertEqual(self.domHandle.callList[2]['name'],'changeItems')
        self.assertEqual(self.domHandle.callList[2]['pairs'][0][0],match[0])
        temp.remove()
        handle.updateRegions[0].doChange()
        self.assertEqual(len(self.domHandle.callList),4)
        self.assertEqual(self.domHandle.callList[3]['name'],'changeItems')
        self.assertEqual(self.domHandle.callList[3]['pairs'][0][0],match[0])
        self.assertEqual(ranOnUnload, 0)
        handle.unlinkTemplate()
        self.assertEqual(ranOnUnload, 1)

    def testHide(self):
        (tch, handle) = fillTemplate("unittest/update-hide",self.domHandle,'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        self.assert_(self.hidePattern.match(text)) #span for template inserted
        id = self.hidePattern.match(text).group(1)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),0)
        self.x.signalChange()
        self.assertEqual(len(self.domHandle.callList),0)
        temp = HTMLObject('<span>object</span>')
        self.assertEqual(len(self.domHandle.callList),1)
        self.assertEqual(self.domHandle.callList[0]['name'],'showItem')
        self.assertEqual(self.domHandle.callList[0]['id'],id)
        temp.remove()
        self.assertEqual(len(self.domHandle.callList),2)
        self.assertEqual(self.domHandle.callList[1]['name'],'hideItem')
        self.assertEqual(self.domHandle.callList[1]['id'],id)
        self.assertEqual(ranOnUnload, 0)
        handle.unlinkTemplate()
        self.assertEqual(ranOnUnload, 1)

    def testTwoViews(self):
        (tch, handle) = fillTemplate("unittest/view-double",self.domHandle,'gtk-x11-MozillaBrowser','platform')
        text = tch.read()
        text = HTMLPattern.match(text).group(1)
        assert(self.doublePattern.match(text)) #span for template inserted
        id = self.doublePattern.match(text).group(1)
        id2 = self.doublePattern.match(text).group(2)
        handle.initialFillIn()
        self.assertEqual(len(self.domHandle.callList),2)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[1]['name'],'addItemBefore')
        self.assert_(self.domHandle.callList[0]['id'] != self.domHandle.callList[1]['id'])
        self.assert_(self.domHandle.callList[0]['id'] in [id, id2])
        self.assert_(self.domHandle.callList[1]['id'] in [id, id2])
        items1 = self.itemPattern.findall(self.domHandle.callList[0]['xml'])
        items2 = self.itemPattern.findall(self.domHandle.callList[1]['xml'])

        match = copy.copy(items1)
        match.extend(items2)
        self.assertEqual(len(match),4)

        # This does nothing to the templates, since the HTML doesn't change
        self.x.signalChange()
        handle.trackedViews[0].callback()
        handle.trackedViews[1].callback()
        self.assertEqual(len(self.domHandle.callList),2)

        # Now, those calls are made
        self.x.html = '<span>changed object</span>'
        self.x.signalChange()
        handle.trackedViews[0].callback()
        handle.trackedViews[1].callback()
        self.assertEqual(len(self.domHandle.callList),4)
        
        self.x.remove()
        handle.trackedViews[0].callback()
        handle.trackedViews[1].callback()
        self.assertEqual(len(self.domHandle.callList),6)
        self.assertEqual(self.domHandle.callList[0]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[1]['name'],'addItemBefore')
        self.assertEqual(self.domHandle.callList[2]['name'],'changeItems')
        self.assertEqual(self.domHandle.callList[3]['name'],'changeItems')
        self.assertEqual(self.domHandle.callList[4]['name'],'removeItems')
        self.assertEqual(self.domHandle.callList[5]['name'],'removeItems')
        changed1 = [p[0] for p in self.domHandle.callList[2]['pairs']]
        changed2 = [p[0] for p in self.domHandle.callList[3]['pairs']]
        self.assertEqual(len(changed1), 1)
        self.assertEqual(len(changed2), 1)
        self.assert_((changed1[0] in items1 and changed2[0] in items2) or
                changed1[0] in items2 and changed2[0] in items1)
        self.assertEqual(self.domHandle.callList[4]['name'],'removeItems')
        self.assertEqual(self.domHandle.callList[5]['name'],'removeItems')
        self.assertEquals(len(self.domHandle.callList[4]['ids']), 1)
        self.assertEquals(len(self.domHandle.callList[5]['ids']), 1)
        self.assert_(((self.domHandle.callList[4]['ids'][0] in items1) and
                          (self.domHandle.callList[5]['ids'][0] in items2)) or
                         ((self.domHandle.callList[4]['ids'][0] in items2) and
                          (self.domHandle.callList[5]['ids'][0] in items1)))

        self.x = HTMLObject('<span>object</span>')
        handle.trackedViews[0].callback()
        handle.trackedViews[1].callback()
        self.assertEqual(len(self.domHandle.callList),8)
        self.assertEqual(self.domHandle.callList[6]['name'],'addItemBefore')
        match.extend(self.itemPattern.findall(self.domHandle.callList[6]['xml']))
        self.assertEqual(self.domHandle.callList[7]['name'],'addItemBefore')
        match.extend(self.itemPattern.findall(self.domHandle.callList[7]['xml']))
        self.assertEqual(len(match),6)
        for x in range(len(match)):
            for y in range(x+1,len(match)):
                self.assertNotEqual(match[x],match[y])
        self.assertEqual(ranOnUnload, 0)
        handle.unlinkTemplate()
        self.assertEqual(ranOnUnload, 1)

class TemplatePerformance(DemocracyTestCase):
    def setUp(self):
        global ranOnUnload
        ranOnUnload = 0
        DemocracyTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.domHandle = DOMTracker()

    def timeIt(self, func, repeat):
        start = time()
        for x in xrange(repeat):
            func()
        totalTime = time() - start
        return totalTime

    def testRender(self):
        repetitions = 3
        self.feeds = []
        self.items = []
        for x in range(50):
            self.feeds.append(feed.Feed(u'http://www.getdemocracy.com/50'))
            for y in range(50):
                self.items.append(item.Item(feedparser.FeedParserDict(
                    {'title': u"%d-%d" % (x, y),
                     'enclosures': [{'url': u'file://%d-%d.mpg' % (x, y)}]}),
                                            feed_id = self.feeds[-1].id
                                            ))
        
        time1 = self.timeIt(self.fillAndUnlink, repetitions)

        for x in range(50):
            for y in range(450):
                self.items.append(item.Item(feedparser.FeedParserDict(
                    {'title': u"%d-%d" % (x, y),
                     'enclosures': [{'url': u'file://%d-%d.mpg' % (x, y)}]}),
                                            feed_id = self.feeds[x].id
                                            ))
        time2 = self.timeIt(self.fillAndUnlink, repetitions)

        # print "Filling in a 500 item feed took roughly %.4f secs" % (time2/10.0)
        # Check that filling in 500 items takes no more than roughly
        # 10x filling in 50 items
        self.assert_(time2/time1 < 11, 'Template filling does not scale linearly')


    def fillAndUnlink(self):
        (tch, handle) = fillTemplate("channel",self.domHandle,'gtk-x11-MozillaBrowser','platform', id=self.feeds[-1].getID())
        tch.read()
        handle.initialFillIn()
        handle.unlinkTemplate()

class OptimizedAttributeChangeTest(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.changer = templateoptimize.HTMLChangeOptimizer()

    def checkChange(self, id, newXML, attributesDiff, htmlChanged):
        changes = self.changer.calcChanges('abc123', newXML)
        self.assertEquals(len(changes), 1)
        self.assertEquals(changes[0][0], id)
        self.assertEquals(changes[0][1], newXML)
        self.assertEquals(changes[0][2].changedAttributes, attributesDiff)
        if htmlChanged:
            self.assert_(changes[0][2].changedInnerHTML is not None)
        else:
            self.assert_(changes[0][2].changedInnerHTML is None)

    def testBigChange(self):
        first = '<div class="item" id="abc123">foo</div>'
        second = '<div class="item" id="abc123">bar</div>'
        self.changer.setInitialHTML('abc123', first)
        self.checkChange('abc123', second, {}, True)

    def testNoChange(self):
        first = '<div class="item" id="abc123">foo</div>'
        self.changer.setInitialHTML('abc123', first)
        changes = self.changer.calcChanges('abc123', first)
        self.assertEquals(len(changes), 0)

    def testAttributeChange(self):
        first = '<div class="item" id="abc123">foo</div>'
        second = '<div class="item highlighed" id="abc123">foo</div>'
        self.changer.setInitialHTML('abc123', first)
        self.checkChange('abc123', second, {'class': 'item highlighed'},
                False)

    def testMultipleChanges(self):
        first = '<div class="item" id="abc123">foo</div>'
        second = '<div class="item highlighed" id="abc123">foo</div>'
        third = '<div class="item highlighed" id="abc123">bar</div>'
        fourth = '<div class="item" id="abc123">bar</div>'
        self.changer.setInitialHTML('abc123', first)
        self.checkChange('abc123', second, {'class': 'item highlighed'},
                False)
        self.checkChange('abc123', third, {}, True)
        self.checkChange('abc123', fourth, {'class': 'item'}, False)

class HotspotOptimizedTest(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.changer = templateoptimize.HTMLChangeOptimizer()

    def makeHotspotArea(self, outertext, innertext):
        return """\
<div id="outer">
   <p>%s</p>
   <!-- HOT SPOT inner --><span id="inner">%s</span><!-- HOT SPOT END -->
</div>""" % (outertext, innertext)

    def makeMultiHotspotArea(self, outertext, innertext, innertext2):
        return """\
<div id="outer">
   <p>%s</p>
   <!-- HOT SPOT inner --><span id="inner">%s</span><!-- HOT SPOT END -->
   <!-- HOT SPOT inner-2 --><span id="inner-2">%s</span><!-- HOT SPOT END -->
</div>""" % (outertext, innertext, innertext2)

    def checkChange(self, newXML, *shouldChangeIDs):
        changes = self.changer.calcChanges('outer', newXML)
        actuallyChanged = [c[0] for c in changes]
        self.assertEquals(set(shouldChangeIDs), set(actuallyChanged))

    def testHotspotChange(self):
        first = self.makeHotspotArea('booya', 'booyaka')
        second = self.makeHotspotArea('booya', 'booyaka booyaka')
        self.changer.setInitialHTML('outer', first)
        self.checkChange(second, 'inner')

    def testOutsideHotspotChange(self):
        first = self.makeHotspotArea('foo', 'booyaka')
        second = self.makeHotspotArea('bar', 'booyaka booyaka')
        self.changer.setInitialHTML('outer', first)
        self.checkChange(second, 'outer')

    def testMultipleHotspots(self):
        first = self.makeMultiHotspotArea('foo', 'apples', 'bananas')
        second = self.makeMultiHotspotArea('foo', 'apples', 'pears')
        third = self.makeMultiHotspotArea('foo', 'kiwi', 'starfruit')
        fourth = self.makeMultiHotspotArea('bar', 'kiwi', 'starfruit')
        self.changer.setInitialHTML('outer', first)
        self.checkChange(second, 'inner-2')
        self.checkChange(third, 'inner', 'inner-2')
        self.checkChange(fourth, 'outer')
