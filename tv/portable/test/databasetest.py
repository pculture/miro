import unittest
from miro import database
from os import remove
from os.path import expanduser
import random
from miro import config
from miro import prefs
import os
import random
import shutil
import time
import tempfile
from miro import storedatabase
from threading import Thread

from miro.test.framework import MiroTestCase

class SortableObject(database.DDBObject):
    def setup_new(self, value):
        self.value = value

class EmptyViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
    def testCur(self):
        self.everything.resetCursor()
        self.assertEqual(self.everything.cur(),None)
    def testNext(self):
        self.everything.resetCursor()
        self.assertEqual(self.everything.getNext(),None)
    def testGetItem(self):
        self.assertEqual(self.everything[0],None)
    def testGetPrev(self):
        self.everything.resetCursor()
        self.assertEqual(self.everything.getPrev(),None)
    def testLen(self):
        self.assertEqual(self.everything.len(),0)
        
class SingleItemViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.x = database.DDBObject()
    def testAdd(self):
        self.assertEqual(self.x.__class__, database.DDBObject)
    def testGetItem(self):
        a = self.everything[0]
        b = self.everything[1]
        self.assertEqual(a.__class__, database.DDBObject)
        self.assertEqual(b,None)
    def testNext(self):
        self.everything.resetCursor()
        a = self.everything.cur()
        b = self.everything.getNext()
        c = self.everything.cur()
        d = self.everything.getNext()
        assert ((a == None) and (b.__class__ == database.DDBObject) and
                (c == b) and (d == None))
    def testGetPrev(self):
        self.everything.resetCursor()
        self.assertEqual(self.everything.getPrev(),None)
    def testLen(self):
        self.assertEqual(self.everything.len(),1)

class AddBeforeViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.x = database.DDBObject()
        self.y = database.DDBObject()
        database.resetDefaultDatabase()
        self.everything = database.defaultDatabase
        self.everything.addBeforeCursor(self.y)
        self.everything.resetCursor()
        self.everything.addBeforeCursor(self.x)
    def testUnique(self):
        self.assertNotEqual(self.x,self.y)
    def testUniqueID(self):
        self.assertNotEqual(self.x.getID(),self.y.getID())
    def testGetItem(self):
        a = self.everything[0]
        b = self.everything[1]
        c = self.everything[2]
        self.assertEqual(a.__class__,database.DDBObject)
        self.assertEqual(b.__class__,database.DDBObject)
        self.assertNotEqual(a,b)
        self.assertEqual(c,None)
    def testNextGetPrev(self):
        self.everything.resetCursor()
        a = self.everything.cur()
        b = self.everything.getNext()
        c = self.everything.cur()
        d = self.everything.getNext()
        e = self.everything.cur()
        f = self.everything.getNext()
        assert ((a == None) and (b.__class__ == database.DDBObject) and
                (c == b) and (d.__class__ == database.DDBObject) and
                (d != c) and (d == e) and (f == None))
    def testLen(self):
        self.assertEqual(self.everything.len(),2)

class AddAfterViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.x = database.DDBObject()
        self.y = database.DDBObject()
        database.resetDefaultDatabase()
        self.everything = database.defaultDatabase
        self.everything.addAfterCursor(self.x)
        self.everything.resetCursor()
        self.everything.getNext()
        self.everything.addAfterCursor(self.y)
    def testUnique(self):
        self.assertNotEqual(self.x,self.y)
    def testUniqueID(self):
        self.assertNotEqual(self.x.getID(),self.y.getID())
    def testGetItem(self):
        a = self.everything[0]
        b = self.everything[1]
        c = self.everything[2]
        self.assertEqual(a.__class__,database.DDBObject)
        self.assertEqual(b.__class__,database.DDBObject)
        self.assertNotEqual(a,b)
        self.assertEqual(c,None)
    def testNextGetPrev(self):
        self.everything.resetCursor()
        a = self.everything.cur()
        b = self.everything.getNext()
        c = self.everything.cur()
        d = self.everything.getNext()
        e = self.everything.cur()
        f = self.everything.getNext()
        assert ((a == None) and (b.__class__ == database.DDBObject) and
                (c == b) and (d.__class__ == database.DDBObject) and
                (d != c) and (d == e) and (f == None))
    def testLen(self):
        self.assertEqual(self.everything.len(),2)

class DeletedItemViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.x = database.DDBObject()
        self.y = database.DDBObject()
        self.x.remove()
    def testRemoveMissing(self):
        self.everything.resetCursor()
        self.assertRaises(database.ObjectNotFoundError,self.everything.remove)
    def testAdd(self):
        self.assertEqual(self.x.__class__,database.DDBObject)
    def testGetItem(self):
        a = self.everything[0]
        b = self.everything[1]
        self.assertEqual(a,self.y)
        self.assertEqual(b,None)
    def testNext(self):
        self.everything.resetCursor()
        a = self.everything.cur()
        b = self.everything.getNext()
        c = self.everything.cur()
        d = self.everything.getNext()
        assert ((a == None) and (b.__class__ == database.DDBObject) and
                (c == b) and (d == None))
    def testLen(self):
        self.assertEqual(self.everything.len(),1)

class FilterViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.x = database.DDBObject()
        self.y = database.DDBObject()
        self.filtered = self.everything.filter(lambda q:q != self.x)
    def testGetItem(self):
        a = self.filtered[0]
        b = self.filtered[1]
        self.assertEqual(a,self.y)
        self.assertEqual(b,None)
    def testNext(self):
        self.filtered.resetCursor()
        a = self.filtered.cur()
        b = self.filtered.getNext()
        c = self.filtered.cur()
        d = self.filtered.getNext()
        assert ((a == None) and (b == self.y) and
                (c == b) and (d == None))
    def testGetPrev(self):
        self.filtered.resetCursor()
        self.assertEqual(self.filtered.getPrev(),None)
    def testLen(self):
        self.assertEqual(self.filtered.len(),1)

class RecomputeFilterViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.x = database.DDBObject()
        self.y = database.DDBObject()
        self.accept = self.x.getID()
        self.filtered = self.everything.filter(self.changeFilt)
        self.accept = self.y.getID()
        self.everything.recomputeFilters()
    def changeFilt(self, obj):
        return obj.getID() == self.accept
    def testGetItem(self):
        a = self.filtered[0]
        b = self.filtered[1]
        self.assertEqual(a,self.y)
        self.assertEqual(b,None)
    def testNext(self):
        self.filtered.resetCursor()
        a = self.filtered.cur()
        b = self.filtered.getNext()
        c = self.filtered.cur()
        d = self.filtered.getNext()
        assert ((a == None) and (b == self.y) and
                (c == b) and (d == None))
    def testGetPrev(self):
        self.filtered.resetCursor()
        self.assertEqual(self.filtered.getPrev(),None)
    def testLen(self):
        self.assertEqual(self.filtered.len(),1)

class SortTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.x = database.DDBObject()
        self.y = database.DDBObject()
        self.higher = self.x
        self.sorted = self.everything.sort(self.sortFunc)
    def sortFunc(self,x,y):
        return x[1] != self.higher
    def testUnique(self):
        self.assertNotEqual(self.x,self.y)
    def testUniqueID(self):
        self.assertNotEqual(self.x.getID(),self.y.getID())
    def testGetItem(self):
        a = self.sorted[0]
        b = self.sorted[1]
        c = self.sorted[2]
        self.assertEqual(a,self.y)
        self.assertEqual(b,self.x)
        self.assertNotEqual(a,b)
        self.assertEqual(c,None)
    def testNextGetPrev(self):
        self.sorted.resetCursor()
        a = self.sorted.cur()
        b = self.sorted.getNext()
        c = self.sorted.cur()
        d = self.sorted.getNext()
        e = self.sorted.cur()
        f = self.sorted.getNext()
        assert ((a == None) and (b.__class__ == database.DDBObject) and
                (c == b) and (d.__class__ == database.DDBObject) and
                (d != c) and (d == e) and (f == None))
    def testLen(self):
        self.assertEqual(self.everything.len(),2)
    def testRecompute(self):
        self.higher = self.y
        self.everything.recomputeFilters()
        a = self.sorted[0]
        b = self.sorted[1]
        c = self.sorted[2]
        self.assertEqual(a,self.x)
        self.assertEqual(b,self.y)
        self.assertNotEqual(a,b)
        self.assertEqual(c,None)
    def testSignalChange(self):
        self.higher = self.y
        self.assertEqual(self.sorted[0],self.y)
        self.assertEqual(self.sorted[1],self.x)
        self.x.signal_change()
        self.assertEqual(self.sorted[0],self.y)
        self.assertEqual(self.sorted[1],self.x)
    def testResort(self):
        self.sorted = self.everything.sort(self.sortFunc, resort=True)
        self.assertEqual(self.sorted[0],self.y)
        self.assertEqual(self.sorted[1],self.x)
        self.higher = self.y
        self.x.signal_change()
        self.assertEqual(self.sorted[0],self.x)
        self.assertEqual(self.sorted[1],self.y)

class MapViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.x = database.DDBObject()
        self.y = database.DDBObject()
        self.add = 0
        self.mapped = self.everything.map(self.mapFunc)
    def mapFunc(self,obj):
        return obj.getID()+self.add
    def testNotAltered(self):
        self.assertNotEqual(self.x,self.mapped[0])
        self.assertNotEqual(self.x,self.mapped[1])
        self.assertNotEqual(self.y,self.mapped[0])
        self.assertNotEqual(self.y,self.mapped[1])
    def testUnique(self):
        self.assertNotEqual(self.x,self.y)
    def testUniqueID(self):
        self.assertNotEqual(self.x.getID(),self.y.getID())
    def testGetItem(self):
        a = self.mapped[0]
        b = self.mapped[1]
        c = self.mapped[2]
        self.assertEqual(a,self.everything[0].getID())
        self.assertEqual(b,self.everything[1].getID())
        self.assertNotEqual(a,b)
        self.assertEqual(c,None)
    def testNextGetPrev(self):
        self.mapped.resetCursor()
        a = self.mapped.cur()
        b = self.mapped.getNext()
        c = self.mapped.cur()
        d = self.mapped.getNext()
        e = self.mapped.cur()
        f = self.mapped.getNext()
        assert ((a == None) and (b.__class__.__name__ == 'int') and
                (c == b) and (d.__class__.__name__ == 'int') and
                (d != c) and (d == e) and (f == None))
    def testLen(self):
        self.assertEqual(self.everything.len(),2)

class CallbackViewTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.filtered = self.everything.filter(lambda x:True)
        self.mapped = self.everything.map(lambda x:x)
        self.sorted = self.everything.sort(lambda x,y:0)
        self.callcount = 0
    def call(self, obj, id):
        assert id == self.everything[0].getID()
        self.callcount+=1
    def removeCall(self, obj, id):
        self.callcount+=1
    def testAdd(self):
        self.everything.addAddCallback(self.call)
        self.x = database.DDBObject()
        self.assertEqual(self.callcount,1)
    def testChange(self):
        self.everything.add_change_callback(self.call)
        self.x = database.DDBObject()
        self.x.signal_change()
        self.assertEqual(self.callcount,1)
    def testRemove(self):
        self.everything.addRemoveCallback(self.removeCall)
        self.x = database.DDBObject()
        self.x.remove()
        self.assertEqual(self.callcount,1)
    def TestFilterAdd(self):
        self.filtered.addAddCallBack(self.call)
        self.x = database.DDBObject()
        self.assertEqual(self.callcount,1)
    def TestFilterRemove(self):
        self.filtered.addRemoveCallBack(self.call)
        self.x = database.DDBObject()
        self.x.remove()
        self.assertEqual(self.callcount,1)
    def TestFilterChange(self):
        self.filtered.addChangeCallBack(self.call)
        self.x = database.DDBObject()
        self.x.change()
        self.assertEqual(self.callcount,1)
    def TestMapAdd(self):
        self.mapped.addAddCallBack(self.call)
        self.x = database.DDBObject()
        self.assertEqual(self.callcount,1)
    def TestMapRemove(self):
        self.mapped.addRemoveCallBack(self.call)
        self.x = database.DDBObject()
        self.x.remove()
        self.assertEqual(self.callcount,1)
    def TestMapChange(self):
        self.mapped.addChangeCallBack(self.call)
        self.x = database.DDBObject()
        self.x.change()
        self.assertEqual(self.callcount,1)
    def TestSortAdd(self):
        self.sorted.addAddCallBack(self.call)
        self.x = database.DDBObject()
        self.assertEqual(self.callcount,1)
    def TestSortRemove(self):
        self.sorted.addRemoveCallBack(self.call)
        self.x = database.DDBObject()
        self.x.remove()
        self.assertEqual(self.callcount,1)
    def TestSortChange(self):
        self.sorted.addChangeCallBack(self.call)
        self.x = database.DDBObject()
        self.x.change()
        self.assertEqual(self.callcount,1)

class FilterUpdateOnChange(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.origObjs = [database.DDBObject(), database.DDBObject(), database.DDBObject()]
        self.origObjs[0].good = True
        self.origObjs[1].good = False
        self.origObjs[2].good = False
        self.objs = self.everything.filter(lambda x: x.good)
        self.changeCalls = 0
    def testLoss(self):
        self.assertEqual(self.objs.len(),1)
        self.origObjs[0].good = False
        self.origObjs[0].signal_change()
        self.assertEqual(self.objs.len(),0)
    def testAdd(self):
        self.assertEqual(self.objs.len(),1)
        self.origObjs[1].good = True
        self.origObjs[1].signal_change()
        self.assertEqual(self.objs.len(),2)

class SortUpdateOnChange(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.origObjs = [database.DDBObject(), database.DDBObject(), database.DDBObject()]
        self.origObjs[0].good = True
        self.origObjs[1].good = False
        self.origObjs[2].good = False
        self.objs = self.everything.sort(lambda x, y: 0).sort(lambda x, y: 0).filter(lambda x: x.good)
        self.changeCalls = 0
    def testLoss(self):
        self.assertEqual(self.objs.len(),1)
        self.origObjs[0].good = False
        self.origObjs[0].signal_change()
        self.assertEqual(self.objs.len(),0)
    def testAdd(self):
        self.assertEqual(self.objs.len(),1)
        self.origObjs[1].good = True
        self.origObjs[1].signal_change()
        self.assertEqual(self.objs.len(),2)

class IDBaseTraversal(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.origObjs = [database.DDBObject(), database.DDBObject(), database.DDBObject()]
        self.sorted = self.everything.sort(self.sortID)
    def sortID(self,x,y):
        return x[1].getID() < y[1].getID()
    def test(self):
        self.assertEqual(self.origObjs[0],
                         self.sorted.getObjectByID(self.origObjs[0].getID()))
        self.assertEqual(self.origObjs[1],
                         self.sorted.getObjectByID(self.origObjs[1].getID()))
        self.assertEqual(self.origObjs[2],
                         self.sorted.getObjectByID(self.origObjs[2].getID()))
        
        self.assertEqual(self.origObjs[1].getID(),
                         self.sorted.getNextID(self.origObjs[0].getID()))
        self.assertEqual(self.origObjs[2].getID(),
                         self.sorted.getNextID(self.origObjs[1].getID()))
        self.assertEqual(None,self.sorted.getNextID(self.origObjs[2].getID()))

        self.assertEqual(None,self.sorted.getPrevID(self.origObjs[0].getID()))
        self.assertEqual(self.origObjs[0].getID(),
                         self.sorted.getPrevID(self.origObjs[1].getID()))
        self.assertEqual(self.origObjs[1].getID(),
                         self.sorted.getPrevID(self.origObjs[2].getID()))
    
        self.sorted.resetCursor()
        self.sorted.getNext()
        self.assertEqual(self.origObjs[0].getID(), self.sorted.getCurrentID())
        self.sorted.getNext()
        self.assertEqual(self.origObjs[1].getID(), self.sorted.getCurrentID())
        self.sorted.getNext()
        self.assertEqual(self.origObjs[2].getID(), self.sorted.getCurrentID())

# class ThreadTest(MiroTestCase):
#     def setUp(self):
#         self.everything = database.defaultDatabase
#     def add100(self):
#         for x in range(0,100):
#             database.DDBObject()
#     def remove100(self):
#         for x in range(0,100):
#             self.everything[0].remove()
#     def testAddRemove(self):
#         self.add100()
#         thread = Thread(target = self.add100)
#         thread.setDaemon(False)
#         thread.start()
#         self.remove100()
#         thread.join()

class IndexFilterTestBase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.addCallbacks = 0
        self.removeCallbacks = 0
        self.changeCallbacks = 0
    def addCallback(self,value,id):
        self.addCallbacks += 1
    def removeCallback(self,value,id):
        self.removeCallbacks += 1
    def changeCallback(self,value,id):
        self.changeCallbacks += 1

class IndexFilterTest(IndexFilterTestBase):
    def setUp(self):
        IndexFilterTestBase.setUp(self)
        self.shift = 0
    def mod10(self, x):
        return (x.getID() + self.shift) % 10
    def mod100(self, x):
        return (x.getID() + self.shift) % 100
    def sortIndexFunc(self, x, y):
        return x[1].myValue < y[1].myValue
    def sortFunc(self, x, y):
        x = x[1].getID()
        y = y[1].getID()
        return x < y
    def testBasicIndexFilter(self):
        for x in range(0,100):
            database.DDBObject()
        self.everything.createIndex(self.mod10)
        filtered = self.everything.filterWithIndex(self.mod10,0)
        self.assertEqual(filtered.len(),10)
        for x in range(0,50):
            database.DDBObject()
        self.assertEqual(filtered.len(),15)
        for i in range(10):
            obj = self.everything.getItemWithIndex(self.mod10, i)
            self.assertEqual(self.mod10(obj), i)
        obj = self.everything.getItemWithIndex(self.mod10, 10)
        self.assertEqual(obj, None)
        obj = self.everything.getItemWithIndex(self.mod10, -1, default=123123)
        self.assertEqual(obj, 123123)
        filtered.addAddCallback(self.addCallback)
        filtered.addRemoveCallback(self.removeCallback)
        filtered.add_change_callback(self.changeCallback)
        for x in range(0,50):
            database.DDBObject()

        self.assertEqual(self.addCallbacks,5)
        for obj in filtered:
            self.assertEqual(self.mod10(obj),0)
        filtered[0].remove()
        self.assertEqual(filtered.len(),19)
        self.assertEqual(self.removeCallbacks,1)
        filtered[0].signal_change()
        self.assertEqual(self.changeCallbacks,1)

        obj = filtered[0]
        self.everything.removeView(filtered)
        for x in range(0,50):
            database.DDBObject()
        self.assertEqual(self.addCallbacks,5)
        obj.signal_change()
        self.assertEqual(self.changeCallbacks,1)
        obj.remove()
        self.assertEqual(self.removeCallbacks,1)
    def testIndexChanges(self):
        class IndexedObject(database.DDBObject):
            def setup_new(self, myValue):
                self.myValue = myValue
        def indexFunc(obj):
            return obj.myValue
        foo = IndexedObject('blue')
        bar = IndexedObject('red')
        baz = IndexedObject('red')
        self.everything.createIndex(indexFunc)
        blueView = self.everything.filterWithIndex(indexFunc, 'blue')
        redView = self.everything.filterWithIndex(indexFunc, 'red')
        self.assertEquals(blueView.len(), 1)
        self.assertEquals(redView.len(), 2)
        baz.myValue = 'blue'
        baz.signal_change()
        self.assertEquals(blueView.len(), 2)
        self.assertEquals(redView.len(), 1)
        # test changing to a new view that we've never referenced before.
        foo.myValue = 'green'
        foo.signal_change()
        greenView = self.everything.filterWithIndex(indexFunc, 'green')
        self.assertEquals(blueView.len(), 1)
        self.assertEquals(redView.len(), 1)
        self.assertEquals(greenView.len(), 1)
    def testRemoveIndexedView(self):
        for x in range(0,100):
            database.DDBObject()
        self.everything.createIndex(self.mod10)
        views = [self.everything.filterWithIndex(self.mod10, i) \
                for i in range(10)]
        # remove half the views with parent.removeView()
        for view in views[:5]:
            self.everything.removeView(view)
        # remove the other half with unlink()
        for view in views[5:]:
            view.unlink()
    def testRecomputeIndex(self):
        for x in range(0,100):
            database.DDBObject()
        self.everything.createIndex(self.mod10)
        for x in range(0,50):
            database.DDBObject()
        filtered = self.everything.filterWithIndex(self.mod10,0)
        for x in range(0,50):
            database.DDBObject()
        self.assertEqual(filtered.len(),20)
        filtered[0].remove()
        self.assertEqual(filtered.len(),19)
        self.shift = 1
        self.everything.recomputeFilters()
        self.assertEqual(filtered.len(),20)
    def testLargeSet(self):
        self.everything.createIndex(self.mod100)
        start = time.clock()
        for x in range(0,500):
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
        mid = time.clock()
        for x in range(0,500):
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
            database.DDBObject()
        end = time.clock()
        # Make sure insert time doesn't increase as the size of the
        # database increases
        assert ( (end-mid) - (mid-start) < (mid-start)/2)
        filtered = self.everything.filterWithIndex(self.mod100,0).sort(self.sortFunc)
        self.assertEqual(filtered.len(),100)
    def testSortedIndex(self):
        class IndexedObject(database.DDBObject):
            def setup_new(self, myValue):
                self.myValue = myValue
        self.everything.createIndex(self.mod10,self.sortIndexFunc, resort = True)
        self.objects = []
        for x in range(100):
            self.objects.append(IndexedObject(x))

        # Test basic sorting
        filtered = self.everything.filterWithIndex(self.mod10,0)
        self.assertEqual(filtered.len(), 10)
        last = None
        for obj in filtered:
            if last is not None:
                self.assert_(last.myValue < obj.myValue)
            last = obj

        # Test changing values without signaling
        filtered[0].myValue = 1000
        filtered[1].myValue = -1000

        unordered = False
        last = None
        filtered.resetCursor()
        for obj in filtered:
            if last is not None:
                if not (last.myValue < obj.myValue):
                    unordered = True
            last = obj
        self.assert_(unordered)

        # Test that things get re-ordered correctly on signal_change
        filtered[0].signal_change()
        filtered[1].signal_change()
        last = None
        filtered.resetCursor()
        for obj in filtered:
            if last is not None:
                self.assert_(last.myValue < obj.myValue)
            last = obj
        # Test that a new filter on the index is sorted
        filtered2 = self.everything.filterWithIndex(self.mod10,0)
        self.assertEqual(filtered2.len(), 10)
        last = None
        for obj in filtered2:
            if last is not None:
                self.assert_(last.myValue < obj.myValue)
            last = obj

    def testChangeIndexValue(self):
        for x in range(0,100):
            database.DDBObject()
        self.everything.createIndex(self.mod10, sortFunc=self.sortFunc, resort = True)
        filtered = self.everything.filterWithIndex(self.mod10,0)
        filtered.addAddCallback(self.addCallback)
        filtered.addRemoveCallback(self.removeCallback)
        filtered.add_change_callback(self.changeCallback)

        filtered.changeIndexValue(self.mod10, 1)
        self.assertEqual(filtered.len(),10)
        self.assertEqual(self.addCallbacks,10)
        self.assertEqual(self.removeCallbacks,10)
        self.assertEqual(self.changeCallbacks,0)

        filtered.resetCursor()
        filtered3 = self.everything.filterWithIndex(self.mod10,0)
        filtered2 = self.everything.filterWithIndex(self.mod10,1)
        for obj in filtered2:
            self.assertEqual(filtered.getNext().id, obj.id)
            self.assertNotEqual(filtered3.getNext().id, obj.id)

        for x in range(0,100):
            database.DDBObject()
        self.assertEqual(filtered.len(),20)
        self.assertEqual(self.addCallbacks,20)

        filtered.changeIndexValue(self.mod10, 0)
        filtered.resetCursor()
        filtered2.resetCursor()
        filtered3.resetCursor()
        for obj in filtered3:
            self.assertEqual(filtered.getNext().id, obj.id)
            self.assertNotEqual(filtered2.getNext().id, obj.id)
        self.assertEqual(filtered.len(),20)
        self.assertEqual(self.addCallbacks,40)
        self.assertEqual(self.removeCallbacks,30)
        self.assertEqual(self.changeCallbacks,0)
        self.everything.removeView(filtered)
        for x in range(0,100):
            database.DDBObject()
        self.assertEqual(self.addCallbacks,40)
        self.assertEqual(self.removeCallbacks,30)
        self.assertEqual(self.changeCallbacks,0)
        
class MultiIndexed(database.DDBObject):
    def setup_new(self, indexValues):
        self.indexValues = indexValues
def testMultiIndex(obj):
    return obj.indexValues

class MultiIndexTestCase(IndexFilterTestBase):
    def setUp(self):
        IndexFilterTestBase.setUp(self)
        random.seed(12341234)
        self.allObjects = []
        self.objectsByValueCount = {}
        for i in range(20):
            self.newObject()
        self.everything.createIndex(testMultiIndex, multiValued=True)

    def genRandomValues(self):
        values = set()
        for i in xrange(random.randint(0, 4)):
            values.add(random.randint(0, 10))
        return list(values)

    def newObject(self):
        indexValues = self.genRandomValues()
        obj = MultiIndexed(indexValues)
        self.allObjects.append(obj)
        try:
            self.objectsByValueCount[len(indexValues)].append(obj)
        except KeyError:
            self.objectsByValueCount[len(indexValues)] = [obj]

    def checkViews(self):
        viewsShouldHave = {}
        for obj in self.allObjects:
            for value in obj.indexValues:
                try:
                    viewsShouldHave[value].add(obj)
                except KeyError:
                    viewsShouldHave[value] = set([obj])
        for value, goal in viewsShouldHave.items():
            filtered = self.everything.filterWithIndex(testMultiIndex, value)
            reality = set([obj for obj in filtered])
            self.assertEqual(goal, reality)

    def testInitalViews(self):
        self.checkViews()

    def testRemove(self):
        while self.allObjects:
            obj = self.allObjects.pop()
            obj.remove()
            self.checkViews()

    def testChange(self):
        for obj in self.allObjects:
            obj.indexValues = self.genRandomValues()
            obj.signal_change(needsSave=False)
            self.checkViews()

    def testCallbacks(self):
        filtered = self.everything.filterWithIndex(testMultiIndex, 0)
        filtered.addAddCallback(self.addCallback)
        filtered.addRemoveCallback(self.removeCallback)
        filtered.add_change_callback(self.changeCallback)
        addCallbackGoal = removeCallbackGoal = changeCallbackGoal = 0
        for obj in self.allObjects:
            newValues = self.genRandomValues()
            if 0 in newValues:
                if 0 not in obj.indexValues:
                    addCallbackGoal += 1
                else:
                    changeCallbackGoal += 1
            elif 0 in obj.indexValues:
                removeCallbackGoal += 1
            obj.indexValues = newValues
            obj.signal_change(needsSave=False)
            self.assertEquals(self.changeCallbacks, changeCallbackGoal)
            self.assertEquals(self.addCallbacks, addCallbackGoal)
            self.assertEquals(self.removeCallbacks, removeCallbackGoal)

class ReSortTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.addCallbacks = 0
        self.removeCallbacks = 0
        self.changeCallbacks = 0
        self.objlist = []
        for x in range(0,10):
            self.objlist.append(SortableObject(x))
        self.sorted = self.everything.sort(self.sortFunc, resort = True)
        self.sorted.addAddCallback(self.addCall)
        self.sorted.addRemoveCallback(self.removeCall)
        self.sorted.add_change_callback(self.changeCall)

    def sortFunc(self, x, y):
        return x[1].value < y[1].value

    def addCall(self, obj, id):
        # We have a convention of setting the cursor after the object
        self.assertEqual(self.sorted.getPrev().getID(),id)
        
        self.addCallbacks += 1

    def removeCall(self, obj, id):
        self.removeCallbacks += 1

    def changeCall(self, obj, id):
        self.changeCallbacks += 1

    def testResort(self):
        self.sorted.resetCursor()
        last = None
        for obj in self.sorted:
            if last is not None:
                self.assert_(last.value < obj.value)
            last = obj
            
        self.objlist[0].value = 100
        self.objlist[0].signal_change()

        self.sorted.resetCursor()
        last = None
        for obj in self.sorted:
            if last is not None:
                self.assert_(last.value < obj.value)
            last = obj
        self.assertEqual(self.addCallbacks, 1)
        self.assertEqual(self.removeCallbacks, 1)
        self.assertEqual(self.changeCallbacks, 0)

class SortingFilterTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.sortCalls = 0
        self.objs = []
        self.reversed = False

    def sortFunc(self, x, y):
        self.sortCalls += 1
        return x[1].value < y[1].value

    def sortFuncReversable(self, x, y):
        self.sortCalls += 1
        retval = x[1].value < y[1].value
        if self.reversed:
            retval = not retval
        return retval

    def testSort(self):
        sortView = self.everything.sort(self.sortFunc)
        for x in range(2000):
            a = SortableObject(2000)
            self.objs.append(a)
        initialSorts = self.sortCalls
        self.sortCalls = 0
        filtView = sortView.filter(lambda x:True,sortFunc=self.sortFunc)
        filterSorts = self.sortCalls
        self.sortCalls = 0

        self.assertEqual(sortView.len(),filtView.len())
        sortView.resetCursor()
        filtView.resetCursor()
        for obj in sortView:
            self.assertEqual(obj,filtView.getNext())

        self.objs[-1].value = -10
        self.objs[-1].signal_change()
        self.objs[-2].value = 0
        self.objs[-2].signal_change()
        self.assertEqual(self.sortCalls, 0)
        sortView.unlink()
        filtView.unlink()

    def testResort(self):
        sortView = self.everything.sort(self.sortFunc, resort = True)
        for x in range(2000):
            a = SortableObject(x)
            self.objs.append(a)
        initialSorts = self.sortCalls
        self.sortCalls = 0
        filtView = sortView.filter(lambda x:True,sortFunc=self.sortFunc,
                                   resort=True)
        filterSorts = self.sortCalls
        self.sortCalls = 0

        self.assertEqual(sortView.len(),filtView.len())
        sortView.resetCursor()
        filtView.resetCursor()
        last = None
        for obj in sortView:
            self.assertEqual(obj,filtView.getNext())
            if last != None:
                self.assert_(obj.value >= last.value)
            last = obj

        self.objs[-1].value = -10
        self.objs[-1].signal_change()
        self.objs[-2].value = -1
        self.objs[-2].signal_change()
        self.assert_(self.sortCalls > 0)

        sortView.resetCursor()
        filtView.resetCursor()
        last = None
        for obj in sortView:
            self.assertEqual(obj,filtView.getNext())
            if last != None:
                self.assert_(obj.value >= last.value)
            last = obj
        
        sortView.unlink()
        filtView.unlink()

    def testPerformance(self):
        # Filtering an already sorted list with a sort must be O(n)
        #
        # In other words, we need to make sure that the list isn't
        # being resorted
        sortView = self.everything.sort(self.sortFunc)
        initialSorts = []
        filterSorts = []
        for n in [100, 900, 9100]:
            for x in range(n):
                a = SortableObject(n)
                self.objs.append(a)
            initialSorts.append(self.sortCalls)
            self.sortCalls = 0
            filtView = sortView.filter(lambda x:True,sortFunc=self.sortFunc)
            filterSorts.append(self.sortCalls)
            self.sortCalls = 0
        ratio1 = float(filterSorts[1])/filterSorts[0]
        ratio2 = float(filterSorts[2])/filterSorts[1]

        # Make sure the ratios are within 1% of each other
        self.assert_(abs(ratio1-ratio2)/ratio1 < 0.01)

    def testResortFilter(self):
        filtView = self.everything.filter(lambda *args: True, resort=True, sortFunc=self.sortFuncReversable)
        self.reversed = False
        for i in range (20):
            a = SortableObject(i)
            self.objs.append(a)
        for i in range (20):
            self.assertEqual(filtView[i].value, i)
        self.reversed = True
        for i in range (20):
            self.assertEqual(filtView[i].value, i)
        self.everything.recomputeSort(filtView)
        for i in range (20):
            self.assertEqual(filtView[i].value, 19 - i)

    def testExplicitResort(self):
        def indexFunc(x):
            return True
        def indexFunc2(x):
            return True
        def multiIndexFunc(x):
            return [True]
        def multiIndexFunc2(x):
            return [True]
        
        sortView = self.everything.sort(self.sortFunc, resort = True)
        for x in range(2000):
            a = SortableObject(x)
            self.objs.append(a)
        initialSorts = self.sortCalls
        self.sortCalls = 0

        subSort = sortView.sort(self.sortFunc, resort = True)
        unSubSort = sortView.sort(self.sortFunc, resort = False)
        sortingFiltView = sortView.filter(lambda x:True,sortFunc=self.sortFunc,
                                   resort=True)
        unsortingFiltView = sortView.filter(lambda x:True,sortFunc=self.sortFunc,
                                            resort=False)
        
        sortView.createIndex(indexFunc,sortFunc=self.sortFunc, resort = True)
        sortingIndexView = sortView.filterWithIndex(indexFunc, True)

        sortView.createIndex(indexFunc2,sortFunc=self.sortFunc, resort = False)
        unsortingIndexView = sortView.filterWithIndex(indexFunc2, True)

        sortView.createIndex(multiIndexFunc,sortFunc=self.sortFunc, resort = True,
                             multiValued = True)
        sortingMultiIndexView = sortView.filterWithIndex(multiIndexFunc, True)
        
        sortView.createIndex(multiIndexFunc2,sortFunc=self.sortFunc, resort = False,
                             multiValued = True)
        unsortingMultiIndexView = sortView.filterWithIndex(multiIndexFunc2, True)

        allMyViews = [sortingFiltView, unsortingFiltView,
                      sortingIndexView, unsortingIndexView,
                      sortingMultiIndexView, unsortingMultiIndexView,
                      subSort, unSubSort]

        allSortingViews = [subSort, sortingFiltView, sortingIndexView,
                           sortingMultiIndexView]

        allUnSortingViews = [unsortingFiltView, unSubSort,
                             unsortingIndexView, unsortingMultiIndexView]

        for view in allMyViews:
            self.assertEqual(sortView.len(),view.len())
            view.resetCursor()

            last = None
            sortView.resetCursor()
            for obj in sortView:
                self.assertEqual(obj,view.getNext())
                if last != None:
                    self.assert_(obj.value >= last.value)
                last = obj

        self.objs[-1].value = -10
        self.objs[-2].value = -1
        self.everything.recomputeSort(sortView)
        self.assert_(self.sortCalls > 0)

        for view in allUnSortingViews:
            self.assertEqual(sortView.len(),view.len())
            view.resetCursor()
            sortView.resetCursor()
            for obj in sortView:
                self.assertNotEqual(obj,view.getNext())

        for view in allSortingViews:
            self.assertEqual(sortView.len(),view.len())
            view.resetCursor()
            last = None
            sortView.resetCursor()
            for obj in sortView:
                self.assertEqual(obj,view.getNext())
                if last != None:
                    self.assert_(obj.value >= last.value)
                last = obj

        sortView.unlink()
        for view in allMyViews:
            view.unlink()

class UnlinkViewTestCase(MiroTestCase):
    def setUp(self):
        self.sortCalls = 0
        MiroTestCase.setUp(self)
        self.everything = database.defaultDatabase
        self.x = database.DDBObject()
        self.y = database.DDBObject()
        self.parent = self.everything.filter(lambda q: True)
        self.filtered = self.parent.filter(lambda q: True)
        self.sorted = self.parent.sort(self.sortFunc)
        self.mapped = self.parent.map(lambda x: x)
        self.index = self.parent.createIndex(self.indexFunc)
        self.indexed = self.parent.filterWithIndex(self.indexFunc, True)

    def indexFunc(self, x):
        return True

    def sortFunc(self, x, y):
        self.sortCalls += 1
        return str(x[1]) < str(y[1])

    def testUnlink(self):
        self.assertEqual(len(self.filtered), len(self.parent))
        self.assertEqual(len(self.sorted), len(self.parent))
        self.assertEqual(len(self.mapped), len(self.parent))
        self.assertEqual(len(self.indexed), len(self.parent))
        numSort = self.sortCalls
        
        self.filtered.unlink()
        self.sorted.unlink()
        self.mapped.unlink()
        self.indexed.unlink()
        self.x.remove()

        self.assertNotEqual(len(self.filtered), len(self.parent))
        self.assertNotEqual(len(self.sorted), len(self.parent))
        self.assertNotEqual(len(self.mapped), len(self.parent))
        self.assertNotEqual(len(self.indexed), len(self.parent))
        self.assertEqual(numSort, self.sortCalls)

        self.x = database.DDBObject()
        self.z = database.DDBObject()

        self.assertNotEqual(len(self.filtered), len(self.parent))
        self.assertNotEqual(len(self.sorted), len(self.parent))
        self.assertNotEqual(len(self.mapped), len(self.parent))
        self.assertNotEqual(len(self.indexed), len(self.parent))
        self.assertEqual(numSort, self.sortCalls)

if __name__ == "__main__":
    unittest.main()
