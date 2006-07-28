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


def makeSimpleGetSet(attributeName):
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
        self.signalChange()
    return getter, setter
