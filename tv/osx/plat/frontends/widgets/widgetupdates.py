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

"""widgetupdates.py -- Handle updates to our widgets
"""

from PyObjCTools import AppHelper

from miro import app

class SizeRequestManager(object):
    """Helper object to manage size requests

    If something changes in a widget that makes us want to request a new size,
    we avoid calculating it immediately.  The reason is that the
    new-size-request will cascade all the way up the widget tree, and then
    result in our widget being placed.  We don't necessary want all of this
    action to happen while we are in the middle of handling an event
    (especially with TableView).  It's also inefficient to calculate things
    immediately, since we might do something else to invalidate the size
    request in the current event.

    SizeRequestManager stores which widgets need to have their size
    recalculated, then calls do_invalidate_size_request() using callAfter
    """

    def __init__(self):
        self.widgets_to_request = set()
        app.widgetapp.connect("event-processed", self._on_event_processed)

    def add_widget(self, widget):
        if len(self.widgets_to_request) == 0:
            AppHelper.callAfter(self._run_requests)
        self.widgets_to_request.add(widget)

    def _run_requests(self):
        this_run = self.widgets_to_request
        self.widgets_to_request = set()
        for widget in this_run:
            widget.do_invalidate_size_request()

    def _on_event_processed(self, app):
        # once we finishing handling an event, process our size requests ASAP
        # to avoid any potential weirdness.  Note: that we also schedule a
        # call using callAfter(), often that will do nothing, but it's
        # possible size requests get scheduled outside of an event
        while self.widgets_to_request:
            self._run_requests()
