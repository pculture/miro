import unittest
from time import time

import eventloop

class SchedulerTest(unittest.TestCase):
    def setUp(self):
        eventloop._scheduler = eventloop.Scheduler()
        eventloop._quitFlag = False
        self.gotArgs = []
        self.gotKwargs = []
        unittest.TestCase.setUp(self)
    
    def callback(self, *args, **kwargs):
        self.gotArgs.append(args)
        self.gotKwargs.append(kwargs)
        if 'stop' in kwargs.keys():
            eventloop.quit()

    def testCallbacks(self):
        eventloop.addIdle(self.callback)
        eventloop.addTimeout(0.1, self.callback, args=("chris",), 
                kwargs={'hula':"hula"})
        eventloop.addTimeout(0.2, self.callback, args=("ben",), 
                kwargs={'hula':'moreHula', 'stop':1})
        eventloop.loop()
        self.assertEquals(self.gotArgs[0], ())
        self.assertEquals(self.gotArgs[1], ("chris",))
        self.assertEquals(self.gotArgs[2], ("ben",))
        self.assertEquals(self.gotKwargs[0], {})
        self.assertEquals(self.gotKwargs[1], {'hula':'hula'})
        self.assertEquals(self.gotKwargs[2], {'hula':'moreHula', 'stop':1})

    def testQuitWithStuffStillScheduled(self):
        eventloop.addTimeout(0.1, self.callback, kwargs={'stop':1})
        eventloop.addTimeout(2, self.callback)
        eventloop.loop()
        self.assertEquals(len(self.gotArgs), 1)

    def testTiming(self):
        startTime = time()
        eventloop.addTimeout(0.2, self.callback, kwargs={'stop':1})
        eventloop.loop()
        endTime = time()
        self.assertAlmostEqual(startTime + 0.2, endTime, places=1)
