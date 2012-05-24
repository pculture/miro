# Miro - an RSS based video player application
# Copyright (C) 2012
# Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""itemlisttest -- Test ItemList"""

import itertools
import random
import string

from miro import app
from miro import models
from miro.frontends.widgets import newitemlist as itemlist
from miro.frontends.widgets import itemsort
from miro.test import mock
from miro.test.framework import MiroTestCase

class ItemListTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.init_data_package()
        self.feed = models.Feed(u'http://example.com/feed.rss')
        self.items = [self.make_item(self.feed, u'item-%s' % i)
                      for i in xrange(10)]
        app.db.finish_transaction()
        self.item_list = itemlist.FeedItemList(self.feed.id)
        self.items_changed_handler = mock.Mock()
        self.list_changed_handler = mock.Mock()
        self.item_list.connect("items-changed", self.items_changed_handler)
        self.item_list.connect("list-changed", self.list_changed_handler)

    def refresh_item_list(self):
        app.db.finish_transaction()
        self.item_list._refetch_id_list()

    def check_list_changed_signal(self):
        self.assertEquals(self.list_changed_handler.call_count, 1)
        self.list_changed_handler.reset_mock()

    def test_filter(self):
        # make some of our items podcasts so we can use the PodcastFilter
        podcast_count = 0
        for i in xrange(0, len(self.items), 2):
            self.items[i].kind = u'podcast'
            self.items[i].signal_change()
            podcast_count += 1
        app.db.finish_transaction()
        # set the filter
        self.item_list.set_filters(['podcasts'])
        self.check_list_changed_signal()
        self.assertEquals(len(self.item_list), podcast_count)
        for i in xrange(podcast_count):
            item = self.item_list.get_row(i)
            self.assertEquals(item.kind, u'podcast')

    def check_sort_order(self, correct_item_order):
        correct_ids = [i.id for i in correct_item_order]
        ids_from_item_list = [ self.item_list.get_row(i).id
                              for i in range(len(self.item_list)) ]
        self.assertEquals(correct_ids, ids_from_item_list)

    def test_sort(self):
        # give each items a random title
        for i in self.items:
            i.title = u''.join(random.choice(string.letters) for i in range(5))
            i.signal_change()
        app.db.finish_transaction()
        # test that the default sort is release date
        self.items.sort(key=lambda i: i.release_date)
        self.check_sort_order(self.items)
        # test TitleSort
        self.item_list.set_sort(itemsort.TitleSort(True))
        self.items.sort(key=lambda i: i.title)
        self.check_sort_order(self.items)
        # test reversing a sort
        self.item_list.set_sort(itemsort.TitleSort(False))
        self.items.sort(key=lambda i: i.title, reverse=True)
        self.check_sort_order(self.items)

    def test_attrs(self):
        id1 = self.items[0].id
        id2 = self.items[-1].id
        id3 = self.items[1].id
        # test setting attributes
        self.item_list.set_attr(id1, 'key', 'value')
        self.item_list.set_attr(id2, 'key', 'value2')
        self.assertEquals(self.item_list.get_attr(id1, 'key'), 'value')
        self.assertEquals(self.item_list.get_attr(id2, 'key'), 'value2')
        # test missing attributes
        self.assertRaises(KeyError, self.item_list.get_attr, id1, 'otherkey')
        self.assertRaises(KeyError, self.item_list.get_attr, id3, 'key')
        # test changing attributes
        self.item_list.set_attr(id1, 'key', 'new-value')
        self.assertEquals(self.item_list.get_attr(id1, 'key'), 'new-value')
        # test that if an item is removed, the attributes stay around
        self.items[4].remove()
        self.refresh_item_list()
        self.assertEquals(len(self.item_list), len(self.items) - 1)
        self.assertEquals(self.item_list.get_attr(id1, 'key'), 'new-value')
        self.assertEquals(self.item_list.get_attr(id2, 'key'), 'value2')
        # test unsetting attributes
        self.item_list.unset_attr(id1, 'key')
        self.assertRaises(KeyError, self.item_list.get_attr, id1, 'key')
        # test that a second unset is okay
        self.item_list.unset_attr(id1, 'key')

    def check_group_info(self, grouping_func):
        items = [self.item_list.get_row(i)
                 for i in xrange(len(self.item_list))]
        row_counter = itertools.count()
        for key, group in itertools.groupby(items, grouping_func):
            group_list = list(group)
            for i, item in enumerate(group_list):
                correct_group_info = (i, len(group_list))
                group_info = self.item_list.get_group_info(row_counter.next())
                self.assertEquals(group_info, correct_group_info)

    def test_grouping(self):
        # change all item titles so they start and end with 'a' or 'b'
        first_letter = itertools.cycle(['a', 'a', 'b'])
        last_letter = itertools.cycle(['b', 'a', 'b'])
        for item in self.items:
            item.title = u''.join((first_letter.next(),
                                   random.choice(string.letters),
                                   last_letter.next()))
            item.signal_change()
        app.db.finish_transaction()
        self.item_list._refetch_id_list()
        # check that get_group_info() raises a ValueError before a grouping
        # func is set
        for i in xrange(len(self.item_list)):
            self.assertRaises(ValueError, self.item_list.get_group_info, i)
        self.assertEquals(self.item_list.get_grouping(), None)
        # test setting a grouping function
        def first_letter_grouping(item):
            return item.title[0]
        self.item_list.set_grouping(first_letter_grouping)
        self.check_group_info(first_letter_grouping)
        # test changing a grouping function
        def last_letter_grouping(info):
            return info.title[-1]
        self.item_list.set_grouping(last_letter_grouping)
        self.check_group_info(last_letter_grouping)
        # test grouping is correct after changing the sort
        self.item_list.set_sort(itemsort.TitleSort())
        self.check_group_info(last_letter_grouping)
