import unittest
from miro import fasttypes

from miro.test.framework import MiroTestCase

class Dummy:
    pass

class LinkedListTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.list = fasttypes.LinkedList()
    def test(self):
        temp = Dummy()
        assert len(self.list) == 0
        self.list.append(temp)
        assert len(self.list) == 1
        del temp
        assert len(self.list) == 1
        temp2 = self.list.pop()
        assert len(self.list) == 0
        it = self.list.append(temp2)
        assert self.list[0] == self.list[it]
        assert self.list[0] == temp2
        self.list.pop()
        self.assertRaises(IndexError, self.list.pop)
        it0 = self.list.append(0)
        it1 = self.list.append(1)
        it2 = self.list.append(2)
        assert self.list[0] == 0
        assert self.list[it0] == 0
        assert self.list[1] == 1
        assert self.list[it1] == 1
        assert self.list[2] == 2
        assert self.list[it2] == 2
        self.assertRaises(ValueError, lambda: self.list[-1])
        self.assertRaises(IndexError, lambda: self.list[3])
        count = 0
        for x in self.list:
            assert x == count
            count += 1
        assert count == 3
        it0.forward()
        assert self.list[it0] == 1
        it2.back()
        assert self.list[it2] == 1
        it0.forward()
        it0.forward()
        self.assertRaises(IndexError,lambda: self.list[it0])
        it2.back()
        it2.back()
        self.assertRaises(IndexError,lambda: self.list[it2])
        newIt = self.list.insertBefore(it1,0)
        assert len(self.list) == 4
        self.list[0] = -1
        count = -1
        for x in self.list:
            assert x == count
            count += 1
        assert count == 3
        assert self.list[newIt] == 0
        for x in range(0,4):
            self.list[x] = x
        count = 0
        for x in self.list:
            assert x == count
            count += 1
        assert count == 4
        try:
            self.list[it0] = 42
        except IndexError:
            pass
        else:
            fail('indexing with a past-the-end iterator should raise IndexError')
        try:
            self.list[-1] = 42
        except (IndexError, ValueError):
            pass
        else:
            fail('indexing -1 should raise IndexError or ValueError')

        try:
            self.list[4] = 42
        except (IndexError, ValueError):
            pass
        else:
            fail('indexing beyond the end should raise IndexError or ValueError')

        # Apparently, reassigning values makes this iterator invalid --NN
        #
        # del self.list[newIt]
        del self.list[self.list.firstIter()]
        assert len(self.list) == 3
        delIt = self.list.remove(0)
        assert len(self.list) == 2
        assert self.list[delIt] == 2
        del2 = self.list.remove(delIt)
        assert len(self.list) == 1
        assert self.list[del2] == 3
        del self.list[0]
        assert len(self.list) == 0
        self.list.append(2)

        it0 = self.list.firstIter()
        it1 = self.list.firstIter()
        assert it0 == it1
        it2 = self.list.lastIter()
        it3 = self.list.lastIter()
        assert it2 == it3
        assert it0 != it2
        it0.forward()
        assert it0 == it2
        assert it0 != it1

        del self.list[0]
        assert self.list.firstIter() == self.list.lastIter()
        assert not self.list.firstIter() != self.list.lastIter()

class SortedListTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.list = fasttypes.SortedList(self.cmp)
    def cmp(self, obj1, obj2):
        return obj1 < obj2
    def test(self):
        temp = Dummy()
        assert len(self.list) == 0
        self.list.append(temp)
        assert len(self.list) == 1
        del temp
        assert len(self.list) == 1
        temp2 = self.list.pop()
        assert len(self.list) == 0
        it = self.list.append(temp2)
        assert self.list[0] == self.list[it]
        assert self.list[0] == temp2
        self.list.pop()
        self.assertRaises(IndexError, self.list.pop)
        it1 = self.list.append(1)
        it0 = self.list.append(0)
        it2 = self.list.append(2)
        assert self.list[0] == 0
        assert self.list[it0] == 0
        assert self.list[1] == 1
        assert self.list[it1] == 1
        assert self.list[2] == 2
        assert self.list[it2] == 2
        self.assertRaises(ValueError, lambda: self.list[-1])
        self.assertRaises(IndexError, lambda: self.list[3])
        count = 0
        for x in self.list:
            assert x == count
            count += 1
        assert count == 3
        it0.forward()
        assert self.list[it0] == 1
        it2.back()
        assert self.list[it2] == 1
        it0.forward()
        it0.forward()
        self.assertRaises(IndexError,lambda: self.list[it0])
        it2.back()
        it2.back()
        self.assertRaises(IndexError,lambda: self.list[it2])
        newIt = self.list.insertBefore(it1,0)
        assert len(self.list) == 4
        self.list[0] = -1
        count = -1
        for x in self.list:
            assert x == count
            count += 1
        assert count == 3
        assert self.list[newIt] == 0
        for x in range(0,4):
            self.list[x] = x
        count = 0
        for x in self.list:
            assert x == count
            count += 1
        assert count == 4
        try:
            self.list[it0] = 42
        except IndexError:
            pass
        else:
            fail('indexing with a past-the-end iterator should raise IndexError')
        try:
            self.list[-1] = 42
        except (IndexError, ValueError):
            pass
        else:
            fail('indexing -1 should raise IndexError')

        try:
            self.list[4] = 42
        except IndexError:
            pass
        else:
            fail('indexing beyond the end should raise IndexError')

        # Apparently, reassigning values makes this iterator invalid --NN
        #
        # del self.list[newIt]
        del self.list[self.list.firstIter()]
        assert len(self.list) == 3
        self.list.remove(0)
        assert len(self.list) == 2
        del self.list[0]
        assert len(self.list) == 1
        
        it0 = self.list.firstIter()
        it1 = self.list.firstIter()
        assert it0 == it1
        it2 = self.list.lastIter()
        it3 = self.list.lastIter()
        assert it2 == it3
        assert it0 != it2
        it0.forward()
        assert it0 == it2
        assert it0 != it1

        del self.list[0]
        assert self.list.firstIter() == self.list.lastIter()
        assert not self.list.firstIter() != self.list.lastIter()
