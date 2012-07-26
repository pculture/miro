from miro.frontends.widgets import itemfilter

from miro.test.framework import MiroTestCase

class FakeItemInfo(object):
    # really simple item info.  This is just enough to pass it to a couple
    # filters
    def __init__(self, file_type, downloaded):
        self.file_type = file_type
        if downloaded:
            self.video_path = '/fake/filename'
        else:
            self.video_path = None

class ItemFilterTest(MiroTestCase):
    def check_active_filters(self, filter_set, *correct_filters):
        self.assertEquals(filter_set.active_filters,
                set(correct_filters))
        # check that all filter keys are unicode
        for filter in filter_set.active_filters:
            self.assertEquals(type(filter), unicode)

    def test_filter_selection(self):
        # Test simple cases of changing filters
        filter_set = itemfilter.ItemFilterSet()
        # all should be the default
        self.check_active_filters(filter_set, 'all')
        # change to unplayed
        filter_set.select('unplayed')
        self.check_active_filters(filter_set, 'unplayed')
        # change back to all
        filter_set.select('all')
        self.check_active_filters(filter_set, 'all')

    def test_podcast_filters_selection(self):
        # Test the filters for the podcasts tab.
        filter_set = itemfilter.ItemFilterSet()
        filter_set.select('all')
        self.check_active_filters(filter_set, 'all')
        # selecting video should auto-select downloaded by default
        filter_set.select('video')
        self.check_active_filters(filter_set, 'video', 'downloaded')
        # but if unplayed is selected, then it should not leave that alone
        filter_set.select('all')
        filter_set.select('unplayed')
        filter_set.select('video')
        self.check_active_filters(filter_set, 'video', 'unplayed')
        # if we select unplayed again nothing should change
        filter_set.select('unplayed')
        self.check_active_filters(filter_set, 'video', 'unplayed')
        # if we select downloaded, then unplayed should unselect
        filter_set.select('downloaded')
        self.check_active_filters(filter_set, 'video', 'downloaded')
