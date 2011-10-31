from miro import eventloop
from miro.test.framework import EventLoopTest

class IdleIterateTest(EventLoopTest):
    """Test feeds that download things.
    """
    def setUp(self):
        self.current_value = None
        EventLoopTest.setUp(self)

    def check_idle_iterator(self, *values):
        """Check the progress of our idle iterator.

        values are be correct value at each stop of the processing.
        """
        # we shouldn't start processing until the eventloop start running
        self.assertEquals(self.current_value, None)
        # Each time through an iteration of the event loop, we should run one
        # step of the idle iterator.
        for v in values:
            self.run_idles_for_this_loop()
            self.assertEquals(self.current_value, v)

    def test_idle_iterate(self):
        # test using eventloop.idle_iterate()
        def foo(start, stop, step):
            for x in xrange(start, stop, step):
                self.current_value = x
                yield

        eventloop.idle_iterate(foo, "test idle iterator",
                args=(10, 20, 2))
        self.check_idle_iterator(10, 12, 14, 16, 18)

    def test_decorator(self):
        # test using the @idle_iterator decorator method
        @eventloop.idle_iterator
        def foo():
            for x in xrange(5):
                self.current_value = x
                yield
        foo()
        self.check_idle_iterator(0, 1, 2, 3, 4)
