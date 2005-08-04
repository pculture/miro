# Pyrex version of the DTV object database
#
# This will be integrated into distutils and setup.py real soon. In
# the meantime, you'll have to compile it by hand
#
# To compile on OS X without distutils:
# /Library/Frameworks/Python.framework/Versions/2.4/bin/pyrexc database.pyx
# gcc -c -fPIC -I/Library/Frameworks/Python.framework/Versions/2.4/Headers/ database.c
# gcc -bundle -framework Python database.o -o database.so
#
# In addition to rewriting most of this code in C, I've made some
# algorithmic changes. We now keep a dictionary of the locations of
# objects in the database to avoid looping through the database. 
#
# This adds an additional restriction to the database: you cannot
# store the same item twice.

#
# At the moment, we don't guarantee that filters preserve order, so
# you should always sort your views last
#

from threading import RLock
from os.path import expanduser, exists
from cPickle import dump, load, HIGHEST_PROTOCOL, UnpicklingError
from shutil import copyfile
from copy import copy
import traceback

import config

# Import Python C functions
cdef extern from "Python.h":
    cdef int PyList_GET_SIZE(object list)
    cdef int PyList_GET_ITEM(object list, int i)
    cdef void PyList_SET_ITEM(object PyList, int idx, object obj)
    cdef int PyList_SetSlice(object list, int low, int high, object itemlist)

    cdef void* PyTuple_GET_ITEM(object list, int i)

    cdef void* PyDict_GetItem(object dict, object key)
    cdef int PyDict_SetItem(object dict, object key, object val)
    cdef int PyDict_Contains(object dict, object key)
    cdef int PyDict_Next(object dict, int *pos, void* key, void* value)

    cdef object PyObject_CallObject(object callable, object args)
    cdef void Py_INCREF(object x)

# A faster equivalent to PyList[idx] = obj
cdef int setListItem(object PyList, int idx, object obj) except -1:
    Py_INCREF(obj)
    PyList_SET_ITEM(PyList, idx, obj)

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
# added, removed, or changed. Most of the actual implementation is in
# CDynamicDaabase
class DynamicDatabase(CDynamicDatabase):
    ##
    # This is needed for the class to function as an iterator
    def __iter__(self):
        self.beginUpdate()
        self.cursor = -1
        self.endUpdate()
        return self    

# A c-based dynamic database class
cdef class CDynamicDatabase:
    cdef int    cursor
    cdef int    rootDB
    cdef object objects
    cdef object changeCallbacks
    cdef object addCallbacks
    cdef object removeCallbacks
    cdef object subFilters
    cdef object subSorts
    cdef object subMaps
    cdef object cursorStack
    cdef object objectLocs

    ##
    # Create a view of a list of objects.
    # @param objects A list of object/mapped value pairs to create the
    # initial view
    # @param rootDB true iff this is not a subview of another DD. Should never be used outside of this class.
    def __new__(self,object objects = [], int rootDB = True):
        self.rootDB = rootDB

    def __init__(self,object objects = [], int rootDB = True):
        cdef int count
        cdef object temp

        self.cursor = -1
        self.objects = objects
        self.changeCallbacks = []
        self.addCallbacks = []
        self.removeCallbacks = []
        self.subFilters = []
        self.subSorts = []
        self.subMaps = []
        self.cursorStack = []
        self.objectLocs = {}
        count = 0
        for count from 0 <= count < PyList_GET_SIZE(objects):
            temp = <object>PyList_GET_ITEM(objects,count)
            temp = <object>PyTuple_GET_ITEM(temp,0)
            PyDict_SetItem(self.objectLocs,temp,count)
        #self.checkObjLocs()

    # Checks to make the sure object location dictionary is accurate
    #
    # Uncomment the calls to this when you change the location
    # dictionary code
    def checkObjLocs(self):
        if len(self.objectLocs) != len(self.objects):
            print "ERROR -- %d objects and %d locations" % (len(self.objects), len(self.objectLocs))
            raise Exception
        for (key, val) in self.objectLocs.items():
            if self.objects[val][0] != key:
                print "Error-- %s in wrong location" % key
                raise Exception
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
    def __getitem__(self,int n):
        cdef object obj
        self.beginRead()
        try:
            if ((n >= 0) and n < PyList_GET_SIZE(self.objects)):
                obj = <object>PyList_GET_ITEM(self.objects,n)
                obj = <object>PyTuple_GET_ITEM(obj,1)
                return obj
            else:
                return None
        finally:
            self.endRead()

    # Python method to grab C attributes
    def __getattr__(self,n):
        if n == "cursor":
            return self.cursor
        elif n == "objects":
            return self.objects
        elif n == "objectLocs":
            return self.objectLocs

    # Python method to grab C attributes
    def __setattr__(self,n,val):
        if n == "cursor":
            self.cursor = val

    # Returns the number of items in the database
    def len(self):
        cdef int length
        self.beginRead()
        length = PyList_GET_SIZE(self.objects)
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
        #cdef object ret
        self.beginRead()
        try:
            if (self.cursor >= 0) and (self.cursor < PyList_GET_SIZE(self.objects)):
                #ret = self.objects[self.cursor][1]
                ret = <object>PyList_GET_ITEM(self.objects,self.cursor)
                ret = <object>PyTuple_GET_ITEM(ret,1)
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
            if self.cursor >= PyList_GET_SIZE(self.objects):
                raise StopIteration
        finally:
            self.endUpdate()
        return ret

    ##
    # returns the previous object in the view
    # null if it is not set
    def getNext(self):
        cdef int length
        self.beginUpdate()
        try:
            length = PyList_GET_SIZE(self.objects)
            self.cursor = self.cursor + 1
            if self.cursor >= length:
                self.cursor = length
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
            self.cursor = self.cursor - 1
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
            temp = []
            for obj in self.objects:
                if f(obj[1]):
                    temp.append(obj)
            new = DynamicDatabase(temp,False)
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
                    for x from 0 <= x < len(self.objects):
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
        #assert(not self.rootDB) # Dude! Don't map the entire DB! Are you crazy?

        self.beginUpdate()
        try:
            temp = []
            for obj in self.objects:
                temp.append((obj[0],f(obj[1])))
            new = DynamicDatabase(temp,False)
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
        #assert(not self.rootDB) # Dude! Don't sort the entire DB! Are you crazy?

        self.beginUpdate()
        try:
            temp = copy(self.objects)
            temp.sort(f,key=self.getVal)
            new = DynamicDatabase(temp,False)
            new.beginUpdate()
            try:
                if self.cursor<0:
                    new.cursor = self.cursor
                elif self.cursor>=self.len():
                    new.cursor = new.len()+self.cursor-self.len()
                else:
                    cur = self.objects[self.cursor]
                    for x from 0 <= x < len(new.objects):
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
    def addBeforeCursor(self, newobject,value=NoValue):
        self.beginUpdate()
        try:
            self.saveCursor()
            self.cursor = self.cursor - 1
            self.addAfterCursor(newobject,value)
            self.restoreCursor()
        finally:
            self.endUpdate()

    ##
    # Adds an item to the object database, filtering changes to subViews
    # @param object the object to add
    def addAfterCursor(self, object newobject, object value = NoValue):
        cdef int point
        cdef int temp
        cdef int viewPos
        cdef int viewSize
        cdef int count
        cdef int count2
        cdef object view
        cdef object f
        cdef object myObj
        cdef object myObjObj
        cdef object viewObj
        cdef object tempObj

        self.beginUpdate()
        try:
            if value == NoValue:
                value = newobject

            #Make sure the point we're adding at is valid
            point = self.cursor+1
            if point < 0:
                point = 0
            if point > PyList_GET_SIZE(self.objects):
                point = PyList_GET_SIZE(self.objects)

            #Update the location dictionary
            for count from point <= count < PyList_GET_SIZE(self.objects):
                myObj = <object>PyList_GET_ITEM(self.objects,count)
                myObjObj = <object>PyTuple_GET_ITEM(myObj,0)
                tempObj = <object>PyDict_GetItem(self.objectLocs,myObjObj)
                tempObj = tempObj+1
                PyDict_SetItem(self.objectLocs,myObjObj,tempObj)
            PyDict_SetItem(self.objectLocs,newobject,point)

            #Add it
            if (PyList_GET_SIZE(self.objects) == 0):
                self.objects = [(newobject,value)]
            else:
                PyList_SetSlice(self.objects,point,point,[(newobject,value)])
                

            for count from 0 <= count < PyList_GET_SIZE(self.cursorStack):
                temp = <object>PyList_GET_ITEM(self.cursorStack,count)
                if temp >= point:
                    setListItem(self.cursorStack,count,temp+1)
            for [view, f] in self.subMaps:
                view.beginUpdate()
                try:
                    view.saveCursor()
                    view.cursor = point - 1
                    view.addAfterCursor(newobject,f(value))
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
                            view.addBeforeCursor(newobject,value)
                            break
                    if not added:
                        view.addBeforeCursor(newobject,value)
                    view.restoreCursor()
                finally:
                    view.endUpdate()
            for count from 0 <= count < PyList_GET_SIZE(self.subFilters):
                tempObj = <object>PyList_GET_ITEM(self.subFilters,count)
                view = <object>PyList_GET_ITEM(tempObj,0)
                viewSize = PyList_GET_SIZE(view.objects)
                f = <object>PyList_GET_ITEM(tempObj,1)

                if <object>PyObject_CallObject(f,(value,)):
                    view.beginUpdate()
                    try:
                        view.saveCursor()
                        view.resetCursor()
                        viewPos = 0

                        count2 = point - 1
                        while count2 >= 0:
                            myObj = <object>PyList_GET_ITEM(self.objects,count2)
                            myObjObj = <object>PyTuple_GET_ITEM(myObj,0)
                            if PyDict_Contains(view.objectLocs,myObjObj):

                                view.cursor = <object>PyDict_GetItem(view.objectLocs,myObjObj)
                                view.addAfterCursor(newobject,value)
                                break
                            count2 = count2 - 1
                        if count2 < 0:
                            view.cursor = -1
                            view.addAfterCursor(newobject,value)
                        view.restoreCursor()
                    finally:
                        view.endUpdate()
            for callback in self.addCallbacks:
                callback(point)
        finally:
            self.endUpdate()
        #self.checkObjLocs()

    #
    # Removes the object from the database
    def removeObj(self,object obj):
        self.beginUpdate()
        try:
            if PyDict_Contains(self.objectLocs,obj):
                self.remove(<object>PyDict_GetItem(self.objectLocs,obj))
        finally:
            self.endUpdate()

    #
    # Removes the object from the database
    def changeObj(self,object obj):
        self.beginUpdate()
        try:
            if PyDict_Contains(self.objectLocs,obj):
                self.change(<object>PyDict_GetItem(self.objectLocs,obj))
        finally:
            self.endUpdate()

    ##
    # remove the object the cursor is on
    #
    # Private function. Should only be called by DynmaicDatabase class members
    # @param item optional position of item to remove
    def remove(self, int item = -1):
        cdef object temp
        cdef object tempobj
        cdef object tempmapped
        cdef object myObj
        cdef object myObjObj
        cdef object callback
        cdef object view
        cdef int cursorItem
        cdef int size
        cdef int count
        cdef int count2

        self.beginUpdate()
        try:
             size = PyList_GET_SIZE(self.objects)
             if item == -1:
                 item = self.cursor
             if (item < 0) or (item>=size):
                 raise ObjectNotFoundError, "No object at position "+str(item)+" in the database"

             #Save a reference to the item to compare with subViews
             temp = <object>PyList_GET_ITEM(self.objects,item)
             tempobj = <object>PyTuple_GET_ITEM(temp,0)
             tempmapped = <object>PyTuple_GET_ITEM(temp,1)
             
            #Update the location dictionary
             for (key,val) in self.objectLocs.items():
                 if val > item:
                     PyDict_SetItem(self.objectLocs,key,val-1)
             del self.objectLocs[tempobj]

             #Remove it
             PyList_SetSlice(self.objects, item, item+1, [])


             size = size - 1

             #Update the cursor
             for count from 0 <= count < PyList_GET_SIZE(self.cursorStack):
                 cursorItem = <object>PyList_GET_ITEM(self.cursorStack,count)
                 if cursorItem > item:
                    self.cursorStack[count] = self.cursorStack[count] - 1
                 if cursorItem >= size:
                    self.cursorStack[count] =  self.cursorStack[count] - 1
             if item < self.cursor:
                 self.cursor = self.cursor - 1
             if self.cursor >= size:
                 self.cursor = self.cursor - 1
         
             #Perform callbacks
             for count from 0 <= count < PyList_GET_SIZE(self.removeCallbacks):
                 callback = <object>PyList_GET_ITEM(self.removeCallbacks,count)
                 <object>PyObject_CallObject(callback,(tempmapped,item))
                 
             for count from 0 <= count < PyList_GET_SIZE(self.subMaps):
                 temp = <object>PyList_GET_ITEM(self.subMaps,count)
                 view = <object>PyList_GET_ITEM(temp,0)
                 view.remove(item)

             for count from 0 <= count < PyList_GET_SIZE(self.subSorts):
                 temp = <object>PyList_GET_ITEM(self.subSorts,count)
                 view = <object>PyList_GET_ITEM(temp,0)
                 view.removeObj(tempobj)

             for count from 0 <= count < PyList_GET_SIZE(self.subFilters):
                 temp = <object>PyList_GET_ITEM(self.subFilters,count)
                 view = <object>PyList_GET_ITEM(temp,0)
                 view.removeObj(tempobj)
        finally:
            self.endUpdate()
        #self.checkObjLocs()

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
                        view.changeObj(self.objects[item][0])
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
                        if f(self.objects[item][1]):
                            if view.objectLocs.has_key(self.objects[item][0]):
                                view.changeObj(self.objects[item][0])
                            else:
                                view.addBeforeCursor(self.objects[item][0],self.objects[item][1])
                        else:
                            if view.objectLocs.has_key(self.objects[item][0]):
                                view.removeObj(self.objects[item][0])
                    finally:
                        view.restoreCursor()
                finally:
                    view.endUpdate()
        finally:
            self.endUpdate()

    # Recomputes a single filter in the database
    def recomputeFilter(self,filter):
        # FIXME: This is copy-and-paste from recomputeFilters
        cdef int count
        cdef int count2
        cdef int viewPos
        cdef int viewSize
        cdef object view
        cdef object f
        cdef object obj
        cdef object viewObj
        cdef object myObj
        cdef object myObjObj
        cdef object myObjVal

        self.beginUpdate()
        try:
            # Go through each one of the filter subviews
            for count from 0 <= count < PyList_GET_SIZE(self.subFilters):

                obj = <object>PyList_GET_ITEM(self.subFilters,count)

                view = <object>PyList_GET_ITEM(obj,0)
                if view is filter:
                    viewSize = PyList_GET_SIZE(view.objects)
                    
                    f = <object>PyList_GET_ITEM(obj,1)

                    view.beginUpdate()
                    try:
                        self.saveCursor()
                        self.resetCursor()
                        view.saveCursor()
                        view.resetCursor()
                        viewPos = 0
                        #Go through all the objects and recompute the filters
                        for count2 from 0 <= count2 < PyList_GET_SIZE(self.objects):
                            # Get the next item from the list as both the
                            # original object and mapped value
                            myObj = <object>PyList_GET_ITEM(self.objects,count2)
                            myObjObj = <object>PyTuple_GET_ITEM(myObj,0)
                            myObjVal = <object>PyTuple_GET_ITEM(myObj,1)

                            if PyDict_Contains(view.objectLocs,myObjObj):
                                if not <object>PyObject_CallObject(f,(myObjVal,)):
                                    view.removeObj(myObjObj)
                            else:
                                if <object>PyObject_CallObject(f,(myObjVal,)):
                                    view.addBeforeCursor(myObjObj,myObjVal)

                        self.restoreCursor()
                        view.restoreCursor()
                        view.recomputeFilters()
                    finally:
                        view.endUpdate()
        finally:
            self.endUpdate()

    #Recompute a single subSort
    def recomputeSort(self,sort):
        # FIXME: This is copy-and-paste from recomputeFilters
        cdef int count
        cdef int count2
        cdef int viewSize
        cdef int madeSwap
        cdef object view
        cdef object f
        cdef object obj
        cdef object viewObj
        cdef object myObj
        cdef object myObjObj
        cdef object myObjVal
        cdef object myObj2
        cdef object myObj2Obj
        cdef object myObj2Val

        self.beginUpdate()
        try:

            for count from 0 <= count < PyList_GET_SIZE(self.subSorts):
                obj = <object>PyList_GET_ITEM(self.subSorts,count)

                view = <object>PyList_GET_ITEM(obj,0)
                if view is sort:
                    viewSize = PyList_GET_SIZE(view.objects)

                    f = <object>PyList_GET_ITEM(obj,1)

                    view.beginUpdate()
                    try:
                            view.saveCursor()

                            # Bubble sort -- used based on the assumption
                            # that most of the time nothing has changed
                            madeSwap = True
                            while madeSwap:
                                madeSwap = False
                                for count2 from 0 <= count2 < PyList_GET_SIZE(view.objects)-1:
                                    myObj = <object>PyList_GET_ITEM(view.objects,count2)
                                    myObjVal = <object>PyTuple_GET_ITEM(myObj,1)

                                    myObj2 = <object>PyList_GET_ITEM(view.objects,count2+1)
                                    myObj2Val = <object>PyTuple_GET_ITEM(myObj2,1)

                                    if <object>PyObject_CallObject(f,(myObjVal,myObj2Val)) > 0:
                                        #FIXME: add an optimized swap
                                        #function, rather than adding and
                                        #removing
                                        madeSwap = True
                                        myObjObj = <object>PyTuple_GET_ITEM(myObj,0)
                                        view.cursor = count2+1
                                        view.remove(count2)
                                        view.addAfterCursor(myObjObj,myObjVal)
                            view.restoreCursor()
                            view.recomputeFilters()
                    finally:
                        view.endUpdate()
        finally:
            self.endUpdate()

    ##
    # This is called when the criteria for one of the filters changes. It
    # calls the appropriate add callbacks to deal with objects that have
    # appeared and disappeared.
    def recomputeFilters(self):
        cdef int count
        cdef int count2
        cdef int viewPos
        cdef int viewSize
        cdef int madeSwap
        cdef object view
        cdef object f
        cdef object obj
        cdef object viewObj
        cdef object myObj
        cdef object myObjObj
        cdef object myObjVal
        cdef object myObj2
        cdef object myObj2Obj
        cdef object myObj2Val
        cdef object temp

        self.beginUpdate()
        try:
            # Go through each one of the filter subviews
            for count from 0 <= count < PyList_GET_SIZE(self.subFilters):

                obj = <object>PyList_GET_ITEM(self.subFilters,count)

                view = <object>PyList_GET_ITEM(obj,0)
                viewSize = PyList_GET_SIZE(view.objects)

                f = <object>PyList_GET_ITEM(obj,1)

                view.beginUpdate()
                try:
                    self.saveCursor()
                    self.resetCursor()
                    view.saveCursor()
                    view.resetCursor()
                    viewPos = 0
                    #Go through all the objects and recompute the filters
                    for count2 from 0 <= count2 < PyList_GET_SIZE(self.objects):
                        # Get the next item from the list as both the
                        # original object and mapped value
                        myObj = <object>PyList_GET_ITEM(self.objects,count2)
                        myObjObj = <object>PyTuple_GET_ITEM(myObj,0)
                        myObjVal = <object>PyTuple_GET_ITEM(myObj,1)

                        if PyDict_Contains(view.objectLocs,myObjObj):
                            if not <object>PyObject_CallObject(f,(myObjVal,)):
                                view.removeObj(myObjObj)
                        else:
                            if <object>PyObject_CallObject(f,(myObjVal,)):
                                view.addBeforeCursor(myObjObj,myObjVal)

                    self.restoreCursor()
                    view.restoreCursor()
                    view.recomputeFilters()
                finally:
                    view.endUpdate()

            #Recompute subSorts
            #
            # FIXME: Can I comment out this whole region and just say that
            # recomputeFilters doesn't touch sorts?
            #
            # FIXME: Is there a sort algorithm that works better in
            # the worst case scenario, but still works ideally in the
            # common case of nothing changed?
            for count from 0 <= count < PyList_GET_SIZE(self.subSorts):
                obj = <object>PyList_GET_ITEM(self.subSorts,count)

                view = <object>PyList_GET_ITEM(obj,0)
                viewSize = PyList_GET_SIZE(view.objects)

                f = <object>PyList_GET_ITEM(obj,1)

                view.beginUpdate()
                try:
                        view.saveCursor()

                        # Bubble sort -- used based on the assumption
                        # that most of the time nothing has changed
                        madeSwap = True
                        while madeSwap:
                            madeSwap = False
                            for count2 from 0 <= count2 < PyList_GET_SIZE(view.objects)-1:
                                myObj = <object>PyList_GET_ITEM(view.objects,count2)
                                myObjVal = <object>PyTuple_GET_ITEM(myObj,1)

                                myObj2 = <object>PyList_GET_ITEM(view.objects,count2+1)
                                myObj2Val = <object>PyTuple_GET_ITEM(myObj2,1)

                                if <object>PyObject_CallObject(f,(myObjVal,myObj2Val)) > 0:
                                    #FIXME: add an optimized swap
                                    #function, rather than adding and
                                    #removing
                                    madeSwap = True
                                    myObjObj = <object>PyTuple_GET_ITEM(myObj,0)
                                    view.cursor = count2+1
                                    view.remove(count2)
                                    view.addAfterCursor(myObjObj,myObjVal)
                        view.restoreCursor()
                        view.recomputeFilters()
                finally:
                    view.endUpdate()

            #Recompute submaps
            for count from 0 <= count < PyList_GET_SIZE(self.subMaps):
                view = <object>PyList_GET_ITEM(self.subMaps,count)
                view = <object>PyList_GET_ITEM(view,0)
                view.recomputeFilters()
        finally:
            self.endUpdate()
        #self.checkObjLocs()

    # Used to sort objects
    def getVal(object self,object obj):
        return <object>PyTuple_GET_ITEM(obj,1)

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
    # Saves this database to disk
    #
    # @param filename the file to save to
    #
    # Maybe we want to add more robust error handling in the future?
    # Right now, I'm assuming that if it doesn't work, there's nothing
    # we can do to make it work anyway.
    def save(self,filename=None):
        if filename == None:
            filename = config.get(config.DB_PATHNAME)
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
    def restore(self,filename=None):
        cdef int count
        cdef object temp

        if filename == None:
            filename = config.get(config.DB_PATHNAME)
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
                    DDBObject.lastID = self.getLastID()
                except ValueError: #For the weird case where we're not
                    pass           #restoring anything

                #Initialize the object location dictionary
                self.objectLocs = {}
                count = 0
                for count from 0 <= count < PyList_GET_SIZE(self.objects):
                    temp = <object>PyList_GET_ITEM(self.objects,count)
                    temp = <object>PyTuple_GET_ITEM(temp,0)
                    PyDict_SetItem(self.objectLocs,temp,count)
                    
                #for object in self.objects:
                #    print str(object[0].__class__.__name__)+" of id "+str(object[0].getID())
            finally:
                self.endUpdate()
            #self.checkObjLocs()
            return True
        else:
            return exists(filename+".bak") and self.restore(filename+".bak")

    def getLastID(self):
        cdef int last
        cdef int temp
        cdef int count
        cdef object obj
        cdef object objobj

        self.beginUpdate()
        try:
            last = DDBObject.lastID
            for count from 0 <= count < PyList_GET_SIZE(self.objects):
                obj = <object>PyList_GET_ITEM(self.objects,count)
                objobj = <object>PyTuple_GET_ITEM(obj,0)
                temp = objobj.getID()
                if temp > last:
                    last = temp
        finally:
            self.endUpdate()
        return last

    ##
    # Removes a filter that's currently not being used from the database
    # This should be called when a filter is no longer in use
    def removeView(self,oldView):
        cdef int count
        cdef object view

        self.beginUpdate()
        try:
            for count from 0 <= count < PyList_GET_SIZE(self.subFilters):
                view = <object>PyList_GET_ITEM(self.subFilters,count)
                view = <object>PyList_GET_ITEM(view, 0)
                if view is oldView:
                    PyList_SetSlice(self.subFilters, count, count+1, [])
                    return
            for count from 0 <= count < PyList_GET_SIZE(self.subSorts):
                view = <object>PyList_GET_ITEM(self.subSorts,count)
                view = <object>PyList_GET_ITEM(view, 0)
                if view is oldView:
                    PyList_SetSlice(self.subSorts, count, count+1, [])
                    return
            for count from 0 <= count < PyList_GET_SIZE(self.subMaps):
                view = <object>PyList_GET_ITEM(self.subMaps,count)
                view = <object>PyList_GET_ITEM(view, 0)
                if view is oldView:
                    PyList_SetSlice(self.subMaps, count, count+1, [])
                    return
        finally:
            self.endUpdate()

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
            DDBObject.lastID = DDBObject.lastID + 1
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
            self.dd.removeObj(self)
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
                self.dd.changeObj(self)
            finally:
                self.dd.restoreCursor()
        finally:
            self.dd.endUpdate()
        globalLock.release()

