# -*- mode: python -*-
# Pyrex version of the DTV object database
#
# 09/26/2005 Checked in change that speeds up inserts, but changes
#            filters so that they no longer keep the order of the
#            parent view. So, filter before you sort.

from os.path import expanduser, exists
from cPickle import dump, dumps, load, HIGHEST_PROTOCOL, UnpicklingError
from shutil import copyfile
from copy import copy
import traceback
from fasttypes import LinkedList, SortedList
from databasehelper import pysort2dbsort
import sys
import types
import threading

import config

##
# Raised when an attempt is made to restore a database newer than the
# one we support
class DatabaseVersionError(StandardError):
    pass

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

# begin* and end* no longer actually lock the database.  Instead
# confirmDBThread prints a warning if it's run from any thread that
# isn't the main thread.  This can be removed from releases for speed
# purposes.

event_thread = None
def set_thread ():
    global event_thread
    event_thread = threading.currentThread()
    
def confirmDBThread():
    global event_thread
    if event_thread is not None and event_thread != threading.currentThread():
        print "database function called from thread %s" % (threading.currentThread(),)
        traceback.print_stack()

def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

def findUnpicklableParts(obj, seen = {}, depth=0):
    thisId = id(obj)
    out = ""

    if thisId in seen:
        return (("  "*depth) + seen[thisId] + " (already checked): " + \
                str(obj) + "\n")
    else:
        if type(obj) == types.InstanceType and \
            '__getstate__' in dir(obj):
            out = out + "[%s ->]\n" % obj
            obj = obj.__getstate__()

        try:
            dumps(obj,HIGHEST_PROTOCOL)
            seen[thisId] = "OK"
            out = out + (("  "*depth) + "OK: " + str(obj) + "\n")
            return out
        except:
            seen[thisId] = "BAD"
            out = out + (("  "*depth) + "BAD: " + str(obj) + "\n")
            if type(obj) == types.DictType:
                for key in obj:
                    out = out + findUnpicklableParts(key, seen, depth+1)
                    out = out + findUnpicklableParts(obj[key], seen, depth+1)
            elif type(obj) == types.InstanceType:
                out = out + ("  "*(depth+1)) + \
                    "WARNING: object missing __getstate__"
                for key in obj.__dict__:
                    out = out + (("  "*(depth+1)) + "--- FOR KEY "+ str(key) + "\n")
                    out = out + findUnpicklableParts(key, seen, depth+1)
                    out = out + findUnpicklableParts(getattr(obj, key), seen, depth+1)
            elif ((type(obj) == types.ListType) or
                  (type(obj) == types.TupleType)):
                for val in obj:
                    out = out + findUnpicklableParts(val, seen, depth+1)
            return out


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
    def __init__(self, objects = [], rootDB = True, sortFunc = None, filterFunc = None, mapFunc = None, cursorID = None, parent = None):
        self.rootDB = rootDB
        self.cursor = None
        self.parent = parent
        self.changeCallbacks = []
        self.addCallbacks = []
        self.removeCallbacks = []
        self.subFilters = []
        self.subSorts = []
        self.subMaps = []
        self.cursorStack = []
        self.objectLocs = {}
        self.indexes = {}
        self.liveStorage = None

        # Normally, any access to fasttypes should be surrounded by a
        # lock. However, inside of an __init__, we can be sure that no
        # other objects can see this object
        if sortFunc is not None:
            self.objects = SortedList(pysort2dbsort(sortFunc))
        else:
            self.objects = LinkedList()
        for temp in objects:
            if filterFunc is None or filterFunc(temp[1]):
                if mapFunc is not None:
                    temp = (temp[0], mapFunc(temp[1]))
                it = self.objects.append(temp)
                id = temp[0].id
                if id == cursorID:
                    self.cursor = it.copy()
                self.objectLocs[id] = it
        #self.checkObjLocs()

    # Checks to make the sure object location dictionary is accurate
    #
    # Uncomment the calls to this when you change the location
    # dictionary code
#     def checkObjLocs(self):
#         self.confirmDBThread()
#         if len(self.objectLocs) != len(self.objects):
#             raise Exception, "ERROR -- %d objects and %d locations" % (len(self.objects), len(self.objectLocs))
#         for (key, val) in self.objectLocs.items():
#             if self.objects[val][0].id != key:
#                 #raise Exception, "Error-- %s in wrong location %s" % (key, val)
#                 print "Error-- %s in wrong location %s" % (key, val)

#         if (self.cursor is not None) and (self.cursor != self.objects.lastIter()):
#             self.objects[self.cursor][0].id

#         for cursor in self.cursorStack:
#             if (cursor is not None) and (cursor != self.objects.lastIter()):
#                 self.objects[cursor][0].id

#     def checkMappedView(self, view):
#         self.confirmDBThread()
#         if len(self.objects) != len(view.objects):
#             raise Exception, "ERROR -- %d objects in mapped and %d in this" % (len(self.objects), len(self.objectLocs))
#         temp = []
#         temp2 = []
#         for (obj, val) in self.objects:
#             temp.append(obj)
#         for (obj, val) in view.objects:
#             temp2.append(obj)
#         for count in range(0,len(temp)):
#             if temp[count] is not temp2[count]:
#                 raise Exception, "%s mapped incorrectly to %s (%d)" % (temp[count],temp2[count],count)

#     def checkFilteredView(self, view, f):
#         self.confirmDBThread()
#         temp = []
#         temp2 = []
#         for (obj, val) in self.objects:
#             if f(val):
#                 temp.append(obj)
#         for (obj, val) in view.objects:
#             temp2.append(obj)
#         if len(temp) != len(temp2):
#             raise Exception, "view (%d) and filtered view (%d) differ in length" % (len(temp),len(temp2))
#         for count in range(0,len(temp)):
#             if temp[count] is not temp2[count]:
#                 raise Exception, "%s filtered incorrectly to %s (%d)" % (temp[count],temp2[count],count)

    ##
    # This is needed for the class to function as an iterator
    def __iter__(self):
        self.confirmDBThread()
        self.cursor = None
        return self    

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
         if self.cursor is not None:
             self.cursorStack.append(self.cursor.copy())
         else:
             self.cursorStack.append(None)


    ##
    # Restores the position of the cursor
    def restoreCursor(self):
        self.cursor = self.cursorStack.pop()

    ##
    # Returns the nth item in the View
    def __getitem__(self,n):
        #print "DTV: Database Warning: numeric subscripts are deprecated"
        self.confirmDBThread()
        try:
            return self.objects[n][1]
        except IndexError:
            return None

    # Returns the number of items in the database
    def __len__(self):
        return self.len()
    def len(self):
        self.confirmDBThread()
        length = len(self.objects)
        return length
        
    ##
    # Call before accessing the database
    #
    # Usage:
    #
    # view.confirmDBThread()
    # ..access database..
    def confirmDBThread(self):
        confirmDBThread()

    ##
    # Returns the object that the cursor is currently pointing to or
    # None if it's not pointing to an object
    def cur(self):
        self.confirmDBThread()
        try:
            return self.objects[self.cursor][1]
        except:
            self.cursor = None
            return None

    ##
    # next() function used by iterator
    def next(self):
        self.confirmDBThread()
        try:
            if self.cursor is None:
                self.cursor = self.objects.firstIter().copy()
            else:
                self.cursor.forward();
            return self.objects[self.cursor][1]
        except:
            raise StopIteration

    ##
    # returns the next object in the view
    # None if it is not set
    def getNext(self):
        self.confirmDBThread()
        if self.cursor is None:
            self.cursor = self.objects.firstIter().copy()
        else:
            self.cursor.forward();
        ret = self.cur()
        return ret

    ##
    # returns the previous object in the view
    # None if it is not set
    def getPrev(self):
        self.confirmDBThread()
        ret = None
        if self.cursor is not None:
            self.cursor.back();
            ret = self.cur()
        return ret

    ##
    # sets the current cursor position to the beginning of the list
    def resetCursor(self):
        self.confirmDBThread()
        self.cursor = None

    ##
    # returns a View of the data filtered through a boolean function
    # @param f boolean function to use as a filter
    def filter(self, f):
        self.confirmDBThread()
        try:
            curID = self.objects[self.cursor][0].id
        except:
            curID = None
        new = DynamicDatabase(self.objects,False,cursorID = curID, filterFunc = f, parent = self)
        self.subFilters.append([new, f])
        return new

    ##
    # returns a View of the data mapped according to the given function
    #
    # @param f function to use as a map
    def map(self, f):
        #assert(not self.rootDB) # Dude! Don't map the entire DB! Are you crazy?

        self.confirmDBThread()
        try:
            curID = self.objects[self.cursor][0].id
        except:
            curID = None
        new = DynamicDatabase(self.objects,False, cursorID = curID, mapFunc = f, parent = self)
        self.subMaps.append([new,f])
        return new

    ##
    # returns a View of the data filtered through a sort function
    # @param f comparision function to use for sorting
    def sort(self, f):
        #assert(not self.rootDB) # Dude! Don't sort the entire DB! Are you crazy?
        self.confirmDBThread()
        try:
            curID = self.objects[self.cursor][0].id
        except:
            curID = None
        new = DynamicDatabase(self.objects,False, sortFunc = f, cursorID = curID, parent = self)
        self.subSorts.append([new,f])
        return new

    ##
    # registers a function to call when an item in the view changes
    #
    # @param function a function that takes in one parameter: the
    # index of the changed object
    def addChangeCallback(self, function):
        self.confirmDBThread()
        self.changeCallbacks.append(function)

    ##
    # registers a function to call when an item is added to the list
    #
    # @param function a function that takes in one parameter: the
    # index of the new object
    def addAddCallback(self, function):
        self.confirmDBThread()
        self.addCallbacks.append(function)

    ##
    # registers a function to call when an item is removed from the view
    #
    # @param function a function that takes in one parameter: the
    # object to be deleted
    def addRemoveCallback(self, function):
        self.confirmDBThread()
        self.removeCallbacks.append(function)


    ##
    # Adds an item to the object database, filtering changes to subViews
    # @param object the object to add
    def addBeforeCursor(self, newobject,value=NoValue):
        self.confirmDBThread()
        if self.objectLocs.has_key(newobject.id):
            raise Exception, "%s (%d) is already in the database" % (newobject, newobject.id)
        point = self.cursor
        if point is None:
            point = self.objects.firstIter().copy()
        try:
            origObj = self.objects[point]
        except IndexError:
            origObj = None
        if value is NoValue:
            value = newobject
        it = self.objects.insertBefore(point, (newobject,value))
        self.objectLocs[newobject.id] = it
        # If this database is sorted, the cursor might not have
        # actually inserted at that point
        point = it.copy()
        if not point == self.objects.lastIter():
            point.forward()
        try:
            origObj = self.objects[point]
        except:
            origObj = None

        #self.checkObjLocs()
        for [view, f] in self.subMaps:
            view.confirmDBThread()
            view.saveCursor()
            #FIXME setting the cursor directly is bad karma
            if origObj is None:
                view.cursor = view.objects.lastIter().copy()
            else:
                view.cursor = view.objectLocs[origObj[0].id].copy()
            view.addBeforeCursor(newobject,f(value))
            view.restoreCursor()
#             try:
#                 self.checkMappedView(view)
#             except Exception, e:
#                 print "--------------"
#                 print "sub map failed"
#                 print "Mapping %s" % newobject
#                 print "initial point %s" % self.cursor
#                 print "actual point %s" % point
#                 print "orig obj %s (%d)" % (str(origObj), origObj[0].id)
#                 print 
#                 print view.objects[view.objectLocs[origObj[0].id]][0]
#                 for obj in self.objects:
#                     print obj[0]
#                 print
#                 for obj in view.objects:
#                     print obj[0]                    
#                 print e
#                 print "--------------"
        for [view, f] in self.subSorts:
            view.addBeforeCursor(newobject,value)
        for [view, f] in self.subFilters:
            if f(value):
                view.addBeforeCursor(newobject,value)
#             try:
#                 self.checkFilteredView(view,f)
#             except Exception, e:
#                 print "--------------"
#                 print "sub filter failed"
#                 print "Filtering %s" % newobject
#                 print "initial point %s" % self.cursor
#                 print "actual point %s" % point
#                 print "orig obj %s" % str(origObj)
#                 for obj in self.objects:
#                     if f(obj[1]):
#                         print obj[0]
#                 print
#                 for obj in self.objects:
#                     print obj[0]
#                 print
#                 for obj in view.objects:
#                     print obj[0]
#                 print
#                 print e
#                 print "--------------"
        for filter in self.indexes.keys():
            view = self.indexes[filter]
            try:
                view[filter(value)].addBeforeCursor(newobject,value)
            except KeyError:
                view[filter(value)] = DynamicDatabase([],False,parent=self)
                view[filter(value)].addBeforeCursor(newobject,value)

        if self.liveStorage:
            self.liveStorage.update (newobject)
        for callback in self.addCallbacks:
            callback(value,newobject.id)
        #self.checkObjLocs()

    ##
    # Adds an item to the object database, filtering changes to subViews
    # @param object the object to add
    def addAfterCursor(self, newobject, value = NoValue):
        self.confirmDBThread()
        try:
            self.saveCursor()
            if (self.cursor != self.objects.lastIter() and 
                self.cursor is not None):
                self.cursor.forward()
            self.addBeforeCursor(newobject, value)
        finally:
            self.restoreCursor()
        #self.checkObjLocs()

    #
    # Removes the object from the database
    def removeObj(self, obj):
        self.confirmDBThread()
        if self.objectLocs.has_key(obj.id):
            self.remove(self.objectLocs[obj.id])

    #
    # Removes the object from the database
    def changeObj(self, obj, needsSave=True):
        changed = False
        self.confirmDBThread()
        if self.objectLocs.has_key(obj.id):
            changed = True
            self.change(self.objectLocs[obj.id], needsSave=needsSave)
        return changed

    ##
    # remove the object the given iterator points to
    #
    # Private function. Should only be called by DynmaicDatabase class members
    # @param item optional position of item to remove
    def remove(self, it = NoValue):
        self.confirmDBThread()
        point = it
        if point is NoValue:
            if self.cursor is None:
                point = None
            else:
                point = self.cursor.copy()
        if point is not None and point is self.cursor:
            point = point.copy()
        if point is None:
            raise ObjectNotFoundError, "No object with id %s in database" % point
        

        #Save a reference to the item to compare with subViews
        temp = self.objects[point]
        tempobj = temp[0]
        tempid = tempobj.id
        tempmapped = temp[1]

        try:
            if point == self.cursor:
                self.cursor.back()
        except:
            pass
        for cursor in self.cursorStack:
            try:
                if point == cursor:
                    cursor.back()
            except:
                pass
        
        #Update the location dictionary
        #self.checkObjLocs()
        self.objectLocs.pop(tempid)

         #Remove it
        self.objects.remove(point)
        #self.checkObjLocs()

         #Perform callbacks
        for callback in self.removeCallbacks:
            callback(tempmapped, tempid)

        if self.liveStorage:
            self.liveStorage.remove (tempobj)

         #Pass the remove on to subViews
        for [view, f] in self.subMaps:
            view.removeObj(tempobj)
        for [view, f] in self.subSorts:
            view.removeObj(tempobj)
        for [view, f] in self.subFilters:
            view.removeObj(tempobj)
        for (key, views) in self.indexes.iteritems():
            # FIXME: Keep an index of items to
            # views. Eliminate this loop
            for (value, view) in views.iteritems():
                view.removeObj(tempobj)
        #self.checkObjLocs()

    ##
    # Signals that object on cursor has changed
    #
    # Private function. Should only be called by DynmaicDatabase class members
    # @param item optional position of item to remove in place of cursor
    def change(self, it = None, needsSave=True):
        self.confirmDBThread()
        if it is None:
            it = self.cursor
        if it is None:
            return
        temp = self.objects[it]
        tempobj = temp[0]
        tempid = tempobj.id
        tempmapped = temp[1]
        
        if needsSave and self.liveStorage:
            self.liveStorage.update (tempobj)

        for callback in self.changeCallbacks:
            callback(tempmapped,tempid)
        for [view, f] in self.subMaps:
            view.changeObj(tempobj, needsSave=needsSave)
        for [view, f] in self.subSorts:
            view.changeObj(tempobj, needsSave=needsSave)
        for [view, f] in self.subFilters:
            view.confirmDBThread()
            #view.checkObjLocs()
            if f(tempmapped):
                if view.objectLocs.has_key(tempid):
                    view.changeObj(tempobj, needsSave=needsSave)
                else:
                    view.addBeforeCursor(tempobj, tempmapped)
            else:
                if view.objectLocs.has_key(tempid):
                    view.removeObj(tempobj)
        for f, views in self.indexes.iteritems():
            index = f (tempmapped)
            if not views[index].changeObj(tempobj, needsSave=needsSave):
                for (value, view) in views.iteritems():
                    if value == index:
                        view.addBeforeCursor(tempobj, tempmapped)
                    else:
                        view.removeObj(tempobj)

    # Recomputes a single filter in the database
    def recomputeFilter(self,filter, all = False):
        self.confirmDBThread()
        # Go through each one of the filter subviews
        for [view, f] in self.subFilters:
            if all or view is filter:
                view.confirmDBThread()
                self.saveCursor()
                self.resetCursor()
                view.saveCursor()
                view.resetCursor()
                #Go through all the objects and recompute the filters
                for myObj in self.objects:
                    myObjObj = myObj[0]
                    myObjVal = myObj[1]
                    if view.objectLocs.has_key(myObjObj.id):
                        if not f(myObjVal):
                            view.removeObj(myObjObj)
                    else:
                        if f(myObjVal):
                            view.addBeforeCursor(myObjObj,myObjVal)

                self.restoreCursor()
                view.restoreCursor()
                view.recomputeFilters()
        #self.checkObjLocs()

    def recomputeIndex(self,filter, all = False):
        self.confirmDBThread()
        # Go through each one of the filter subviews
        for filt, views in self.indexes.iteritems():
            if all or filt is filter:
                self.saveCursor()
                try:
                    self.resetCursor()
                    for myObj in self.objects:
                        myObjObj = myObj[0]
                        myObjVal = myObj[1]
                        filtVal = filt(myObjVal)
                        if not views.has_key(filtVal):
                            views[filtVal] = DynamicDatabase([],False,parent=self)
                            views[filtVal].addBeforeCursor(myObjObj,
                                                           myObjVal)
                        if not views[filtVal].objectLocs.has_key(myObjObj.id):
                            # FIXME: Keep an index of items to
                            # views. Eliminate this loop
                            for val, view in views.iteritems():
                                if view.objectLocs.has_key(myObjObj.id):
                                    view.removeObj(myObjObj)
                                    break
                            views[filtVal].addBeforeCursor(myObjObj,myObjVal)
                finally:
                    self.restoreCursor()
                for val, view in views.iteritems():
                    view.recomputeFilters()

    #Recompute a single subSort
    def recomputeSort(self,sort, all = False):
        self.confirmDBThread()
        for [view, f] in self.subSorts:
            if all or view is sort:
                view.confirmDBThread()
                #FIXME this probably doesn't even work
                #      right. We should remove every item,
                #      then re-add them
                try:
                    curObj = view.objects[view.cursor]
                except:
                    curObj = None
                newCursor = None
                newLocs = {}
                temp = SortedList(pysort2dbsort(f))
                for obj in view.objects:
                    it = temp.append(obj)
                    newLocs[obj[0].id] = it
                    if obj is curObj:
                        newCursor = it.copy()
                newStack = []
                for it in view.cursorStack:
                    if it is None:
                        newStack.append(None)
                    elif it == view.objects.lastIter():
                        newStack.append(view.objects.lastIter().copy())
                    else:
                        newStack.append(newLocs[view.objects[it][0].id])
                view.objects = temp
                view.cursor = newCursor
                view.objectLocs = newLocs
                view.cursorStack = newStack
                view.recomputeFilters()
        #self.checkObjLocs()

    ##
    # This is called when the criteria for one of the filters changes. It
    # calls the appropriate add callbacks to deal with objects that have
    # appeared and disappeared.
    def recomputeFilters(self):
        self.confirmDBThread()
        self.recomputeFilter(None,True)
        self.recomputeSort(None, True)
        for [view, f] in self.subMaps:
            view.recomputeFilters()
        self.recomputeIndex(None,True)
        #self.checkObjLocs()

    # Used to sort objects
    def getVal(self, obj):
        return obj[1]

    ##
    # This is called to remove all elements matching a particular filter
    def removeMatching(self,f):
        print "DTV: WARNING: removeMatching is deprecated"
        if not self.rootDB:
            raise NotRootDBError, "removeMatching() cannot be called from subviews"
        self.confirmDBThread()
        self.saveCursor()
        self.resetCursor()
        for obj in self:
            if f(obj):
                obj.remove()
        self.restoreCursor()
    
    ##
    # Restores this database
    #
    def restoreFromObjectList(self, objectList):
        """Restore the database using a list of DDBObjects."""

        self.confirmDBThread()
        #Initialize the object location dictionary
        self.objectLocs = {}
        self.objects = LinkedList()
        for obj in objectList:
            it = self.objects.append((obj, obj))
            self.objectLocs[obj.id] = it

        self.cursor = None    
        self.cursorStack = []
        try:
            DDBObject.lastID = self.getLastID()
        except ValueError: #For the weird case where we're not
            pass           #restoring anything
        
        return True

    def getLastID(self):
        self.confirmDBThread()
        last = DDBObject.lastID
        for obj in self.objects:
            temp = obj[0].getID()
            if temp > last:
                last = temp
        return last

    ##
    # Removes this view from the hierarchy of views
    def unlink(self):
        self.parent.removeView(self)

    ##
    # Removes a filter that's currently not being used from the database
    # This should be called when a filter is no longer in use
    def removeView(self,oldView):
        #FIXME: We should keep indexes to make this faster
        self.confirmDBThread()
        for count in range(0,len(self.subFilters)):
            if self.subFilters[count][0] is oldView:
                self.subFilters[count:count+1] =  []
                return
        for count in range(0,len(self.subSorts)):
            if self.subSorts[count][0] is oldView:
                self.subSorts[count:count+1] =  []
                return
        for count in range(0,len(self.subMaps)):
            if self.subMaps[count][0] is oldView:
                self.subMaps[count:count+1] =  []
                return
        for func, views in self.indexes.iteritems():
            # Clear out subfilters and callbacks on this view
            for key, view in views.iteritems():
                if view is oldView:
                    view.subFilters = []
                    view.subMaps = []
                    view.subSorts = []
                    view.indexes = {}
                    view.addCallbacks = []
                    view.removeCallbacks = []
                    view.changeCallbacks = []
                    return

    ##
    # returns the object with the given id
    def getObjectByID(self, id):
        self.confirmDBThread()
        try:
            return self.objects[self.objectLocs[id]][1]
        except:
            raise ObjectNotFoundError, "No object with id %s in the database" % id

    ##
    # returns the id of the object the cursor is currently pointing to
    def getCurrentID(self):
        self.confirmDBThread()
        try:
            return self.objects[self.cursor][0].id
        except:
            raise ObjectNotFoundError, "No object at current cursor position"

    ##
    # returns the id of the object after the object identified by id
    def getNextID(self, id):
        self.confirmDBThread()
        try:
            pos = self.objectLocs[id].copy()
            pos.forward()
            return self.objects[pos][0].id
        except:
            return None

    ##
    # returns the id of the object before the object identified by id
    def getPrevID(self, id):
        self.confirmDBThread()
        try:
            pos = self.objectLocs[id].copy()
            pos.back()
            return self.objects[pos][0].id
        except:
            return None

    def createIndex(self, indexFunc):
        self.confirmDBThread()
        indexViews = {}
        for obj in self.objects:
            index = indexFunc(obj[1])
            if not indexViews.has_key(index):
                indexViews[index] = DynamicDatabase([],False, parent=self)
            indexViews[index].addBeforeCursor(obj[0],obj[1])
        self.indexes[indexFunc] = indexViews

    def filterWithIndex(self, indexFunc, value):
        # Throw an exception if there's no filter for this func
        views = self.indexes[indexFunc]
        try:
            return views[value]
        except:
            views[value] = DynamicDatabase([],False, parent=self)
            return views[value]


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
        self.confirmDBThread()
        DDBObject.lastID = DDBObject.lastID + 1
        self.id =  DDBObject.lastID
        if add:
            self.dd.addAfterCursor(self)

    ##
    # returns unique integer assocaited with this object
    def getID(self):
        return self.id

    #
    #Call this after you've removed all references to the object
    def remove(self):
        self.dd.confirmDBThread()
        self.dd.removeObj(self)

    ##
    # Call this before you grab data from an object
    #
    # Usage:
    #
    # view.confirmDBThread()
    #  ...
    #
    def confirmDBThread(self):
        confirmDBThread()

    ##
    # Call this after you change the object
    def signalChange(self, needsSave=True):
        self.dd.confirmDBThread()
        self.dd.saveCursor()
        try:
            self.dd.resetCursor()
            self.dd.changeObj(self, needsSave=needsSave)
        finally:
            self.dd.restoreCursor()

# Erases the current database and replaces it with a blank slate
def resetDefaultDatabase():
    global defaultDatabase
    defaultDatabase.__init__()
    import views
    reload(views)
