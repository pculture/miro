# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

"""Support for licensing in Miro-consumed feeds."""

from gtcache import gettext as _
import rdfa

DC_TITLE = "http://purl.org/dc/elements/1.1/title"

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

    # retrieve the license document and parse it for RDFa
    sink = rdfa.parseURI(license_uri, sink=DictSink())

    # look for the license title
    try:
        # look for explicit assertions about the license URI first, 
        # then fall back to looking for assertions about the document
        license_name = sink.data.get(license_uri,
                             sink.data[u''])[DC_TITLE][0].strip()

        # note this is parser-specific; swapping out rdfa.py
        # may invalidate this extraction 
        return license_name[1:license_name.find('"',1)]

    except KeyError, e:
        return _('license page')
