from miro import app
from miro import dialogs
from miro.data import dberrors
from miro.test import mock
from miro.test.framework import MiroTestCase

class DBErrorTest(MiroTestCase):
    """Test database error handling."""

    def setUp(self):
        MiroTestCase.setUp(self)
        self.frontend = mock.Mock()
        self.run_choice_dialog = self.frontend.run_choice_dialog
        self.db_error_handler = dberrors.DBErrorHandler(self.frontend)

    def test_frontend_error_handling(self):
        self.run_choice_dialog.return_value = dialogs.BUTTON_RETRY
        # the frontend calls run_dialog() when it sees an error
        retry_callback = mock.Mock()
        self.db_error_handler.run_dialog('test 1', 'test 2', retry_callback)
        # run_dialog() should pop up a choice dialog
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(self.run_choice_dialog.call_args[0],
                          ('test 1', 'test 2',
                           [dialogs.BUTTON_RETRY, dialogs.BUTTON_QUIT]))
        self.assertEquals(self.run_choice_dialog.call_args[1], {})
        # since RETRY was chosen, the retry callback should be called
        self.assertEquals(retry_callback.call_count, 1)
        # try again with QUIT chosen.  In that case, the retry callback
        # shouldn't be called
        retry_callback.reset_mock()
        self.run_choice_dialog.return_value = dialogs.BUTTON_QUIT
        self.db_error_handler.run_dialog('test 1', 'test 2', retry_callback)
        self.assertEquals(retry_callback.call_count, 0)

    def test_backend_error_handling(self):
        # when the backend sees an error, it should send the
        # DatabaseErrorDialog to the frontend and the frontend should call
        # DBErrorHandler.run_backend_dialog().  This test is testing what
        # happens when run_backend_dialog() is called.
        self.run_choice_dialog.return_value = dialogs.BUTTON_RETRY
        dialog = mock.Mock(title='test 1', description='test 2')
        self.db_error_handler.run_backend_dialog(dialog)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(dialog.run_callback.call_count, 1)
        self.assertEquals(dialog.run_callback.call_args,
                          ((dialogs.BUTTON_RETRY,), {}))

    def test_backend_then_frontend_errors(self):
        retry_callback = mock.Mock()
        def run_choice_dialog(title, description, buttons):
            # while inside the choice dialog for the backend, we trigger
            # another error from the frontend.
            self.db_error_handler.run_dialog('test 1', 'test 2',
                                             retry_callback)
            return dialogs.BUTTON_RETRY
        self.run_choice_dialog.side_effect = run_choice_dialog
        dialog = mock.Mock(title='test 1', description='test 2')
        self.db_error_handler.run_backend_dialog(dialog)
        # even though we saw 2 errors, only 1 dialog should be shown
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        # since RETRY was chosen for the dialog, both backend and frontend
        # should see that
        self.assertEquals(dialog.run_callback.call_args[0][0],
                          dialogs.BUTTON_RETRY)
        self.assertEquals(retry_callback.call_count, 1)

    def test_frontend_then_backend_errors(self):
        retry_callback = mock.Mock()
        dialog = mock.Mock(title='test 1', description='test 2')
        def run_choice_dialog(title, description, buttons):
            # while inside the choice dialog for the backend, we trigger
            # another error from the frontend.
            self.db_error_handler.run_backend_dialog(dialog)
            return dialogs.BUTTON_RETRY
        self.run_choice_dialog.side_effect = run_choice_dialog
        self.db_error_handler.run_dialog('test 1', 'test 2', retry_callback)
        # even though we saw 2 errors, only 1 dialog should be shown
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        # since RETRY was chosen for the dialog, both backend and frontend
        # should see that
        self.assertEquals(dialog.run_callback.call_args[0][0],
                          dialogs.BUTTON_RETRY)
        self.assertEquals(retry_callback.call_count, 1)

    def test_nested_frontend_errors(self):
        retry_callback = mock.Mock()
        def run_choice_dialog(title, description, buttons):
            # simulate several other errors while running the dialog
            self.db_error_handler.run_dialog('test 1', 'test 2',
                                             retry_callback)
            self.db_error_handler.run_dialog('test 1', 'test 2',
                                             retry_callback)
            self.db_error_handler.run_dialog('test 1', 'test 2',
                                             retry_callback)
            return dialogs.BUTTON_RETRY
        self.run_choice_dialog.side_effect = run_choice_dialog
        self.db_error_handler.run_dialog('test 1', 'test 2',
                                         retry_callback)
        # even though we saw 4 errors, only 1 dialog should be shown
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        # the retry_callback should be called for each run_dialog() call.
        self.assertEquals(retry_callback.call_count, 4)

    def test_reuse_retry(self):
        # if we get an error on one thread and the user response with RETRY,
        # then we should reuse that response if another thread sees an error.
        self.run_choice_dialog.return_value = dialogs.BUTTON_RETRY
        dialog = mock.Mock(title='test 1', description='test 2')
        # handle a backend error
        self.db_error_handler.run_backend_dialog(dialog)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(dialog.run_callback.call_args[0][0],
                          dialogs.BUTTON_RETRY)
        # handle a frontend error, we should reuse the RETRY response
        retry_callback = mock.Mock()
        self.db_error_handler.run_dialog('test 1', 'test 2', retry_callback)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(retry_callback.call_count, 1)
        # handle another frontend error this time we shouldn't reuse the RETRY
        # response
        self.db_error_handler.run_dialog('test 1', 'test 2', retry_callback)
        self.assertEquals(self.run_choice_dialog.call_count, 2)
        self.assertEquals(retry_callback.call_count, 2)

    def test_reuse_quit(self):
        # if the user replies with QUIT, then we should always return QUIT
        # for future errors
        self.run_choice_dialog.return_value = dialogs.BUTTON_QUIT
        dialog = mock.Mock(title='test 1', description='test 2')
        # handle a backend error
        self.db_error_handler.run_backend_dialog(dialog)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(dialog.run_callback.call_args[0][0],
                          dialogs.BUTTON_QUIT)
        # for future errors, we should assume the user still wants to quit

        # try a bunch of frontend errors
        retry_callback = mock.Mock()
        self.db_error_handler.run_dialog('test 1', 'test 2', retry_callback)
        self.db_error_handler.run_dialog('test 1', 'test 2', retry_callback)
        self.db_error_handler.run_dialog('test 1', 'test 2', retry_callback)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(retry_callback.call_count, 0)
        # try a bunch of backend errors
        self.db_error_handler.run_backend_dialog(dialog)
        self.db_error_handler.run_backend_dialog(dialog)
        self.db_error_handler.run_backend_dialog(dialog)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(dialog.run_callback.call_args_list, [
            ((dialogs.BUTTON_QUIT,), {}),
            ((dialogs.BUTTON_QUIT,), {}),
            ((dialogs.BUTTON_QUIT,), {}),
            ((dialogs.BUTTON_QUIT,), {})
        ])
