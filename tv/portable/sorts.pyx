# Since we have a sort named "item" we name the item module "itemmod"
import item as itemmod

def item(x,y):
    if x.parent_id == y.parent_id:
        out = cmp(y.releaseDateObj, x.releaseDateObj)
        if out != 0: return out
        # If we're going to sort file items and non-file items
        # differently, then one must precede the other or it won't be
        # a valid sort.
        if x.__class__ is itemmod.FileItem:
            if y.__class__ is itemmod.FileItem:
                return cmp(x.getTitle(), y.getTitle())
            else:
                return 1
        else:
            if y.__class__ is not itemmod.FileItem:
                out = cmp (y.linkNumber, x.linkNumber)
                if out != 0: return out
                return cmp(y.id, x.id)
            else:
                return -1
    else:
        if x.parent_id == y.id:
            # y is x's parent
            return 1
        elif y.parent_id == x.id:
            # x is y's parent
            return -1
        else:
            # x and y are not children of the same item, so sort by the parent (which might be the self)
            return item(x.getParent(), y.getParent())

def itemsUnwatchedFirst(x,y):
    uwx = x.getState() == 'newly-downloaded'
    uwy = y.getState() == 'newly-downloaded'
    if uwx != uwy:
        if uwx:
            return -1
        else:
            return 1
    else:
        return item(x,y)

# The sort function used to order tabs in the tab list: just use the
# sort keys provided when mapToTab created the Tabs. These can be
# lists, which are tested left-to-right in the way you'd
# expect. Generally, the way this is used is that static tabs are
# assigned a numeric priority, and get a single-element list with that
# number as their sort key; feeds get a list with '100' in the first
# position, and a value that determines the order of the feeds in the
# second position. This way all of the feeds are together, and the
# static tabs can be positioned around them.
def tabs(x, y):
    if x.sortKey < y.sortKey:
        return -1
    elif x.sortKey > y.sortKey:
        return 1
    return 0
