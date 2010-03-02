import logging

from miro.test.framework import MiroTestCase
from miro import database
from miro import databaselog
from miro import item
from miro import feed
from miro import schema

class DatabaseTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.feed = feed.Feed(u"http://feed.org")
        self.i1 = item.Item(item.FeedParserValues({'title': u'item1'}),
                            feed_id=self.feed.id)
        self.i2 = item.Item(item.FeedParserValues({'title': u'item2'}),
                            feed_id=self.feed.id)

        self.feed2 = feed.Feed(u"http://feed.com")
        self.i3 = item.Item(item.FeedParserValues({'title': u'item3'}),
                            feed_id=self.feed2.id)

class ViewTest(DatabaseTestCase):
    def test_iter(self):
        view = item.Item.make_view('feed_id=?', (self.feed.id,))
        self.assertSameSet(view, [self.i2, self.i1])

    def test_count(self):
        view = item.Item.make_view('feed_id=?', (self.feed.id,))
        self.assertEquals(view.count(), 2)

    def test_join(self):
        self.feed.set_title(u'booya')
        view = item.Item.make_view("feed.userTitle='booya'",
                joins={'feed': 'feed.id=item.feed_id'})
        self.assertSameSet(view, [self.i2, self.i1])
        self.assertEquals(view.count(), 2)

class ViewTrackerTest(DatabaseTestCase):
    def setUp(self):
        DatabaseTestCase.setUp(self)
        self.add_callbacks = []
        self.remove_callbacks = []
        self.change_callbacks = []
        self.feed.set_title(u"booya")
        self.setup_view(feed.Feed.make_view("userTitle LIKE 'booya%'"))

    def setup_view(self, view):
        if hasattr(self, 'tracker'):
            self.tracker.unlink()
        self.view = view
        self.tracker = self.view.make_tracker()
        self.tracker.connect('added', self.on_add)
        self.tracker.connect('removed', self.on_remove)
        self.tracker.connect('changed', self.on_change)

    def on_add(self, tracker, obj):
        self.add_callbacks.append(obj)

    def on_remove(self, tracker, obj):
        self.remove_callbacks.append(obj)

    def on_change(self, tracker, obj):
        self.change_callbacks.append(obj)

    def test_track(self):
        # test new addition
        self.feed2.set_title(u"booya")
        self.assertEquals(self.add_callbacks, [self.feed2])
        self.assertEquals(self.remove_callbacks, [])
        self.assertEquals(self.change_callbacks, [])
        # test change that doesn't add or remove
        self.feed2.set_title(u"booya2")
        self.assertEquals(self.add_callbacks, [self.feed2])
        self.assertEquals(self.remove_callbacks, [])
        self.assertEquals(self.change_callbacks, [self.feed2])
        # test removing existing objects
        self.feed.revert_title()
        self.assertEquals(self.add_callbacks, [self.feed2])
        self.assertEquals(self.remove_callbacks, [self.feed])
        self.assertEquals(self.change_callbacks, [self.feed2])
        # test change of object not in view
        self.feed.revert_title()
        self.assertEquals(self.add_callbacks, [self.feed2])
        self.assertEquals(self.remove_callbacks, [self.feed])
        self.assertEquals(self.change_callbacks, [self.feed2])
        # test removing newly added objects
        self.feed2.revert_title()
        self.assertEquals(self.add_callbacks, [self.feed2])
        self.assertEquals(self.remove_callbacks, [self.feed, self.feed2])
        self.assertEquals(self.change_callbacks, [self.feed2])

    def test_track_creation_add(self):
        self.setup_view(item.Item.make_view("feed.userTitle='booya'",
                joins={'feed': 'feed.id=item.feed_id'}))

        i4 = item.Item(item.FeedParserValues({'title': u'item4'}), 
                       feed_id=self.feed.id)
        self.assertEquals(self.add_callbacks, [i4])

    def test_track_destruction_remove(self):
        self.setup_view(item.Item.make_view("feed.userTitle='booya'",
                joins={'feed': 'feed.id=item.feed_id'}))
        self.i1.remove()
        self.assertEquals(self.remove_callbacks, [self.i1])

    def test_unlink(self):
        self.tracker.unlink()
        self.feed2.set_title(u"booya")
        self.feed.revert_title()
        self.assertEquals(self.add_callbacks, [])
        self.assertEquals(self.remove_callbacks, [])
        self.assertEquals(self.change_callbacks, [])

    def test_reset(self):
        database.setup_managers()
        self.feed2.set_title(u"booya")
        self.feed.revert_title()
        self.assertEquals(self.add_callbacks, [])
        self.assertEquals(self.remove_callbacks, [])
        self.assertEquals(self.change_callbacks, [])


class TestDDBObject(database.DDBObject):
    def setup_new(self, testcase, remove=False):
        testcase.id_exists_retval = self.id_exists()
        if remove:
            self.remove()

class TestDDBObjectSchema(schema.ObjectSchema):
    klass = TestDDBObject
    table_name = 'test'
    fields = [
        ('id', schema.SchemaInt()),
    ]

class DDBObjectTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        TestDDBObject.track_attribute_changes('foo')
        self.reload_database(schema_version=0,
                object_schemas=[TestDDBObjectSchema])

    def test_id_exists_in_setup_new(self):
        TestDDBObject(self)
        self.assertEquals(self.id_exists_retval, True)

    def test_remove_in_setup_new(self):
        self.assertEquals(TestDDBObject.make_view().count(), 0)
        TestDDBObject(self, remove=True)
        self.assertEquals(TestDDBObject.make_view().count(), 0)

    def test_test_attribute_track(self):
        testobj = TestDDBObject(self)
        self.assertEquals(testobj.changed_attributes, set())
        testobj.foo = 1
        self.assertEquals(testobj.changed_attributes, set(['foo']))
        testobj.bar = 2
        self.assertEquals(testobj.changed_attributes, set(['foo']))

class LogFilter(logging.Filter):
    def __init__(self):
        self.allow = False
        self.records = []

    def filter(self, record):
        if not self.allow:
            raise AssertionError("We shouldn't see any logging")
        else:
            self.records.append(record)
            return False

    def forget_records(self):
        self.records = []

class DatabaseLoggingTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        logger = logging.getLogger()
        self._log_level = logger.getEffectiveLevel()
        self._old_filters = logger.filters

        self.log_filter = LogFilter()
        logger.setLevel(logging.DEBUG)
        for old_filter in logger.filters:
            logger.removeFilter(old_filter)
        logger.addFilter(self.log_filter)

    def tearDown(self):
        MiroTestCase.tearDown(self)
        logger = logging.getLogger()
        logger.setLevel(self._log_level)
        for old_filter in logger.filters:
            logger.removeFilter(old_filter)
        for filter in self._old_filters:
            logger.addFilter(filter)

    def check_records(self, count):
        records = self.log_filter.records
        self.assertEqual(len(records), count)
        for rec in records:
            self.assertEqual(rec.levelno, logging.getLevelName('DBLOG'))

    def test_warning_logged(self):
        self.log_filter.allow = True
        databaselog.info("message %s", 1)
        databaselog.debug("message %s", 2)
        self.check_records(2)

    def test_backlog(self):
        self.log_filter.allow = True
        databaselog.info("message %s", 1)
        databaselog.debug("message %s", 2)
        self.log_filter.forget_records()
        databaselog.print_old_log_entries()
        # should have 3 log entries, 1 header, 1 footer, and the 1 for the
        # info message
        self.check_records(3)
