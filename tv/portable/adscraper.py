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

import re

def purify(data):
    """Purify a feed item data (usually its description) from ads.
    Returns the data untouched if no ad were found.
    """
    return _process(data, 'purify', data)

def scrape(data):
    """Scrape ads from a feed item data (usually its description). Returns
    an empty string if no ad were found.
    """
    return _process(data, 'scrape', '')

def _process(data, fkey, default):
    if data is None:
        return ''
    processed = None
    for funcs in FUNCS:
        process = funcs[fkey]
        processed = process(data)
        if processed is not None:
            break
    if processed is None:
        processed = default
    return processed

FEEDBURNER_AD_PATTERN = re.compile("""
    &lt;p&gt;                                                               # <p>
    &lt;a\shref="http://feeds\.feedburner\.com/~a/[^"]*"&gt;                # <a href="...">
    &lt;img\ssrc="http://feeds\.feedburner\.com/~a/[^"]*"\sborder="0"&gt;   # <img src="..." border="0">
    &lt;/img&gt;                                                            # </img>
    &lt;/a&gt;                                                              # </a>
    &lt;/p&gt;                                                              # </p>
    """, re.VERBOSE)
    
def _try_purifying_feedburner(data):
    if FEEDBURNER_AD_PATTERN.search(data):
        return FEEDBURNER_AD_PATTERN.sub('', data)
    return None

def _try_scraping_feedburner(data):
    match = FEEDBURNER_AD_PATTERN.search(data)
    if match is not None:
        return match.group(0)
    return None

FUNCS = [
    {'purify': _try_purifying_feedburner,
     'scrape': _try_scraping_feedburner}
]
