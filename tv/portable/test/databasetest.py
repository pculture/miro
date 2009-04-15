from miro.test.framework import MiroTestCase
from miro import database
from miro import item
from miro import feed

class DatabaseTestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.feed = feed.Feed(u"http://feed.org")
        self.i1 = item.Item({'title': u'item1'},
                       feed_id=self.feed.id)
        self.i2 = item.Item({'title': u'item2'},
                       feed_id=self.feed.id)
        self.feed2 = feed.Feed(u"http://feed.com")
        self.i3 = item.Item({'title': u'item3'},
                       feed_id=self.feed2.id)

class ViewTest(DatabaseTestCase):
    def test_iter(self):
        view = item.Item.make_view('feed_id=?', (self.feed.id,))
        self.assertEquals(set(view), set([self.i2, self.i1]))

    def test_count(self):
        view = item.Item.make_view('feed_id=?', (self.feed.id,))
        self.assertEquals(view.count(), 2)

    def test_join(self):
        self.feed.set_title(u'booya')
        view = item.Item.make_view("feed.userTitle='booya'",
                joins={'feed': 'feed.id=item.feed_id'})
        self.assertEquals(set(view), set([self.i2, self.i1]))
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

    def test_track_join(self):
        self.setup_view(item.Item.make_view("feed.userTitle='booya'",
                joins={'feed': 'feed.id=item.feed_id'}))
        self.feed2.set_title(u'booya')
        self.feed2.signal_related_change()
        self.assertEquals(self.add_callbacks, [self.i3])
        self.assertEquals(self.remove_callbacks, [])
        self.assertEquals(self.change_callbacks, [])
        self.feed2.revert_title()
        self.feed2.signal_related_change()
        self.assertEquals(self.add_callbacks, [self.i3])
        self.assertEquals(self.remove_callbacks, [self.i3])
        self.assertEquals(self.change_callbacks, [])

    def test_track_creation_add(self):
        self.setup_view(item.Item.make_view("feed.userTitle='booya'",
                joins={'feed': 'feed.id=item.feed_id'}))
        self.feed2.set_title(u'booya')
        self.feed2.signal_related_change()
        self.assertEquals(self.add_callbacks, [self.i3])

        i4 = item.Item({'title': u'item4'}, feed_id=self.feed.id)
        self.assertEquals(self.add_callbacks, [self.i3, i4])

    def test_track_destruction_remove(self):
        self.setup_view(item.Item.make_view("feed.userTitle='booya'",
                joins={'feed': 'feed.id=item.feed_id'}))
        self.feed2.set_title(u'booya')
        self.feed2.signal_related_change()
        self.assertEquals(self.remove_callbacks, [])
        self.i3.remove()
        self.assertEquals(self.remove_callbacks, [self.i3])

    def test_unlink(self):
        self.tracker.unlink()
        self.feed2.set_title(u"booya")
        self.feed.revert_title()
        self.assertEquals(self.add_callbacks, [])
        self.assertEquals(self.remove_callbacks, [])
        self.assertEquals(self.change_callbacks, [])

    def test_unlink_join(self):
        self.setup_view(item.Item.make_view("feed.userTitle='booya'",
                joins={'feed': 'feed.id=item.feed_id'}))
        self.tracker.unlink()
        self.feed2.set_title(u'booya')
        self.feed2.signal_related_change()
        self.feed.revert_title()
        self.feed.signal_related_change()
        self.assertEquals(self.add_callbacks, [])
        self.assertEquals(self.remove_callbacks, [])
        self.assertEquals(self.change_callbacks, [])

    def test_reset(self):
        database.ViewTracker.reset_trackers()
        self.feed2.set_title(u"booya")
        self.feed.revert_title()
        self.assertEquals(self.add_callbacks, [])
        self.assertEquals(self.remove_callbacks, [])
        self.assertEquals(self.change_callbacks, [])
