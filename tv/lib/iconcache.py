# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
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

import os
import logging
import collections

from miro import httpclient
from miro import eventloop
from miro.database import DDBObject, ObjectNotFoundError
from miro.download_utils import next_free_filename, get_file_url_path
from miro.util import unicodify
from miro.plat.utils import unicode_to_filename
from miro import app
from miro import prefs
from miro import fileutil

RUNNING_MAX = 3

class IconCacheUpdater:
    def __init__(self):
        self.idle = collections.deque()
        self.vital = collections.deque()
        self.running_count = 0
        self.in_shutdown = False
        self.started = False

    def start_updates(self):
        self.started = True
        self.run_next_update()

    def request_update(self, item, is_vital=False):
        if is_vital:
            item.dbItem.confirm_db_thread()
            if (item.filename and fileutil.access(item.filename, os.R_OK)
                   and item.url == item.dbItem.get_thumbnail_url()):
                is_vital = False
        if self.started and self.running_count < RUNNING_MAX:
            eventloop.add_idle(item.request_icon, "Icon Request")
            self.running_count += 1
        else:
            if is_vital:
                self.vital.append(item)
            else:
                self.idle.append(item)

    def update_finished(self):
        if self.in_shutdown:
            self.running_count -= 1
            return

        self.run_next_update()

    def run_next_update(self):
        if len(self.vital) > 0:
            item = self.vital.popleft()
        elif len(self.idle) > 0:
            item = self.idle.popleft()
        else:
            self.running_count -= 1
            return

        eventloop.add_idle(item.request_icon, "Icon Request")

    @eventloop.as_idle
    def clear_vital(self):
        self.vital = collections.deque()

    @eventloop.as_idle
    def shutdown(self):
        self.in_shutdown = True

class IconCache(DDBObject):
    def setup_new(self, dbItem):
        self.etag = None
        self.modified = None
        self.filename = None
        self.url = None

        self.updating = False
        self.needsUpdate = False
        self.dbItem = dbItem
        self.removed = False

        self.request_update(is_vital=dbItem.ICON_CACHE_VITAL)

    @classmethod
    def orphaned_view(cls):
        """Downloaders with no items associated with them."""
        return cls.make_view("id NOT IN (SELECT icon_cache_id from item "
                "UNION select icon_cache_id from channel_guide "
                "UNION select icon_cache_id from feed)")

    @classmethod
    def all_filenames(cls):
        return [r[0] for r in cls.select(["filename"], 'filename IS NOT NULL')]

    def icon_changed(self, needs_save=True):
        self.signal_change(needs_save=needs_save)
        if hasattr(self.dbItem, 'icon_changed'):
            self.dbItem.icon_changed()
        else:
            self.dbItem.signal_change(needs_save=False)

    def remove(self):
        self.removed = True
        if self.filename:
            self.remove_file(self.filename)
        DDBObject.remove(self)

    def reset(self):
        if self.filename:
            self.remove_file(self.filename)
        self.filename = None
        self.url = None
        self.etag = None
        self.modified = None
        self.removed = False
        self.updating = False
        self.needsUpdate = False
        self.icon_changed()

    def remove_file(self, filename):
        try:
            fileutil.remove(filename)
        except OSError:
            pass

    def error_callback(self, url, error=None):
        self.dbItem.confirm_db_thread()

        if self.removed:
            app.icon_cache_updater.update_finished()
            return

        # Don't clear the cache on an error.
        if self.url != url:
            self.url = url
            self.etag = None
            self.modified = None
            self.icon_changed()
        self.updating = False
        if self.needsUpdate:
            self.needsUpdate = False
            self.request_update(True)
        app.icon_cache_updater.update_finished()

    def update_icon_cache(self, url, info):
        self.dbItem.confirm_db_thread()

        if self.removed:
            app.icon_cache_updater.update_finished()
            return

        needs_save = False
        needsChange = False

        if info == None or (info['status'] != 304 and info['status'] != 200):
            self.error_callback(url, "bad response")
            return
        try:
            # Our cache is good.  Hooray!
            if info['status'] == 304:
                return

            needsChange = True

            # We have to update it, and if we can't write to the file, we
            # should pick a new filename.
            if ((self.filename and
                 not fileutil.access(self.filename, os.R_OK | os.W_OK))):
                self.filename = None

            cachedir = app.config.get(prefs.ICON_CACHE_DIRECTORY)
            try:
                fileutil.makedirs(cachedir)
            except OSError:
                pass

            try:
                # Write to a temp file.
                if self.filename:
                    tmp_filename = self.filename + ".part"
                else:
                    tmp_filename = os.path.join(cachedir, info["filename"]) + ".part"
                tmp_filename, output = next_free_filename(tmp_filename)
                output.write(info["body"])
                output.close()
            except IOError:
                self.remove_file(tmp_filename)
                return
            except ValueError:
                logging.warn('update_icon_cache: next_free_filename failed '
                             '#1, candidate = %r', tmp_filename)
                return

            filename = unicode(info["filename"])
            filename = unicode_to_filename(filename, cachedir)
            filename = os.path.join(cachedir, filename)
            needs_save = True
            try:
                filename, fp = next_free_filename(filename)
            except ValueError:
                logging.warn('update_icon_cache: next_free_filename failed '
                             '#2, candidate = %r', filename)
                return

            if self.filename:
                filename = self.filename
                self.filename = None
                self.remove_file(filename)

            # we need to move the file here--so we close the file
            # pointer and then move the file.
            fp.close()
            try:
                self.remove_file(filename)
                fileutil.rename(tmp_filename, filename)
            except (IOError, OSError):
                logging.exception("iconcache: fileutil.move failed")
                filename = None

            self.filename = filename

            etag = unicodify(info.get("etag"))
            modified = unicodify(info.get("modified"))

            if self.etag != etag:
                needs_save = True
                self.etag = etag
            if self.modified != modified:
                needs_save = True
                self.modified = modified
            if self.url != url:
                needs_save = True
                self.url = url
        finally:
            if needsChange:
                self.icon_changed(needs_save=needs_save)
            self.updating = False
            if self.needsUpdate:
                self.needsUpdate = False
                self.request_update(True)
            app.icon_cache_updater.update_finished()

    def request_icon(self):
        if self.removed:
            app.icon_cache_updater.update_finished()
            return

        self.dbItem.confirm_db_thread()
        if self.updating:
            self.needsUpdate = True
            app.icon_cache_updater.update_finished()
            return

        if hasattr(self.dbItem, "get_thumbnail_url"):
            url = self.dbItem.get_thumbnail_url()
        else:
            url = self.url

        # Only verify each icon once per run unless the url changes
        if (url == self.url and self.filename
                and fileutil.access(self.filename, os.R_OK)):
            app.icon_cache_updater.update_finished()
            return

        self.updating = True

        # No need to extract the icon again if we already have it.
        if url is None or url.startswith(u"/") or url.startswith(u"file://"):
            self.error_callback(url)
            return

        # Last try, get the icon from HTTP.
        httpclient.grab_url(url, lambda info: self.update_icon_cache(url, info),
                lambda error: self.error_callback(url, error))

    def request_update(self, is_vital=False):
        if hasattr(self, "updating") and hasattr(self, "dbItem"):
            if self.removed:
                return

            app.icon_cache_updater.request_update(self, is_vital=is_vital)

    def setup_restored(self):
        self.removed = False
        self.updating = False
        self.needsUpdate = False

    def is_valid(self):
        self.dbItem.confirm_db_thread()
        return self.filename and fileutil.exists(self.filename)

    def get_filename(self):
        self.dbItem.confirm_db_thread()
        if self.url and self.url.startswith(u"file://"):
            return get_file_url_path(self.url)
        elif self.url and self.url.startswith(u"/"):
            return unicode_to_filename(self.url)
        else:
            return self.filename

def make_icon_cache(obj):
    if obj.icon_cache_id is not None:
        try:
            icon_cache = IconCache.get_by_id(obj.icon_cache_id)
        except ObjectNotFoundError:
            logging.warn("Icon Cache Not in database for %s (id: %s)",
                         obj, obj.icon_cache_id)
        else:
            icon_cache.dbItem = obj
            if not icon_cache.is_valid():
                icon_cache.request_update()
            return icon_cache
    return IconCache(obj)

class IconCacheOwnerMixin(object):
    """Mixin class for objects that own IconCache instances
    (currently, Feed, Item and ChannelGuide).
    """

    def setup_new_icon_cache(self):
        self._icon_cache = IconCache(self)
        self.icon_cache_id = self._icon_cache.id

    # the icon_cache attribute is fetched lazily
    def _icon_cache_getter(self):
        try:
            return self._icon_cache
        except AttributeError:
            self._icon_cache = make_icon_cache(self)
            if self.icon_cache_id != self._icon_cache.id:
                self.icon_cache_id = self._icon_cache.id
                self.signal_change()
            return self._icon_cache
    icon_cache = property(_icon_cache_getter)

    def remove_icon_cache(self):
        if self.icon_cache_id is not None:
            self.icon_cache.remove()
            self._icon_cache = self.icon_cache_id = None
