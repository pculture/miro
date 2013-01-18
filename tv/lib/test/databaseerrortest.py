import sqlite3

from miro import app
from miro import dialogs
from miro.data import dberrors
from miro.data import item
from miro.data import itemtrack
from miro.test import mock
from miro.test import testobjects
from miro.test.framework import MiroTestCase

class DBErrorTest(MiroTestCase):
    """Test database error handling."""

    def setUp(self):
        MiroTestCase.setUp(self)
        self.frontend = mock.Mock()
        self.run_choice_dialog = self.frontend.run_choice_dialog
        self.db_error_handler = dberrors.DBErrorHandler(self.frontend)

    def check_run_dialog_scheduled(self, title, description, thread,
                                   reset_mock=True):
        call_on_ui_thread = self.frontend.call_on_ui_thread
        self.assertEquals(call_on_ui_thread.call_count, 1)
        func = call_on_ui_thread.call_args[0][0]
        args = call_on_ui_thread.call_args[0][1:]
        self.assertEquals(func, self.db_error_handler._run_dialog)
        self.assertEquals(args, (title, description, thread))
        if reset_mock:
            call_on_ui_thread.reset_mock()
        return args

    def check_run_dialog_not_scheduled(self):
        self.assertEquals(self.frontend.call_on_ui_thread.call_count, 0)

    def run_dialog(self, title, description, retry_callback=None):
        self.db_error_handler.run_dialog(title, description, retry_callback)
        # run_dialog should schedule the dialog to be run later using
        # call_on_ui_thread()
        args = self.check_run_dialog_scheduled(title, description, 'ui thread')
        # call _run_dialog to simulate showing the dialog
        self.db_error_handler._run_dialog(*args)

    def run_backend_dialog(self, dialog):
        self.db_error_handler.run_backend_dialog(dialog)
        # run_dialog should schedule the dialog to be run later using
        # call_on_ui_thread()
        call_on_ui_thread = self.frontend.call_on_ui_thread
        self.assertEquals(call_on_ui_thread.call_count, 1)
        func = call_on_ui_thread.call_args[0][0]
        args = call_on_ui_thread.call_args[0][1:]
        call_on_ui_thread.reset_mock()
        self.assertEquals(func, self.db_error_handler._run_dialog)
        self.assertEquals(args, (dialog.title, dialog.description,
                                 'eventloop thread'))
        # call _run_dialog to simulate showing the dialog
        self.db_error_handler._run_dialog(*args)

    def test_frontend_error_handling(self):
        self.run_choice_dialog.return_value = dialogs.BUTTON_RETRY
        # the frontend calls run_dialog() when it sees an error
        retry_callback = mock.Mock()
        self.run_dialog('test 1', 'test 2', retry_callback)
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
        self.run_dialog('test 1', 'test 2', retry_callback)
        self.assertEquals(retry_callback.call_count, 0)

    def test_backend_error_handling(self):
        # when the backend sees an error, it should send the
        # DatabaseErrorDialog to the frontend and the frontend should call
        # DBErrorHandler.run_backend_dialog().  This test is testing what
        # happens when run_backend_dialog() is called.
        self.run_choice_dialog.return_value = dialogs.BUTTON_RETRY
        dialog = mock.Mock(title='test 1', description='test 2')
        self.run_backend_dialog(dialog)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(dialog.run_callback.call_count, 1)
        self.assertEquals(dialog.run_callback.call_args,
                          ((dialogs.BUTTON_RETRY,), {}))

    def test_backend_then_frontend_errors(self):
        retry_callback = mock.Mock()
        def run_choice_dialog(title, description, buttons):
            # while inside the choice dialog for the backend, we trigger
            # another error from the frontend.
            self.run_dialog('test 1', 'test 2', retry_callback)
            return dialogs.BUTTON_RETRY
        self.run_choice_dialog.side_effect = run_choice_dialog
        dialog = mock.Mock(title='test 1', description='test 2')
        self.run_backend_dialog(dialog)
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
            self.run_backend_dialog(dialog)
            return dialogs.BUTTON_RETRY
        self.run_choice_dialog.side_effect = run_choice_dialog
        self.run_dialog('test 1', 'test 2', retry_callback)
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
            self.run_dialog('test 1', 'test 2', retry_callback)
            self.run_dialog('test 1', 'test 2', retry_callback)
            self.run_dialog('test 1', 'test 2', retry_callback)
            return dialogs.BUTTON_RETRY
        self.run_choice_dialog.side_effect = run_choice_dialog
        self.run_dialog('test 1', 'test 2', retry_callback)
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
        self.run_backend_dialog(dialog)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(dialog.run_callback.call_args[0][0],
                          dialogs.BUTTON_RETRY)
        # handle a frontend error, we should reuse the RETRY response
        retry_callback = mock.Mock()
        self.run_dialog('test 1', 'test 2', retry_callback)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(retry_callback.call_count, 1)
        # handle another frontend error this time we shouldn't reuse the RETRY
        # response
        self.run_dialog('test 1', 'test 2', retry_callback)
        self.assertEquals(self.run_choice_dialog.call_count, 2)
        self.assertEquals(retry_callback.call_count, 2)

    def test_reuse_quit(self):
        # if the user replies with QUIT, then we should always return QUIT
        # for future errors
        self.run_choice_dialog.return_value = dialogs.BUTTON_QUIT
        dialog = mock.Mock(title='test 1', description='test 2')
        # handle a backend error
        self.run_backend_dialog(dialog)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(dialog.run_callback.call_args[0][0],
                          dialogs.BUTTON_QUIT)
        # for future errors, we should assume the user still wants to quit

        # try a bunch of frontend errors
        retry_callback = mock.Mock()
        self.run_dialog('test 1', 'test 2', retry_callback)
        self.run_dialog('test 1', 'test 2', retry_callback)
        self.run_dialog('test 1', 'test 2', retry_callback)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(retry_callback.call_count, 0)
        # try a bunch of backend errors
        self.run_backend_dialog(dialog)
        self.run_backend_dialog(dialog)
        self.run_backend_dialog(dialog)
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        self.assertEquals(dialog.run_callback.call_args_list, [
            ((dialogs.BUTTON_QUIT,), {}),
            ((dialogs.BUTTON_QUIT,), {}),
            ((dialogs.BUTTON_QUIT,), {}),
            ((dialogs.BUTTON_QUIT,), {})
        ])

    def test_quit(self):
        # Check that we call Frontend.quit()
        self.run_choice_dialog.return_value = dialogs.BUTTON_QUIT
        dialog = mock.Mock(title='test 1', description='test 2')
        self.run_backend_dialog(dialog)
        self.assertEquals(self.frontend.quit.call_count, 1)
        # another error shouldn't result in 2 quit calls
        self.run_choice_dialog.return_value = dialogs.BUTTON_QUIT
        dialog = mock.Mock(title='test 1', description='test 2')
        self.run_backend_dialog(dialog)
        self.assertEquals(self.frontend.quit.call_count, 1)

    def test_error_in_retry_callback(self):
        self.run_choice_dialog.return_value = dialogs.BUTTON_RETRY
        # the frontend calls run_dialog() when it sees an error
        mock_retry_callback = mock.Mock()
        def retry_callback():
            # the first time this one is called, we similate another error
            # happening
            if mock_retry_callback.call_count == 1:
                self.db_error_handler.run_dialog('test 1', 'test 2',
                                                 mock_retry_callback)
        mock_retry_callback.side_effect = retry_callback
        self.run_dialog('test 1', 'test 2', mock_retry_callback)
        # the first run through retry_callback resulted in an error.  We
        # should have a new dialog scheduled to pop up.  We shouldn't call
        # retry_callback() again yet, nor have actually popped up the dialog.
        self.assertEquals(self.run_choice_dialog.call_count, 1)
        args = self.check_run_dialog_scheduled('test 1', 'test 2', 'ui thread')
        self.assertEquals(mock_retry_callback.call_count, 1)
        # Run the dialog again.  The second time through our retry callback
        # won't have an error
        self.db_error_handler._run_dialog(*args)
        self.assertEquals(self.run_choice_dialog.call_count, 2)
        self.assertEquals(mock_retry_callback.call_count, 2)
        self.check_run_dialog_not_scheduled()

class TestItemTrackErrors(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.init_data_package()
        self.idle_scheduler = mock.Mock()
        self.feed, self.items = testobjects.make_feed_with_items(10)
        app.db.finish_transaction()

    def make_tracker(self):
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.feed.id)
        query.set_order_by(['release_date'])
        item_tracker = itemtrack.ItemTracker(self.idle_scheduler, query,
                                     item.ItemSource())
        self.list_changed_callback = mock.Mock()
        self.items_changed_callback = mock.Mock()
        item_tracker.connect('list-changed', self.list_changed_callback)
        item_tracker.connect('items-changed', self.items_changed_callback)
        return item_tracker

    def force_db_error(self):
        def execute_that_fails(*args, **kwargs):
            raise sqlite3.DatabaseError("Test Error")
        mock_execute = mock.Mock(side_effect=execute_that_fails)
        return mock.patch('miro.data.connectionpool.Connection.execute',
                          mock_execute)

    def fetch_item_infos(self):
        return item.fetch_item_infos(app.db, [i.id for i in self.items])

    def test_error_fetching_list(self):
        with self.allow_warnings():
            with self.force_db_error():
                tracker = self.make_tracker()
        self.assertEquals(app.db_error_handler.run_dialog.call_count, 1)
        # since there was an error while fetching the initial item list,
        # get_items() should return None
        self.assertEquals(tracker.get_items(), [])
        # when the retry callback is called, we should send the list-changed
        # callback with the correct data
        retry_callback = app.db_error_handler.run_dialog.call_args[0][2]
        self.assertNotEquals(retry_callback, None)
        self.assertEquals(self.list_changed_callback.call_count, 0)
        retry_callback()
        self.assertEquals(self.list_changed_callback.call_count, 1)
        # get_items() should return the correct items now
        self.assertSameSet(tracker.get_items(), self.fetch_item_infos())

    def test_error_fetching_rows(self):
        tracker = self.make_tracker()
        with self.allow_warnings():
            with self.force_db_error():
                # call get_row a bunch of items.  On GTK I think we can get
                # nested errors while waiting for the dialog response.
                rv1 = tracker.get_row(0)
                rv2 = tracker.get_row(1)
                rv3 = tracker.get_row(2)
                self.assertEquals(rv1.__class__, item.DBErrorItemInfo)
                self.assertEquals(rv2.__class__, item.DBErrorItemInfo)
                self.assertEquals(rv3.__class__, item.DBErrorItemInfo)
                self.assertSameSet(tracker.get_items(),
                                   [item.DBErrorItemInfo(item_obj.id)
                                    for item_obj in self.items])
        self.assertEquals(app.db_error_handler.run_dialog.call_count, 1)
        # when the retry callback is called, we should send the list-changed
        # callback with the correct data
        retry_callback = app.db_error_handler.run_dialog.call_args[0][2]
        self.assertNotEquals(retry_callback, None)
        self.assertEquals(self.list_changed_callback.call_count, 0)
        retry_callback()
        self.assertEquals(self.list_changed_callback.call_count, 1)
        # get_items() should return the correct items now
        self.assertSameSet(tracker.get_items(), self.fetch_item_infos())

    def test_error_has_playables(self):
        tracker = self.make_tracker()
        with self.allow_warnings():
            with self.force_db_error():
                retval = tracker.has_playables()
        self.assertEquals(app.db_error_handler.run_dialog.call_count, 1)
        # on db errors, has_playables() should return False
        self.assertEquals(retval, False)
        # We don't need a retry callback for this.
        retry_callback = app.db_error_handler.run_dialog.call_args[0][2]
        self.assertNotEquals(retry_callback, None)

    def test_error_get_playable_ids(self):
        tracker = self.make_tracker()
        with self.allow_warnings():
            with self.force_db_error():
                retval = tracker.get_playable_ids()
        self.assertEquals(app.db_error_handler.run_dialog.call_count, 1)
        # on db errors, get_playable_ids() should return an empty list
        self.assertEquals(retval, [])
        # We don't need a retry callback for this.
        retry_callback = app.db_error_handler.run_dialog.call_args[0][2]
        self.assertNotEquals(retry_callback, None)
