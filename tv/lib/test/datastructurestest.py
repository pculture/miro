import unittest
from miro import datastructures

from miro.test.framework import MiroTestCase

class FifoTestCase(MiroTestCase):
    def test_fifo(self):
        fifo = datastructures.Fifo()
        self.assertEquals(len(fifo), 0)
        self.assertRaises(ValueError, fifo.dequeue)

        fifo.enqueue(1)
        fifo.enqueue(2)
        fifo.enqueue(3)

        self.assertEquals(len(fifo), 3)
        self.assertEquals(fifo.dequeue(), 1)
        self.assertEquals(fifo.dequeue(), 2)
        self.assertEquals(fifo.dequeue(), 3)
        self.assertRaises(ValueError, fifo.dequeue)

        fifo.enqueue(1)
        fifo.enqueue(2)
        self.assertEquals(fifo.dequeue(), 1)
        self.assertEquals(len(fifo), 1)
        fifo.enqueue(3)
        fifo.enqueue(4)
        self.assertEquals(len(fifo), 3)
        self.assertEquals(fifo.dequeue(), 2)
        fifo.enqueue(5)
        self.assertEquals(len(fifo), 3)
        self.assertEquals(fifo.dequeue(), 3)
        self.assertEquals(fifo.dequeue(), 4)
        self.assertEquals(fifo.dequeue(), 5)
        self.assertEquals(len(fifo), 0)

    def test_empty(self):
        fifo = datastructures.Fifo()
        self.assertRaises(ValueError, fifo.dequeue)
