import app
import item

def itemsByFeed(x):
    return x.getFeed().getID()

def feedsByURL(x):
    return str(x.getURL())

def downloadsByDLID(x):
    return str(x.dlid)

def downloadsByURL(x):
    return str(x.url)

# Returns the class of the object, aggregating all Item subtypes under Item
def objectsByClass(x):
    if isinstance(x,item.Item):
        return item.Item
    else:
        return x.__class__

def itemsByState(x):
    return x.getState()

def itemsByChannelCategory(x):
    return x.getChannelCategory()

tabIDIndex = lambda x: x.id

tabObjIDIndex = lambda x: x.obj.getID()


