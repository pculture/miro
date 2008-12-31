# -*- mode: python -*-

# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

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
import sys
import types
import threading

from miro import signals
from miro.fasttypes import LinkedList, SortedList

class DatabaseConstraintError(Exception):
    """Raised when a DDBObject fails its constraint checking during
    signalChange().
    """
    pass

class DatabaseConsistencyError(Exception):
    """Raised when the database encounters an internal consistency issue.
    """
    pass

class DatabaseThreadError(Exception):
    """Raised when the database encounters an internal consistency issue.
    """
    pass

class DatabaseVersionError(StandardError):
    """Raised when an attempt is made to restore a database newer than the
    one we support
    """
    pass

class ObjectNotFoundError(StandardError):
    """Raised when an attempt is made to remove an object that doesn't exist
    """
    pass

class NotRootDBError(StandardError):
    """Raised when an attempt is made to call a function that's only
    allowed to be called from the root database
    """
    pass

class NoValue:
    """Used as a dummy value so that "None" can be treated as a valid value
    """
    pass

# begin* and end* no longer actually lock the database.  Instead
# confirmDBThread prints a warning if it's run from any thread that
# isn't the main thread.  This can be removed from releases for speed
# purposes.

event_thread = None
def set_thread(thread):
    global event_thread
    if event_thread is None:
        event_thread = thread
    
import traceback
def confirmDBThread():
    global event_thread
    if event_thread is None or event_thread != threading.currentThread():
        if event_thread is None:
            errorString = "Database event thread not set"
        else:
            errorString = "Database called from %s" % threading.currentThread()
        traceback.print_stack()
        raise DatabaseThreadError, errorString

def findUnpicklableParts(obj, seen={}, depth=0):
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

class IndexMap:
    """Maps index values to database views.

    An IndexMap is a dict that maps index values to views, and also remembers
    what values each object maps to.  Remembering the mapped values allows us
    to efficently locate objects after their mapped value changes.
    """

    def __init__(self, indexFunc, parentDB, sortFunc=None, resort=False):
        self.indexFunc = indexFunc
        self.sortFunc = sortFunc
        if self.sortFunc is None:
            self.resort = False
        else:
            self.resort = resort
        self.parentDB = parentDB
        self.views = {} # maps index values -> view
        self.mappings = {} # maps object id -> index value

    def addObject(self, newobject, value):
        """Add a new object to the IndexMap.
        """

        indexValue = self.indexFunc(value)
        self.mappings[newobject.getID()] = indexValue
        self.getViewForValue(indexValue).addBeforeCursor(newobject, value)

    def removeObject(self, obj):
        """Remove an object from the IndexMap.
        """
        indexValue = self.mappings.pop(obj.getID())
        self.views[indexValue].removeObj(obj)

    def _changeOrRecompute(self, obj, value, isChange):
        indexValue = self.indexFunc(value)
        try:
            oldIndexValue = self.mappings[obj.getID()]
        except KeyError:
            # This happens when an object gets a signalChange() before the
            # addObject call.  There are two cases that cause this:  getting a
            # signalChange call before the original addObject percolates down
            # to the IndexMap and getting a signalChange call in a remove
            # callback during the removeObject call below, but before the
            # addObject call.
            return
        if indexValue == oldIndexValue:
            if isChange:
                self.views[indexValue].changeObj(obj, needsSave=False)
        else:
            self.removeObject(obj)
            self.addObject(obj, value)
            # Calling addObject takes care of creating the new view if
            # nessecary and updating self.mappings

    def changeObject(self, obj, value):
        """Call this method when an object has been changed.  

        If the object now maps to a new view, it will be moved from the old
        view to the new one.  Otherwise, we will call changeObj() on the old
        view.
        """
        self._changeOrRecompute(obj, value, True)

    def recomputeObject(self, obj, value):
        """Recompute which view an object maps to.  This function must be
        called when the output of an index function changes (at least
        potentially), but the object itself hasn't changed.
        """
        if obj.getID() not in self.mappings:
            self.addObject(obj, value)
        else:
            self._changeOrRecompute(obj, value, False)

    def getViewForValue(self, indexValue):
        """Get a view for an index value.  The view will be all objects such
        that indexFunc(object) == indexValue.
        """
        try:
            view = self.views[indexValue]
        except KeyError:
            view = DynamicDatabase([], False, parent=self.parentDB, sortFunc = self.sortFunc, resort = self.resort)
            self.views[indexValue] = view
        return view

    def getItemForValue(self, indexValue, default):
        """Get a single item that maps to a given value.  If no items map to
        indexValue, default will be returned.  If multiple items map to
        indexValue, the one returned is not defined.
        """
        try:
            return self.views[indexValue].objects[0][1]
        except (KeyError, IndexError):
            return default

    def getViews(self):
        return self.views.values()

    def count_databases(self):
        count = 0
        size = 0
        for db in self.views.itervalues():
            new = db.count_databases()
            count = count + new[0]
            size = size + new[1]
        return (count, size)

class MultiIndexMap(IndexMap):
    """Maps index values to database views.

    A MultiIndexMap is like an IndexMap, except it expects the index function
    to return a sequence of values.  For each value it returns, the object
    will be added to the corresponding view.
    """

    def addObject(self, newobject, value):
        """Add a new object to the IndexMap.
        """
        indexValues = set(self.indexFunc(value))
        self.mappings[newobject.getID()] = indexValues
        for indexValue in indexValues:
            self.getViewForValue(indexValue).addBeforeCursor(newobject, value)

    def removeObject(self, obj):
        """Remove an object from the IndexMap.
        """
        indexValues = self.mappings.pop(obj.getID())
        for indexValue in indexValues:
            self.views[indexValue].removeObj(obj)

    def _changeOrRecompute(self, obj, value, isChange):
        indexValues = set(self.indexFunc(value))
        try:
            oldIndexValues = self.mappings.pop(obj.getID())
            # by poping the value, we ensure that if a callback for the
            # addBeforeCursor or removeObj calls invokes signalChange() on
            # this object, we'll ignore it.
        except KeyError:
            return
        for indexValue in (indexValues - oldIndexValues):
            self.getViewForValue(indexValue).addBeforeCursor(obj, value)
        for indexValue in (oldIndexValues - indexValues):
            self.getViewForValue(indexValue).removeObj(obj)
        if isChange:
            for indexValue in indexValues.intersection(oldIndexValues):
                self.views[indexValue].changeObj(obj, needsSave=False)
        self.mappings[obj.getID()] = indexValues

    def changeObject(self, obj, value):
        """Call this method when an object has been changed.  

        If the object now maps to a new view, it will be moved from the old
        view to the new one.  Otherwise, we will call changeObj() on the old
        view.
        """
        self._changeOrRecompute(obj, value, True)

    def recomputeObject(self, obj, value):
        """Recompute which view an object maps to.  This function must be
        called when the output of an index function changes (at least
        potentially), but the object itself hasn't changed.
        """
        if obj.getID() not in self.mappings:
            self.addObject(obj, value)
        else:
            self._changeOrRecompute(obj, value, False)

    def getViewForValue(self, indexValue):
        """Get a view for an index value.  The view will be all objects such
        that indexFunc(object) == indexValue.
        """
        try:
            view = self.views[indexValue]
        except KeyError:
            view = DynamicDatabase([], False, parent=self.parentDB, sortFunc = self.sortFunc, resort = self.resort)
            self.views[indexValue] = view
        return view

    def getItemForValue(self, indexValue, default):
        """Get a single item that maps to a given value.  If no items map to
        indexValue, default will be returned.  If multiple items map to
        indexValue, the one returned is not defined.
        """
        try:
            return self.views[indexValue].objects[0][1]
        except (KeyError, IndexError):
            return default

    def getViews(self):
        return self.views.values()

class DynamicDatabase:
    """Implements a view of the database

    A Dynamic Database is a list of objects that can be filtered,
    sorted, and mapped. It can also give notification when an object is
    added, removed, or changed.
    """

    def __init__(self, objects=[], rootDB=True, sortFunc=None, filterFunc=None, mapFunc=None, cursorID=None, parent=None, resort=False):
        """Create a view of a list of objects.

        @param objects A list of object/mapped value pairs to create the
        initial view
        @param rootDB true iff this is not a subview of another DD. Should never be used outside of this class.
        """
        self.rootDB = rootDB
        self.cursor = None
        self.parent = parent
        self.changeCallbacks = set()
        self.addCallbacks = set()
        self.removeCallbacks = set()
        self.viewChangeCallbacks = set()
        self.resortCallbacks = set()
        self.viewUnlinkCallbacks = set()
        self.subFilters = []
        self.subSorts = []
        self.subMaps = []
        self.clones = [] # clones are children who are identical to
                         # their parents. Currently, only indexed
                         # views have clones now.
        self.cursorStack = []
        self.objectLocs = {}
        self.indexes = {}
        self.liveStorage = None
        self.sortFunc = sortFunc

        if sortFunc is not None:
            self.objects = SortedList(sortFunc)
            self.resort = resort
        else:
            self.objects = LinkedList()
            self.resort = False
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

    def count_databases(self):
        count = 1
        size = len(self.objects)
        for db, func in self.subFilters:
            new = db.count_databases()
            count = count + new[0]
            size = size + new[1]
        for db in self.clones:
            db = db[0]
            new = db.count_databases()
            count = count + new[0]
            size = size + new[1]
        for db, func in self.subSorts:
            new = db.count_databases()
            count = count + new[0]
            size = size + new[1]
        for db, func in self.subMaps:
            new = db.count_databases()
            count = count + new[0]
            size = size + new[1]
        for index in self.indexes.itervalues():
            new = index.count_databases()
            count = count + new[0]
            size = size + new[1]
        return (count, size)

#     def checkObjLocs(self):
#         """Checks to make the sure object location dictionary is accurate
#
#         Uncomment the calls to this when you change the location
#         dictionary code
#         """
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

    def __iter__(self):
        """This is needed for the class to function as an iterator
        """
        self.confirmDBThread()
        self.cursor = None
        return self    

    def saveCursor(self):
        """Saves the current position of the cursor on the stack

        Usage:

            view.saveCursor()
            try:
                ...
            finally:
                view.restoreCursor()
        """
        if self.cursor is not None:
            self.cursorStack.append(self.cursor.copy())
        else:
            self.cursorStack.append(None)


    def restoreCursor(self):
        """Restores the position of the cursor
        """
        self.cursor = self.cursorStack.pop()

    def __getitem__(self, n):
        """Returns the nth item in the View
        """
        #print "DTV: Database Warning: numeric subscripts are deprecated"
        self.confirmDBThread()
        try:
            return self.objects[n][1]
        except IndexError:
            return None

    def __len__(self):
        """Returns the number of items in the database
        """
        return self.len()
    def len(self):
        self.confirmDBThread()
        length = len(self.objects)
        return length
        
    def confirmDBThread(self):
        """Call before accessing the database

        Usage:

            view.confirmDBThread()
            ..access database..
        """
        confirmDBThread()

    def cur(self):
        """Returns the object that the cursor is currently pointing to or
        None if it's not pointing to an object
        """
        self.confirmDBThread()
        try:
            return self.objects[self.cursor][1]
        except:
            self.cursor = None
            return None

    def next(self):
        """next() function used by iterator
        """
        self.confirmDBThread()
        try:
            if self.cursor is None:
                self.cursor = self.objects.firstIter().copy()
            else:
                self.cursor.forward();
            return self.objects[self.cursor][1]
        except:
            try:
                raise StopIteration, "No next"
            except TypeError:
                raise StopIteration

    def getNext(self):
        """Returns the next object in the view None if it is not set
        """
        self.confirmDBThread()
        if self.cursor is None:
            self.cursor = self.objects.firstIter().copy()
        else:
            self.cursor.forward();
        ret = self.cur()
        return ret

    def getPrev(self):
        """Returns the previous object in the view None if it is not set
        """
        self.confirmDBThread()
        ret = None
        if self.cursor is not None:
            self.cursor.back();
            ret = self.cur()
        return ret

    def resetCursor(self):
        """Sets the current cursor position to the beginning of the list
        """
        self.confirmDBThread()
        self.cursor = None

    def moveCursorToObject(self, obj):
        """Sets the current cursor position to point to a given object
        """
        self.confirmDBThread()
        self.moveCursorToID(obj.id)

    def moveCursorToID(self, id):
        """Sets the current cursor position to point the object with a given id
        """
        self.confirmDBThread()
        try:
            self.cursor = self.objectLocs[id].copy()
        except KeyError:
            msg = "No object with id %s in the database" % id
            raise ObjectNotFoundError, msg

    def filter(self, f, sortFunc=None, resort=False):
        """Returns a View of the data filtered through a boolean function
        @param f boolean function to use as a filter
        """
        self.confirmDBThread()
        try:
            curID = self.objects[self.cursor][0].id
        except:
            curID = None
        new = DynamicDatabase(self.objects, False, cursorID=curID, filterFunc=f, parent=self, sortFunc=sortFunc, resort=resort)
        self.subFilters.append([new, f])
        return new

    def clone(self):
        """Returns a View of the database identical to this one. Equivalent
        to filter(lambda x:True).

        Private use only
        """
        self.confirmDBThread()
        try:
            curID = self.objects[self.cursor][0].id
        except:
            curID = None
        new = DynamicDatabase(self.objects, False, cursorID=curID, parent=self, sortFunc=self.sortFunc, resort=self.resort)
        self.clones.append([new])
        return new

    def map(self, f):
        """Returns a View of the data mapped according to the given function

        @param f function to use as a map
        """
        #assert(not self.rootDB) # Dude! Don't map the entire DB! Are you crazy?

        self.confirmDBThread()
        try:
            curID = self.objects[self.cursor][0].id
        except:
            curID = None
        new = DynamicDatabase(self.objects, False, cursorID=curID, mapFunc=f, parent=self)
        self.subMaps.append([new, f])
        return new

    def sort(self, f, resort=False):
        """Returns a View of the data filtered through a sort function
        @param f comparision function to use for sorting
        """
        #assert(not self.rootDB) # Dude! Don't sort the entire DB! Are you crazy?
        self.confirmDBThread()
        try:
            curID = self.objects[self.cursor][0].id
        except:
            curID = None
        new = DynamicDatabase(self.objects, False, sortFunc=f, cursorID=curID, parent=self, resort=resort)
        self.subSorts.append([new, f])
        return new

    def add_change_callback(self, function):
        """Registers a function to call when an item in the view changes

        @param function a function that takes in one parameter: the
        index of the changed object
        """
        self.confirmDBThread()
        self.changeCallbacks.add(function)

    def addAddCallback(self, function):
        """Registers a function to call when an item is added to the list

        @param function a function that takes in one parameter: the
        index of the new object
        """
        self.confirmDBThread()
        self.addCallbacks.add(function)

    def addRemoveCallback(self, function):
        """Registers a function to call when an item is removed from the view

        @param function a function that takes in one parameter: the
        object to be deleted
        """
        self.confirmDBThread()
        self.removeCallbacks.add(function)

    def addViewChangeCallback(self, function):
        """Registers a function to call when the view is updated, even if no items change.

        @param function a function that takes in no parameters
        """
        self.confirmDBThread()
        self.viewChangeCallbacks.add(function)

    def addResortCallback(self, function):
        """Registers a function to call when the view is resorted

        @param function a function that takes in one parameter: the
        index of the new object
        """
        self.confirmDBThread()
        self.resortCallbacks.add(function)

    def addViewUnlinkCallback(self, function):
        """Registers a function to call when the view is about to be unlinked

        @param function a function that takes in no parameters
        """
        self.confirmDBThread()
        self.viewUnlinkCallbacks.add(function)

    def remove_change_callback(self, function):
        self.confirmDBThread()
        self.changeCallbacks.remove(function)

    def removeAddCallback(self, function):
        self.confirmDBThread()
        self.addCallbacks.remove(function)

    def removeRemoveCallback(self, function):
        self.confirmDBThread()
        self.removeCallbacks.remove(function)

    def removeViewChangeCallback(self, function):
        self.confirmDBThread()
        self.viewChangeCallbacks.remove(function)

    def removeResortCallback(self, function):
        self.confirmDBThread()
        self.resortCallbacks.remove(function)

    def removeViewUnlinkCallback(self, function):
        self.confirmDBThread()
        self.viewUnlinkCallbacks.remove(function)

    def addBeforeCursor(self, newobject, value=NoValue):
        """Adds an item to the object database, filtering changes to subViews
        @param object the object to add
        """
        self.confirmDBThread()
        if self.objectLocs.has_key(newobject.id):
            raise DatabaseConsistencyError,("%s (%d) is already in the database" % (newobject, newobject.id))
        point = self.cursor
        if point is None:
            point = self.objects.firstIter().copy()
        if value is NoValue:
            value = newobject
        it = self.objects.insertBefore(point, (newobject, value))
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
        for view, f in self.subMaps:
            view.confirmDBThread()
            view.saveCursor()
            #FIXME setting the cursor directly is bad karma
            if origObj is None:
                view.cursor = view.objects.lastIter().copy()
            else:
                view.cursor = view.objectLocs[origObj[0].id].copy()
            view.addBeforeCursor(newobject, f(value))
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
        for view, f in self.subSorts:
            view.addBeforeCursor(newobject, value)
        for view, f in self.subFilters:
            if f(value):
                view.addBeforeCursor(newobject, value)
#             try:
#                 self.checkFilteredView(view, f)
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
        for [view] in self.clones:
            view.addBeforeCursor(newobject, value)
        for indexFunc, indexMap in self.indexes.iteritems():
            indexMap.addObject(newobject, value)

        if self.liveStorage:
            self.liveStorage.update(newobject)
        for callback in self.addCallbacks:
            callback(value, newobject.id)
        #self.checkObjLocs()

    def addAfterCursor(self, newobject, value=NoValue):
        """Adds an item to the object database, filtering changes to subViews
        @param object the object to add
        """
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

    def removeObj(self, obj):
        """Removes the object from the database
        """
        self.confirmDBThread()
        if self.objectLocs.has_key(obj.id):
            self.remove(self.objectLocs[obj.id])

    def _removeIter(self, it):
        first = self.objects.firstIter()
        if it == self.cursor:
            if self.cursor == first:
                self.cursor = None
            else:
                self.cursor.back()
        for i in range(len(self.cursorStack)):
            cursor = self.cursorStack[i]
            if it == cursor:
                if cursor == first:
                    self.cursorStack[i] = None
                else:
                    cursor.back()
        self.objects.remove(it)

    def changeObj(self, obj, needsSave=True):
        """Removes the object from the database
        """
        changed = False
        self.confirmDBThread()
        if self.objectLocs.has_key(obj.id):
            changed = True
            self.change(self.objectLocs[obj.id], needsSave=needsSave)
        return changed

    def remove(self, it=NoValue):
        """Remove the object the given iterator points to

        Private function. Should only be called by DynmaicDatabase class members
        @param item optional position of item to remove
        """
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

        #Update the location dictionary
        #self.checkObjLocs()
        self.objectLocs.pop(tempid)

        #Remove it
        self._removeIter(point)
        #self.checkObjLocs()

        #Perform callbacks
        for callback in self.removeCallbacks:
            callback(tempmapped, tempid)

        if self.liveStorage:
            self.liveStorage.remove(tempobj)

        #Pass the remove on to subViews
        for view, f in self.subMaps:
            view.removeObj(tempobj)
        for view, f in self.subSorts:
            view.removeObj(tempobj)
        for view, f in self.subFilters:
            view.removeObj(tempobj)
        for [view] in self.clones:
            view.removeObj(tempobj)
        for indexFunc, indexMap in self.indexes.iteritems():
            indexMap.removeObject(tempobj)
        #self.checkObjLocs()

    def change(self, it=None, needsSave=True):
        """Signals that object on cursor has changed

        Private function. Should only be called by DynmaicDatabase class members
        @param item optional position of item to remove in place of cursor
        """
        self.confirmDBThread()
        madeCallback = False
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

        if self.resort:
            before = it.copy()
            after = it.copy()
            before.back()
            after.forward()
            if (it == self.objects.firstIter() and 
                    after == self.objects.lastIter()):
                # changed the only item in the list
                doResort = False
            elif it == self.objects.firstIter():
                # changed the first item in the list
                nexttemp = self.objects[after]
                doResort = self.sortFunc(nexttemp, temp)
            elif after == self.objects.lastIter():
                # changed the last item in the list
                prevtemp = self.objects[before]
                doResort = self.sortFunc(temp, prevtemp)
            else:
                # changed an item in the middle
                nexttemp = self.objects[after]
                prevtemp = self.objects[before]
                doResort = (self.sortFunc(temp, prevtemp) or
                            (self.sortFunc(nexttemp, temp)))
            if doResort:
                # Item Moved -- trigger remove and add callbacks
                self._removeIter(it)
                newIt = self.objects.insertBefore(after, (tempobj, tempmapped))
                self.objectLocs[tempid] = newIt
                self.saveCursor()
                iterAfter = newIt.copy()
                iterAfter.forward()
                try:
                    self.cursor = newIt.copy()
                    self.cursor.forward()
                    for callback in self.removeCallbacks:
                        callback(tempmapped, tempid)
                    for callback in self.addCallbacks:
                        callback(tempmapped, tempid)
                    try:
                        nextId = self.objects[iterAfter][0].id
                    except IndexError:
                        nextId = None
                    for view, f in self.subMaps:
                        view.saveCursor()
                        try:
                            if nextId is not None:
                                view.cursor = view.objectLocs[nextId]
                            else:
                                view.cursor = view.objects.lastIter()
                            view.removeObj(tempobj)
                            view.addBeforeCursor(tempobj, f(tempmapped))
                        finally:
                            view.restoreCursor()
                finally:
                    self.restoreCursor()
                    madeCallback = True

        if not madeCallback:
            for callback in self.changeCallbacks:
                callback(tempmapped, tempid)
        for view, f in self.subMaps:
            view.changeObj(tempobj, needsSave=needsSave)
        for view, f in self.subSorts:
            view.changeObj(tempobj, needsSave=needsSave)
        for view, f in self.subFilters:
            #view.checkObjLocs()
            if f(tempmapped):
                if view.objectLocs.has_key(tempid):
                    view.changeObj(tempobj, needsSave=needsSave)
                else:
                    view.addBeforeCursor(tempobj, tempmapped)
            else:
                if view.objectLocs.has_key(tempid):
                    view.removeObj(tempobj)
        for [view] in self.clones:
            #view.checkObjLocs()
            view.changeObj(tempobj, needsSave=needsSave)
        for indexFunc, indexMap in self.indexes.iteritems():
            indexMap.changeObject(tempobj, tempmapped)

    def recomputeFilter(self, filter, all=False):
        """Recomputes a single filter in the database
        """
        self.confirmDBThread()
        # Go through each one of the filter subviews
        for view, f in self.subFilters:
            if all or view is filter:
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
                            view.addBeforeCursor(myObjObj, myObjVal)

                self.restoreCursor()
                view.restoreCursor()
                view.recomputeFilters()
                for callback in view.viewChangeCallbacks:
                    callback()
        #self.checkObjLocs()

    def recomputeIndex(self, filter, all=False):
        self.confirmDBThread()
        # Go through each one of the filter subviews
        for indexFunc, indexMap in self.indexes.iteritems():
            if all or indexFunc is filter:
                self.saveCursor()
                try:
                    self.resetCursor()
                    for obj, value in self.objects:
                        indexMap.recomputeObject(obj, value)
                finally:
                    self.restoreCursor()
                for view in indexMap.getViews():
                    view.recomputeFilters()
                    for callback in view.viewChangeCallbacks:
                        callback()

    def _recomputeSingleSort(self, view, f):
        try:
            curObj = view.objects[view.cursor]
        except:
            curObj = None
        newCursor = None
        newLocs = {}
        temp = SortedList(f)
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
        changed = view.objects != temp

        view.objects = temp
        view.cursor = newCursor
        view.objectLocs = newLocs
        view.cursorStack = newStack

        if changed:
            for callback in view.resortCallbacks:
                callback()

        # Only recompute sorts that asked to be resorted
        for subView, f in view.subSorts:
            if subView.resort:
                view.recomputeSort(subView)
            else:
                subView.recomputeFilters()

        # Recompute all filters, resorting where necessary
        for subView, f in view.subFilters:
            if subView.resort:
                view._recomputeSingleSort(subView, subView.sortFunc)
            view.recomputeFilter(subView)

        # Recompute everything below maps
        for subView, f in view.subMaps:
            subView.recomputeFilters()

        # Recompute indexes
        for f, index in view.indexes.iteritems():
            if index.resort:
                for key, subView in index.views.iteritems():
                    view._recomputeSingleSort(subView, subView.sortFunc)
        view.recomputeIndex(None, all=True)

        for [subView] in view.clones:
            if subView.resort:
                view._recomputeSingleSort(subView, subView.sortFunc)
            view.recomputeFilter(subView)

        for callback in view.viewChangeCallbacks:
            callback()

    def recomputeSort(self, sort, all=False):
        """Recompute a single subSort
        """
        self.confirmDBThread()
        for view, f in self.subSorts:
            if all or view is sort:
                self._recomputeSingleSort(view, f)
        if sort is not None and all == False:
            for view, f in self.subFilters:
                if view is sort:
                    self._recomputeSingleSort(view, view.sortFunc)
        #self.checkObjLocs()

    def recomputeFilters(self):
        """This is called when the criteria for one of the filters changes. It
        calls the appropriate add callbacks to deal with objects that have
        appeared and disappeared.
        """
        self.confirmDBThread()
        self.recomputeFilter(None, True)
        self.recomputeSort(None, True)
        for view, f in self.subMaps:
            view.recomputeFilters()
        self.recomputeIndex(None, True)
        #self.checkObjLocs()

    def getVal(self, obj):
        """Used to sort objects
        """
        return obj[1]
    
    def restoreFromObjectList(self, objectList):
        """Restore the database using a list of DDBObjects.
        """
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

    def unlink(self):
        """Removes this view from the hierarchy of views
        """
        for callback in self.viewUnlinkCallbacks:
            callback()
        self.parent.removeView(self)

    def removeView(self, oldView):
        """Removes a filter that's currently not being used from the database
        This should be called when a filter is no longer in use
        """
        #FIXME: We should keep indexes to make this faster
        self.confirmDBThread()
        for count in range(0, len(self.subFilters)):
            if self.subFilters[count][0] is oldView:
                self.subFilters[count:count+1] =  []
                return
        for count in range(0, len(self.clones)):
            if self.clones[count][0] is oldView:
                self.clones[count:count+1] =  []
                return
        for count in range(0, len(self.subSorts)):
            if self.subSorts[count][0] is oldView:
                self.subSorts[count:count+1] =  []
                return
        for count in range(0, len(self.subMaps)):
            if self.subMaps[count][0] is oldView:
                self.subMaps[count:count+1] =  []
                return
        for indexFunc, indexMap in self.indexes.iteritems():
            # Clear out subfilters and callbacks on this view
            for view in indexMap.getViews():
                if view is oldView:
                    raise DatabaseConsistencyError, "Indexed views should never be directly returned"
                for count in range(0, len(view.clones)):
                    if view.clones[count][0] is oldView:
                        view.clones[count:count+1] = []
                        return

    def getObjectByID(self, id):
        """Returns the object with the given id
        """
        self.confirmDBThread()
        try:
            return self.objects[self.objectLocs[id]][1]
        except:
            raise ObjectNotFoundError, "No object with id %s in the database" % id

    def idExists(self, id):
        self.confirmDBThread()
        return id in self.objectLocs

    def getCurrentID(self):
        """Returns the id of the object the cursor is currently pointing to
        """
        self.confirmDBThread()
        try:
            return self.objects[self.cursor][0].id
        except:
            raise ObjectNotFoundError, "No object at current cursor position"

    def getNextID(self, id):
        """Returns the id of the object after the object identified by id
        """
        self.confirmDBThread()
        try:
            pos = self.objectLocs[id].copy()
            pos.forward()
            return self.objects[pos][0].id
        except:
            return None

    def getPrevID(self, id):
        """Returns the id of the object before the object identified by id
        """
        self.confirmDBThread()
        try:
            pos = self.objectLocs[id].copy()
            pos.back()
            return self.objects[pos][0].id
        except:
            return None

    def createIndex(self, indexFunc, sortFunc=None, multiValued=False, resort=False):
        self.confirmDBThread()
        if not multiValued:
            indexMap = IndexMap(indexFunc, self, sortFunc=sortFunc, resort=resort)
        else:
            indexMap = MultiIndexMap(indexFunc, self, sortFunc=sortFunc, resort=resort)
        for obj, value in self.objects:
            indexMap.addObject(obj, value)
        self.indexes[indexFunc] = indexMap

    def filterWithIndex(self, indexFunc, value):
        # Throw an exception if there's no filter for this func
        return self.indexes[indexFunc].getViewForValue(value).clone()

    def changeIndexValue(self, indexFunc, value):
        """Changes the index associated with the current view. This should
        only be called on views created by filterWithIndex. Useful for
        cases where indexed views need to change on the fly.
        """
        for obj, mapped in self.objects:
            self.remove(self.objectLocs[obj.id])

        # Remove references to the cloned view
        self.parent.removeView(self)

        # Self should always be a clone of an indexed view
        # Find the new index view
        newView = self.parent.parent.indexes[indexFunc].getViewForValue(value)
        self.parent = newView
        newView.clones.append([self])

        if self.resort:
            self.objects = SortedList(self.sortFunc)
        else:
            self.objects = LinkedList()
        self.objectLocs = {}
        
        for temp in newView.objects:
            self.addBeforeCursor(temp[0], temp[1])

    def getItemWithIndex(self, indexFunc, value, default=None):
        """Get a single item using an index.

        This will return an item such that indexFunc(item) == value.  If
        multiple objects match have the same index value, the one choosen is
        not defined.  If no items in the db map to the value, default will be
        returned.

        If there isn't an index for indexFunc, a KeyError will be raised.
        """
        return self.indexes[indexFunc].getItemForValue(value, default)

##
# Global default database
defaultDatabase = DynamicDatabase()

class DDBObject(signals.SignalEmitter):
    """Dynamic Database object
    """
    #The last ID used in this class
    lastID = 0

    #The database associated with this object
    dd = defaultDatabase

    def __init__(self, dd=None, add=True):
        """
        @param dd optional DynamicDatabase to associate with this object
               -- if ommitted the global database is used
        @param add Iff true, object is added to the database
        """
        signals.SignalEmitter.__init__(self, 'removed')
        if dd != None:
            self.dd = dd
        
        #Set the ID to the next free number
        self.confirmDBThread()
        DDBObject.lastID = DDBObject.lastID + 1
        self.id =  DDBObject.lastID
        if add:
            self.check_constraints()
            self.dd.addAfterCursor(self)

    def onRestore(self):
        signals.SignalEmitter.__init__(self, 'removed')

    def getID(self):
        """Returns unique integer assocaited with this object
        """
        return self.id

    def idExists(self):
        self.confirmDBThread()
        return self.dd.idExists(self.id)

    def remove(self):
        """Call this after you've removed all references to the object
        """
        self.dd.confirmDBThread()
        self.dd.removeObj(self)
        self.emit('removed')

    def confirmDBThread(self):
        """Call this before you grab data from an object

        Usage:

            view.confirmDBThread()
            ...
        """
        confirmDBThread()

    def check_constraints(self):
        """Subclasses can override this method to do constraint checking
        before they get saved to disk.  They should raise a
        DatabaseConstraintError on problems.
        """
        pass

    def signalChange(self, needsSave=True):
        """Call this after you change the object
        """
        self.dd.confirmDBThread()
        if not self.dd.idExists(self.id):
            msg = "signalChange() called on non-existant object (id is %s)" \
                    % self.id
            raise DatabaseConstraintError, msg
        self.check_constraints()
        self.dd.saveCursor()
        try:
            self.dd.resetCursor()
            self.dd.changeObj(self, needsSave=needsSave)
        finally:
            self.dd.restoreCursor()

def resetDefaultDatabase():
    """Erases the current database and replaces it with a blank slate
    """
    global defaultDatabase
    defaultDatabase.__init__()
    import views
    reload(views)
