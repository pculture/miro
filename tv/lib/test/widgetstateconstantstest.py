from miro.test.framework import MiroTestCase
from miro.frontends.widgets.widgetstatestore import WidgetStateStore

class WidgetStateConstants(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.display_types = set(WidgetStateStore.get_display_types())
        self.columns = set()
        for display_type in self.display_types:
            self.columns.update(WidgetStateStore.get_columns_available(display_type))

    def test_view_types(self):
        self.assertNotEqual(WidgetStateStore.get_list_view_type(),
                            WidgetStateStore.get_standard_view_type())

    def test_default_view_types(self):
        display_types = set(WidgetStateStore.DEFAULT_VIEW_TYPE.keys())
        self.assertEqual(self.display_types, display_types)

    def test_default_column_widths(self):
        columns = set(WidgetStateStore.DEFAULT_COLUMN_WIDTHS.keys())
        self.assertEqual(self.columns, columns)

    def test_default_sort_column(self):
        display_types = set(WidgetStateStore.DEFAULT_SORT_COLUMN.keys())
        self.assertEqual(self.display_types, display_types)

    def test_default_columns(self):
        display_types = set(WidgetStateStore.DEFAULT_COLUMNS.keys())
        self.assertEqual(self.display_types, display_types)

    def test_available_columns(self):
        # Currently what get_display_types() uses. Testing it anyway.
        display_types = set(WidgetStateStore.AVAILABLE_COLUMNS.keys())
        self.assertEqual(self.display_types, display_types)
