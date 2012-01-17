import gc

from miro import messages
from miro import models
from miro import search
from miro import ngrams
from miro import itemsource
from miro.item import FeedParserValues
from miro.singleclick import _build_entry
from miro.test.framework import MiroTestCase
from miro.frontends.widgets.itemtrack import SearchFilter

class NGramTest(MiroTestCase):
    def test_simple(self):
        results = ngrams.breakup_word('foobar', 2, 3)
        self.assertSameSet(results, [
            'fo', 'oo', 'ob', 'ba', 'ar',
            'foo', 'oob', 'oba', 'bar'])

    def test_list(self):
        word_list = ['foo', 'bar', 'bazbaz']
        results = ngrams.breakup_list(word_list, 2, 3)
        self.assertSameSet(results, [
                'fo', 'oo', 'foo',
                'ba', 'ar', 'bar',
                'az', 'zb', 'baz', 'azb', 'zba'])

class SearchTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.feed = models.Feed(u'http://example.com/')
        self.item1 = self.make_item(u'http://example.com/', u'my first item')
        self.item2 = self.make_item(u'http://example.com/', u'my second item')

    def make_item(self, url, title=u'default item title'):
        additional = {'title': title}
        entry = _build_entry(url, 'video/x-unknown', additional)
        item = models.Item(FeedParserValues(entry), feed_id=self.feed.id)
        return itemsource.DatabaseItemSource._item_info_for(item)

    def assertMatches(self, query, item_info):
        self.assertTrue(search.item_matches(item_info, query))

    def assertNotMatches(self, query, item_info):
        self.assertFalse(search.item_matches(item_info, query))

    def test_item_matches(self):
        self.assertMatches('first', self.item1)
        self.assertNotMatches('first', self.item2)
        self.assertMatches('second', self.item2)
        self.assertNotMatches('second', self.item1)
        self.assertMatches('my', self.item1)
        self.assertMatches('my', self.item2)
        self.assertNotMatches('foo', self.item1)
        self.assertNotMatches('foo', self.item2)

    def test_item_matches_substring(self):
        self.assertMatches('eco', self.item2)
        self.assertNotMatches('eco', self.item1)
        self.assertMatches('irst', self.item1)
        self.assertNotMatches('irst', self.item2)

    def test_item_matches_short(self):
        # try a 3-character search.  This is the shortest search that we have
        # n-grams for.
        self.assertMatches('ond', self.item2)
        self.assertNotMatches('ond', self.item1)
        # all searches less than 3 characters should match everything
        self.assertMatches('', self.item1)
        self.assertMatches('', self.item2)
        self.assertMatches('d', self.item1)
        self.assertMatches('d', self.item2)
        self.assertMatches('st', self.item1)
        self.assertMatches('st', self.item2)

    def test_item_matches_case_insensitive(self):
        self.assertMatches('FiRsT', self.item1)
        self.assertNotMatches('FiRsT', self.item2)
        self.assertMatches('sEcOnD', self.item2)
        self.assertNotMatches('sEcOnD', self.item1)

    def test_list_matches(self):
        items = [self.item1, self.item2]
        self.assertEquals(list(search.list_matches(items, 'first')),
                          [self.item1])
        self.assertEquals(list(search.list_matches(items, 'second')),
                          [self.item2])
        self.assertEquals(list(search.list_matches(items, 'my')),
                          [self.item1, self.item2])
        self.assertEquals(list(search.list_matches(items, 'foo')),
                          [])

    def test_ngrams_for_term(self):
        self.assertEquals(search._ngrams_for_term('abc'),
                ['abc'])
        self.assertEquals(search._ngrams_for_term('five'),
                ['five'])
        self.assertEquals(search._ngrams_for_term('verybig'),
                ['veryb', 'erybi', 'rybig'])

class ItemSearcherTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.searcher = search.ItemSearcher()
        self.feed = models.Feed(u'http://example.com/')
        self.item1 = self.make_item(u'http://example.com/', u'my first item')
        self.item2 = self.make_item(u'http://example.com/', u'my second item')

    def make_item(self, url, title=u'default item title'):
        additional = {'title': title}
        entry = _build_entry(url, 'video/x-unknown', additional)
        item = models.Item(FeedParserValues(entry), feed_id=self.feed.id)
        self.searcher.add_item(self.make_info(item))
        return item

    def make_info(self, item):
        return itemsource.DatabaseItemSource._item_info_for(item)

    def check_search_results(self, search_text, *correct_items):
        correct_ids = [i.id for i in correct_items]
        self.assertSameSet(self.searcher.search(search_text), correct_ids)

    def check_empty_result(self, search_text):
        self.assertSameSet(self.searcher.search(search_text), [])

    def test_match(self):
        self.check_search_results('my', self.item1, self.item2)
        self.check_search_results('first', self.item1)
        self.check_empty_result('miro')

    def test_update(self):
        self.item1.entry_title = u'my new title'
        self.item1.signal_change()
        self.searcher.update_item(self.make_info(self.item1))
        self.check_search_results('my', self.item1, self.item2)
        self.check_search_results('item', self.item2)
        self.check_search_results('title', self.item1)
        self.check_empty_result('first')

    def test_remove(self):
        self.searcher.remove_item(self.make_info(self.item2).id)
        self.check_search_results('my', self.item1)
        self.check_empty_result('second')

class SearchFilterTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.feed = models.Feed(u'http://example.com/')
        self.initial_list = []
        self.added_objects = []
        self.changed_objects = []
        self.removed_objects = []
        self.filterer = SearchFilter()
        self.info1 = self.make_info(u'info one')
        self.info2 = self.make_info(u'info two')
        self.info3 = self.make_info(u'info three')
        self.info4 = self.make_info(u'info four')

    def make_info(self, title):
        additional = {'title': title}
        url = u'http://example.com/'
        entry = _build_entry(url, 'video/x-unknown', additional)
        item = models.Item(FeedParserValues(entry), feed_id=self.feed.id)
        return itemsource.DatabaseItemSource._item_info_for(item)

    def check_initial_list_filter(self, initial_list, filtered_list):
        self.assertEquals(self.filterer.filter_initial_list(initial_list),
                filtered_list)

    def check_changed_filter(self, added, changed, removed,
            filtered_added, filtered_changed, filtered_removed):
        removed_ids = [i.id for i in removed]
        filtered_removed_ids = [i.id for i in filtered_removed]
        results = self.filterer.filter_changes(added, changed, removed_ids)
        self.assertSameSet(results[0], filtered_added)
        self.assertSameSet(results[1], filtered_changed)
        self.assertSameSet(results[2], filtered_removed_ids)

    def check_search_change(self, query, filtered_added, filtered_removed):
        filtered_removed_ids = [i.id for i in filtered_removed]
        results = self.filterer.set_search(query)
        self.assertSameSet(results[0], filtered_added)
        self.assertSameSet(results[1], filtered_removed_ids)

    def send_items_changed_message(self, added, changed, removed):
        removed = [i.id for i in removed]
        message = messages.ItemsChanged('mytpe', 123, added, changed, removed)
        self.filterer.handle_items_changed(message)

    def update_info(self, info, name):
        info.name = name
        info.search_terms = search.calc_search_terms(info)

    def test_initial_list(self):
        # try with no search just to see
        self.check_initial_list_filter([self.info1, self.info2],
            [self.info1, self.info2])
        # try again with a search set
        self.filterer = SearchFilter()
        self.filterer.set_search("two")
        self.check_initial_list_filter([self.info1, self.info2], [self.info2])

    def test_change_search(self):
        self.filterer.filter_initial_list([self.info1, self.info2])
        # info1 doesn't matches the search, it should be removed
        self.check_search_change("two", [], [self.info1])
        # info1 matches now, item2 doesn't
        self.check_search_change("one", [self.info1], [self.info2])

    def test_add(self):
        # setup initial state
        self.filterer.filter_initial_list([self.info1, self.info2])
        self.filterer.set_search("three")
        # only info3 matches the search, it should be the only one added
        self.check_changed_filter([self.info3, self.info4], [], [],
                [self.info3], [], [])

    def test_update(self):
        # setup initial state
        infos = [self.info1, self.info2, self.info3]
        self.filterer.filter_initial_list(infos)
        self.filterer.set_search("three")
        # info1 now matches the search, it should be added
        # info3 matched the search before and now, so it should be changed
        self.update_info(self.info1, u'three')
        self.check_changed_filter([], infos, [],
            [self.info1], [self.info3], [])
        # info1 no longer matches the search, it should be removed
        # info3 matched the search before and now, so it should be changed
        self.update_info(self.info1, u'one')
        self.check_changed_filter([], infos, [],
            [], [self.info3], [self.info1])

    def test_remove(self):
        self.filterer.filter_initial_list([self.info1, self.info2])
        self.filterer.set_search("two")
        # only info2 matches the search, so removed should only include it
        self.check_changed_filter([], [], [self.info1, self.info2],
                [], [], [self.info2])
