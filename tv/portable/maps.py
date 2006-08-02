import tabs
import feed
import folder
import playlist
import guide

# Given an object for which mappableToTab returns true, return a Tab
def mapToTab(obj):
    if isinstance(obj, guide.ChannelGuide):
        # Guides come first and default guide comes before the others.  The rest are currently sorted by URL.
        return tabs.Tab('guidetab', 'go-to-guide', [1, not obj.getDefault(), obj.getURL()], obj)
    elif isinstance(obj, tabs.StaticTab):
        return tabs.Tab(obj.tabTemplateBase, obj.contentsTemplate, [obj.order], obj)
    elif isinstance(obj, feed.Feed):
        sortKey = obj.getTitle().lower()
        return tabs.Tab('feedtab', 'channel', [100, sortKey], obj)
    elif isinstance(obj, folder.Folder):
        sortKey = obj.getTitle().lower()
        return tabs.Tab('foldertab','folder',[500,sortKey],obj)
    elif isinstance(obj, playlist.SavedPlaylist):
        sortKey = obj.getTitle().lower()
        return tabs.Tab('playlisttab','playlist',[900,sortKey],obj)
    else:
        raise StandardError
    
