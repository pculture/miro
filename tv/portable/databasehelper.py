from itertools import count

import database

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

    def __init__(self, db, idList, sortFunc=None):
        """Construct an TrackedIDList.  

        This object will keep a reference to idList.  When insertID, appendID,
        removeID, or moveID are called idList will be modified to
        reflect the change.
        """
        if sortFunc == None:
            sortFunc = self.sort

        self.trackedIDs = set()
        self.positions = {}
        self.list = idList
        self.db = db
        pos = count()
        for id in idList:
            self.positions[id] = pos.next()
            self.trackedIDs.add(id)
        self.extraFilterFunc = lambda x: True
        self.filter1 = db.filter(self.filter)
        self.filter2 = self.filter1.filter(self.extraFilter)        
        self.view = self.filter2.sort(sortFunc, resort=True)

    def recomputeSort(self):
        self.filter2.recomputeSort(self.view)

    def sort(self, a, b):
        return self.positions[a[1].getID()] < self.positions[b[1].getID()]

    def filter(self, object):
        return object.getID() in self.trackedIDs

    def extraFilter(self, object):
        return self.extraFilterFunc(object)

    def setFilter(self, extraFilterFunc):
        self.extraFilterFunc = extraFilterFunc
        self.filter1.recomputeFilter(self.filter2)

    def _sendSignalChange(self, id):
        if self.db.idExists(id):
            self.db.getObjectByID(id).signalChange(needsSave=False)

    def __contains__(self, id):
        return id in self.trackedIDs

    def getPosition(self, id):
        """Get the position of an id in the list.  If id is not in the list a
        KeyError will be raised."""
        return self.positions[id]

    def appendID(self, id, sendSignalChange=True):
        if id in self:
            raise ValueError("%s is already being tracked" % id)
        self.positions[id] = len(self.list)
        self.trackedIDs.add(id)
        self.list.append(id)
        if sendSignalChange:
            self._sendSignalChange(id)

    def insertID(self, pos, id):
        if id in self:
            raise ValueError("%s is already being tracked" % id)
        for toMove, oldPos in self.positions.items():
            if oldPos >= pos:
                self.positions[toMove] += 1
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

    def moveIDList(self, idList, anchorID):
        """Move a set of IDs to be above anchorID.

        More precicely, we move idList so it is one contiguous block, in
        between anchorID and the first id not in idList.  The ids in idList
        won't change position relative to each other.

        If anchorID is None, idList will be positioned at the bottom.
        """

        if anchorID in idList:
            return
        toMove = [(self.getPosition(id), id) for id in idList]
        toMove.sort()
        for oldPos, id in toMove:
            self.removeID(id)
        for oldPos, id in toMove:
            if anchorID is not None:
                anchorPos = self.getPosition(anchorID)
                self.insertID(anchorPos, id)
            else:
                self.appendID(id)
