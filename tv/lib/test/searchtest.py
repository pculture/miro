import gc

from miro import app
from miro import models
from miro import search
from miro import ngrams
from miro.item import FeedParserValues
from miro.singleclick import _build_entry
from miro.test.framework import MiroTestCase

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

    def test_memory(self):
        # make sure we aren't leaking memory in our C module
        gc.collect()
        start_count = len(gc.get_objects())
        results = ngrams.breakup_list(['foo', 'bar', 'bazbaz'], 1, 3)
        results2 = ngrams.breakup_word('miroiscool', 1, 3)
        del results
        del results2
        gc.collect()
        end_count = len(gc.get_objects())
        self.assertEquals(start_count, end_count)

class SearchTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.feed = models.Feed(u'http://example.com/')
        self.item1 = self.make_item(u'http://example.com/', u'my first item')
        self.item2 = self.make_item(u'http://example.com/', u'my second item')

    def make_item(self, url, title=u'default item title'):
        additional = {'title': title}
        entry = _build_entry(url, 'video/x-unknown', additional)
        return models.Item(FeedParserValues(entry), feed_id=self.feed.id)

    def _check_search(self, query, matching_items):
        matching_ids = [item.id for item in matching_items]
        self.assertSameSet(app.item_searcher.search(query), matching_ids)

    def test_simple(self):
        self._check_search('first', [self.item1])
        self._check_search('second', [self.item2])
        self._check_search('my', [self.item1, self.item2])
        self._check_search('foo', [])
        # test matching substrings
        self._check_search('eco', [self.item2])
        self._check_search('irst', [self.item1])
        # check 0/1 characters as an edge case
        self._check_search('d', [self.item2])
        self._check_search('', [self.item1, self.item2])
        # Check that case doesn't matter
        self._check_search('FiRsT', [self.item1])
        self._check_search('sEcOnD', [self.item2])

    def test_track_changes(self):
        # test that as Item objects change, we update our index
        self.item1.set_title(u"foo")
        self._check_search('foo', [self.item1])
        self.item1.set_title(u"bar")
        self._check_search('foo', [])

    def test_initialize(self):
        # test initialize() sets up the initial state correctly
        app.item_searcher = search.ItemSearcher()
        app.item_searcher.initialize()
        self._check_search('first', [self.item1])
        self._check_search('second', [self.item2])
        self._check_search('my', [self.item1, self.item2])
        self._check_search('foo', [])

    def test_no_initialize(self):
        # test that calling search() before initialize is okay
        app.item_searcher = search.ItemSearcher()
        self._check_search('first', [self.item1])
        self._check_search('second', [self.item2])
        self._check_search('my', [self.item1, self.item2])
        self._check_search('foo', [])

    def test_ngrams_for_term(self):
        self.assertEquals(app.item_searcher._ngrams_for_term('a'),
                ['a'])
        self.assertEquals(app.item_searcher._ngrams_for_term('five'),
                ['five'])
        self.assertEquals(app.item_searcher._ngrams_for_term('verybig'),
                ['veryb', 'erybi', 'rybig'])
