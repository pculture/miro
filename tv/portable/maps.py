import tabs
import feed
import folder
import playlist
import guide

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
    
