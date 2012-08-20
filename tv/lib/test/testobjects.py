"""miro.test.testobjs -- Create test objects.

This module is a collection of functions to make objects to use for testing.
"""

import datetime
import itertools
import random
import os

from miro import app
from miro import database
from miro import devices
from miro import item
from miro import models
from miro import messages
from miro import util
from miro.data.item import fetch_item_infos
from miro.plat.utils import filename_to_unicode, unicode_to_filename
from miro.test import mock

feed_counter = itertools.count()

def test_started(current_test_case):
    """Reset the test object data"""
    global feed_counter, current_test
    feed_counter = itertools.count()
    current_test = current_test_case

def make_item_info(itemobj):
    return fetch_item_infos(app.db.connection, [itemobj.id])[0]

def make_feed():
    url = u'http://feed%d.com/feed.rss' % feed_counter.next()
    return models.Feed(url)

def make_feed_for_file(path):
    """Create a feed with a file:// URL that points to a file """
    url = u'file://%s' % path
    return models.Feed(url)

    return models.Feed(filename_to_unicode(util.make_file_url(path)))

def make_item(feed, title):
    """Make a new item."""
    fp_values = item.FeedParserValues({})
    fp_values.data['entry_title'] = title
    fp_values.data['url'] = u'http://example.com/%s.mkv' % title
    # pick a random recent date for the release date
    seconds_ago = random.randint(0, 60 * 60 * 24 * 7)
    release_date = (datetime.datetime.now() -
                    datetime.timedelta(seconds=seconds_ago))
    fp_values.data['release_date'] = release_date
    return models.Item(fp_values, feed_id=feed.id)

def make_file_item(feed, path=None):
    if path is None:
        path = current_test.make_temp_path()
    ensure_file_exists(path)
    return models.FileItem(path, feed.id)

def make_feed_with_items(item_count):
    feed = make_feed()
    items = []
    for i in xrange(item_count):
        name = u"feed%d-item%d" % (feed.id, i)
        items.append(make_item(feed, name))
    return feed, items

def ensure_file_exists(path):
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write("test-data")
            f.close()

def make_mock_device(no_database=False):
    device = mock.Mock()
    device.mount = current_test.make_temp_dir_path()
    device.id = 123
    device.name = 'Device'
    device.size = 1024000
    device.remaining = 512000
    device.read_only = False
    os.makedirs(os.path.join(device.mount, '.miro'))
    os.makedirs(os.path.join(device.mount, 'cover-art'))
    if not no_database:
        setup_mock_device_database(device)
    return device

def make_device_info(device):
    return messages.DeviceInfo(device.id, device, device.mount,
                               devices.sqlite_database_path(device.mount),
                               device.database,
                               device.db_info,
                               device.metadata_manager,
                               device.size, device.remaining,
                               device.read_only)

def setup_mock_device_database(device):
    device.database = devices.DeviceDatabase()
    sqlite_db = devices.load_sqlite_database(device.mount,
                                             device.size)
    db_info = database.DBInfo(sqlite_db)
    metadata_manager = devices.make_metadata_manager(device.mount,
                                                     db_info,
                                                     device.id)
    device.db_info = db_info
    device.metadata_manager = metadata_manager
    return device

def make_device_items(device, *filenames):
    return [make_device_item(device, filename) for filename in filenames]

def make_device_item(device, filename):
    # ensure that filename is the correct type for our platform
    filename = unicode_to_filename(unicode(filename))
    ensure_file_exists(os.path.join(device.mount, filename))
    return item.DeviceItem(device, filename)
