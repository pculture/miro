import unittest
from scheduler import *
from time import sleep
import threading

class SchedulerTestCase(unittest.TestCase):
    def setUp(self):
        self.callcount = 0
    def call(self):
        self.callcount += 1
    def testSingleEvent(self):
        x = ScheduleEvent(2,self.call,False)
        sleep(3)
        self.assertEqual(self.callcount,1)
        x.remove()
    def testRepeatEvent(self):
        x = ScheduleEvent(2,self.call,True)
        sleep(5)
        self.assertEqual(self.callcount,2)
        x.remove()
    def testDoubleRepeatEvent(self):
        x = ScheduleEvent(2,self.call,True)
        y = ScheduleEvent(3,self.call,True)
        sleep(5)
        self.assertEqual(self.callcount,3)
        x.remove()
        y.remove()
    def testWholeBunchaEvents(self):
        threads = []
        for x in range(0,100):
            threads.append(ScheduleEvent(2,self.call,False))
        sleep(3)
        self.assertEqual(self.callcount,100)
        for x in range(0,100):
            threads[x].remove()
        self.assertEqual(threading.activeCount(),1)
##
# This tests for a bug found early on where the timer thread wouldn't
# close, even if there were no more pending threads, resulting in a crash
#
# Must be run last
class ZZZExitTestCase(unittest.TestCase):
    def call(self):
        pass
    def testRun(self):
        x = ScheduleEvent(1,self.call,True)
        sleep(1)
        x.remove()

if __name__ == "__main__":
    unittest.main()
