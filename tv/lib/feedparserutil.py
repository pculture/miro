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
from miro import filetypes
from miro import flashscraper
from miro import util
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

def parse(url_file_stream_or_string):
    """Parse a feed.

    This method runs the feed data through feedparser.parse, then does some
    other things like unicodify it and fix issues with certain feed providers.
    """
    parsed = feedparser.parse(url_file_stream_or_string)
    parsed = util.unicodify(parsed)
    _yahoo_hack(parsed['entries'])
    return parsed

def _yahoo_hack(feedparser_entries):
    """Hack yahoo search to provide enclosures"""
    for entry in feedparser_entries:
        if 'enclosures' not in entry:
            try:
                url = entry['link']
            except KeyError:
                continue
            mimetype = filetypes.guess_mime_type(url)
            if mimetype is not None:
                entry['enclosures'] = [{'url': util.to_uni(url),
                                        'type': util.to_uni(mimetype)}]
            elif flashscraper.is_maybe_flashscrapable(url):
                entry['enclosures'] = [{'url': util.to_uni(url),
                                        'type': util.to_uni("video/flv")}]

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
