# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""feedupdate.py -- Handles updating feeds.

Our basic strategy is to limit the number of feeds that are
simultaniously updating at any given time.  Right now the limit is set
to 3.
"""

from miro import eventloop
from miro import datastructures

MAX_UPDATES = 3

class FeedUpdateQueue(object):
    def __init__(self):
        self.update_queue = datastructures.Fifo()
        self.timeouts = {}
        self.callback_handles = {}
        self.currently_updating = set()

    def schedule_update(self, delay, feed, update_callback):
        name = "Feed update (%s)" % feed.get_title()
        self.timeouts[feed.id] = eventloop.add_timeout(delay, self.do_update, 
                name, args=(feed, update_callback))

    def cancel_update(self, feed):
        try:
            timeout = self.timeouts.pop(feed.id)
        except KeyError:
            pass
        else:
            timeout.cancel()

    def do_update(self, feed, update_callback):
        del self.timeouts[feed.id]
        self.update_queue.enqueue((feed, update_callback))
        self.run_update_queue()

    def update_finished(self, feed):
        for callback_handle in self.callback_handles.pop(feed.id):
            feed.disconnect(callback_handle)
        self.currently_updating.remove(feed)
        self.run_update_queue()

    def run_update_queue(self):
        while (len(self.update_queue) > 0 and 
               len(self.currently_updating) < MAX_UPDATES):
            feed, update_callback = self.update_queue.dequeue()
            if feed in self.currently_updating:
                continue
            handle = feed.connect('update-finished', self.update_finished)
            handle2 = feed.connect('removed', self.update_finished)
            self.callback_handles[feed.id] = (handle, handle2)
            self.currently_updating.add(feed)
            update_callback()

global_update_queue = FeedUpdateQueue()

def cancel_update(feed):
    """Cancel any pending updates for feed."""
    global_update_queue.cancel_update(feed)

def schedule_update(delay, feed, update_callback):
    """Schedules a feed to be updated sometime around delay seconds in
    the future.
    """
    global_update_queue.schedule_update(delay, feed, update_callback)
