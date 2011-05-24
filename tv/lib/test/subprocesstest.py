import time
import Queue

from miro import app
from miro import subprocessmanager
from miro.test.framework import EventLoopTest

# setup some test messages/handlers
class TestSubprocessHandler(subprocessmanager.SubprocessHandler):
    def __init__(self):
        subprocessmanager.SubprocessHandler.__init__(self)

    def on_startup(self):
        SawEvent("startup").send_to_main_process()

    def on_shutdown(self):
        SawEvent("shutdown").send_to_main_process()

    def on_restart(self):
        SawEvent("restart").send_to_main_process()

    def handle_ping(self, msg):
        Pong().send_to_main_process()

    def handle_force_exception(self, msg):
        1/0

class TestSubprocessResponder(subprocessmanager.SubprocessResponder):
    def __init__(self):
        subprocessmanager.SubprocessResponder.__init__(self)
        self.events_saw = []
        self.subprocess_events_saw = []
        self.pong_count = 0
        self.break_on_pong = False
        self.subprocess_ready = False

    def on_startup(self):
        self.events_saw.append("startup")

    def on_restart(self):
        self.events_saw.append("restart")

    def on_shutdown(self):
        self.events_saw.append("shutdown")

    def handle_pong(self, msg):
        if self.break_on_pong:
            1/0
        self.pong_count += 1

    def handle_saw_event(self, msg):
        self.subprocess_events_saw.append(msg.event)
        if msg.event == 'startup':
            self.subprocess_ready = True

class TestMessage(subprocessmanager.SubprocessMessage):
    pass

class Ping(TestMessage):
    pass

class ForceException(TestMessage):
    pass

class Pong(subprocessmanager.SubprocessResponse):
    pass

class SawEvent(subprocessmanager.SubprocessResponse):
    def __init__(self, event):
        self.event = event

# Actual tests go below here

class SubprocessManagerTest(EventLoopTest):
    # FIXME: we should have a better way of waiting for the subprocess to do
    # things, than calling runEventLoop() with an arbitrary timeout.

    def setUp(self):
        EventLoopTest.setUp(self)

        self.responder = TestSubprocessResponder()
        self.subprocess = subprocessmanager.SubprocessManager(TestMessage,
                self.responder, TestSubprocessHandler)
        self.subprocess.start()
        self._wait_for_subprocess_ready()

    def tearDown(self):
        self.subprocess.shutdown()
        EventLoopTest.tearDown(self)

    def _wait_for_subprocess_ready(self, timeout=4.0):
        """Wait for the subprocess to startup."""

        start = time.time()
        while True:
            # wait a bit for the subprocess to send us a message
            self.runEventLoop(0.1, timeoutNormal=True)
            if self.responder.subprocess_ready:
                return
            if time.time() - start > timeout:
                self.subprocess.process.terminate()
                raise AssertionError("subprocess didn't startup in %s secs",
                        timeout)

    def test_startup(self):
        # test that we startup the process
        self.assert_(self.subprocess.process.poll() is None)
        self.assert_(self.subprocess.thread.is_alive())

    def test_quit(self):
        # test asking processes to quit nicely
        thread = self.subprocess.thread
        process = self.subprocess.process
        self.subprocess.send_quit()
        # give a bit of time to let things quit
        self.runEventLoop(0.3, timeoutNormal=True)
        self.assert_(not thread.is_alive())
        self.assert_(process.poll() is not None)
        self.assert_(not self.subprocess.is_running)

    def test_send_and_receive(self):
        # test sending and receiving messages

        # send a bunch of pings
        Ping().send_to_process()
        Ping().send_to_process()
        Ping().send_to_process()
        # allow some time for the responses to come back
        self.runEventLoop(0.1, timeoutNormal=True)
        # check that we got a pong for each ping
        self.assertEquals(self.responder.pong_count, 3)

    def test_event_callbacks(self):
        # test that we get event callbacks

        # check that on_startup() gets called on both sides
        self.runEventLoop(0.1, timeoutNormal=True)
        self.assertEqual(self.responder.events_saw, ['startup'])
        self.assertEqual(self.responder.subprocess_events_saw, ['startup'])

        # check that on_restart() gets called on both sides
        self.responder.events_saw = []
        self.responder.subprocess_events_saw = []
        self.subprocess.process.terminate()
        self.responder.subprocess_ready = False
        self._wait_for_subprocess_ready()
        # the subprocess should see a startup
        self.assertEqual(self.responder.subprocess_events_saw, ['startup'])
        # the main process should see a startup and a restart
        self.assertEqual(self.responder.events_saw, ['startup', 'restart'])

        # check that on_shutdown() gets called on both sides
        self.responder.events_saw = []
        self.responder.subprocess_events_saw = []
        self.subprocess.shutdown()
        self.runEventLoop(0.2, timeoutNormal=True)
        self.assertEqual(self.responder.subprocess_events_saw, ['shutdown'])
        self.assertEqual(self.responder.events_saw, ['shutdown'])

    def test_restart(self):
        # test that we restart process when the quit unexpectedly
        old_pid = self.subprocess.process.pid
        old_thread = self.subprocess.thread
        self.subprocess.process.terminate()
        # wait a bit for the subprocess to quit then restart
        self.responder.subprocess_ready = False
        self._wait_for_subprocess_ready()
        # test that process #1 has been restarted
        self.assert_(self.subprocess.is_running)
        self.assert_(self.subprocess.process.poll() is None)
        self.assert_(self.subprocess.thread.is_alive())
        self.assertNotEqual(old_pid, self.subprocess.process.pid)
        # test that the original thread is gone
        self.assert_(not old_thread.is_alive())

    def test_subprocess_exception(self):
        # check that subprocess handler exceptions don't break things
        original_pid = self.subprocess.process.pid
        # sending this message causes the subprocess handler to throw an
        # exception
        ForceException().send_to_process()
        app.controller.failed_soft_okay = True
        # check that we handled the exception with failed_soft
        self.runEventLoop(0.1, timeoutNormal=True)
        self.assertEquals(app.controller.failed_soft_count, 1)
        # check that we're didn't restart the process
        self.assertEquals(original_pid, self.subprocess.process.pid)
        # check that we can still send messages
        Ping().send_to_process()
        self.runEventLoop(0.1, timeoutNormal=True)
        self.assertEquals(self.responder.pong_count, 1)
