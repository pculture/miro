import gc

from miro import app
from miro import models
from miro import search
from miro import ngrams
from miro import itemsource
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
        self.assertMatches('d', self.item2)
        self.assertNotMatches('d', self.item1)
        self.assertMatches('', self.item1)
        self.assertMatches('', self.item2)

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
        self.assertEquals(search._ngrams_for_term('a'),
                ['a'])
        self.assertEquals(search._ngrams_for_term('five'),
                ['five'])
        self.assertEquals(search._ngrams_for_term('verybig'),
                ['veryb', 'erybi', 'rybig'])
