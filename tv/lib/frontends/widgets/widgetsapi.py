# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
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

"""miro.frontends.widgets.widgetsapi -- Widgets API for extensions.

This module implements the extension API for doing tasks specific to the
widgets frontend
"""

__all__ = [
    "APIVERSION",
    "ExtensionItemFilter",
    ]

from miro.frontends.widgets import itemfilter

# increase this by 1 every time the API changes
APIVERSION = 0

class ExtensionItemFilter(itemfilter.ItemFilter):
    """Base class for item filters coming from extensions.

    Item filters are used to filter out items from item lists.  They are
    displayed as buttons on top of the list.

    Right now this class has the exact same interface as
    itemfilter.ItemFilter.  ItemFilter may change at any point.  We'll try to
    keep this one the same.
    """
    pass
