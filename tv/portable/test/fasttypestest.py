import unittest
from miro import fasttypes

from miro.test.framework import MiroTestCase

class Dummy:
    pass

class LinkedListTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        fasttypes._reset_nodes_deleted()
        self.reset_list()

    def reset_list(self):
        self.list = fasttypes.LinkedList()

    def check_list(self, *correct_list):
        actual_list = []
        iter = self.list.firstIter()
        while iter != self.list.lastIter():
            actual_list.append(iter.value())
            iter.forward()
        self.assertEquals(actual_list, list(correct_list))
        self.assertEquals(len(self.list), len(correct_list))

    def test(self):
        temp = Dummy()
        assert len(self.list) == 0
        self.assertEqual(self.list.firstIter(), self.list.lastIter())

        self.list.append(temp)
        assert len(self.list) == 1
        del temp
        assert len(self.list) == 1
        self.assertNotEqual(self.list.firstIter(), self.list.lastIter())

        self.reset_list()
        it0 = self.list.append(0)
        it1 = self.list.append(1)
        it2 = self.list.append(2)
        assert self.list[it0] == 0
        assert self.list[it1] == 1
        assert self.list[it2] == 2
        self.assertRaises(TypeError, lambda: self.list[None])
        self.assertEqual(it0, self.list.firstIter())
        self.assertNotEqual(it2, self.list.lastIter())
        it3 = it2.copy()
        it3.forward()
        self.assertEqual(it3, self.list.lastIter())
        self.assertRaises(IndexError, self.list.lastIter().value)
        self.check_list(0, 1, 2)

        it0.forward()
        assert self.list[it0] == 1
        it2.back()
        assert self.list[it2] == 1
        it0.forward()
        it0.forward()
        self.assertEquals(it0, self.list.lastIter())
        self.assertRaises(IndexError,lambda: self.list[it0])
        it2.back()
        it2.back()
        self.assertRaises(IndexError,lambda: self.list[it2])
        newIt = self.list.insertBefore(it1,0)
        assert len(self.list) == 4
        self.list[self.list.firstIter()] = -1
        self.check_list(-1, 0, 1, 2)

        assert self.list[newIt] == 0

        try:
            self.list[it0] = 42
        except IndexError:
            pass
        else:
            fail('indexing with a past-the-end iterator should raise IndexError')
        self.reset_list()
        self.list.append(0)

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

        del self.list[self.list.firstIter()]
        assert self.list.firstIter() == self.list.lastIter()
        assert not self.list.firstIter() != self.list.lastIter()

    def test_remove(self):
        self.list.append(0)
        self.list.append(1)
        self.list.append(2)
        self.check_list(0, 1, 2)
        self.list.remove(self.list.firstIter())
        self.check_list(1, 2)
        self.list.remove(self.list.firstIter())
        self.check_list(2)
        self.list.remove(self.list.firstIter())
        self.check_list()

        it0 = self.list.append(0)
        it1 = self.list.append(1)
        it2 = self.list.append(2)

        remove_iter = self.list.remove(it1)
        self.check_list(0, 2)
        self.assertEquals(self.list[remove_iter], 2)
        remove_iter = self.list.remove(it2)
        self.assertEquals(remove_iter, self.list.lastIter())
        self.check_list(0)
        remove_iter = self.list.remove(it0)
        self.assertEquals(remove_iter, self.list.lastIter())
        self.check_list()

        self.assertRaises(IndexError, self.list.remove, self.list.lastIter())

    def test_remove_deletes_obj(self):
        self.list.append(Dummy())
        self.assertEqual(fasttypes._count_nodes_deleted(), 0)
        self.list.remove(self.list.firstIter())
        self.assertEqual(fasttypes._count_nodes_deleted(), 1)
        # try again, but keep a reference to the iter this time
        it = self.list.append(Dummy())
        self.list.remove(it)
        self.assertEqual(fasttypes._count_nodes_deleted(), 1)
        del it
        self.assertEqual(fasttypes._count_nodes_deleted(), 2)

    def test_delete_list(self):
        it = self.list.append(Dummy())
        del self.list
        self.assertRaises(ValueError, it.value)
        self.assertEqual(fasttypes._count_nodes_deleted(), 0)
        del it
        self.assertEqual(fasttypes._count_nodes_deleted(), 1)

    def test_access_deleted(self):
        it0 = self.list.append(0)
        it1 = self.list.append(1)
        self.list.remove(it0)
        self.assertRaises(ValueError, it0.value)
        self.assertRaises(ValueError, self.list.__getitem__, it0)
        self.assertRaises(ValueError, self.list.__setitem__, it0, 1)
        self.assertRaises(ValueError, self.list.__delitem__, it0)
