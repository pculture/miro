import unittest
from database import *
from os import remove
from os.path import expanduser
import random
import config

class EmptyViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd 
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
        
class SingleItemViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.x = DDBObject()
    def testAdd(self):
        self.assertEqual(self.x.__class__.__name__,'DDBObject')
    def testGetItem(self):
        a = self.everything[0]
        b = self.everything[1]
        self.assertEqual(a.__class__.__name__,'DDBObject')
        self.assertEqual(b,None)
    def testNext(self):
        self.everything.resetCursor()
        a = self.everything.cur()
        b = self.everything.getNext()
        c = self.everything.cur()
        d = self.everything.getNext()
        assert ((a == None) and (b.__class__.__name__ == 'DDBObject') and
                (c == b) and (d == None))
    def testGetPrev(self):
        self.everything.resetCursor()
        self.assertEqual(self.everything.getPrev(),None)
    def testLen(self):
        self.assertEqual(self.everything.len(),1)

class AddBeforeViewTestCase(unittest.TestCase):
    def setUp(self):
        self.x = DDBObject()
        self.y = DDBObject()
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
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
        self.assertEqual(a.__class__.__name__,'DDBObject')
        self.assertEqual(b.__class__.__name__,'DDBObject')
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
        assert ((a == None) and (b.__class__.__name__ == 'DDBObject') and
                (c == b) and (d.__class__.__name__ == 'DDBObject') and
                (d != c) and (d == e) and (f == None))
    def testLen(self):
        self.assertEqual(self.everything.len(),2)

class AddAfterViewTestCase(unittest.TestCase):
    def setUp(self):
        self.x = DDBObject()
        self.y = DDBObject()
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
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
        self.assertEqual(a.__class__.__name__,'DDBObject')
        self.assertEqual(b.__class__.__name__,'DDBObject')
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
        assert ((a == None) and (b.__class__.__name__ == 'DDBObject') and
                (c == b) and (d.__class__.__name__ == 'DDBObject') and
                (d != c) and (d == e) and (f == None))
    def testLen(self):
        self.assertEqual(self.everything.len(),2)

class DeletedItemViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.x = DDBObject()
        self.y = DDBObject()
        self.x.remove()
    def testRemoveMissing(self):
        self.everything.resetCursor()
        self.assertRaises(ObjectNotFoundError,self.everything.remove)
    def testAdd(self):
        self.assertEqual(self.x.__class__.__name__,'DDBObject')
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
        assert ((a == None) and (b.__class__.__name__ == 'DDBObject') and
                (c == b) and (d == None))
    def testLen(self):
        self.assertEqual(self.everything.len(),1)

class FilterViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.x = DDBObject()
        self.y = DDBObject()
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

class RecomputeFilterViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.x = DDBObject()
        self.y = DDBObject()
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

class SortTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.x = DDBObject()
        self.y = DDBObject()
        self.higher = self.x
        self.sorted = self.everything.sort(self.sortFunc)
    def sortFunc(self,x,y):
        if x is y:
            return 0
        elif x == self.higher:
            return 1
        else:
            return -1
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
        assert ((a == None) and (b.__class__.__name__ == 'DDBObject') and
                (c == b) and (d.__class__.__name__ == 'DDBObject') and
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

class MapViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.x = DDBObject()
        self.y = DDBObject()
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

class CallbackViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.filtered = self.everything.filter(lambda x:True)
        self.mapped = self.everything.map(lambda x:x)
        self.sorted = self.everything.sort(lambda x,y:0)
        self.callcount = 0
    def call(self, count):
        assert count == 0
        self.callcount+=1
    def removeCall(self, obj, count):
        assert count == 0
        self.callcount+=1
    def testAdd(self):
        self.everything.addAddCallback(self.call)
        self.x = DDBObject()
        self.assertEqual(self.callcount,1)
    def testChange(self):
        self.everything.addChangeCallback(self.call)
        self.x = DDBObject()
        self.x.beginChange()
        self.x.endChange()
        self.assertEqual(self.callcount,1)
    def testRemove(self):
        self.everything.addRemoveCallback(self.removeCall)
        self.x = DDBObject()
        self.x.remove()
        self.assertEqual(self.callcount,1)
    def TestFilterAdd(self):
        self.filtered.addAddCallBack(self.call)
        self.x = DDBObject()
        self.assertEqual(self.callcount,1)
    def TestFilterRemove(self):
        self.filtered.addRemoveCallBack(self.call)
        self.x = DDBObject()
        self.x.remove()
        self.assertEqual(self.callcount,1)
    def TestFilterChange(self):
        self.filtered.addChangeCallBack(self.call)
        self.x = DDBObject()
        self.x.change()
        self.assertEqual(self.callcount,1)
    def TestMapAdd(self):
        self.mapped.addAddCallBack(self.call)
        self.x = DDBObject()
        self.assertEqual(self.callcount,1)
    def TestMapRemove(self):
        self.mapped.addRemoveCallBack(self.call)
        self.x = DDBObject()
        self.x.remove()
        self.assertEqual(self.callcount,1)
    def TestMapChange(self):
        self.mapped.addChangeCallBack(self.call)
        self.x = DDBObject()
        self.x.change()
        self.assertEqual(self.callcount,1)
    def TestSortAdd(self):
        self.sorted.addAddCallBack(self.call)
        self.x = DDBObject()
        self.assertEqual(self.callcount,1)
    def TestSortRemove(self):
        self.sorted.addRemoveCallBack(self.call)
        self.x = DDBObject()
        self.x.remove()
        self.assertEqual(self.callcount,1)
    def TestSortChange(self):
        self.sorted.addChangeCallBack(self.call)
        self.x = DDBObject()
        self.x.change()
        self.assertEqual(self.callcount,1)

class SaveViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.x = DDBObject()
        self.y = DDBObject()
        self.last = DDBObject.lastID
    def testSaveRestore(self):
        self.everything.save()
        self.z = DDBObject()
        self.zz = DDBObject()
        self.x.remove()
        self.everything.restore()
        self.assertEqual(self.everything.len(),2)
        self.assertEqual(self.everything[0].getID(),self.y.getID())
        self.assertEqual(self.everything[1].getID(),self.x.getID())
        self.assertEqual(self.everything[2],None)
        assert DDBObject.lastID >= self.last
    def testBackup(self):
        self.everything.save()
        self.everything.save()
        remove(config.get(config.DB_PATHNAME))
        self.z = DDBObject()
        self.zz = DDBObject()
        self.x.remove()
        self.everything.restore()
        self.assertEqual(self.everything.len(),2)
        self.assertEqual(self.everything[0].getID(),self.y.getID())
        self.assertEqual(self.everything[1].getID(),self.x.getID())
        self.assertEqual(self.everything[2],None)
        assert DDBObject.lastID >= self.last


class MapFilterRemoveViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.objlist = []
        for x in range(0,10):
            DDBObject()
        self.add = 0
        self.mapped = self.everything.map(self.mapFunc)
        self.mapped = self.mapped.filter(lambda x:True)
    def mapFunc(self,obj):
        return obj.getID() % 2
    def testBasicMap(self):
        self.everything.resetCursor()
        self.mapped.resetCursor()
        for obj in self.everything:
            self.assertEqual(self.mapFunc(obj),self.mapped.getNext())
    def testOneOffBasicMap(self):
        self.everything.resetCursor()
        self.mapped.resetCursor()
        for x in range(1,6):
            obj = self.everything.getNext()
        obj.remove()
        self.everything.addBeforeCursor(DDBObject(add=False))
        self.everything.getPrev()
        self.everything.getPrev()
        self.everything.addAfterCursor(DDBObject(add=False))
        self.everything.resetCursor()
        for obj in self.everything:
            self.assertEqual(self.mapFunc(obj),self.mapped.getNext())

class FilterSortMapTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.callbacks = 0
        self.objlist = []
        for x in range(0,10):
            self.objlist.append(DDBObject())
        self.myfiltFunc = lambda x:x.getID()%2 == 0
        self.filted = self.everything.filter(self.filterFunc)
        self.sorted = self.filted.sort(self.sortFunc)
        self.mapped = self.sorted.map(lambda x:x)
    def filterFunc(self, x):
        return self.myfiltFunc(x)
    def sortFunc(self, x, y):
        x = x.getID()
        y = y.getID()
        if x < y:
            return -1
        elif x > y:
            return 1
        else:
            return 0
    def call(self,item):
        self.callbacks += 1
    def removeCall(self,obj,item):
        self.callbacks += 1
    def test(self):
        self.assertEqual(self.mapped.len(),5)
        self.mapped.addAddCallback(self.call)
        self.myfiltFunc = lambda x:x is self.objlist[1]
        self.everything.recomputeFilters()
        self.assertEqual(self.mapped.len(),1)
        self.myfiltFunc = lambda x:True
        self.everything.recomputeFilters()
        self.assertEqual(self.mapped.len(),10)
    def testTwoSets(self):
        self.callbacks2 = 0
        def call2(item):
            self.callbacks2 += 1
        filtFunc2 = lambda x:True
        filted2 = self.everything.filter(filtFunc2)
        sorted2 = filted2.sort(self.sortFunc)
        mapped2 = sorted2.map(lambda x:x)
        self.mapped.addChangeCallback(self.call)
        mapped2.addChangeCallback(call2)
        if self.myfiltFunc(self.objlist[0]):
            self.objlist[1].beginChange()
            self.objlist[1].endChange()
        else:
            self.objlist[0].beginChange()
            self.objlist[0].endChange()
        self.assertEqual(self.callbacks,0)
        self.assertEqual(self.callbacks2,1)
        self.everything.recomputeFilters()
        self.assertEqual(self.callbacks,0)
        self.assertEqual(self.callbacks2,1)
        self.everything.recomputeFilters()
        self.assertEqual(self.callbacks,0)
        self.assertEqual(self.callbacks2,1)
        if self.myfiltFunc(self.objlist[0]):
            self.objlist[0].beginChange()
            self.objlist[0].endChange()
        else:
            self.objlist[1].beginChange()
            self.objlist[1].endChange()
        self.assertEqual(self.callbacks,1)
        self.assertEqual(self.callbacks2,2)
        self.everything.recomputeFilters()
        self.assertEqual(self.callbacks,1)
        self.assertEqual(self.callbacks2,2)
        self.everything.recomputeFilters()
        self.assertEqual(self.callbacks,1)
        self.assertEqual(self.callbacks2,2)
    def testTwoSets2(self):
        self.callbacks2 = 0
        def removeCall2(obj,item):
            self.callbacks2 += 1
        def call2(item):
            self.callbacks2 += 1
        filtFunc2 = lambda x:x.getID()%2 == 1
        filted2 = self.everything.filter(filtFunc2)
        sorted2 = filted2.sort(self.sortFunc)
        mapped2 = sorted2.map(lambda x:x)
        self.mapped.addChangeCallback(self.call)
        mapped2.addChangeCallback(call2)
        self.mapped.addAddCallback(self.call)
        mapped2.addAddCallback(call2)
        self.mapped.addRemoveCallback(self.removeCall)
        mapped2.addRemoveCallback(removeCall2)

        self.mapped.next()
        self.mapped.next()
        self.mapped.next()
        mapped2.next()
        self.assertEqual(self.mapped.cursor,2)
        self.assertEqual(mapped2.cursor,0)
        if self.myfiltFunc(self.objlist[0]):
            self.objlist[1].beginChange()
            self.objlist[1].endChange()
        else:
            self.objlist[0].beginChange()
            self.objlist[0].endChange()
        self.assertEqual(self.mapped.cursor,2)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,0)
        self.assertEqual(self.callbacks2,1)
        self.everything.recomputeFilters()
        self.assertEqual(self.mapped.cursor,2)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,0)
        self.assertEqual(self.callbacks2,1)
        self.everything.recomputeFilters()
        self.assertEqual(self.mapped.cursor,2)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,0)
        self.assertEqual(self.callbacks2,1)
        if self.myfiltFunc(self.objlist[0]):
            self.objlist[0].beginChange()
            self.objlist[0].endChange()
        else:
            self.objlist[1].beginChange()
            self.objlist[1].endChange()
        self.assertEqual(self.mapped.cursor,2)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,1)
        self.assertEqual(self.callbacks2,1)
        self.everything.recomputeFilters()
        self.assertEqual(self.mapped.cursor,2)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,1)
        self.assertEqual(self.callbacks2,1)
        self.everything.recomputeFilters()
        self.assertEqual(self.mapped.cursor,2)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,1)
        self.assertEqual(self.callbacks2,1)
        if self.myfiltFunc(self.objlist[0]):
            self.objlist[0].remove()
        else:
            self.objlist[1].remove()
        self.assertEqual(self.mapped.cursor,1)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,2)
        self.assertEqual(self.callbacks2,1)
        self.everything.recomputeFilters()
        self.assertEqual(self.mapped.cursor,1)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,2)
        self.assertEqual(self.callbacks2,1)
        self.everything.recomputeFilters()
        self.assertEqual(self.mapped.cursor,1)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,2)
        self.assertEqual(self.callbacks2,1)
        self.objlist.append(DDBObject(add = False))
        self.objlist.append(DDBObject(add = False))
        self.everything.resetCursor()
        self.everything.addAfterCursor(self.objlist[10])
        self.everything.addAfterCursor(self.objlist[11])
        self.assertEqual(self.mapped.cursor,1)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,3)
        self.assertEqual(self.callbacks2,2)
        self.objlist[10].beginChange()
        self.objlist[10].endChange()
        self.objlist[11].beginChange()
        self.objlist[11].endChange()
        self.assertEqual(self.mapped.cursor,1)
        self.assertEqual(mapped2.cursor,0)
        self.assertEqual(self.callbacks,4)
        self.assertEqual(self.callbacks2,3)
        self.everything.recomputeFilters()
        self.assertEqual(self.callbacks,4)
        self.assertEqual(self.callbacks2,3)
        self.myfiltFunc = lambda x:x is self.objlist[2]
        self.everything.recomputeFilters()
        self.assertEqual(self.callbacks2,3)
        self.objlist[2].beginChange()
        self.objlist[2].endChange()
        self.objlist[3].beginChange()
        self.objlist[3].endChange()
        self.assertEqual(self.callbacks2,4)
        
class RemoveMatchingViewTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
        self.x = DDBObject()
        self.y = DDBObject()
        self.z = DDBObject()

    def testRemove(self):
        self.everything.removeMatching(lambda x:x.getID() == self.x.getID())
        self.assertEqual(self.everything.len(), 2)
        self.everything.removeMatching(lambda x:x.getID() == self.z.getID())
        self.assertEqual(self.everything.len(), 1)
        self.everything.removeMatching(lambda x:x.getID() == self.z.getID())
        self.assertEqual(self.everything.len(), 1)
        self.everything.removeMatching(lambda x:x.getID() == self.y.getID())
        self.assertEqual(self.everything.len(), 0)

class CursorTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
	self.origObjs = [DDBObject(), DDBObject(), DDBObject()]
	self.objs = self.everything.filter(lambda x: True).map(self.mapToObject).sort(self.sortOldID)
    def sortOldID(self,x,y):
	if x.oldID > y.oldID:
	    return 1
	elif x.oldID < y.oldID:
	    return -1
	else:
	    return 0
    def mapToObject(self, obj):
	temp = DDBObject(add = False)
	temp.oldID = obj.getID()
	return temp
    def test(self):
	self.assertEqual(self.objs.len(),3)
	self.assertEqual(self.objs.cursor,-1)
	self.objs.getNext()
	self.objs.getNext()
	self.objs.getNext()
	self.assertEqual(self.objs.cursor,2)
	self.everything.removeMatching(lambda x: x.getID() == max(map(lambda x:x.getID(),self.origObjs)))
	self.assertEqual(self.objs.cursor,1)
	self.objs.getPrev()
	self.assertEqual(self.objs.cursor,0)

class RecomputeMapTestCase(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
	self.origObjs = [DDBObject(), DDBObject(), DDBObject()]
	self.objs = self.everything.filter(lambda x: True).map(self.mapToObject).sort(self.sortOldID).map(self.mapToObject)
	self.changeCalls = 0
    def sortOldID(self,x,y):
	if x.oldID > y.oldID:
	    return 1
	elif x.oldID < y.oldID:
	    return -1
	else:
	    return 0
    def mapToObject(self, obj):
	temp = DDBObject(add = False)
	temp.oldID = obj.getID()
	return temp
    def changeCall(self,item):
	self.changeCalls +=1
    def test(self):
	self.objs.addChangeCallback(self.changeCall)
	self.everything.recomputeFilters()
	self.everything.recomputeFilters()
	temp = self.everything.getNext()
	temp.beginChange()
	temp.endChange()
	self.assertEqual(self.changeCalls,1)

class FilterUpdateOnChange(unittest.TestCase):
    def setUp(self):
        DDBObject.dd = DynamicDatabase()
        self.everything = DDBObject.dd
	self.origObjs = [DDBObject(), DDBObject(), DDBObject()]
        self.goodID = self.origObjs[0].getID()
	self.objs = self.everything.map(self.mapToObject).sort(lambda x, y:0).filter(lambda x: x.oldID == self.goodID)
	self.changeCalls = 0
    def mapToObject(self, obj):
	temp = DDBObject(add = False)
	temp.oldID = obj.getID()
	return temp
    def testLoss(self):
        self.assertEqual(self.objs.len(),1)
        self.origObjs[0].beginChange()
        self.origObjs[0].id = -1
        self.origObjs[0].endChange()
        self.assertEqual(self.objs.len(),0)
    def testAdd(self):
        self.assertEqual(self.objs.len(),1)
        self.origObjs[1].beginChange()
        self.origObjs[1].id = self.goodID
        self.origObjs[1].endChange()
        self.assertEqual(self.objs.len(),2)

#FIXME: Add a test such that recomputeFilters code that assumes
#       subfilters keep the same order as their parent will fail.
#
#       v1.4 of database.pyx should pass, while 1.5 should fail

#FIXME: Add test for recomputing sorts on endChange()

if __name__ == "__main__":
    unittest.main()
