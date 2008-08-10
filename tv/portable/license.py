# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

"""Support for licensing in Miro-consumed feeds."""

from miro.gtcache import gettext as _
from miro import rdfa
from xml.sax import SAXParseException


DC_TITLE = "http://purl.org/dc/elements/1.1/title"
# Use caching to reduce number of get requests we need.
# This is a mapping of {license_uri: license_name_string}
URI_CACHE = {}


class DictSink(object):
    """Simple sink for the RDFa parser; stores triples in a nested dict
    structure.  After parsing self[subject][predicate] contains a list 
    of objects."""

    def __init__(self):

        self.data = {}

    def triple(self, s, p, o):
        self.data.setdefault(s, {}).setdefault(p, []).append(o)

def license_name(license_uri):
    """Attempt to determine the license name from the URI; if the name cannot
    be determined, the URI is returned unchanged."""
    cached_name = URI_CACHE.get(license_uri)
    if cached_name is not None:
        return cached_name

    # retrieve the license document and parse it for RDFa
    try:
        # this throws an AttributeError way down in urllib in some cases
        sink = rdfa.parseURI(license_uri, sink=DictSink())

        # look for explicit assertions about the license URI first, 
        # then fall back to looking for assertions about the document
        license_name = sink.data.get(license_uri,
                             sink.data[u''])[DC_TITLE][0].strip()

        # note this is parser-specific; swapping out rdfa.py
        # may invalidate this extraction 
        return_name = license_name[1:license_name.find('"',1)]

    except (IOError, KeyError, SAXParseException), e:
        return_name = _('license page')

    URI_CACHE[license_uri] = return_name
    return return_name
