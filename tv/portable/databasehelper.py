# PyRex has no lambda, so we need this separated
#
# It takes in a Python style sort function that returns -1 for x<y, 0
# for equal, and 1 for x>y and turns it into a STL style sort function
# that returns true for x<y and false otherwise.
#
# It also changes the function to compare the second value in the
# tuple instead of comparing x and y direction, so that we can use it
# in our database
def pysort2dbsort(func):
    return lambda x, y:func(x[1],y[1]) == -1


def makeSimpleGetSet(attributeName, changeNeedsSave=True):
    """Creates a simple DDBObject getter and setter for an attribute.

    This exists because for many DDBOBject attributes we have methods like the
    following:

    def getFoo(self):
        self.confirmDBThread()
        return self.foo
    def setFoo(self, newFoo):
        self.confirmDBThread()
        self.foo = newFoo
        self.signalChange()
    """

    def getter(self):
        self.confirmDBThread()
        return getattr(self, attributeName)
    def setter(self, newValue):
        self.confirmDBThread()
        setattr(self, attributeName, newValue)
        self.signalChange(needsSave=changeNeedsSave)
    return getter, setter

class TrackedIDList(object):
    """Creates a view that tracks a list of DDBObject IDs.

    The view will have the corresponding DDBObject for each ID in the list and
    will be in the same order.

    Attributes:

    view -- Database view that tracks the list of ids
    """

    def __init__(self, db, idList):
        """Construct an IDListView.  

        This object will keep a reference to idList.  When insertID, appendID,
        removeID, or moveID are called idList will be modified to
        reflect the change.
        """

        self.trackedIDs = set()
        self.positions = {}
        self.list = idList
        self.db = db
        for id in idList:
            self.positions[id] = len(self.list)
            self.trackedIDs.add(id)
        self.view = db.filter(self.filter).sort(self.sort, resort=True)

    def sort(self, a, b):
        return cmp(self.positions[a.getID()], self.positions[b.getID()])

    def filter(self, object):
        return object.getID() in self.trackedIDs

    def _sendSignalChange(self, id):
        self.db.getObjectByID(id).signalChange(needsSave=False)

    def __contains__(self, id):
        return id in self.trackedIDs

    def appendID(self, id):
        if id in self:
            raise ValueError("%s is already being tracked" % id)
        self.positions[id] = len(self.list)
        self.trackedIDs.add(id)
        self.list.append(id)
        self._sendSignalChange(id)

    def insertID(self, pos, id):
        if id in self:
            raise ValueError("%s is already being tracked" % id)
        for id, oldPos in self.positions.items():
            if oldPos >= pos:
                self.positions[id] += 1
        self.positions[id] = pos
        self.list.insert(pos, id)
        self.trackedIDs.add(id)
        self._sendSignalChange(id)

    def removeID(self, id):
        removedPos = self.positions.pop(id)
        for toMove, oldPos in self.positions.items():
            if oldPos > removedPos:
                self.positions[toMove] -= 1
        del self.list[removedPos]
        self.trackedIDs.remove(id)
        self._sendSignalChange(id)

    def moveID(self, id, pos):
        """Move an id from it's current position to a new position, shifting
        the rest of the list to accomidate it.
        """

        currentPos = self.positions[id]
        if currentPos > pos:
            minChange = pos
            maxChange = currentPos-1
            delta = 1
        else:
            minChange = currentPos+1
            maxChange = pos
            delta = -1
        for toMove, oldPos in self.positions.items():
            if minChange <= oldPos <= maxChange:
                self.positions[toMove] = oldPos + delta
        self.positions[id]  = pos
        del self.list[currentPos]
        self.list.insert(pos, id)
        self._sendSignalChange(id)
