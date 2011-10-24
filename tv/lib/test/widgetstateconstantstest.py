from miro.test.framework import MiroTestCase
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.frontends.widgets.itemlist import SORT_KEY_MAP

class WidgetStateConstants(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.display_types = set(WidgetStateStore.get_display_types())

    def test_view_types(self):
        # test that all view types are different
        view_types = (WidgetStateStore.get_list_view_type(),
                WidgetStateStore.get_standard_view_type(),
                WidgetStateStore.get_album_view_type())

        for i in range(len(view_types)):
            for j in range(i + 1, len(view_types)):
                self.assertNotEqual(view_types[i], view_types[j])

    def test_default_view_types(self):
        display_types = set(WidgetStateStore.DEFAULT_VIEW_TYPE)
        self.assertEqual(self.display_types, display_types)

    def test_default_column_widths(self):
        # test that all available columns have widths set for them

        # calculate all columns that available for some display/view
        # combination
        available_columns = set()
        display_id = None # this isn't used yet, just set it to a dummy value
        for display_type in self.display_types:
            for view_type in (WidgetStateStore.get_list_view_type(),
                            WidgetStateStore.get_standard_view_type(),
                            WidgetStateStore.get_album_view_type()):
                available_columns.update(
                        WidgetStateStore.get_columns_available(
                            display_type, display_id, view_type))

        # make sure that we have widths for those columns
        self.assertEqual(available_columns,
                set(WidgetStateStore.DEFAULT_COLUMN_WIDTHS.keys()))

    def test_default_sort_column(self):
        display_types = set(WidgetStateStore.DEFAULT_SORT_COLUMN)
        self.assertEqual(self.display_types, display_types)

    def test_default_columns(self):
        display_types = set(WidgetStateStore.DEFAULT_COLUMNS)
        self.assertEqual(self.display_types, display_types)

    def test_available_columns(self):
        # Currently what get_display_types() uses. Testing it anyway.
        display_types = set(WidgetStateStore.AVAILABLE_COLUMNS)
        self.assertEqual(self.display_types, display_types)

    def test_sort_key_map(self):
        columns = set(WidgetStateStore.DEFAULT_COLUMN_WIDTHS)
        sort_keys = set(SORT_KEY_MAP)
        self.assertEqual(sort_keys, columns)
