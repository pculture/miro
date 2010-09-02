import os
import logging
import unittest
import tempfile
import threading
import shutil

from miro import database
from miro import eventloop
from miro import app
from miro import config
from miro import downloader
from miro import httpauth
from miro import httpclient
from miro import util
from miro import databaseupgrade
from miro import prefs
from miro import searchengines
from miro import signals
from miro import storedatabase
from miro import subscription
from time import sleep
from miro import models

from miro.test import testhttpserver

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

FILES_TO_CLEAN_UP = []
def clean_up_temp_files():
    for mem in FILES_TO_CLEAN_UP:
        shutil.rmtree(mem, ignore_errors=True)

def uses_httpclient(fun):
    """Decorator for tests that use the httpclient.

    .. Note::

       Make sure that one test method doesn't call another test_
       method that also uses httpclient.  This decorator doesn't
       nest.
    """
    def _uses_httpclient(*args, **kwargs):
        httpclient.start_thread()
        try:
            return fun(*args, **kwargs)
        finally:
            httpclient.stop_thread()
    return _uses_httpclient

class MiroTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        if not os.path.exists(self.tempdir):
            os.makedirs(self.tempdir)
        self.setup_downloader_log()
        models.initialize()
        app.in_unit_tests = True
        # reload config and initialize it to temprary
        config.load()
        config.init_temporary()
        self.platform = config.get(prefs.APP_PLATFORM)
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
        self.httpserver = None
        httpauth.init()

    def on_windows(self):
        return self.platform == "windows"

    def on_linux(self):
        return self.platform == "linux"

    def on_osx(self):
        return self.platform == "osx"

    def tearDown(self):
        signals.system.disconnect_all()
        util.chatter = True
        self.stop_http_server()

        # Remove any leftover database
        app.db.close()
        app.db = None
        database.setup_managers()

        # Remove anything that may have been accidentally queued up
        eventloop._eventloop = eventloop.EventLoop()

        # Remove tempdir
        shutil.rmtree(self.tempdir, onerror=self._on_rmtree_error)

    def _on_rmtree_error(self, func, path, excinfo):
        global FILES_TO_CLEAN_UP
        FILES_TO_CLEAN_UP.append(path)

    def setup_downloader_log(self):
        handle, filename = tempfile.mkstemp(".log", dir=self.tempdir)
        fp = os.fdopen(handle, "w")
        fp.write("EMPTY DOWNLOADER LOG FOR TESTING\n")
        fp.close()
        config.set(prefs.DOWNLOADER_LOG_PATHNAME, filename)

    def make_temp_path(self, extension=".xml"):
        handle, filename = tempfile.mkstemp(extension, dir=self.tempdir)
        return filename

    def start_http_server(self):
        self.stop_http_server()
        self.httpserver = testhttpserver.HTTPServer()
        self.httpserver.start()

    def last_http_info(self, info_name):
        return self.httpserver.last_info()[info_name]

    def wait_for_libcurl_manager(self):
        """wait for the libcurl thread to complete it's business"""
        end_loop_event = threading.Event()
        def on_end_loop(curl_manager):
            end_loop_event.set()
        handle = httpclient.curl_manager.connect('end-loop', on_end_loop)
        httpclient.curl_manager.wakeup()
        end_loop_event.wait()
        httpclient.curl_manager.disconnect(handle)

    def stop_http_server(self):
        if self.httpserver:
            self.httpserver.stop()
            self.httpserver = None

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

    def assertDictEquals(self, dict1, dict2):
        self.assertSameSet(dict1.keys(), dict2.keys())
        for k in dict1:
            if not dict1[k] == dict2[k]:
                raise AssertionError("Values differ for key %s: %s -- %s",
                        k, dict1[k], dict2[k])

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
            timeout_handle = eventloop.add_timeout(timeout, self.stopEventLoop, 
                                           "Stop test event loop")
            eventloop._eventloop.quit_flag = False
            eventloop._eventloop.loop()
            if self.hadToStopEventLoop and not timeoutNormal:
                raise HadToStopEventLoop()
            else:
                timeout_handle.cancel()
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
