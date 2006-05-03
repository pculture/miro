import tabs
import feed

# Given an object for which mappableToTab returns true, return a Tab
def mapToTab(obj):
    if isinstance(obj, tabs.StaticTab):
        return tabs.Tab(obj.tabTemplateBase, obj.contentsTemplate, [obj.order], obj)
    elif isinstance(obj, feed.Feed):
        sortKey = obj.getTitle().lower()
        return tabs.Tab('feedtab', 'channel', [100, sortKey], obj)
    elif isinstance(obj, folder.Folder):
        sortKey = obj.getTitle().lower()
        return tabs.Tab('foldertab','folder',[500,sortKey],obj)
    else:
        raise StandardError
    
