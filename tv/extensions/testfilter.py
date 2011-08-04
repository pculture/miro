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

from miro import api
from miro.frontends.widgets import widgetsapi

class StartsWithVowelItemFilter(widgetsapi.ExtensionItemFilter):
    """Sample item filter for items that start with vowels."""

    key = u'starts-with-vowel'
    # FIXME: it would be nice to use gettext for user_label, but we don't
    # really have support for that in extensions.
    user_label = 'Vowel'

    def filter(self, item_info):
        # return True if the first char of name is a vowel
        return (len(item_info.name) > 0 and
                item_info.name[0].lower() in ('a', 'e', 'i', 'o', 'u'))

def get_item_list_filters(type_, id_):
    # add our filter to all item lists
    return [StartsWithVowelItemFilter()]

def load():
    # only load if we are running the widgets frontend
    # FIXME: get_frontend() doesn't seem to be working, skip check for now
    #if api.get_frontend() != 'widgets':
    #    raise api.FrontendNotSupported('Widgets frontend only')
    pass

def unload():
    pass

