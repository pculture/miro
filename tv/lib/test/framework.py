import datetime
import os
import logging
import random
import unittest
import tempfile
import threading
import shutil
import functools

from miro import api
from miro import app
from miro import config
from miro import data
from miro import database
from miro import eventloop
from miro import extensionmanager
from miro import feed
from miro import downloader
from miro import httpauth
from miro import httpclient
from miro import item
from miro import iteminfocache
from miro import itemsource
from miro import util
from miro import prefs
from miro import schema
from miro import searchengines
from miro import signals
from miro import storedatabase
from time import sleep
from miro import models
from miro import workerprocess
from miro.fileobject import FilenameType

from miro.test import mock
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

import sys

class MatchAny(object):
    """Object that matches anything.

    Useful for creating a wildcard when calling Mock.assert_called_with().
    """
    def __eq__(self, other):
        return True

VALID_PLATFORMS = ['linux', 'win32', 'osx']
PLATFORM_MAP = {
    'osx': 'osx',
    'darwin': 'osx',
    'linux2': 'linux',
    'linux': 'linux',
    'win32': 'win32'
    }

skipped_tests = []

def skipping(reason):
    def _skipping(*args, **kwargs):
        global skipped_tests
        skipped_tests.append("%s.%s: %s" % 
                             (args[0].__module__, 
                              args[0].__name__,
                              reason))
    return _skipping

def identity(fun):
    return fun

def get_sys_platform():
    return PLATFORM_MAP[sys.platform]

def only_on_platforms(*platforms):
    """Decorator for running a test only on the listed platforms.

    This works as both a function decorator and a class decorator.
    
    Example::

        @only_on_platforms('win32')
        def test_something_that_works_on_win32(self):
            print "ha!  nothing works on win32!"
            assert False

        @only_on_platforms('osx')
        class TestSomethingOSXy(MiroTestCase):
            ...

    .. Note::

       Valid platform strings are from sys.platform and NOT from the
       Miro platform names.  Use 'win32', 'linux', and 'osx'.
    """
    for mem in platforms:
        if mem not in VALID_PLATFORMS:
            raise ValueError("'%s' is not a valid platform" % mem)

    platform = get_sys_platform()

    if platform in platforms:
        return identity
    else:
        return skipping("only_on_platform %r" % (platforms,))

def skip_for_platforms(*platforms):
    """Decorator for skipping a test on the listed platforms.

    This works as both a function decorator and also a class
    decorator.
    
    Example::

        @skip_for_platforms('win32')
        def test_something_that_fails_on_win32(self):
            ...

        @skip_for_platforms('osx')
        class ThingsThatFailOnOSX(MiroTestCase):
            ...

    .. Note::

       Valid platform strings are from sys.platform and NOT from the
       Miro platform names.  Use 'win32', 'linux', and 'osx'.
    """
    for mem in platforms:
        if mem not in VALID_PLATFORMS:
            raise ValueError("'%s' is not a valid platform" % mem)

    platform = get_sys_platform()

    if platform in platforms:
        return skipping("skip_for_platforms %r" % (platforms,))
    else:
        return identity

class HadToStopEventLoop(StandardError):
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
        self.failed_soft_okay = False
        self.failed_soft_count = 0

    def get_global_feed(self, url):
        return DummyGlobalFeed()

    def failed_soft(self, when, details, with_exception=False):
        # FIXME: should have some way to make this turn into an exception
        if not self.failed_soft_okay:
            print "failed_soft called in DummyController"
            print details
            raise AssertionError("failed_soft called in DummyController")
        self.failed_soft_count += 1

FILES_TO_CLEAN_UP = []
def clean_up_temp_files():
    for mem in FILES_TO_CLEAN_UP:
        shutil.rmtree(mem, ignore_errors=True)

def uses_httpclient(fun):
    """Decorator for tests that use the httpclient.
    """
    def _uses_httpclient(*args, **kwargs):
        # if there's already a curl_manager, then this is probably
        # being called in a nested context, so this iteration is not
        # in charge of starting and stopping the httpclient
        if httpclient.curl_manager:
            return fun(*args, **kwargs)

        httpclient.start_thread()
        try:
            return fun(*args, **kwargs)
        finally:
            httpclient.stop_thread()
    return functools.update_wrapper(_uses_httpclient, fun)

def decorate_all_tests(class_dict, bases, decorator):
    for name, func in class_dict.iteritems():
        if name.startswith("test"):
            class_dict[name] = decorator(func)
    for cls in bases:
        for name in dir(cls):
            if name.startswith("test"):
                class_dict[name] = decorator(getattr(cls, name))

class LogFilter(logging.Filter):
    """Log filter that turns logging messages into exceptions."""

    def __init__(self):
        self.exception_level = logging.CRITICAL
        self.records = []

    def set_exception_level(self, level):
        """Set the min logging level where we should throw an exception"""
        self.exception_level = level

    def filter(self, record):
        if record.levelno >= self.exception_level:
            raise AssertionError("Unexpected logging: %s" % record)
        else:
            self.records.append(record)
            return False

    def reset_records(self):
        self.records = []

    def check_record_count(self, count):
        assert len(self.records) == count

    def check_record_level(self, level):
        for rec in self.records:
            assert rec.levelno == level

class MiroTestCase(unittest.TestCase):
    def setUp(self):
        self.setup_log_filter()
        self.tempdir = tempfile.mkdtemp()
        if not os.path.exists(self.tempdir):
            os.makedirs(self.tempdir)
        self.setup_downloader_log()
        models.initialize()
        app.in_unit_tests = True
        models.Item._path_count_tracker.reset()
        # Tweak Item to allow us to make up fake paths for FileItems
        models.Item._allow_nonexistent_paths = True
        # setup the deleted file checker
        item.setup_deleted_checker()
        item.start_deleted_checker()
        # Skip worker proccess for feedparser
        feed._RUN_FEED_PARSER_INLINE = True
        signals.system.connect('new-dialog', self.handle_new_dialog)
        # reload config and initialize it to temprary
        config.load_temporary()
        self.setup_config_watcher()
        self.platform = app.config.get(prefs.APP_PLATFORM)
        self.set_temp_support_directory()
        database.set_thread(threading.currentThread())
        self.raise_db_load_errors = True
        app.db = None
        self.allow_db_upgrade_error_dialog = False
        self.reload_database()
        self.setup_new_item_info_cache()
        item.setup_metadata_manager(self.tempdir)
        item.setup_change_tracker()
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
        # reset any logging records from our setUp call()
        self.log_filter.reset_records()
        # create an extension manager that searches our tempdir for extensions
        # NOTE: this doesn't actually load any extensions, since the directory
        # is currently empty.  If you want to use the ExtensionManager you
        # need to put a .miroext file in the tempdir then call
        # app.extension_manager.load_extension()
        app.extension_manager = extensionmanager.ExtensionManager(
                [self.tempdir], [])
        # Create a download state object (but don't start the downloader
        # for the individual test unless necessary.  In this case we override
        # the class to run the downloader).
        app.download_state_manager = downloader.DownloadStateManager()
        self.mock_patchers = []

    def setup_config_watcher(self):
        app.backend_config_watcher = config.ConfigWatcher(
            lambda func, *args: func(*args))

    def set_temp_support_directory(self):
        self.sandbox_support_directory = os.path.join(self.tempdir, 'support')
        if not os.path.exists(self.sandbox_support_directory):
            os.makedirs(self.sandbox_support_directory)
        app.config.set(prefs.SUPPORT_DIRECTORY, self.sandbox_support_directory)

    def on_windows(self):
        return self.platform == "windows"

    def tearDown(self):
        for patcher in self.mock_patchers:
            patcher.stop()
        # shutdown workerprocess if we started it for some reason.
        workerprocess.shutdown()
        workerprocess._subprocess_manager = \
                workerprocess.WorkerSubprocessManager()
        workerprocess._miro_task_queue.reset()
        self.reset_log_filter()
        signals.system.disconnect_all()
        util.chatter = True
        self.stop_http_server()

        # unload extensions
        self.unload_extensions()

        # Remove any leftover database
        app.db.close()
        app.db = None

        # Remove anything that may have been accidentally queued up
        eventloop._eventloop = eventloop.EventLoop()

        # Remove tempdir
        shutil.rmtree(self.tempdir, onerror=self._on_rmtree_error)

    def handle_new_dialog(self, obj, dialog):
        """Handle the new-dialog signal

        Subclasses must implement this if they expect to see a dialog.
        """
        raise AssertionError("Unexpected dialog: %s" % dialog)

    def patch_function(self, function_name, new_function):
        """Use Mock to replace an existing function for a single test.

        function_name should be in the form "full.module.name.object".  For
        example "miro.startup.startup"

        This can also be used on a class object in order to return a different
        object, if we only use class objects as factory functions.

        :param function_name: name of the function to patch
        :param new_function: function object to replace it with
        """
        patcher = mock.patch(function_name,
                             mock.Mock(side_effect=new_function))
        patcher.start()
        self.mock_patchers.append(patcher)

    def unload_extensions(self):
        for ext in app.extension_manager.extensions:
            if ext.loaded:
                app.extension_manager.unload_extension(ext)

    def make_item_info(self, itemobj):
        return itemsource.DatabaseItemSource._item_info_for(itemobj)

    def make_feed(self, url):
        url = u'http://feed%d.com/feed.rss' % self.feed_counter.next()
        return models.Feed(url)

    def make_item(self, feed, title):
        """Make a new item."""
        fp_values = item.FeedParserValues({})
        fp_values.data['entry_title'] = title
        # pick a random recent date for the release date
        seconds_ago = random.randint(0, 60 * 60 * 24 * 7)
        release_date = (datetime.datetime.now() -
                        datetime.timedelta(seconds=seconds_ago))
        fp_values.data['release_date'] = release_date
        return models.Item(fp_values, feed_id=feed.id)

    def setup_log_filter(self):
        """Make a LogFilter that will turn loggings into exceptions."""
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        for old_filter in logger.filters:
            logger.removeFilter(old_filter)
        self.log_filter = LogFilter()
        logger.addFilter(self.log_filter)

    def crash_on_warning(self):
        """Convenience function to crash when we log a warning."""
        # FIXME This probably should be the default and tests should have to
        # opt-out of it
        self.log_filter.set_exception_level(logging.WARN)

    def reset_log_filter(self):
        logger = logging.getLogger()
        for old_filter in logger.filters:
            logger.removeFilter(old_filter)
        # reset the level so we don't get debugging printouts during the
        # tearDown call.
        logger.setLevel(logging.ERROR)

    def _on_rmtree_error(self, func, path, excinfo):
        global FILES_TO_CLEAN_UP
        FILES_TO_CLEAN_UP.append(path)

    def setup_downloader_log(self):
        handle, filename = tempfile.mkstemp(".log", dir=self.tempdir)
        fp = os.fdopen(handle, "w")
        fp.write("EMPTY DOWNLOADER LOG FOR TESTING\n")
        fp.close()
        app.config.set(prefs.DOWNLOADER_LOG_PATHNAME, filename)

    # Like make_temp_path() but returns a name as well as an open file object.
    def make_temp_path_fileobj(self, extension=".xml"):
        handle, filename = tempfile.mkstemp(extension, dir=self.tempdir)
        fp = os.fdopen(handle, 'wb')
        return filename, fp

    def make_temp_path(self, extension=".xml"):
        handle, filename = tempfile.mkstemp(extension, dir=self.tempdir)
        os.close(handle)
        return filename

    def make_temp_dir_path(self):
        return tempfile.mkdtemp(dir=self.tempdir)

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

    def setup_new_item_info_cache(self):
        app.item_info_cache = iteminfocache.ItemInfoCache()
        app.item_info_cache.load()

    def reset_failed_soft_count(self):
        app.controller.failed_soft_count = 0

    def check_failed_soft_count(self, count):
        self.assertEquals(app.controller.failed_soft_count, count)

    def reload_database(self, path=':memory:', upgrade=True, **kwargs):
        self.shutdown_database()
        self.setup_new_database(path, **kwargs)
        if upgrade:
            if self.allow_db_upgrade_error_dialog:
                # this means that exceptions in the upgrade will be sent to a
                # dialog box.  Be careful with this, if you don't handle the
                # dialog, then the unit tests will hang.
                app.db.upgrade_database()
            else:
                # normal case: use _upgrade_database() because we want
                # exceptions to keep propagating
                app.db._upgrade_database()
        app.db.attach_temp_db()
        database.initialize()

    def init_data_package(self):
        """Initialize the data package

        The data package is used by the frontend to get data.

        Note: Since data uses a different connection than the backend system
        (storedatabase and friends), we need to create an on-disk database.
        """
        self.db_path = self.make_temp_path(".sqlite")
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        self.reload_database(FilenameType(self.db_path))
        data.init(self.db_path)

    def clear_ddb_object_cache(self):
        app.db._ids_loaded = set()
        app.db._object_map = {}
        app.db.cache = storedatabase.DatabaseObjectCache()

    def setup_new_database(self, path, **kwargs):
        app.db = storedatabase.LiveStorage(path, **kwargs)
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
        key = (obj.id, app.db.table_name(obj.__class__))
        del app.db._object_map[key]
        app.db._ids_loaded.remove(key)
        return obj.__class__.get_by_id(obj.id)

    def handle_error(self, obj, report):
        if self.error_signal_okay:
            self.saw_error = True
        else:
            raise Exception("error signal %s" % report)

    def assertSameSet(self, list1, list2):
        self.assertEquals(set(list1), set(list2))

    def assertSameList(self, list1, list2):
        for i in xrange(len(list1)):
            self.assertEquals(list1[i], list2[i])
        self.assertEquals(len(list1), len(list2))

    def assertDictEquals(self, dict1, dict2):
        self.assertSameSet(dict1.keys(), dict2.keys())
        for k in dict1:
            if not dict1[k] == dict2[k]:
                raise AssertionError("Values differ for key %r: %r -- %r" %
                        (k, dict1[k], dict2[k]))

    def assertClose(self, value1, value2, tolerance=0.1):
        """Assert that 2 values are near each other.

        :param value1: value to compare
        :param value2: value to compare
        :param tolerance: how different the two can be
        """

        difference = abs(value1 - value2)
        relative_difference = difference / max(abs(value1), abs(value2))
        if relative_difference > tolerance:
            raise AssertionError("Difference too big: %s, %s" % (value1,
                                                                 value2))

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
            # make sure that idles scheduled for the next loop run as well.
            eventloop._eventloop._add_idles_for_next_loop()

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
            timeout_handle = eventloop.add_timeout(timeout,
                                                   self.stopEventLoop,
                                                   "Stop test event loop")
            eventloop._eventloop.quit_flag = False
            eventloop._eventloop.loop()
            if self.hadToStopEventLoop and not timeoutNormal:
                raise HadToStopEventLoop()
            else:
                timeout_handle.cancel()
        finally:
            eventloop.thread_pool_quit()

    def run_idles_for_this_loop(self):
        idle_queue = eventloop._eventloop.idle_queue
        urgent_queue = eventloop._eventloop.urgent_queue
        while idle_queue.has_pending_idle() or urgent_queue.has_pending_idle():
            if urgent_queue.has_pending_idle():
                urgent_queue.process_idles()
            if idle_queue.has_pending_idle():
                idle_queue.process_next_idle()
        # make sure that idles scheduled for the next loop run as well, but
        # don't do this inside the while loop.
        eventloop._eventloop._add_idles_for_next_loop()


    def run_pending_timeouts(self):
        scheduler = eventloop._eventloop.scheduler
        while scheduler.has_pending_timeout():
            scheduler.process_next_timeout()

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

def dynamic_test(expected_cases=None):
    """Class decorator for tests that use external test cases. This creates a
    separate test method for each case; this makes it easier to debug tests that
    go awry, makes it easier to see test progress from the command line (lots of
    little tests rather than one big test), and increases the test count
    appropriately::

        class ExampleDynamicTest(object):
            @classmethod
            def generate_tests(cls):
                # Should return an iterable of test cases. Each test case is an
                # iterable of arguments to pass to the dynamic_test_case implementation.
                #
                # Test names will be created by stripping non-alphanumeric chars out of
                # the value of the first arg in each test case, so the first arg should be
                # a string that can be used to identify the test uniquely.
                raise NotImplementedError

            def dynamic_test_case(self, *args):
                # This will be run once for each value produced by setup_tests. The
                # iterables of values returned by generate_tests will be passed as
                # arguments.
                raise NotImplementedError
    """

    def _generate_closure(cls, args):
        return lambda self: cls.dynamic_test_case(self, *args)

    def wrap_class(cls):
        generated_cases = 0
        for test_args in cls.generate_tests():
            test_name = ''.join(x for x in
                                test_args[0].encode('ascii', 'ignore')
                                if x.isalnum())
            setattr(cls, 'test_%s_dyn' % test_name, _generate_closure(cls, test_args))
            generated_cases += 1

        if expected_cases is not None:
            assert generated_cases == expected_cases, (
                    "generated test count %d not equal to expected count %d for"
                    " %s; if you have just added a test, update expected_cases"
                    " (in the dynamic_test args); if not, there are test cases"
                    " missing" % (generated_cases, expected_cases, cls.__name__))
        return cls
    return wrap_class
