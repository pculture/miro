import os
import logging
import unittest
import tempfile
import threading

from miro import database
from miro import eventloop
from miro import app
from miro import downloader
from miro import util
from miro import databaseupgrade
from miro import searchengines
from miro import signals
from miro import storedatabase
from miro import subscription
from time import sleep
from miro import models

util.setup_logging()

# Generally, all test cases should extend MiroTestCase or
# EventLoopTest.  MiroTestCase cleans up any database changes you
# might have made, and EventLoopTest provides an API for accessing the
# eventloop in addition to managing the thread pool and cleaning up
# any events you may have scheduled.
# 
# Our general strategy here is to "revirginize" the environment after
# each test, rather than trying to reset applicable pieces of the
# environment before each test. This way, when writing new tests you
# don't have to anticipate what another test may have changed, you
# just have to make sure you clean up what you changed. Usually, that
# is handled transparently through one of these test cases

class HadToStopEventLoop(Exception):
    pass

class DummyMainFrame:
    def __init__(self):
        self.displays = {}
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.collectionDisplay = "collectionDisplay"
        self.videoInfoDisplay = "videoInfoDisplay"

    def selectDisplay(self, display, area):
        self.displays[area] = display

    def getDisplay(self, area):
        return self.displays.get(area)

    def onSelectedTabChange(self, tabType, multiple, guide_url, videoFilename):
        pass

class DummyVideoDisplay:
    def fileDuration(self, filename, callback):
        pass

    def fillMovieData(self, filename, movie_data, callback):
        pass

class DummyGlobalFeed:
    def connect(self, foo1, foo2):
        pass

class DummyController:
    def __init__(self):
        self.frame = DummyMainFrame()
        self.videoDisplay = DummyVideoDisplay()

    def get_global_feed(self, url):
        return DummyGlobalFeed()

class MiroTestCase(unittest.TestCase):
    def setUp(self):
        models.initialize()
        app.in_unit_tests = True
        database.set_thread(threading.currentThread())
        database.setup_managers()
        self.raise_db_load_errors = True
        app.db = None
        self.reload_database()
        searchengines._engines = [
            searchengines.SearchEngineInfo(u"all", u"Search All", u"", -1)
            ]
        # reset the event loop
        util.chatter = False
        self.saw_error = False
        self.error_signal_okay = False
        signals.system.connect('error', self.handle_error)
        app.controller = DummyController()
        self.temp_files = []

    def tearDown(self):
        signals.system.disconnect_all()
        util.chatter = True
        # Remove any leftover database
        app.db.close()
        app.db = None
        database.setup_managers()
        # Remove anything that may have been accidentally queued up
        eventloop._eventloop = eventloop.EventLoop()
        for filename in self.temp_files:
            try:
                os.remove(filename)
            except OSError:
                pass

    def make_temp_path(self):
        [handle, filename] = tempfile.mkstemp(".xml")
        self.temp_files.append(filename)
        return filename

    def reload_database(self, path=':memory:', schema_version=None,
                        object_schemas=None, upgrade=True):
        self.shutdown_database()
        self.setup_new_database(path, schema_version, object_schemas)
        if upgrade:
            app.db.upgrade_database()
            database.update_last_id()

    def setup_new_database(self, path, schema_version, object_schemas):
        app.db = storedatabase.LiveStorage(path,
                                           schema_version=schema_version,
                                           object_schemas=object_schemas)
        app.db.raise_load_errors = self.raise_db_load_errors

    def allow_db_load_errors(self, allow):
        app.db.raise_load_errors = self.raise_db_load_errors = not allow

    def shutdown_database(self):
        if app.db:
            try:
                app.db.close()
            except StandardError:
                pass

    def reload_object(self, obj):
        # force an object to be reloaded from the databas.
        del app.db._object_map[obj.id]
        app.db._ids_loaded.remove(obj.id)
        return obj.__class__.get_by_id(obj.id)

    def handle_error(self, obj, report):
        if self.error_signal_okay:
            self.saw_error = True
        else:
            raise Exception("error signal %s" % report)

    def assertSameSet(self, list1, list2):
        self.assertEquals(set(list1), set(list2))

class EventLoopTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.hadToStopEventLoop = False

    def stopEventLoop(self, abnormal = True):
        self.hadToStopEventLoop = abnormal
        eventloop.shutdown()

    def runPendingIdles(self):
        idle_queue = eventloop._eventloop.idle_queue
        urgent_queue = eventloop._eventloop.urgent_queue
        while idle_queue.has_pending_idle() or urgent_queue.has_pending_idle():
            if urgent_queue.has_pending_idle():
                urgent_queue.process_idles()
            if idle_queue.has_pending_idle():
                idle_queue.process_next_idle()

    def runUrgentCalls(self):
        urgent_queue = eventloop._eventloop.urgent_queue
        while urgent_queue.has_pending_idle():
            if urgent_queue.has_pending_idle():
                urgent_queue.process_idles()

    def runEventLoop(self, timeout=10, timeoutNormal=False):
        eventloop.thread_pool_init()
        eventloop._eventloop.quit_flag = False
        eventloop._eventloop.idle_queue.quit_flag = False
        eventloop._eventloop.urgent_queue.quit_flag = False
        try:
            self.hadToStopEventLoop = False
            timeout = eventloop.add_timeout(timeout, self.stopEventLoop, 
                                           "Stop test event loop")
            eventloop._eventloop.quit_flag = False
            eventloop._eventloop.loop()
            if self.hadToStopEventLoop and not timeoutNormal:
                raise HadToStopEventLoop()
            else:
                timeout.cancel()
        finally:
            eventloop.thread_pool_quit()

    def add_timeout(self,delay, function, name, args=None, kwargs=None):
        eventloop.add_timeout(delay, function, name, args, kwargs)

    def add_write_callback(self, socket, callback):
        eventloop.add_write_callback(socket, callback)

    def remove_write_callback(self, socket):
        eventloop.remove_write_callback(socket)

    def add_idle(self, function, name, args=None, kwargs=None):
        eventloop.add_idle(function, name, args=None, kwargs=None)

    def hasIdles(self):
        return not (eventloop._eventloop.idle_queue.queue.empty() and
                    eventloop._eventloop.urgent_queue.queue.empty())

    def processThreads(self):
        eventloop._eventloop.threadpool.init_threads()
        while not eventloop._eventloop.threadpool.queue.empty():
            sleep(0.05)
        eventloop._eventloop.threadpool.close_threads()

    def process_idles(self):
        eventloop._eventloop.idle_queue.process_idles()
        eventloop._eventloop.urgent_queue.process_idles()

class DownloaderTestCase(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        downloader.startup_downloader()

    def tearDown(self):
        downloader.shutdown_downloader(eventloop.shutdown)
        self.runEventLoop()
        EventLoopTest.tearDown(self)
