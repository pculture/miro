from miro.test.framework import MiroTestCase
from miro import metadata

class TestSource(metadata.Source):
    pass

class TestStore(metadata.Store):
    def confirm_db_thread(self): pass
    def signal_change(self): pass
    # doesn't need a get_filename() because no coverart file will be written

class Metadata(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)

    def test_iteminfo_round_trip(self):
        """Test that properties changed by ItemInfo name affect the right
        attributes. Test will also fail with errors if setup_new doesn't
        initialize all the properties that are used by ItemInfo.
        """
        source = TestSource()
        source.setup_new()
        info = source.get_iteminfo_metadata()

        store = TestStore()
        store.setup_new()
        store.set_metadata_from_iteminfo(info)

        original_dict = info
        after_round_trip = store.get_iteminfo_metadata()
        self.assertDictEqual(original_dict, after_round_trip)
