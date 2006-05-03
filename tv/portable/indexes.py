import app
import item

def itemsByFeed(x):
    return x.getFeed().getID()

def feedsByURL(x):
    return str(x.getURL())

def downloadsByDLID(x):
    return str(x.dlid)

# Returns the class of the object, aggregating all Item subtypes under Item
def objectsByClass(x):
    if isinstance(x,item.Item):
        return item.Item
    else:
        return x.__class__


tabIDIndex = lambda x: x.id

tabObjIDIndex = lambda x: x.obj.getID()


