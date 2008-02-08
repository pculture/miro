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

from miro import tabs
from miro import feed
from miro import folder
from miro import playlist
from miro import guide

# Given an object for which mappableToTab returns true, return a Tab
def mapToTab(obj):
    if isinstance(obj, guide.ChannelGuide):
        # Guides come first and default guide comes before the others.  The rest are currently sorted by URL.
        return tabs.Tab('guidetab', 'guide-loading', 'default', obj)
    elif isinstance(obj, tabs.StaticTab):
        return tabs.Tab(obj.tabTemplateBase, obj.contentsTemplate, obj.templateState, obj)
    elif isinstance(obj, feed.Feed):
        return tabs.Tab('feedtab', 'channel',  'default', obj)
    elif isinstance(obj, folder.ChannelFolder):
        return tabs.Tab('channelfoldertab', 'channel-folder', 'default', obj)
    elif isinstance(obj, folder.PlaylistFolder):
        return tabs.Tab('playlistfoldertab','playlist-folder', 'default', obj)
    elif isinstance(obj, playlist.SavedPlaylist):
        return tabs.Tab('playlisttab','playlist', 'default', obj)
    else:
        raise StandardError
    
