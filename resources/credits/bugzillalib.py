# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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

import httplib
import urllib
import StringIO
import csv
from xml.etree.ElementTree import ElementTree

def bz_query_bug_id(host, bug_id):
    """Queries a bugzilla instance for a specific bug and returns an
    ElementTree.

    Example:

    >>> etree = bz_query_bug_id('bugzilla.pculture.org', 14761)
    """
    conn = httplib.HTTPConnection(host)

    args = [("id", bug_id), ("ctype", "xml")]
    querystring = urllib.urlencode(args)

    path = "/show_bug.cgi?%s" % querystring
    conn.request("GET", path)
    r1 = conn.getresponse()
    conn.close()

    data = StringIO.StringIO(r1.read())

    tree = ElementTree()
    tree.parse(data)

    return tree

def bz_query(host, args):
    """Queries a bugzilla instance and returns a list of bugs.

    Takes a hostname and a list of 2-tuple args (key, value).

    Example:
    
    >>> rows = bz_query('bugzilla.pculture.org', [
    ...     ('query_format', 'advanced'),
    ...     ('product', 'Miro'),
    ...     ('chfieldfrom', '7d'),
    ...     ('chfieldto', 'Now'),
    ...     ('chfield' '[Bug creation]'),
    ...     ('order', 'Bug Number'),
    ...     ('ctype', 'csv')
    ...     ])
    ...
    """
    conn = httplib.HTTPConnection(host)

    querystring = urllib.urlencode(args)

    path = "/buglist.cgi?%s" % querystring
    conn.request("GET", path)
    r1 = conn.getresponse()
    conn.close()

    data = StringIO.StringIO(r1.read())

    reader = csv.reader(data)
    firstrow = reader.next()
    rows = []
    for row in reader:
        rows.append(dict(zip(firstrow, row)))
    return rows
