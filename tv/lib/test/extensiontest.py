import ConfigParser
import logging

from miro import api
from miro import app

from miro.test.framework import MiroTestCase
from miro.test import mock

# define stubs to allow us to use this module as an extension module
def unload():
    pass

def load():
    pass

class ExtensionHookTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        # Make a Mock object to use as a hook function.  Nest inside another
        # Mock object to test hook parser better
        global hook_holder
        hook_holder = mock.Mock()
        hook_holder.hook_func = mock.Mock()
        self.mock_hook = hook_holder.hook_func
        # make a fake extension that will implement a hook
        config = ConfigParser.SafeConfigParser()
        config.add_section('extension')
        config.set('extension', 'name', 'Unittest Extension')
        config.set('extension', 'version', 'core')
        config.set('extension', 'enabled_by_default', 'False')
        config.set('extension', 'module', 'miro.test.extensiontest')
        config.add_section('hooks')
        config.set('hooks', 'test_hook',
                'miro.test.extensiontest:hook_holder.hook_func')
        self.ext_path, fp = self.make_temp_path_fileobj('.miroext')
        config.write(fp)
        fp.close()
        app.extension_manager.load_extensions()

    def load_extension(self):
        ext = app.extension_manager.get_extension_by_name(
                "Unittest Extension")
        app.extension_manager.import_extension(ext)
        app.extension_manager.load_extension(ext)

    def unload_extension(self):
        ext = app.extension_manager.get_extension_by_name(
                "Unittest Extension")
        app.extension_manager.unload_extension(ext)

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
