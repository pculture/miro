"""This module does the reading/writing of our database to/from disk.  It
works with the schema module to validate the data that we read/write and with
the upgradedatabase module to upgrade old database storages.

We avoid ever writing a DDB class to disk.  This allows us to change our
classes without concern to how it will affect old databases.  For instance, we
can delete classes and not have to worry about users with old databases that
reference those classes.  Instead of class names, we write a string that
represents the classes ("feed" instead of feed.Feed).  If we decide to delete
the feed class, the upgrade code can handle upgrading old feed objects.

To achieve the above, before we save the DDBObjects to disk, we convert them
to SavableObjects.  A SavableObject is a really simple storage container that
remembers the class it was saved from and selected attributes of the object
(one for each item in the object's schema).  When we restore DDBObjects, we
need to convert the other way.

Right now we implement the conversion/unconversion using 2 classes
(SavableConverter and SavableUnconverter) that share a base classes
(ConverterBase).  Converter base handles walking the object tree, which is
most of the actual conversion.  The SavableConverter and SavableUnconverter
override some methods which are specific to the conversion/unconversion
process.

"""

import cPickle
import os
import shutil
import traceback

import config
import database
import databasesanity
import databaseupgrade
import olddatabaseupgrade
import prefs
import util
import schema as schema_mod
import eventloop
import app

# FILEMAGIC should be the first portion of the database file.  After that the
# file will contain pickle data
FILEMAGIC = "Democracy Database V1"

# skipOnRestore and skipUpgrade are set by the unit tests to bypass
# some of our usual operations
skipOnRestore = False
skipUpgrade = False

class DatabaseError(Exception):
    pass

class BadFileFormatError(DatabaseError):
    pass

# _BootStrapClass is used to as the initial class when we restore an object.
class _BootStrapClass:
    pass

class SavableObject:
    """Object that can be safely pickled and saved to disk.  

    Member variables:

    classString -- specifies the class this object was converted from.  
    savedData -- dict that stores the data we've saved.
    
    The SavableObject class is guarenteed to never change.  This means we can
    always safely unpickle them.
    """

    def __init__(self, classString):
        self.classString = classString
        self.savedData = {}

class ConverterBase(object):
    """Base class for SavableConverter and SavableUnconverter.  It handles the
    common tasks relating to converting the database to/from SavableObjects.
    This include stuff like walking the object hierarchy, handling circular
    references, keeping track of the path, etc.

    The subclasses of ConverterBase are responsible for creating a
    convertObject method, and adding validation to the convertData method
    (SavableConverter does validation at the begining, SavableUnconverter does
    it at the end).
    """

    def __init__(self, objectSchemas=None):
        """Contruct a converter.  object schemas is a list of ObjectSchema
        objects to use.  If none is given (the default), the schemas will be
        taken from schema.objectSchemas.
        """

        if objectSchemas is None:
            objectSchemas = schema_mod.objectSchemas

        self.objectSchemaLookup = {}
        self.classesToStrings = {}
        self.stringsToClasses = {}
        for os in objectSchemas:
            self.stringsToClasses[os.classString] = os.klass
            self.classesToStrings[os.klass] = os.classString
            self.objectSchemaLookup[os.klass] = os

    def convertData(self, data, schema, path=""):
        """Convert one piece of data.

        Arguments:
            data -- piece of data to be converted
            schema -- schema that the data should conform to
            path -- string describing how we got to this object.  Its format
                is totally arbitrary, we just use it to help debug validation
                errors.
        """

        try:
            self.preValidate(data, schema)
        except schema_mod.ValidationError, e:
            self.handleValidationError(e, data, path, schema)

        if data is None:
            rv = None
        elif isinstance(schema, schema_mod.SchemaSimpleItem):
            rv = data
        elif isinstance(schema, schema_mod.SchemaList):
            rv = self.convertList(data, schema, path)
        elif isinstance(schema, schema_mod.SchemaDict):
            rv = self.convertDict(data, schema, path)
        elif isinstance(schema, schema_mod.SchemaObject):
            rv = self.convertObject(data, schema, path)
        else:
            raise ValueError("%s has an unknown SchemaItem type" % schema)

        try:
            self.postValidate(rv, schema)
        except schema_mod.ValidationError, e:
            self.handleValidationError(e, data, path, schema)
        return rv

    def convertList(self, list, schema, path):
        childSchema = schema.childSchema
        rv = []
        for i in xrange(len(list)):
            child = list[i]
            newPath = path + "\n[%d] -> %s" % (i, child)
            rv.append(self.convertData(child, childSchema, newPath))
        return rv

    def convertDict(self, dict, schema, path):
        keySchema = schema.keySchema
        valueSchema = schema.valueSchema
        rv = {}
        for key, value in dict.items():
            # convert the key
            newPath = path + "\nkey: %s" % key
            newKey = self.convertData(key, keySchema, newPath)
            # convert the value
            newPath = path + "\n{%s} -> %s" % (key, value)
            newValue = self.convertData(value, valueSchema, newPath)
            # put it together
            rv[newKey] = newValue
        return rv

    def convertObjectList(self, objects):
        """Convert a list of objects.  This is the top-level method that the
        saveDatabase and restoreDatabase methods use to convert a list of
        DDBObjects to/from SavableObjects.
        """

        retval = []
        self.memory = {}
        for object, schema in self.prepareObjectList(objects):
            path = "%s" % object
            retval.append(self.convertData(object, schema, path))
        self.onPostConversion()
        return retval

    def convertObject(self, object, schema, path):
        if id(object) in self.memory:
            return self.memory[id(object)]

        # NOTE: we can't use the schema variable for anything here because
        # object might be a subclass of the class specified in schema.
        # Instead we call getObjectSchema() and use the info from there.

        try:
            objectSchema = self.getObjectSchema(object)
            convertedObject = self.makeNewConvert(objectSchema.classString)
            self.memory[id(object)] = convertedObject

            for name, schema in objectSchema.fields:
                data = self.getSourceAttr(object, name)
                try:
                    dataStr = str(data)
                except Exception, e:
                    # this will happen when data is invalid unicode
                    dataStr = "<couldn't convert (%s)>" % e
                newPath = path + "\n%s -> %s" % (name, dataStr)
                convertedData = self.convertData(data, schema, newPath)
                self.setTargetAttr(convertedObject, name, convertedData)
            return convertedObject
        except schema_mod.ValidationError, e:
            self.handleValidationError(e, object, path, schema)


    # Methods that may be overridden by SavableConverter/SavableUnconverter
    def preValidate(self, data, schema):
        """Can be used to validate that a piece of data that is about to be
        converted matches the schema for it.
        """
        pass

    def postValidate(self, converted, schema):
        """Can be used to validate that a converted piece of data matches the
        schema for it.
        """
        pass

    def getSourceAttr(self, object, attrName):
        """Retrive the value of an attribute on a source object."""
        try:
            return getattr(object, attrName)
        except AttributeError:
            msg = "%s doesn't have the %s attribute" % (object, attrName)
            raise schema_mod.ValidationError(msg)

    def setTargetAttr(self, object, attrName, attrValue):
        """Set the value of an attribute on a target object."""
        setattr(object, attrName, attrValue)

    def handleValidationError(self, e, object, path, schema):
        reason = e.args[0]
        message = """\
Error validating object %r

Path:
%s

Schema: %s
Reason: %s""" % (object, path, schema, reason)
        raise schema_mod.ValidationError(message)

    def onPostConversion(self):
        """Called when the conversion process is done, just before
        we return the result."""
        pass

    # methods below here *must* be implemented by subclasses
    def getObjectSchema(self, object):
        """Get an ObjectSchema for a object to be converted."""

        raise NotImplementError()

    def prepareObjectList(self, objectList):
        """Do the prep work for convertObjectList.

        Given a list of objects, return a list of (object, schema) tuples
        that should be converted.
        """

        raise NotImplementError()

    def makeNewConvert(self, classString):
        """Construct a new object to use as our converted value.

        SavableConverter returns a SavableObject, SavableUnconverter returns a
        DDBObject.
        """
        raise NotImplementError()

class SavableConverter(ConverterBase):
    """Used to convert a list of DDBObjects into a list with the same
    structure, but with DDBObject converted to SavableObjects.
    """

    def prepareObjectList(self, objectList):
        rv = []
        for object in objectList:
            if object.__class__ in self.classesToStrings:
                rv.append((object, schema_mod.SchemaObject(object.__class__)))
        return rv

    def getObjectSchema(self, object):
        try:
            return self.objectSchemaLookup[object.__class__]
        except KeyError:
            # object passed schema.validate() because it was a subclass of the 
            # type we're trying to save, but we don't have an ObjectSchema for
            # it, so raise ValidationError here.
            msg = "No ObjectSchema for %s" % object.__class__
            raise schema_mod.ValidationError(msg)

    def preValidate(self, data, schema):
        schema.validate(data)

    def makeNewConvert(self, classString):
        return SavableObject(classString)

    def setTargetAttr(self, savable, attrName, attrValue):
        savable.savedData[attrName] = attrValue

class SavableUnconverter(ConverterBase):
    """Used to reverse the work of SavableConverter."""

    def prepareObjectList(self, objectList):
        rv = []
        for o in objectList:
            klass = self.stringsToClasses[o.classString]
            rv.append((o, schema_mod.SchemaObject(klass)))
        return rv

    def getObjectSchema(self, object):
        klass = self.stringsToClasses[object.classString]
        return self.objectSchemaLookup[klass]

    def makeNewConvert(self, classString):
        restored = _BootStrapClass()
        restored.__class__ = self.stringsToClasses[classString]
        return restored

    def getSourceAttr(self, savable, attrName):
        try:
            return savable.savedData[attrName]
        except KeyError:
            msg = "SavableObject: %s doesn't have %s " % (savable.classString,
                    attrName)
            raise schema_mod.ValidationError(msg)

    def postValidate(self, converted, schema):
        schema.validate(converted)

    def handleValidationError(self, e, object, path, schema):
        reason = e.args[0]
        message = """\
Error validating object %r
Will use data anyway, bad things may happen soon

Path:
%s

Schema: %s
Reason: %s""" % (object, path, schema, reason)
        raise schema_mod.ValidationWarning(message)

    def onPostConversion(self):
        if not skipOnRestore:
            for object in self.memory.values():
                if hasattr(object, 'onRestore'):
                    object.onRestore()

def objectsToSavables(objects, objectSchemas=None):
    """Transform a list of objects into something that we can save to disk.
    This means converting any DDBObjects into SavebleObjects.
    """

    saver = SavableConverter(objectSchemas)
    return saver.convertObjectList(objects)

def savablesToObjects(savedObjects, objectSchemas=None):
    """Reverses the work of objectsToSavables"""

    restorer = SavableUnconverter(objectSchemas)
    restorer.objectSchemas = objectSchemas
    return restorer.convertObjectList(savedObjects)

def saveObjectList(objects, pathname, objectSchemas=None, version=None):
    """Save a list of objects to disk."""

    if version is None:
        version = schema_mod.VERSION
    savableObjects = objectsToSavables(objects, objectSchemas)
    toPickle = (version, savableObjects)
    f = open(pathname, 'wb')
    f.write(FILEMAGIC)
    try:
        cPickle.dump(toPickle, f, cPickle.HIGHEST_PROTOCOL)
    finally:
        f.close()

def restoreObjectList(pathname, objectSchemas=None):
    """Restore a list of objects saved with saveObjectList."""

    f = open(pathname, 'rb')
    try:
        if f.read(len(FILEMAGIC)) != FILEMAGIC:
            msg = "%s doesn't seem to be a democracy database" % pathname
            raise BadFileFormatError(pathname)
        version, savedObjects = cPickle.load(f)
    finally:
        f.close()

    if not skipUpgrade:
        if version != schema_mod.VERSION:
            shutil.copyfile(pathname, pathname + '.beforeupgrade')
        databaseupgrade.upgrade(savedObjects, version)

    return savablesToObjects(savedObjects, objectSchemas)

backedUp = False

def saveDatabase(db=None, pathname=None, scheduleAnother=False):
    """Save a database object."""

    retval = False

    if db is None:
        db = database.defaultDatabase
    if pathname is None:
        pathname = config.get(prefs.DB_PATHNAME)

    pathname = os.path.expanduser(pathname)

    global backedUp
    if (not backedUp):
        try:
            shutil.copyfile(pathname, pathname + '.bak')
        except:
            pass
        else:
            backedUp = True

    tempPathname = pathname + '.temp'
    try:
        db.beginRead()
        try:
            objectsToSave = []
            for o in db.objects:
                objectsToSave.append(o[0])
            databasesanity.checkSanity(objectsToSave)
            saveObjectList(objectsToSave, tempPathname)
        finally:
            db.endRead()
        try:
            os.remove(pathname)
        except:
            pass
        os.rename(tempPathname, pathname)
    except IOError, err:
        print "IO Error"
        app.controller.getBackendDelegate().saveFailed(err.strerror)
    except:
        util.failedExn("While saving database")
    else:
        retval = True
    if scheduleAnother:
        eventloop.addTimeout(300, saveDatabase, "Database Save", args=(db, pathname, scheduleAnother))
    return retval

def restoreDatabase(db=None, pathname=None, convertOnFail=True):
    """Restore a database object."""

    if db is None:
        db = database.defaultDatabase
    if pathname is None:
        pathname = config.get(prefs.DB_PATHNAME)

    db.beginUpdate()
    try:
        pathname = os.path.expanduser(pathname)
        if not os.path.exists(pathname):
            # maybe we crashed in saveDatabase() after deleting the real file, but
            # before renaming the temp file?
            tempPathname = pathname + '.temp'
            if os.path.exists(tempPathname):
                os.rename(tempPathname, pathname)
            else:
                return # nope, there's no database to restore
    
        try:
            objects = restoreObjectList(pathname)
        except BadFileFormatError:
            if convertOnFail:
                print "trying to convert database from old version"
                olddatabaseupgrade.convertOldDatabase(pathname)
                objects = restoreObjectList(pathname)
                print "*** Conversion Successfull ***"
            else:
                raise
        except ImportError, e:
            if e.args == ("No module named storedatabase\r",):
                # this looks like an error caused by reading a file saved in text
                # mode on windows, let's try converting it.
                print "WARNING: trying to convert text-mode database"
                f = open(pathname, 'rt')
                data = f.read()
                f.close()
                f = open(pathname, 'wb')
                f.write(data.replace("\r\n", "\n"))
                f.close()
                objects = restoreObjectList(pathname)
            else:
                raise
    
        try:
            databasesanity.checkSanity(objects)
        except databasesanity.DatabaseInsaneError, e:
            util.failedExn("When restoring database", e)
            # if the database fails the sanity check, try to restore it anyway.
            # It's better than notheing
        db.restoreFromObjectList(objects)
    finally:
        db.endUpdate()
