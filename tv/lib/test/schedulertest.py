import unittest
from time import time, sleep
import threading

from miro import eventloop
from miro.test.framework import EventLoopTest

class SchedulerTest(EventLoopTest):
    def setUp(self):
        self.got_args = []
        self.got_kwargs = []
        EventLoopTest.setUp(self)
    
    def callback(self, *args, **kwargs):
        self.got_args.append(args)
        self.got_kwargs.append(kwargs)
        if 'stop' in kwargs.keys():
            eventloop.quit()

    def test_callbacks(self):
        eventloop.addIdle(self.callback, "foo")
        eventloop.addTimeout(0.1, self.callback, "foo", args=("chris",), 
                             kwargs={'hula': "hula"})
        eventloop.addTimeout(0.2, self.callback, "foo", args=("ben",), 
                             kwargs={'hula': 'moreHula', 'stop': 1})
        self.runEventLoop()
        self.assertEquals(self.got_args[0], ())
        self.assertEquals(self.got_args[1], ("chris",))
        self.assertEquals(self.got_args[2], ("ben",))
        self.assertEquals(self.got_kwargs[0], {})
        self.assertEquals(self.got_kwargs[1], {'hula':'hula'})
        self.assertEquals(self.got_kwargs[2], {'hula': 'moreHula', 'stop': 1})

    def test_quit_with_stuff_still_scheduled(self):
        eventloop.addTimeout(0.1, self.callback, "foo", kwargs={'stop': 1})
        eventloop.addTimeout(2, self.callback, "foo")
        self.runEventLoop()
        self.assertEquals(len(self.got_args), 1)

    def test_timing(self):
        start_time = time()
        eventloop.addTimeout(0.2, self.callback, "foo", kwargs={'stop': 1})
        self.runEventLoop()
        end_time = time()
        self.assertAlmostEqual(start_time + 0.2, end_time, places=1)

    def test_lots_of_threads(self):
        timeouts = [0, 0, 0.1, 0.2, 0.3]
        threadCount = 8
        def thread():
            sleep(0.5)
            for timeout in timeouts:
                eventloop.addTimeout(timeout, self.callback, "foo")
        for i in range(threadCount):
            t = threading.Thread(target=thread)
            t.start()
        eventloop.addTimeout(1, self.callback, "foo", kwargs={'stop':1})
        self.runEventLoop()
        totalCalls = len(timeouts) * threadCount + 1
        self.assertEquals(len(self.got_args), totalCalls)
