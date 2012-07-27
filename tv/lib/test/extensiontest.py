import ConfigParser
import logging

from miro import api
from miro import app

from miro.test.framework import MiroTestCase
from miro.test import mock

# define stubs to allow us to use this module as an extension module
def unload():
    pass

ext_context = None
def load(context):
    global ext_context
    ext_context = context

class ExtensionTestBase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.reset_ext_storage_manager()

    def tearDown(self):
        self.reset_ext_storage_manager()
        MiroTestCase.tearDown(self)

    def reset_ext_storage_manager(self):
        global ext_context
        ext_context = None

    def make_extension_config(self):
        """Generate a SafeConfigParser object to use as a test extension."""
        config = ConfigParser.SafeConfigParser()
        config.add_section('extension')
        config.set('extension', 'name', 'Unittest Extension')
        config.set('extension', 'version', 'core')
        config.set('extension', 'enabled_by_default', 'False')
        config.set('extension', 'module', 'miro.test.extensiontest')
        return config

    def create_extension(self):
        """Write a .miroext file using a SafeConfigParser object."""
        config = self.make_extension_config()
        self.ext_path, fp = self.make_temp_path_fileobj('.miroext')
        config.write(fp)
        fp.close()
        app.extension_manager.load_extensions()

    def load_extension(self):
        ext = app.extension_manager.get_extension_by_name(
                "Unittest Extension")
        app.extension_manager.import_extension(ext)
        app.extension_manager.load_extension(ext)
        self.storage_manager = ext_context.storage_manager

    def unload_extension(self):
        ext = app.extension_manager.get_extension_by_name(
                "Unittest Extension")
        app.extension_manager.unload_extension(ext)

class ExtensionStorageTest(ExtensionTestBase):
    # test extensions storing data
    def setUp(self):
        ExtensionTestBase.setUp(self)
        # load our extension
        self.create_extension()
        self.load_extension()

    def check_simple_set(self, key, value):
        self.storage_manager.set_value(key, value)
        stored_value = self.storage_manager.get_value(key)
        if stored_value != value:
            raise AssertionError("Error storing %s: set %r, got %r" % (key,
                value, stored_value))

    def test_simple_store(self):
        self.check_simple_set('a', 'foo')
        self.check_simple_set('b', 200)
        self.check_simple_set('c', 3.0)
        # try some unicode values
        self.check_simple_set(u'd', [1, 2, 'three'])
        self.check_simple_set(u'e\u03a0', {'key': 'value'})
        # try clearing a value
        self.storage_manager.clear_value("a")
        self.assertRaises(KeyError, self.storage_manager.get_value, 'a')
        # test key_exists()
        self.assertEquals(self.storage_manager.key_exists('b'), True)
        self.assertEquals(self.storage_manager.key_exists('c'), True)
        self.assertEquals(self.storage_manager.key_exists('z'), False)
        self.assertEquals(self.storage_manager.key_exists('a'), False)

    def test_sqlite_store(self):
        # test that the sqlite connection works
        conn = self.storage_manager.get_sqlite_connection()
        # all we need to test is if we have a real sqlite connection.  Let's
        # assume that if we can run a few SQL commands, we're good
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE foo(a, b)")
        cursor.execute("INSERT INTO foo (a, b) VALUES (?, ?)", (1, 'two'))
        cursor.execute("INSERT INTO foo (a, b) VALUES (?, ?)", (3, 'four'))
        cursor.execute("SELECT a, b FROM foo ORDER BY a ASC")
        self.assertEquals(cursor.fetchall(), [(1, 'two'), (3, 'four')])

class ExtensionHookTest(ExtensionTestBase):
    def setUp(self):
        ExtensionTestBase.setUp(self)
        # Make a Mock object to use as a hook function.  Nest inside another
        # Mock object to test hook parser better
        global hook_holder
        hook_holder = mock.Mock()
        hook_holder.hook_func = mock.Mock()
        self.mock_hook = hook_holder.hook_func
        # make our extension
        self.create_extension()

    def make_extension_config(self):
        config = ExtensionTestBase.make_extension_config(self)
        # add hooks
        config.add_section('hooks')
        config.set('hooks', 'test_hook',
                'miro.test.extensiontest:hook_holder.hook_func')
        return config

    def test_hook_invoke(self):
        # test calling hook functions
        self.load_extension()
        # setup our mock function to return a value
        self.mock_hook.return_value = 123
        # invoke the hook
        results1 = api.hook_invoke('test_hook', 1, 2, foo=3)
        results2 = api.hook_invoke('test_hook', 4, 5, bar=6)
        # check thath the function was called and the results are correct
        self.assertEquals(self.mock_hook.call_count, 2)
        self.assertEquals(self.mock_hook.call_args_list[0],
                ((1, 2), {'foo': 3}))
        self.assertEquals(self.mock_hook.call_args_list[1],
                ((4, 5), {'bar': 6}))
        self.assertEquals(results1, [123])
        self.assertEquals(results2, [123])

    def test_hook_exception(self):
        # test hook functions raising exceptions
        self.load_extension()
        self.log_filter.reset_records()
        # setup our mock function to throw an error
        self.mock_hook.side_effect = ValueError("Bad Value")
        # invoke the hook
        with self.allow_warnings():
            results = api.hook_invoke('test_hook')
        # check that the error isn't included in the results and that we
        # logged the exception
        self.log_filter.check_record_count(1)
        self.log_filter.check_record_level(logging.ERROR)
        self.assertEquals(results, [])

    def test_unloaded_extension(self):
        # check that unloaded extensions don't provide hooks
        # before we load our extension, the hook shouldn't be registered
        # invoking the hook shouldn't do anything now
        results = api.hook_invoke('test_hook')
        self.assertEquals(self.mock_hook.call_count, 0)
        self.assertEquals(results, [])
        # if we load, then unload our extension, the hook shouldn't be
        # registered
        self.load_extension()
        self.unload_extensions()
        results = api.hook_invoke('test_hook')
        self.assertEquals(self.mock_hook.call_count, 0)
        self.assertEquals(results, [])
