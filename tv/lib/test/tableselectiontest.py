from miro.test.framework import MiroTestCase

from miro.errors import WidgetActionError
from miro.signals import SignalEmitter
from miro.frontends.widgets.tableselection import SelectionOwnerMixin

class TestSelectionOwnerMixin(SelectionOwnerMixin):
    def __init__(self):
        SelectionOwnerMixin.__init__(self)
        self._selected_iters = set()
        self._selected_iter = None

    def _set_allow_multiple_select(self, allow):
        """SOM memoizes this, so we don't need to do anything here."""
        pass

    def _get_allow_multiple_select(self):
        """Return the memoized value, or False if it's not set."""
        return self._allow_multiple_select or False

    def _get_selected_iters(self):
        if self.allow_multiple_select:
            return list(self._selected_iters)
        elif self._selected_iter is None:
            return []
        else:
            return [self._selected_iter]

    def _get_selected_iter(self):
        if self.allow_multiple_select:
            raise WidgetActionError("get_selected with multiple select")
        else:
            return self._selected_iter

    def _select(self, iter_):
        if not iter_ in self:
            raise WidgetActionError("iter doesn't exist")
        if self.allow_multiple_select:
            self._selected_iters.add(iter_)
        else:
            self._selected_iter = iter_

    def _is_selected(self, iter_):
        if not iter_ in self:
            raise WidgetActionError("iter doesn't exist")
        if self.allow_multiple_select:
            return iter_ in self._selected_iters
        else:
            return iter_ == self._selected_iter

    def _unselect_all(self):
        if self.allow_multiple_select:
            self._selected_iters.clear()
        else:
            self._selected_iter = None

    def _unselect_iter(self, iter_):
        if not iter_ in self:
            raise WidgetActionError("iter doesn't exist")
        if self.allow_multiple_select:
            self._selected_iters.discard(iter_)
        elif iter_ == self._selected_iter:
            self._selected_iter = None

    def _iter_to_string(self, iter_):
        return str(iter_)

    def _iter_from_string(self, iter_):
        return int(iter_)

    def _iter_to_smart_selector(self, iter_):
        return unicode(iter_)

    def _iter_from_smart_selector(self, iter_):
        return int(iter_)

class MockTableView(set, SignalEmitter, TestSelectionOwnerMixin):
    """A set() of iters, which in this case are just ints."""
    def __init__(self):
        SignalEmitter.__init__(self)
        TestSelectionOwnerMixin.__init__(self)

class TableSelectionTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.view = MockTableView()
        self.view.add(2)
        self.view.add(45)
        self.view.add(90)

    def assert_nothing_selected(self):
        self.assertEquals(self.view.num_rows_selected, 0)
        self.assertEquals(self.view.get_selection(), [])
        if not self.view.allow_multiple_select:
            self.assertEquals(self.view.get_selected(), None)

    def test_single_selection_mode(self):
        self.view.allow_multiple_select = False
        # nothing selected
        self.assert_nothing_selected()
        # select something that doesn't exist
        self.assertRaises(WidgetActionError, lambda: self.view.select(9))
        # select first thing
        self.view.select(45)
        self.assertEquals(self.view.num_rows_selected, 1)
        self.assertEquals(self.view.get_selected(), 45)
        self.assertEquals(self.view.get_selection(), [45])
        # select different thing
        self.view.select(90)
        self.assertEquals(self.view.num_rows_selected, 1)
        self.assertEquals(self.view.get_selected(), 90)
        self.assertEquals(self.view.get_selection(), [90])
        # unselect something that doesn't exist
        self.assertRaises(WidgetActionError, lambda: self.view.select(9))
        # unselect something that isn't what's selected
        self.view.unselect(45)
        self.assertEquals(self.view.num_rows_selected, 1)
        self.assertEquals(self.view.get_selected(), 90)
        self.assertEquals(self.view.get_selection(), [90])
        # unselect thing specifically
        self.view.unselect(90)
        self.assert_nothing_selected()
        # select thing
        self.view.select(45)
        # unselect everything
        self.view.unselect_all()
        self.assert_nothing_selected()

    def test_multiple_selection_mode(self):
        self.view.allow_multiple_select = True
        self.assertRaises(WidgetActionError, self.view.get_selected)
        # nothing selected
        self.assert_nothing_selected()
        # select something that doesn't exist
        self.assertRaises(WidgetActionError, lambda: self.view.select(9))
        # select first thing
        self.view.select(45)
        self.assertEquals(self.view.num_rows_selected, 1)
        self.assertEquals(self.view.get_selection(), [45])
        # select different thing
        self.view.select(90)
        self.assertEquals(self.view.num_rows_selected, 2)
        self.assertEquals(set(self.view.get_selection()), set([45, 90]))
        # unselect something that doesn't exist
        self.assertRaises(WidgetActionError, lambda: self.view.select(9))
        # unselect something that isn't what's selected
        self.view.unselect(2)
        self.assertEquals(self.view.num_rows_selected, 2)
        self.assertEquals(set(self.view.get_selection()), set([45, 90]))
        # unselect thing specifically
        self.view.unselect(90)
        self.assertEquals(self.view.num_rows_selected, 1)
        self.assertEquals(self.view.get_selection(), [45])
        # unselect everything
        self.view.unselect_all()
        self.assert_nothing_selected()

    def test_save_restore_single(self):
        self.view.allow_multiple_select = False
        self.view.select(45)
        self.view._save_selection()
        self.view._unselect_all()
        self.view._restore_selection()
        self.view._restore_selection()
        self.assertEquals(self.view.get_selection(), [45])

    def test_save_restore_multiple(self):
        self.view.allow_multiple_select = True
        self.view.select(45)
        self.view.select(90)
        self.view._save_selection()
        self.view._unselect_all()
        self.view._restore_selection()
        self.view._restore_selection()
        self.assertEquals(set(self.view.get_selection()), set([45, 90]))

    def test_save_restore_as_strings_single(self):
        # _save and _restore used here to make sure they don't interfere with
        # _as_strings
        self.view.allow_multiple_select = False
        self.view.select(2)
        self.view._save_selection()
        self.view.select(45)
        sel = self.view.get_selection_as_strings()
        self.view._unselect_all()
        self.view._restore_selection()
        self.view.set_selection_as_strings(sel)
        self.view._restore_selection()
        self.assertEquals(self.view.get_selection(), [45])

    def test_save_restore_as_strings_multiple(self):
        # _save and _restore used here to make sure they don't interfere with
        # _as_strings
        self.view.allow_multiple_select = True
        self.view.select(45)
        self.view._save_selection()
        self.view.select(90)
        sel = self.view.get_selection_as_strings()
        self.view._unselect_all()
        self.view._restore_selection()
        self.view.set_selection_as_strings(sel)
        self.view._restore_selection()
        self.assertEquals(set(self.view.get_selection()), set([45, 90]))
