# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""ddblinks.py - Setup links between DDBObjects

When DDBObjects are stored on disk, they don't have references to each other.
Instead they have SQL foreign keys.  This module sets up the references based
on the foreign keys.  It also handles invalid values for foreign keys.
"""

import logging

from miro import app
from miro import feed
from miro import guide
from miro import iconcache
from miro import item

def setup_links(all_objects):
    om = ObjectMap(all_objects)
    to_remove = []
    for i, obj in enumerate(all_objects):
        if isinstance(obj, feed.Feed):
            try:
                obj.actualFeed = om.feed_impls[obj.feed_impl_id]
            except KeyError:
                obj.setup_default_feed_impl()
            _setup_icon_cache(obj, om)
        elif isinstance(obj, feed.FeedImpl):
            try:
                obj.ufeed = om.feeds[obj.ufeed_id]
            except KeyError:
                logging.warn("No feed for FeedImpl: %s.  Discarding", obj)
                to_remove.append(i)
        elif isinstance(obj, item.Item):
            _setup_icon_cache(obj, om)
        elif isinstance(obj, guide.ChannelGuide):
            _setup_icon_cache(obj, om)
    for i in reversed(to_remove):
        if app.db.liveStorage is not None:
            app.db.liveStorage.remove(all_objects[i])
        del all_objects[i]

def _setup_icon_cache(obj, om):
    if obj.icon_cache_id is not None:
        try:
            obj.icon_cache = om.icon_caches[obj.icon_cache_id]
        except KeyError:
            logging.warn("Icon Cache Not in database for %s (id: %s)" %
                    (obj, obj.icon_cache_id))
        else:
            obj.icon_cache.dbItem = obj
            obj.icon_cache.request_update()
            return

    obj.icon_cache = iconcache.IconCache(obj)

class ObjectMap:
    """Maps object ids to the associated objects.

    Normally we would use code like views.feeds.getObjectByID(id), however,
    setup_links() runs before the views are setup, so we need another way of
    getting objects from their ids.
    """

    def __init__(self, all_objects):
        self.feeds = {}
        self.feed_impls = {}
        self.icon_caches = {}
        self.items = {}
        self.guides = {}

        for obj in all_objects:
            if isinstance(obj, feed.Feed):
                self.feeds[obj.id] = obj
            elif isinstance(obj, feed.FeedImpl):
                self.feed_impls[obj.id] = obj
            elif isinstance(obj, iconcache.IconCache):
                self.icon_caches[obj.id] = obj
            elif isinstance(obj, item.Item):
                self.items[obj.id] = obj
            elif isinstance(obj, guide.ChannelGuide):
                self.guides[obj.id] = obj
