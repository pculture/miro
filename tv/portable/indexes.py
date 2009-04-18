# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

def itemsByFeed(x):
    # This specifically sorts subitems by their parent's feed.
    return x.getFeed().getID()

def itemsByChannelFolder(x):
    return x.getFeed().get_folder()

def feedsByURL(x):
    return x.getOriginalURL()

def downloadsByDLID(x):
    return str(x.dlid)

def downloadsByURL(x):
    return x.origURL.encode('ascii', 'replace')

# Returns the class of the object, aggregating all Item subtypes under Item
def objectsByClass(x):
    from miro import item

    if isinstance(x, item.Item):
        return item.Item
    else:
        return x.__class__

def itemsByState(x):
    return x.get_state()

def itemsByChannelCategory(x):
    return x.get_channel_category()

def downloadsByCategory(x):
    """Splits downloading items into 3 categories:
        normal -- not pending or external
        pending  -- pending manual downloads
        external -- external torrents
    """
    if x.getFeed().url == 'dtv:manualFeed':
        return 'external'
    elif x.is_pending_manual_download():
        return 'pending'
    else:
        return 'normal'

def tabType(tab):
    return tab.type

def tabOrderType(tabOrder):
    return tabOrder.type

def byFolder(obj):
    return obj.get_folder()

def foldersByTitle(obj):
    return obj.title

def byLicense(obj):
    return obj.get_license()
