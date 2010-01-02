import unittest
from miro import datastructures

from miro.test.framework import MiroTestCase

class FifoTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.fifo = datastructures.Fifo()

    def test_fifo(self):
        self.assertEquals(len(self.fifo), 0)
        self.assertRaises(ValueError, self.fifo.dequeue)

        self.fifo.enqueue(1)
        self.fifo.enqueue(2)
        self.fifo.enqueue(3)

        self.assertEquals(len(self.fifo), 3)
        self.assertEquals(self.fifo.dequeue(), 1)
        self.assertEquals(self.fifo.dequeue(), 2)
        self.assertEquals(self.fifo.dequeue(), 3)
        self.assertRaises(ValueError, self.fifo.dequeue)

        self.fifo.enqueue(1)
        self.fifo.enqueue(2)
        self.assertEquals(self.fifo.dequeue(), 1)
        self.assertEquals(len(self.fifo), 1)
        self.fifo.enqueue(3)
        self.fifo.enqueue(4)
        self.assertEquals(len(self.fifo), 3)
        self.assertEquals(self.fifo.dequeue(), 2)
        self.fifo.enqueue(5)
        self.assertEquals(len(self.fifo), 3)
        self.assertEquals(self.fifo.dequeue(), 3)
        self.assertEquals(self.fifo.dequeue(), 4)
        self.assertEquals(self.fifo.dequeue(), 5)
        self.assertEquals(len(self.fifo), 0)
        self.assertRaises(ValueError, self.fifo.dequeue)
