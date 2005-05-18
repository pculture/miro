from threading import RLock
from os.path import expanduser, exists
from cPickle import dump, load, HIGHEST_PROTOCOL, UnpicklingError
from shutil import copyfile
import traceback

##
# Raised when an attempt is made to remove an object that doesn't exist
class ObjectNotFoundError(StandardError):
    pass

# Raised when an attempt is made to call a function that's only
# allowed to be called from the root database
class NotRootDBError(StandardError):
    pass

# Used as a dummy value so that "None" can be treated as a valid value
class NoValue:
    pass

globalLock = RLock()

##
# Implements a view of the database
#
# A Dynamic Database is a list of objects that can be filtered,
# sorted, and mapped. It can also give notification when an object is
# added, removed, or changed.
class DynamicDatabase:

    ##
    # Create a view of a list of objects.
    # @param objects A list of object/mapped value pairs to create the
    # initial view
    # @param rootDB true iff this is not a subview of another DD. Should never be used outside of this class.
    def __init__(self,objects = [], rootDB = True,mappedValues = NoValue):
        if mappedValues == NoValue:
            mappedValues = objects
        for x in range(0,len(objects)):
            objects[x] = (objects[x],mappedValues[x])
        self.objects = objects;
        self.cursor = -1;
        self.changeCallbacks = []
        self.addCallbacks = []
        self.removeCallbacks = []
        self.subFilters = []
        self.subSorts = []
        self.subMaps = []
        self.cursorStack = []
        self.rootDB = rootDB

    ##
    # Saves the current position of the cursor on the stack
    #
    # Usage:
    #
    # view.saveCursor()
    # try:
    #     ...
    # finally:
    #     view.restoreCursor()
    def saveCursor(self):
        self.cursorStack.append(self.cursor)

    ##
    # Restores the position of the cursor
    def restoreCursor(self):
        self.cursor = self.cursorStack.pop()

    ##
    # Returns the nth item in the View
    def __getitem__(self,n):
        self.beginRead()
	try:
	    if ((n >= 0) and n < len(self.objects)):
		return self.objects[n][1]
	    else:
		return None
	finally:
	    self.endRead()

    def len(self):
        self.beginRead()
        length = len(self.objects)
        self.endRead()
        return length

    ##
    # Call before writing changes to the database
    #
    # Usage:
    #
    # view.beginUpdate()
    # try:
    #     ..updates..
    # finally:
    #     endUpdate()
    #
    def beginUpdate(self):
        globalLock.acquire()

    ##
    # Call this after beginUpdate when you're done making changes to
    # the database
    def endUpdate(self):
        globalLock.release()
        
    ##
    # Call before reading from the database
    # Note: we can get better performance in the future by allowing
    # multiple threads in the read lock
    #
    # Usage:
    #
    # view.beginRead()
    # try:
    #     ..updates..
    # finally:
    #     endRead()
    #
    def beginRead(self):
        globalLock.acquire()
        
    ##
    # Call this after beginRead to end the lock
    # Note: we can get better performance in the future by allowing
    # multiple threads in the read lock
    def endRead(self):
        globalLock.release()

    ##
    # Returns the object that the cursor is currently pointing to or
    # None if it's not pointing to an object
    def cur(self):
        self.beginRead()
        try:
            if (self.cursor >= 0) and (self.cursor < len(self.objects)):
                ret = self.objects[self.cursor][1]
            else:
                ret = None
        finally:
            self.endRead()
        return ret

    ##
    # next() function used by iterator
    def next(self):
        self.beginUpdate()
        try:
            ret = self.getNext()
            if self.cursor >= self.len():
                raise StopIteration
        finally:
            self.endUpdate()
        return ret

    ##
    # returns the previous object in the view
    # null if it is not set
    def getNext(self):
        self.beginUpdate()
        try:
            self.cursor += 1
            if self.cursor >= len(self.objects):
                self.cursor = len(self.objects)
            ret = self.cur()
        finally:
            self.endUpdate()
        return ret

    ##
    # returns the previous object in the view
    # null if it is not set
    def getPrev(self):
        self.beginUpdate()
        try:
            self.cursor -= 1
            if self.cursor < 0:
                self.cursor = -1
            ret = self.cur()
        finally:
            self.endUpdate()
        return ret

    ##
    # sets the current cursor position to the beginning of the list
    def resetCursor(self):
        self.beginUpdate()
        try:
            self.cursor = -1
        finally:
            self.endUpdate()

    ##
    # returns a View of the data filtered through a boolean function
    # @param f boolean function to use as a filter
    def filter(self, f):
        self.beginUpdate()
        try:
            g = lambda x : f(x[1])
            obsmap = lambda x:x[0]
            valsmap = lambda x:x[1]
            both = filter(g,self.objects)
            objs = map(obsmap,both)
            vals = map(valsmap,both)
            new = DynamicDatabase(objs,False,vals)
            new.beginUpdate()
            try:
                if self.cursor<0:
                    new.cursor = self.cursor
                elif self.cursor>=self.len():
                    new.cursor = new.len()+self.cursor-self.len()
                else:
                    new.resetCursor()
                    try:
                        tempobj = new.objects[new.cursor]
                    except IndexError:
                        tempobj = NoValue
                    for x in range(0,len(self.objects)):
                        if x == self.cursor:
                            break
                        if self.objects[x] is tempobj:
                            new.next()
                            try:
                                tempobj = new.objects[new.cursor]
                            except IndexError:
                                tempobj = NoValue
            finally:
                new.endUpdate()
            self.subFilters.append([new, f])
        finally:
            self.endUpdate()
        return new

    ##
    # returns a View of the data mapped according to the given function
    #
    # @param f function to use as a map
    def map(self, f):
        self.beginUpdate()
        try:
            obsmap = lambda x:x[0]
            valsmap = lambda x:f(x[1])
            new = DynamicDatabase(map(obsmap,self.objects),False,map(valsmap,self.objects))
            new.beginUpdate()
            try:
                new.cursor = self.cursor
            finally:
                new.endUpdate()
            self.subMaps.append([new,f])
        finally:
            self.endUpdate()
        return new

    ##
    # returns a View of the data filtered through a sort function
    # @param f comparision function to use for sorting
    def sort(self, f):
        self.beginUpdate()
        try:
            g = lambda x,y:f(x[1],y[1])
            sorter = self.make_sorter(g)
            obsmap = lambda x:x[0]
            valsmap = lambda x:x[1]
            both = sorter(self.objects)
            objs = map(obsmap,both)
            vals = map(valsmap,both)
            new = DynamicDatabase(objs,False,vals)
            new.beginUpdate()
            try:
                if self.cursor<0:
                    new.cursor = self.cursor
                elif self.cursor>=self.len():
                    new.cursor = new.len()+self.cursor-self.len()
                else:
                    cur = self.objects[self.cursor]
                    for x in range(0,len(new.objects)):                
                        if new.objects[x] == cur:
                            new.cursor = x
                            break
            finally:
                new.endUpdate()
            
            self.subSorts.append([new,f])
        finally:
            self.endUpdate()
        return new

    ##
    # registers a function to call when an item in the view changes
    #
    # @param function a function that takes in one parameter: the
    # index of the changed object
    def addChangeCallback(self, function):
        self.beginUpdate()
        try:
            self.changeCallbacks.append(function)
        finally:
            self.endUpdate()

    ##
    # registers a function to call when an item is added to the list
    #
    # @param function a function that takes in one parameter: the
    # index of the new object
    def addAddCallback(self, function):
        self.beginUpdate()
        try:
            self.addCallbacks.append(function)
        finally:
            self.endUpdate()

    ##
    # registers a function to call when an item is removed from the view
    #
    # @param function a function that takes in one parameter: the
    # object to be deleted
    def addRemoveCallback(self, function):
        self.beginUpdate()
        try:
            self.removeCallbacks.append(function)
        finally:
            self.endUpdate()


    ##
    # Adds an item to the object database, filtering changes to subViews
    # @param object the object to add
    def addBeforeCursor(self, object,value=NoValue):
        self.beginUpdate()
        try:
            self.saveCursor()
            self.cursor -= 1
            self.addAfterCursor(object,value)
            self.restoreCursor()
        finally:
            self.endUpdate()

    ##
    # Adds an item to the object database, filtering changes to subViews
    # @param object the object to add
    def addAfterCursor(self, object, value = NoValue):
        self.beginUpdate()
        try:
            if value == NoValue:
                value = object
            point = self.cursor+1
            if point < 0:
                point = 0
            if point > len(self.objects):
                point = len(self.objects)
            if (len(self.objects) == 0):
                self.objects = [(object,value)]
            else:
                self.objects[point:point] = [(object,value)]
            for count in range(0,len(self.cursorStack)):
                if self.cursorStack[count] >= point:
                    self.cursorStack[count] += 1
            for [view, f] in self.subMaps:
                view.beginUpdate()
                try:
                    view.saveCursor()
                    view.cursor = point - 1
                    view.addAfterCursor(object,f(value))
                    view.restoreCursor()
                finally:
                    view.endUpdate()
            for [view, f] in self.subSorts:
                view.beginUpdate()
                try:
                    view.saveCursor()
                    view.resetCursor()
                    added = False
                    for obj in view:
                        if f(obj,value) >= 0:
                            added = True
                            view.addBeforeCursor(object,value)
                            break
                    if not added:
                        view.addBeforeCursor(object,value)
                    view.restoreCursor()
                finally:
                    view.endUpdate()
            for [view, f] in self.subFilters:
                if f(value):
                    view.beginUpdate()
                    try:
                        view.saveCursor()
                        view.resetCursor()
                        viewPos = 0
                        for myObj in self.objects:
                            try:
                                viewObj = view.objects[viewPos]
                            except IndexError:
                                viewObj = (NoValue, NoValue)
                            if myObj[0] is object:
                                view.cursor = viewPos
                                view.addBeforeCursor(object,value)
                                break
                            if viewObj[0] is myObj[0]:
                                viewPos += 1
                        view.restoreCursor()
                    finally:
                        view.endUpdate()
            for callback in self.addCallbacks:
                callback(point)
        finally:
            self.endUpdate()

    ##
    # remove the object the cursor is on
    #
    # Private function. Should only be called by DynmaicDatabase class members
    # @param item optional position of item to remove
    def remove(self, item = None):
         self.beginUpdate()
         try:
             if item == None:
                 item = self.cursor
             if (item < 0) or (item>=len(self.objects)):
                 raise ObjectNotFoundError, "No object at position "+str(item)+" in the database"

             #Save a reference to the item to compare with subViews
             tempobj = self.objects[item][0]
             tempmapped = self.objects[item][1]
             self.objects[item:item+1] = []
             for count in range(0,len(self.cursorStack)):
                if self.cursorStack[count] > item:
                    self.cursorStack[count] -= 1
		if self.cursorStack[count] >= self.len():
		    self.cursorStack[count] -= 1
             if item < self.cursor:
                 self.cursor -= 1
	     if self.cursor >= self.len():
		 self.cursor -= 1

             for callback in self.removeCallbacks:
                 callback(tempmapped,item)
                 
             for [view, f] in self.subMaps:
                 view.remove(item)
             for [view, f] in self.subSorts:
                 view.beginUpdate()
                 try:
                     view.saveCursor()
                     view.resetCursor()
                     for obj in view.objects:
                         view.getNext()
                         if obj[0] is tempobj:
                             view.remove()
                     view.restoreCursor()
                 finally:
                     view.endUpdate()
             for [view, f] in self.subFilters:
                 view.beginUpdate()
                 try:
                     view.saveCursor()
                     view.resetCursor()
                     for obj in view.objects:
                         view.getNext()
                         if obj[0] is tempobj:
                             view.remove()
                     view.restoreCursor()
                 finally:
                     view.endUpdate()
         finally:
             self.endUpdate()

    ##
    # Signals that object on cursor has changed
    #
    # Private function. Should only be called by DynmaicDatabase class members
    # @param item optional position of item to remove in place of cursor
    def change(self, item = None):
        self.beginUpdate()
        try:
            if item == None:
                item = self.cursor
            for callback in self.changeCallbacks:
                callback(item)
            for [view, f] in self.subMaps:
                view.change(item)
            for [view, f] in self.subSorts:
                view.beginUpdate()
                try:
                    view.saveCursor()
                    try:
                        view.resetCursor()
                        for obj in view:
                            if obj is self[item]:
                                view.change()
                    finally:
                        view.restoreCursor()
                finally:
                    view.endUpdate()
            for [view, f] in self.subFilters:
                view.beginUpdate()
                try:
                    view.saveCursor()
                    try:
                        view.resetCursor()
                        for obj in view:
                            if obj is self[item]:
                                view.change()
                    finally:
                        view.restoreCursor()
                finally:
                    view.endUpdate()
        finally:
            self.endUpdate()

    ##
    # This is needed for the class to function as an iterator
    def __iter__(self):
        self.beginUpdate()
        self.cursor = -1
        self.endUpdate()
        return self

    ## 
    # This is called when the criteria for one of the filters changes. It
    # calls the appropriate add callbacks to deal with objects that have
    # appeared and disappeared.
    def recomputeFilters(self):
        self.beginUpdate()
        try:
            for [view, f] in self.subFilters:
                view.beginUpdate()
                try:
                    self.saveCursor()
                    self.resetCursor()
                    view.saveCursor()
                    view.resetCursor()
                    viewPos = 0
                    for myObj in self.objects:
                        try:
                            viewObj = view.objects[viewPos]
                        except IndexError:
                            viewObj = (NoValue, NoValue)
                        if viewObj[0] is myObj[0]:
                            if f(myObj[1]): #The object passes the
                                            #filter and is already in
                                            #the subView
                                viewPos += 1
                            else:
                                view.remove(viewPos) #The object
                                                     #doesn't pass,
                                                     #but is in the
                                                     #subView, so we
                                                     #remove it
                        else:
                            if f(myObj[1]): #The object is not in the
                                            #subview, but should be
                                view.cursor = viewPos
                                view.addBeforeCursor(myObj[0],myObj[1])
                                viewPos += 1
                    self.restoreCursor()
                    view.restoreCursor()
                    view.recomputeFilters()
                finally:
                    view.endUpdate()
            for [view, f] in self.subSorts:
                view.beginUpdate()
                try:
                    g = lambda x,y:f(x[1],y[1])
                    temp = self.make_sorter(g)(self.objects)
                    view.beginUpdate()
                    try:
                        view.saveCursor()
                        view.resetCursor()
                        for obj in temp:
                            view.getNext()
                            try:
                                if not obj[0] is view.objects[view.cursor][0]:
                                    view.addAfterCursor(obj[0],obj[1])
                                    view.remove()
                            except IndexError:
                                view.addAfterCursor(obj[0],obj[1])
                        view.restoreCursor()
                        view.recomputeFilters()
                    finally:
                        view.endUpdate()
                finally:
                    view.endUpdate()
	    for [view, f] in self.subMaps:
		view.recomputeFilters()
        finally:
            self.endUpdate()

    ##
    # This is called to remove all elements matching a particular filter
    def removeMatching(self,f):
        if not self.rootDB:
            raise NotRootDBError, "removeMatching() cannot be called from subviews"
        self.beginUpdate()
        try:
            self.saveCursor()
            self.resetCursor()
            for obj in self:
                if f(obj):
                    obj.remove()
		    self.getPrev()
            self.restoreCursor()
        finally:
            self.endUpdate()        
    ##
    # Returns a function that sorts on cmp
    #
    # Adapted from http://www.python.org/tim_one/000236.html
    #
    # @param cmp Comparison function should return < 0 if a < b
    # 0 if a = b and > 0 if a > b
    def make_sorter(self,cmp):
        class Sorter:
            def __init__( self, cmp ):
                self.Cmp = cmp

            def sort( self, list ):
                # simple quicksort
                if len(list) <= 1: return list
                key = list[0]
                less, same, greater = [], [], []
                for thing in list:
                    outcome = self.Cmp( thing, key )
                    if outcome < 0:
                        which = less
                    elif outcome > 0:
                        which = greater
                    else: which = same
                    which.append( thing )
                return self.sort(less) + same + self.sort(greater)

        # return a sorting function that sorts a list according to comparator
        # function `cmp' # cmp(a,b) 
        return Sorter(cmp).sort 

    ##
    # Saves this database to disk
    #
    # @param filename the file to save to
    #
    # Maybe we want to add more robust error handling in the future?
    # Right now, I'm assuming that if it doesn't work, there's nothing
    # we can do to make it work anyway.
    def save(self,filename = "~/.tvdump"):
        filename = expanduser(filename)
        self.beginRead()
        try:
	    try:
		if exists(filename):
		    copyfile(filename,filename+".bak")
		handle = file(filename,"wb")
		dump(self.objects,handle,HIGHEST_PROTOCOL)
		handle.close()
	    except:
		print "Error saving database:"
		traceback.print_exc()
        finally:
            self.endRead()

    ##
    # Restores this database
    #
    # @param filename the file to save to
    #
    def restore(self,filename = "~/.tvdump"):
        filename = expanduser(filename)
        if exists(filename):
            self.beginUpdate()
            try:
                handle = file(filename,"rb")
                try:
                    temp = load(handle)
                except UnpicklingError:
                    handle.close()
                    return (self.restore(filename+".bak"))
                except EOFError:
                    handle.close()
                    return (self.restore(filename+".bak"))
                handle.close()
                self.objects = temp
		try:
		    DDBObject.lastID = max([DDBObject.lastID,max(map(lambda x:x.getID(),map(lambda x:x[0],self.objects)))])
		except ValueError: #For the weird case where we're not
		    pass	   #restoring anything

 		#for object in self.objects:
		#    print str(object[0].__class__.__name__)+" of id "+str(object[0].getID())
            finally:
                self.endUpdate()
            return True
        else:
            return exists(filename+".bak") and self.restore(filename+".bak")

##
# Global default database
defaultDatabase = DynamicDatabase()

# Dynamic Database object
class DDBObject:
    #The last ID used in this class
    lastID = 0

    #The database associated with this object
    dd = defaultDatabase
    #The id number associated with this object
    id = 0

    ##
    #
    # @param dd optional DynamicDatabase to associate with this object
    #        -- if ommitted the global database is used
    # @param add Iff true, object is added to the database
    def __init__(self, dd = None,add = True):
        if dd != None:
            self.dd = dd
        
        #Set the ID to the next free number
        globalLock.acquire()
        try:
            DDBObject.lastID += 1
            self.id =  DDBObject.lastID
        finally:
            globalLock.release()
        if add:
            self.dd.addAfterCursor(self)

    ##
    # returns unique integer assocaited with this object
    def getID(self):
        return self.id

    #
    #Call this after you've removed all references to the object
    def remove(self):
        self.dd.beginUpdate()
        try:
            x = 0
            for obj in self.dd.objects:
                if obj[0] is self:
                    self.dd.remove(x)
                    break
                x += 1
        finally:
            self.dd.endUpdate()

    ##
    # Call this before you grab data from an object
    #
    # Usage:
    #
    # view.beginRead()
    # try:
    #     ...
    # finally:
    #     endRead()
    #
    def beginRead(self):
	globalLock.acquire()

    ##
    # Used with beginRead()
    def endRead(self):
	globalLock.release()

    ##
    # Call this before you change the object
    #
    # Usage:
    #
    # view.beginChange()
    # try:
    #     ..updates..
    # finally:
    #     endChange()
    #
    def beginChange(self):
        globalLock.acquire()

    ##
    # Call this after you change the object
    def endChange(self):
        self.dd.beginUpdate()
        try:
            self.dd.saveCursor()
            try:
                self.dd.resetCursor()
                for obj in self.dd:
                    if obj is self:
                        self.dd.change()
            finally:
                self.dd.restoreCursor()
        finally:
            self.dd.endUpdate()
        globalLock.release()

