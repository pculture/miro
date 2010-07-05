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

"""feedparserutil.py -- Utility functions to handle feedparser.
"""

from datetime import datetime
from time import struct_time
from types import NoneType

from miro import feedparser

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
