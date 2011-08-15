import itertools
import weakref

from miro.test.framework import (MiroTestCase, skip_for_platforms,
                                 only_on_platforms)
from miro import infolist

class FakeInfo(object):
    def __init__(self, name, id_=None):
        if id_ is None:
            id_ = FakeInfo.counter.next()
        self.id = id_
        self.name = name

    def __eq__(self, other):
        return (type(self) == type(other) and
                self.name == other.name)

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return "FakeInfo(%r, %s)" % (self.name, self.id)

class InfoListTestBase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        FakeInfo.counter = itertools.count()
        self.infolist = self.build_infolist()
        self.sorter = self.sort_key_func
        self.reverse = False
        self.grouping_func = None
        self.correct_infos = []

    def build_infolist(self):
        return infolist.InfoList(self.sort_key_func, False)

    def sort_key_func(self, info):
        return info.name.lower()

    def sort_info_list(self, info_list):
        if self.sorter is not None:
            info_list.sort(key=self.sorter, reverse=self.reverse)

    def make_infos(self, *names):
        return [FakeInfo(n) for n in names]

    def check_info_list(self, check_against):
        if self.sorter is None:
            self.assertEquals(self.infolist.info_list(), check_against)
        else:
            # allow for variations in the order that still match the sort
            self.assertSameSet(self.infolist.info_list(), check_against)
            self.assertEquals([self.sorter(i) for i in
                    self.infolist.info_list()], [self.sorter(i) for i in
                        check_against])

        # test index_of_id(), get_prev_info() and get_next_info()
        list_of_infos = self.infolist.info_list()
        for i, info in enumerate(list_of_infos):
            self.assertEquals(self.infolist.index_of_id(info.id), i)
            if i > 0:
                self.assertEquals(self.infolist.get_prev_info(info.id),
                        list_of_infos[i-1])
            else:
                self.assertEquals(self.infolist.get_prev_info(info.id), None)
            if i < len(list_of_infos) - 1:
                self.assertEquals(self.infolist.get_next_info(info.id),
                        list_of_infos[i+1])
            else:
                self.assertEquals(self.infolist.get_next_info(info.id), None)

        # test get_first_info()
        if list_of_infos:
            self.assertEquals(self.infolist.get_first_info(),
                    list_of_infos[0])
        else:
            self.assertEquals(self.infolist.get_first_info(), None)

        # test get_last_info()
        if list_of_infos:
            self.assertEquals(self.infolist.get_last_info(),
                    list_of_infos[-1])
        else:
            self.assertEquals(self.infolist.get_last_info(), None)

        self.infolist._sanity_check()

        # test grouping info
        if self.grouping_func is not None:
            self.check_grouping()

    def check_insert(self, infos):
        self.correct_infos.extend(infos)
        self.sort_info_list(self.correct_infos)
        self.infolist.add_infos(infos)
        self.check_info_list(self.correct_infos)

    def find_info_index(self, id_):
        filtered_list = filter(lambda i: i.id ==id_, self.correct_infos)
        if len(filtered_list) == 0:
            raise ValueError("no info with id %s", id_)
        if len(filtered_list) > 1:
            raise ValueError("multiple infos with id %s", id_)
        return self.correct_infos.index(filtered_list[0])

    def check_update(self, *args, **kwargs):
        """Update the list and check it.  args should be in the format id,
        name, id2, name2, ...
        """
        to_update = []
        resort = bool(kwargs.get('resort'))
        for i in xrange(0, len(args), 2):
            info = FakeInfo(args[i+1], args[i])
            idx = self.find_info_index(info.id)
            self.correct_infos[idx] = info
            to_update.append(info)
        if resort:
            self.sort_info_list(self.correct_infos)
        self.infolist.update_infos(to_update, resort=resort)
        self.check_info_list(self.correct_infos)

    def check_remove(self, *id_list):
        for i in reversed(range(len(self.correct_infos))):
            if self.correct_infos[i].id in id_list:
                del self.correct_infos[i]
        self.infolist.remove_ids(id_list)
        self.check_info_list(self.correct_infos)

    def check_update_sort(self, new_sorter, reverse=False):
        self.sorter = new_sorter
        self.reverse = reverse
        if new_sorter is not None:
            self.correct_infos.sort(key=new_sorter, reverse=reverse)
        self.infolist.change_sort(new_sorter, reverse)
        self.check_info_list(self.correct_infos)

    def check_update_grouping(self, new_grouping):
        old_list = self.infolist.info_list()
        self.infolist.set_grouping(new_grouping)
        self.grouping_func = new_grouping
        # check that the ordering of infos is the same
        self.assertEquals(old_list, self.infolist.info_list())
        # check grouping info
        self.check_grouping()

    def check_grouping(self):
        # check that grouping info is correct for each info
        groups = itertools.groupby(self.infolist.info_list(),
                self.grouping_func)
        for key, group in groups:
            # key is the value that new_grouping() returned.  group is an
            # iterater that contains infos in that group
            group = list(group)
            total_count = len(group)
            for i, info in enumerate(group):
                # check get_group_info()
                self.assertEquals(self.infolist.get_group_info(info.id),
                        (i, total_count))
                # check get_group_top()
                self.assertEquals(self.infolist.get_group_top(info.id),
                        group[0])
                # check group_info part of row_for_iter
                it = self.infolist.iter_for_id(info.id)
                info, attrs, group_info = self.infolist.row_for_iter(it)
                self.assertEquals(group_info, (i, total_count))

class InfoListDataTest(InfoListTestBase):
    def check_list(self, *names):
        self.assertEquals(list(names),
                [i.name for i in self.infolist.info_list()])

    def test_insert(self):
        self.check_insert(self.make_infos('m', 'i', 'r', 'o'))
        self.check_insert(self.make_infos('n', 'p', 'r'))
        # inserting an info twice should result in value error
        self.assertRaises(ValueError, self.infolist.add_infos,
                self.correct_infos[0:1])
        self.check_info_list(self.correct_infos)
        # inserting if even 1 info is not new then to changes should be made
        info2 = FakeInfo('non-dup')
        self.assertRaises(ValueError, self.infolist.add_infos,
                [info2, self.correct_infos[-1]])
        self.check_info_list(self.correct_infos)
        # check reversed order
        self.check_update_sort(self.sorter, reverse=True)
        self.check_insert(self.make_infos('a', 'z', 'd'))

    def test_insert_in_order(self):
        # ordered inserts is a possible edge case
        self.check_insert(self.make_infos('a', 'b', 'c', 'd'))

    def test_insert_in_reversed_order(self):
        # reversed order inserts is another possible edge case
        self.check_insert(self.make_infos('d', 'c', 'b', 'a'))

    def test_remove(self):
        self.check_insert(self.make_infos('m', 'i', 'r', 'o'))
        self.check_remove(0, 2)
        # check removing node that's already been removed
        self.assertRaises(KeyError, self.infolist.remove_ids, [0])
        self.check_info_list(self.correct_infos)
        # check removing node that was never in the list
        self.assertRaises(KeyError, self.infolist.remove_ids, [200])
        self.check_info_list(self.correct_infos)
        # check removing with one node in the list and one out
        # nothing node with id==1 shouldn't be removed in this case
        self.assertRaises(KeyError, self.infolist.remove_ids, [1, 0])
        self.check_info_list(self.correct_infos)

    def test_update(self):
        self.check_insert(self.make_infos('m', 'i', 'r', 'o'))
        self.check_update(0, 'ZZZ', 3, 'ABC')
        # check info not in list raises KeyError
        new_info = FakeInfo("bar")
        self.assertRaises(KeyError, self.infolist.update_infos, [new_info],
                True)
        self.check_info_list(self.correct_infos)
        # check no changes if any info is not in the list
        self.assertRaises(KeyError, self.infolist.update_infos,
                [new_info, self.correct_infos[2]], True)
        self.check_info_list(self.correct_infos)

    def test_update_resort(self):
        self.check_insert(self.make_infos('m', 'i', 'r', 'o'))
        self.check_update(0, 'ZXY', 3, 'abc', resort=True)
        # check reversed order
        self.check_update_sort(self.sorter, reverse=True)
        self.check_update(1, 'aaa', 2, 'ZZZ', resort=True)

    def test_non_integer_id(self):
        infos = self.make_infos('m', 'i', 'r', 'o', 'p', 'c', 'f')
        for i in infos:
            i.id = i.name # id is the initial name of the info
        self.check_insert(infos[:4])
        self.check_update('m', 'ZZZ', 'r', 'ABC')
        self.check_remove('m', 'i')

    def test_new_sort_order(self):
        self.check_insert(self.make_infos('m', 'i', 'r', 'o'))
        self.check_update_sort(lambda info: info.id)
        # None shouldn't be allowed
        self.assertRaises(ValueError, self.infolist.change_sort, None)

    def test_grouping(self):
        # insert and order some infos
        self.check_insert(self.make_infos('miro', 'monday', 'tuesday', 'moo'))
        self.check_update_sort(lambda info: info.id)
        # check that get_group_info() raises a ValueError before a grouping
        # func is set
        for info in self.correct_infos:
            self.assertRaises(ValueError, self.infolist.get_group_info,
                    info.id)
        # test setting a grouping function
        def first_letter_grouping(info):
            return info.name[0]
        self.check_update_grouping(first_letter_grouping)
        # test changing a grouping function
        def last_letter_grouping(info):
            return info.name[-1]
        self.check_update_grouping(first_letter_grouping)
        # test grouping is correct after changing the sort
        self.check_update_sort(lambda info: info.name)

class InfoListMemoryTest(InfoListTestBase):
    def test_objects_released(self):
        self.check_insert(self.make_infos('m', 'i', 'r', 'o'))
        # make weakrefs to all data in the list
        info_refs = []
        for info in self.correct_infos:
            info_refs.append(weakref.ref(self.infolist.get_info(info.id)))
        # try to do as many operations as possible on the list
        self.check_update(0, 'ZZZ', 1, '123', 2, 'pcf', resort=True)
        self.check_remove(0, 2)
        self.infolist.remove_all()
        # drop all our references and check that the objects are now deleted
        del self.correct_infos
        del info
        for wr in info_refs:
            self.assertEquals(wr(), None)

    def test_objects_released_insert_exception(self):
        # test the edge case where we make some nodes, then see an exception
        # in add_infos()
        self.check_insert(self.make_infos('m', 'i', 'r', 'o'))
        # prepare a batch of infos to add, except 1 is a duplicate which
        # should raise an exception
        new_infos = self.make_infos('a', 'c', 'd')
        new_infos[-1].id = 3
        # make weakrefs to all data in the list
        info_refs = []
        for info in self.correct_infos + new_infos:
            info_refs.append(weakref.ref(info))
        # try to do as many operations as possible on the list
        self.assertRaises(ValueError, self.infolist.add_infos, new_infos)
        self.infolist.remove_all()
        # drop all our references and check that the objects are now deleted
        del new_infos
        del self.correct_infos
        del info
        for wr in info_refs:
            self.assertEquals(wr(), None)

class InfoListFeaturesTest(InfoListTestBase):
    def test_attrs(self):
        self.check_insert(self.make_infos('m', 'i', 'r', 'o'))
        self.infolist.set_attr(0, 'miro', 'foo')
        self.assertEquals(self.infolist.get_attr(0, 'miro'), 'foo')
        self.assertRaises(KeyError, self.infolist.get_attr, 0, 'miro2')
        self.infolist.unset_attr(0, 'miro')
        self.assertRaises(KeyError, self.infolist.get_attr, 0, 'miro')
        # test second unset is okay
        self.infolist.unset_attr(0, 'miro')

@skip_for_platforms('osx')
class InfoListGTKTest(InfoListDataTest):
    # Test the same things as in InfoListTest, but check using GTK's classes.
    # Also, check that GTK signal handlers work.

    def setUp(self):
        InfoListDataTest.setUp(self)
        self.signals_seen = []
        # import gtk inside the function because it will fail on OS X
        import gtk
        self.treeview = gtk.TreeView()
        self.infolist.add_to_tableview(self.treeview)
        # track what infos should be visible when we handle callbacks
        self.tracked_infos = []
        self.signal_error = False # did we get an exception in our signals?
        gtk_model = self.treeview.get_model()
        gtk_model.connect('row-inserted', self.on_row_inserted)
        gtk_model.connect('row-deleted', self.on_row_deleted)
        gtk_model.connect('row-changed', self.on_row_changed)
        gtk_model.connect('rows-reordered', self.on_rows_reordered)

    def check_info_list(self, info_list):
        # check GTK-specific data structures
        gtk_model = self.treeview.get_model()
        self.assertEquals(len(info_list), len(gtk_model))
        it = gtk_model.get_iter_first()
        for x in xrange(len(info_list)):
            check_path = (x,)
            self.assertEquals(gtk_model.get_path(it), check_path)
            iter_for_path = gtk_model.get_iter(check_path)
            self.assertEquals(self.infolist.row_for_iter(iter_for_path),
                    self.infolist.row_for_iter(it))
            # check that iter_for_id gives a correct iter.  This is a bit
            # weird, because iters don't do all that much directly.  To check,
            # make sure that the iter is associated with the correct path.
            info = self.infolist.row_for_iter(it)[0]
            iter_to_check = self.infolist.iter_for_id(info.id)
            self.assertEquals(gtk_model.get_path(iter_to_check), check_path)
            # prepare next loop
            it = gtk_model.iter_next(it)

    def on_row_inserted(self, obj, path, it):
        try:
            # check that that our current model reflects the insert
            info, attrs, group_info = self.infolist.row_for_iter(it)
            if self.sorter is not None:
                self.tracked_infos.append(info)
                self.sort_info_list(self.tracked_infos)
            else:
                self.tracked_infos.insert(path[0], info)
            self.check_info_list(self.tracked_infos)
            # check that path is correct
            possible_paths = [(i,) for i in xrange(len(self.tracked_infos))
                if self.tracked_infos[i] == info]
            self.assert_(path in possible_paths)
        except Exception:
            # Exceptions in signal handlers won't actually halt the test, we
            # have to do that manually
            self.signal_error = True
            raise

    def on_row_changed(self, obj, path, it):
        try:
            # check path points to the correct info
            self.assertEquals(len(path), 1)
            info = self.tracked_infos[path[0]]
            model_info, attrs, group_info = self.infolist.row_for_iter(it)
            self.assertEquals(info.id, model_info.id)
            # update tracked_infos to reflect the change
            self.tracked_infos[path[0]] = model_info
        except Exception:
            # Exceptions in signal handlers won't actually halt the test, we
            # have to do that manually
            self.signal_error = True
            raise

    def on_row_deleted(self, obj, path):
        try:
            # check that the model reflects the change
            self.assertEquals(len(path), 1)
            del self.tracked_infos[path[0]]
            self.check_info_list(self.tracked_infos)
        except Exception:
            # Exceptions in signal handlers won't actually halt the test, we
            # have to do that manually
            self.signal_error = True
            raise

    def on_rows_reordered(self, obj, path, it, new_order):
        try:
            # path and iter should always be empty, since we aren't a tree
            self.assertEquals(it, None)
            self.assertEquals(path, ())
            # check new_order.
            # NOTE: tracked_infos contains our updates, but is in the old
            # order at this point
            correct_new_order = [0 for i in xrange(len(self.tracked_infos))]
            for old_index, info in enumerate(self.tracked_infos):
                new_index = self.find_info_index(info.id)
                correct_new_order[new_index] = old_index
            # FIXME: new_order is not available in python
            # new_order == correct_new_order

            # update tracked_infos to reflect the change
            self.tracked_infos = self.infolist.info_list()
        except Exception:
            # Exceptions in signal handlers won't actually halt the test, we
            # have to do that manually
            self.signal_error = True
            raise

    def check_insert(self, *args, **kwargs):
        self.tracked_infos = self.correct_infos[:]
        InfoListDataTest.check_insert(self, *args, **kwargs)
        if self.signal_error:
            raise AssertionError("assertion failure in signal callback")
        self.check_info_list(self.tracked_infos)

    def check_update(self, *args, **kwargs):
        self.tracked_infos = self.correct_infos[:]
        InfoListDataTest.check_update(self, *args, **kwargs)
        if self.signal_error:
            raise AssertionError("assertion failure in signal callback")
        self.check_info_list(self.tracked_infos)

    def check_remove(self, *args, **kwargs):
        self.tracked_infos = self.correct_infos[:]
        InfoListDataTest.check_remove(self, *args, **kwargs)
        if self.signal_error:
            raise AssertionError("assertion failure in signal callback")
        self.check_info_list(self.tracked_infos)

    def check_update_sort(self, *args, **kwargs):
        self.tracked_infos = self.correct_infos[:]
        InfoListDataTest.check_update_sort(self, *args, **kwargs)
        if self.signal_error:
            raise AssertionError("assertion failure in signal callback")
        self.check_info_list(self.tracked_infos)

@only_on_platforms('osx')
class InfoListCocoaTest(InfoListDataTest):
    # Test the same things as in InfoListTest, but check using Cocoa's classes

    def setUp(self):
        from miro.plat.frontends.widgets import tablemodel

        InfoListDataTest.setUp(self)
        source = tablemodel.MiroInfoListDataSource.alloc()
        self.data_source = source.initWithModel_(self.infolist)

    def build_infolist(self):
        from miro.plat.frontends.widgets import tablemodel
        return tablemodel.InfoListModel(self.sort_key_func, False)

    def check_info_list(self, info_list):
        # Note we just pass in a None for tableviews, the InfoList data source
        # doesn't use it.
        rows = self.data_source.numberOfRowsInTableView_(None)
        data_source_rows = []
        for i in xrange(rows):
            info, attrs, group_info = self.infolist.row_for_iter(i)
            self.assertEquals((info, attrs, group_info),
                    self.data_source.tableView_objectValueForTableColumn_row_(
                        None, 0, i))
            data_source_rows.append(info)
            # check that iter_for_id gives the correct iter.  On OS X, this is
            # just the index of the row
            self.assertEquals(self.infolist.iter_for_id(info.id), i)
        InfoListDataTest.check_info_list(self, data_source_rows)
