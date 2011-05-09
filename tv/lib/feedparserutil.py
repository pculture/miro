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

"""feedparserutil.py -- Utility functions to handle feedparser.
"""

from datetime import datetime
from time import struct_time
from types import NoneType
import threading

from miro.clock import clock

from miro import eventloop
from miro import feedparser
from miro.datastructures import Fifo

# values from feedparser dicts that don't have to convert in
# normalize_feedparser_dict()
SIMPLE_FEEDPARSER_VALUES = (int, long, str, unicode, bool, NoneType,
                            datetime, struct_time)

def normalize_feedparser_dict(fp_dict):
    """Convert FeedParserDicts to simple dictionaries."""

    retval = {}
    for key, value in fp_dict.items():
        if isinstance(value, feedparser.FeedParserDict):
            value = normalize_feedparser_dict(value)
        elif isinstance(value, dict):
            value = dict(
                (_convert_if_feedparser_dict(k),
                 _convert_if_feedparser_dict(v))
                for (k, v) in value.items())
        elif isinstance(value, list):
            value = [_convert_if_feedparser_dict(o) for o in value]
        elif isinstance(value, tuple):
            value = tuple(_convert_if_feedparser_dict(o) for o in value)
        else:
            if not value.__class__ in SIMPLE_FEEDPARSER_VALUES:
                raise ValueError("Can't normalize: %r (%s)" %
                                 (value, value.__class__))
        retval[key] = value
    return retval

def _convert_if_feedparser_dict(obj):
    """If it's a FeedParserDict, returns the converted dict.  Otherwise
    returns the argument.
    """
    if isinstance(obj, feedparser.FeedParserDict):
        return normalize_feedparser_dict(obj)
    return obj

from miro import app
from miro import prefs
USER_AGENT = (feedparser.USER_AGENT + " %s/%s (%s)" %
              (app.config.get(prefs.SHORT_APP_NAME),
               app.config.get(prefs.APP_VERSION),
               app.config.get(prefs.PROJECT_URL)))

def parse(url_file_stream_or_string):
    return feedparser.parse(url_file_stream_or_string, USER_AGENT)

class _QueueParseProcessor(threading.Thread):
    """Object that handles the queue_parse() call."""

    WAIT_TIME = 0.2 # time to wait between parse() calls

    def __init__(self):
        self.queue = Fifo()
        self.last_end_time = 0
        self.current_call_info = None

    def add_to_queue(self, url_file_stream_or_string, callback, errback):
        call_info = (url_file_stream_or_string, callback, errback)
        self.queue.enqueue(call_info)
        self._schedule_next()

    def _schedule_next(self):
        if len(self.queue) == 0:
            return # nothing to schedule
        if self.current_call_info is not None:
            return # we'll run again once that call is finished

        self.current_call_info = self.queue.dequeue()
        wait_left = (self.last_end_time + self.WAIT_TIME) - clock()
        if wait_left <= 0:
            self._run_current()
        else:
            eventloop.add_timeout(wait_left, self._run_current,
                    "feedparser queue timeout")

    def _run_current(self):
        url_file_stream_or_string = self.current_call_info[0]
        eventloop.call_in_thread(self._callback, self._errback,
                feedparser.parse, "Feedparser callback",
                url_file_stream_or_string)

    def _finish_call(self, callback, *args, **kwargs):
        self.last_end_time = clock()
        self.current_call_info = None
        callback(*args, **kwargs)
        self._schedule_next()

    def _callback(self, *args, **kwargs):
        callback = self.current_call_info[1]
        self._finish_call(callback, *args, **kwargs)

    def _errback(self, *args, **kwargs):
        callback = self.current_call_info[2]
        self._finish_call(errback, *args, **kwargs)

_queue_parse_proccessor = _QueueParseProcessor()

def queue_parse(url_file_stream_or_string, callback, errback):
    """Call parse in a separet thread.

    This method tries to ensure that feedparser doesn't hog the whole CPU
    using a few methods:
      - Only feedparser.parse() call is running at a given time.
      - After a parse() call, we wait for a bit to give other things time to
        access the CPU.
    """
    _queue_parse_proccessor.add_to_queue(url_file_stream_or_string, callback,
            errback)

def sanitizeHTML(htmlSource, encoding):
    return feedparser.sanitizeHTML(htmlSource, encoding)

def convert_datetime(elem):
    """Takes part of a FeedParserDict and converts any
    time.struct_time instances to appropriate timezone-agnostic
    strings.
    """
    if isinstance(elem, struct_time):
        return "DATETIME"
    if isinstance(elem, tuple):
        return tuple([convert_datetime(e) for e in elem])
    if isinstance(elem, list):
        return [convert_datetime(e) for e in elem]
    if isinstance(elem, dict):
        for key, val in elem.items():
            elem[key] = convert_datetime(val)
        return elem
    return elem

FeedParserDict = feedparser.FeedParserDict
