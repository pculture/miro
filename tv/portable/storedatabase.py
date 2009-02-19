# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
import traceback
import shutil

from miro import config
from miro import database
from miro import databaseupgrade
from miro import prefs
from miro import util
from miro import schema as schema_mod
from miro import eventloop
from miro import dialogs
import logging
from zipfile import ZipFile
import tempfile
from random import randrange
import os.path
from miro.plat.utils import exit

# FIXME - bsddb3.db is never used
try:
    import bsddb.db
except ImportError:
    import bsddb3.db

# FIXME - why do we prefer pysqlite2 over sqlite3?
try:
    from pysqlite2 import dbapi2 as sql
except ImportError:
    import sqlite3 as sql

from miro.gtcache import gettext as _

from miro.clock import clock

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

class NotImplementError(DatabaseError):
    pass

# _BootStrapClass is used to as the initial class when we restore an object.
class _BootStrapClass:
    pass

class SavableObject:
    """Object that can be safely pickled and saved to disk.  

    Member variables:

    classString -- specifies the class this object was converted from.  
    savedData -- dict that stores the data we've saved.
    
    The SavableObject class is guaranteed to never change.  This means we can
    always safely unpickle them.
    """

    # This is a complete hack to prevent problems if data is saved with a
    # newer version of Miro and an older version of Miro tries to open it.
    # Now adays the name of this module is "miro.storedatabase", but for older
    # versions it's just "storedatabase".  Hacking the module name here
    # changes where pickle tries to unpickle it from.
    #
    # In both cases "storedatabase" works, because we try to unpickle it from
    # inside the miro directory.
    __module__ = 'storedatabase'

    def __init__(self, classString):
        self.classString = classString
        self.savedData = {}

    def __str__(self):
        return '<SavableObject: %s>' % self.classString

class ConverterBase(object):
    """Base class for SavableConverter and SavableUnconverter.  It handles the
    common tasks relating to converting the database to/from SavableObjects.
    This include stuff like walking the object hierarchy, handling circular
    references, keeping track of the path, etc.

    The subclasses of ConverterBase are responsible for creating a
    convertObject method, and adding validation to the convertData method
    (SavableConverter does validation at the beginning, SavableUnconverter does
    it at the end).
    """

    def __init__(self, objectSchemas=None):
        """Construct a converter.  object schemas is a list of ObjectSchema
        objects to use.  If none is given (the default), the schemas will be
        taken from miro.schema.objectSchemas.
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
            newPath = path + "\n[%d] -> %s" % (i, util.stringify(child))
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
            newPath = path + "\n{%s} -> %s" % (util.stringify(key), util.stringify(value))
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
        except schema_mod.ValidationError, e:
            self.handleValidationError(e, object, path, schema)

        convertedObject = self.makeNewConvert(objectSchema.classString)
        self.memory[id(object)] = convertedObject

        for name, schema in objectSchema.fields:
            try:
                data = self.getSourceAttr(object, name)
            except schema_mod.ValidationError, e:
                self.handleValidationError(e, object, path, schema)
            try:
                dataStr = str(data)
            except Exception, e:
                # this will happen when data is invalid unicode
                dataStr = "<couldn't convert (%s)>" % e
            newPath = path + "\n%s -> %s" % (util.stringify(name), util.stringify(dataStr))
            convertedData = self.convertData(data, schema, newPath)
            self.setTargetAttr(convertedObject, name, convertedData)
        return convertedObject


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
        """Retrieve the value of an attribute on a source object."""
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

oneSaver = SavableConverter()
oneRestorer = SavableUnconverter()

def objectToSavable(object):
    """Transform a list of objects into something that we can save to disk.
    This means converting any DDBObjects into SavebleObjects.
    """

    global oneSaver
    if object.__class__ in oneSaver.classesToStrings:
        oneSaver.memory = {}
        return oneSaver.convertObject(object, schema_mod.SchemaObject(object.__class__), "")
    else:
        return None

def savablesToObjects(savedObjects, objectSchemas=None):
    """Reverses the work of objectsToSavables"""

    restorer = SavableUnconverter(objectSchemas)
    restorer.objectSchemas = objectSchemas
    return restorer.convertObjectList(savedObjects)

def savableToObject(savedObject):
    """Transform a list of objects into something that we can save to disk.
    This means converting any DDBObjects into SavebleObjects.
    """

    global oneRestorer
    oneRestorer.memory = {}
    klass = oneRestorer.stringsToClasses[savedObject.classString]
    object = oneRestorer.convertObject(savedObject, schema_mod.SchemaObject(klass), "")
    oneRestorer.onPostConversion()
    return object

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

def loadPickle(pathname, objectSchemas=None):
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

def restoreObjectList(pathname, objectSchemas=None):
    """Restore a list of objects saved with saveObjectList."""

    return loadPickle (pathname, objectSchemas)

def getObjects(pathname, convertOnFail):
    """Restore a database object."""

    pathname = os.path.expanduser(pathname)
    if not os.path.exists(pathname):
        # maybe we crashed in saveDatabase() after deleting the real file, but
        # before renaming the temp file?
        tempPathname = pathname + '.temp'
        if os.path.exists(tempPathname):
            os.rename(tempPathname, pathname)
        else:
            return None # nope, there's no database to restore


    global skipOnRestore
    oldSkipOnRestore = skipOnRestore
    skipOnRestore = True
    try:
        objects = restoreObjectList(pathname)
    except BadFileFormatError:
        if convertOnFail:
            logging.info ("trying to convert database from old version")
            from miro import olddatabaseupgrade
            olddatabaseupgrade.convertOldDatabase(pathname)
            objects = restoreObjectList(pathname)
            logging.info ("*** Conversion Successful ***")
        else:
            raise
    except ImportError, e:
        if e.args == ("No module named storedatabase\r",):
            # this looks like an error caused by reading a file saved in text
            # mode on windows, let's try converting it.
            logging.info ("trying to convert text-mode database")
            f = open(pathname, 'rt')
            data = f.read()
            f.close()
            f = open(pathname, 'wb')
            f.write(data.replace("\r\n", "\n"))
            f.close()
            objects = restoreObjectList(pathname)
        else:
            raise

    from miro import databasesanity
    try:
        databasesanity.checkSanity(objects, quiet=True, 
                reallyQuiet=(not util.chatter))
    except databasesanity.DatabaseInsaneError, e:
        signals.system.failed_exn("When restoring database", e)
        # if the database fails the sanity check, try to restore it anyway.
        # It's better than nothing
    skipOnRestore = oldSkipOnRestore
    if not skipOnRestore:
        for object in objects:
            if hasattr(object, 'onRestore'):
                object.onRestore()
    return objects

def restoreDatabase(db=None, pathname=None, convertOnFail=True):
    if db is None:
        db = database.defaultDatabase
    if pathname is None:
        pathname = config.get(prefs.DB_PATHNAME)

    objects = getObjects (pathname, convertOnFail)
    if objects:
        db.restoreFromObjectList(objects)

VERSION_KEY = "Democracy Version"

class LiveStorageBDB:
    TRANSACTION_TIMEOUT = 10
    TRANSACTION_NAME = "Save database"

    def __init__(self, dbPath=None, restore=True):
        database.confirmDBThread()
        try:
            self.txn = None
            self.dc = None
            self.toUpdate = set()
            self.toRemove = set()
            self.errorState = False
            if dbPath is not None:
                self.dbPath = dbPath
            else:
                self.dbPath = config.get(prefs.BSDDB_PATHNAME)
            start = clock()
            self.openEmptyDB()
            if restore:
                try:
                    try:
                        self.db.open ("database")
                        self.version = int(self.db[VERSION_KEY])
                    except (bsddb.db.DBNoSuchFileError, KeyError):
                        self.closeInvalidDB()
                        try:
                            restoreDatabase()
                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except:
                            logging.exception ("Error restoring old database")
                        self.saveDatabase()
                    else:
                        self.loadDatabase()
                except (SystemExit, KeyboardInterrupt):
                    raise
                except databaseupgrade.DatabaseTooNewError:
                    raise
                except:
                    self.handleDatabaseLoadError()
            else:
                self.saveDatabase()
            # Since this is only used for upgrading, I'm commenting
            # this out --NN
            #
            # eventloop.addIdle(self.checkpoint, "Remove Unused Database Logs")
            end = clock()
            if end - start > 0.05 and util.chatter:
                logging.timing ("Database load slow: %.3f", end - start)
        except bsddb.db.DBNoSpaceError:
            exit(28)

    def dumpDatabase(self, db):
        from miro.download_utils import nextFreeFilename
        output = open (nextFreeFilename (os.path.join (config.get(prefs.SUPPORT_DIRECTORY), "database-dump.xml")), 'w')
        global indentation
        indentation = 0
        def indent():
            output.write('    ' * indentation)
        def output_object(o):
            global indentation
            indent()
            if o in memory:
                if o.savedData.has_key ('id'):
                    output.write('<%s id="%s"/>\n' % (o.classString, o.savedData['id']))
                else:
                    output.write('<%s/>\n' % (o.classString,))
                return
            memory.add(o)
            if o.savedData.has_key ('id'):
                output.write('<%s id="%s">\n' % (o.classString, o.savedData['id']))
            else:
                output.write('<%s>\n' % (o.classString,))
            indentation = indentation + 1
            for key in o.savedData:
                if key == 'id':
                    continue
                indent()
                output.write('<%s>' % (key,))
                value = o.savedData[key]
                if isinstance (value, SavableObject):
                    output.write ('\n')
                    indentation = indentation + 1
                    output_object(value)
                    indentation = indentation - 1
                    indent()
                elif isinstance (value, unicode):
                    output.write (value.encode('ascii', 'replace'))
                else:
                    output.write (str(value))
                output.write ('</%s>\n' % (key,))
            indentation = indentation - 1
            indent()
            output.write ('</%s>\n' % (o.classString,))
        output.write ('<?xml version="1.0"?>\n')
        output.write ('<database schema="%d">\n' % (schema_mod.VERSION,))
        indentation = indentation + 1
        for o in db:
            global memory
            memory = set()
            o = objectToSavable (o)
            if o is not None:
                output_object (o)
        indentation = indentation - 1
        output.write ('</database>\n')
        output.close()

    def handleDatabaseLoadError(self):
        database.confirmDBThread()
        logging.exception ("exception while loading database")
        self.closeInvalidDB()
        self.dbenv.close()
        self.saveInvalidDB()
        self.openEmptyDB()
        self.saveDatabase()

    def saveInvalidDB(self):
        dir = os.path.dirname(self.dbPath)
        saveName = "corrupt_database"
        i = 0
        while os.path.exists(os.path.join(dir, saveName)):
            i += 1
            saveName = "corrupt_database.%d" % i

        os.rename(self.dbPath, os.path.join(dir, saveName))

    def openEmptyDB(self):
        database.confirmDBThread()
        try:
            os.makedirs(self.dbPath)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            pass
        self.dbenv = bsddb.db.DBEnv()
        self.dbenv.set_flags (bsddb.db.DB_AUTO_COMMIT | bsddb.db.DB_TXN_NOSYNC, True)
        self.dbenv.set_lg_max (1024 * 1024)
        self.dbenv.open (self.dbPath, bsddb.db.DB_INIT_LOG | bsddb.db.DB_INIT_MPOOL | bsddb.db.DB_INIT_TXN | bsddb.db.DB_RECOVER | bsddb.db.DB_CREATE)
        self.db = bsddb.db.DB(self.dbenv)
        self.closed = False

    def closeInvalidDB(self):
        database.confirmDBThread()
        try:
            self.db.close()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            pass
        self.db = None

    def upgradeDatabase(self):
        database.confirmDBThread()
        logging.info ("Upgrading database...")
        savables = []
        cursor = self.db.cursor()
        while True:
            next = cursor.next()
            if next is None:
                break
            key, data = next
            if key != VERSION_KEY:
                try:
                    savable = cPickle.loads(data)
                    savables.append(savable)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    logging.info ('Error loading data in upgradeDatabase')
                    raise
        cursor.close()
        changed = databaseupgrade.upgrade(savables, self.version)
        
        txn = self.dbenv.txn_begin()
        if changed is None:
            self.rewriteDatabase(savables, txn)
        else:
            savables_set = set()
            for o in savables:
                savables_set.add(o)
            for o in changed:
                if o in savables_set:
                    data = cPickle.dumps(o,cPickle.HIGHEST_PROTOCOL)
                    self.db.put (str(o.savedData['id']), data, txn=txn)
                else:
                    try:
                        self.db.delete (str(o.savedData['id']))
                    except bsddb.db.DBNotFoundError:
                        # If an object was created and removed during
                        # upgrade, it won't be in the database to be
                        # removed, so catch the exception
                        pass
        self.version = schema_mod.VERSION
        self.db.put (VERSION_KEY, str(self.version), txn=txn)
        txn.commit()
        self.db.sync()

        objects = savablesToObjects (savables)
        db = database.defaultDatabase
        db.restoreFromObjectList(objects)

    def rewriteDatabase(self, savables, txn):
        """Delete, then rewrite the entire database.  savables is a list of
        SavableObjects that will be in the new database.  WARNING: This method
        will probably take a long time.
        """
        database.confirmDBThread()
        logging.info ("Rewriting database")
        cursor = self.db.cursor(txn=txn)
        while True:
            next = cursor.next()
            if next is None:
                break
            cursor.delete()
        cursor.close()
        for o in savables:
            data = cPickle.dumps(o,cPickle.HIGHEST_PROTOCOL)
            self.db.put (str(o.savedData['id']), data, txn=txn)

    def loadDatabase(self):
        database.confirmDBThread()
        upgrade = (self.version != schema_mod.VERSION)
        if upgrade:
            return self.upgradeDatabase()
        objects = []
        cursor = self.db.cursor()
        while True:
            next = cursor.next()
            if next is None:
                break
            key, data = next
            if key != VERSION_KEY:
                try:
                    savable = cPickle.loads(data)
                    object = savableToObject(savable)
                    objects.append(object)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    logging.info ("Error loading data in loadDatabase")
                    raise
        cursor.close()
        db = database.defaultDatabase
        db.restoreFromObjectList(objects)

    def saveDatabase(self):
        database.confirmDBThread()
        db = database.defaultDatabase
        self.txn = self.dbenv.txn_begin()
        self.db = bsddb.db.DB(self.dbenv)
        self.db.open ("database", flags = bsddb.db.DB_CREATE, dbtype = bsddb.db.DB_HASH, txn=self.txn)
        for o in db.objects:
            self.update(o[0])
        self.version = schema_mod.VERSION
        self.db.put (VERSION_KEY, str(self.version), txn=self.txn)
        self.txn.commit()
        self.txn = None
        self.db.sync()

    def sync(self):
        database.confirmDBThread()
        self.db.sync()

    def close(self):
        database.confirmDBThread()
        self.runUpdate()
        self.closed = True
        self.db.close()
        self.dbenv.close()

    def runUpdate(self):
        database.confirmDBThread()
        try:
            self.txn = self.dbenv.txn_begin()
            for object in self.toRemove:
                # If an object was created and removed between saves, it
                # won't be in the database to be removed, so catch the
                # exception
                try:
                    self.remove (object)
                except bsddb.db.DBNotFoundError:
                    pass
            for object in self.toUpdate:
                self.update (object)
            self.txn.commit()
            self.sync()
            self.txn = None
            self.dc = None
            self.toUpdate = set()
            self.toRemove = set()
            if self.errorState:
                title = _("%(appname)s database save succeeded",
                          {"appname": config.get(prefs.SHORT_APP_NAME)})
                description = _(
                    "The database has been successfully saved. It is now safe "
                    "to quit without losing any data."
                )
                dialogs.MessageBoxDialog(title, description).run()
                self.errorState = False
        except bsddb.db.DBNoSpaceError, err:
            if not self.errorState:
                title = _("%(appname)s database save failed",
                          {"appname": config.get(prefs.SHORT_APP_NAME)})
                description = _(
                    "%(appname)s was unable to save its database: Disk Full.\n"
                    "We suggest deleting files from the full disk or simply "
                    "deleting some movies from your collection.\n"
                    "Recent changes may be lost.",
                    {"appname": config.get(prefs.SHORT_APP_NAME)}
                )
                dialogs.MessageBoxDialog(title, description).run()
                self.errorState = True
            try:
                self.txn.abort()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                # if we tried to do a commit and failed an abort doesn't work
                pass
            self.txn = None
            self.dc = eventloop.addTimeout(self.TRANSACTION_TIMEOUT, self.runUpdate, self.TRANSACTION_NAME)
            

    def update (self, object):
        database.confirmDBThread()
        if self.closed:
            return
        if self.txn is None:
            self.toUpdate.add (object)
            if self.dc is None:
                self.dc = eventloop.addTimeout(self.TRANSACTION_TIMEOUT, self.runUpdate, self.TRANSACTION_NAME)
        else:
            savable = objectToSavable (object)
            if savable:
                key = str(object.id)
                data = cPickle.dumps(savable,cPickle.HIGHEST_PROTOCOL)
                self.db.put (key, data, txn=self.txn)

    def remove (self, object):
        database.confirmDBThread()
        if self.closed:
            return
        if self.txn is None:
            self.toRemove.add (object)
            try:
                self.toUpdate.remove (object)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
            if self.dc is None:
                self.dc = eventloop.addTimeout(self.TRANSACTION_TIMEOUT, self.runUpdate, self.TRANSACTION_NAME)
        else:
            self.db.delete (str(object.id), txn=self.txn)

    def checkpoint (self):
        database.confirmDBThread()
        try:
            if self.closed:
                return
            self.dbenv.txn_checkpoint()
            self.sync()
            for logfile in self.dbenv.log_archive(bsddb.db.DB_ARCH_ABS):
                try:
                    os.remove(logfile)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    pass
        except bsddb.db.DBNoSpaceError:
            pass
        eventloop.addTimeout(60, self.checkpoint, "Remove Unused Database Logs")
    def backupDatabase(self):
        return None

class LiveStorage:
    TRANSACTION_TIMEOUT = 10
    TRANSACTION_NAME = "Save database"

    def __init__(self, dbPath=None, restore=True):
        database.confirmDBThread()
        try:
            self.toUpdate = set()
            self.toRemove = set()
            self.errorState = False
            self.closed = True
            self.updating = False
            self.dc = None
            if dbPath is not None:
                self.dbPath = dbPath
            else:
                self.dbPath = config.get(prefs.SQLITE_PATHNAME)
            start = clock()
            SQLiteDBExists = os.access(self.dbPath, os.F_OK)
            self.openDatabase()
            if restore:
                try:
                    if SQLiteDBExists:
                        self.cursor.execute("SELECT serialized_value FROM dtv_variables WHERE name=:name",{'name':VERSION_KEY})
                        self.version = self.cursor.fetchone()
                        if self.version:
                            self.version = cPickle.loads(str(self.version[0]))
                        else:
                            self.version = schema_mod.VERSION
                        self.loadDatabase()
                    else:
                        self.version = None
                        if (os.access(config.get(prefs.BSDDB_PATHNAME), os.F_OK) or
                            os.access(config.get(prefs.DB_PATHNAME), os.F_OK)):

                            logging.info("Upgrading from previous version of database")
                            try:
                                LiveStorageBDB()
                            except (SystemExit, KeyboardInterrupt):
                                raise
                            except:
                                logging.warning("Upgrading from previous version of database failed")
                        self.saveDatabase()
                except (SystemExit, KeyboardInterrupt):
                    raise
                except databaseupgrade.DatabaseTooNewError:
                    raise
                except:
                    self.handleDatabaseLoadError()
            else:
                self.saveDatabase()
            eventloop.addIdle(self.checkpoint, "Remove Unused Database Logs")
            end = clock()
            if end - start > 0.05 and util.chatter:
                logging.timing("Database load slow: %.3f", end - start)
            try:
                import stat
                logging.info("Database size on disk (in bytes): %s", os.stat(self.dbPath)[stat.ST_SIZE])
                logging.info("Database object count: %s", database.defaultDatabase.count_objects())
            except IOError:
                logging.error("IOError when statting database file.")
        except sql.DatabaseError, e:
            logging.error(e)
            raise

    def openDatabase(self):
        logging.info("Connecting to %s" % self.dbPath)
        if not os.path.isdir(os.path.dirname(self.dbPath)):
            os.makedirs(os.path.dirname(self.dbPath))

        # have to convert this from a unicode to a utf-8 encoded string because 
        # otherwise sql.connect fails if there are non-ascii characters
        self.conn = sql.connect(self.dbPath.encode("utf-8"), isolation_level=None)
        self.closed = False
        self.cursor = self.conn.cursor()

        # In the future, we may need a way to upgrade this
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in self.cursor]
        if 'dtv_objects' not in tables:
            self.cursor.execute("""CREATE TABLE dtv_objects(
            id INTEGER PRIMARY KEY NOT NULL,
            serialized_object BLOB NOT NULL UNIQUE
);""")
        if 'dtv_variables' not in tables:
            self.cursor.execute("""CREATE TABLE dtv_variables(
            name TEXT PRIMARY KEY NOT NULL,
            serialized_value BLOB NOT NULL
    );""")

    def dumpDatabase(self, db):
        from miro.download_utils import nextFreeFilename
        output = open (nextFreeFilename (os.path.join (config.get(prefs.SUPPORT_DIRECTORY), "database-dump.xml")), 'w')
        global indentation
        indentation = 0
        def indent():
            output.write('    ' * indentation)
        def output_object(o):
            global indentation
            indent()
            if o in memory:
                if o.savedData.has_key ('id'):
                    output.write('<%s id="%s"/>\n' % (o.classString, o.savedData['id']))
                else:
                    output.write('<%s/>\n' % (o.classString,))
                return
            memory.add(o)
            if o.savedData.has_key ('id'):
                output.write('<%s id="%s">\n' % (o.classString, o.savedData['id']))
            else:
                output.write('<%s>\n' % (o.classString,))
            indentation = indentation + 1
            for key in o.savedData:
                if key == 'id':
                    continue
                indent()
                output.write('<%s>' % (key,))
                value = o.savedData[key]
                if isinstance (value, SavableObject):
                    output.write ('\n')
                    indentation = indentation + 1
                    output_object(value)
                    indentation = indentation - 1
                    indent()
                elif isinstance (value, unicode):
                    output.write (value.encode('ascii', 'replace'))
                else:
                    output.write (str(value))
                output.write ('</%s>\n' % (key,))
            indentation = indentation - 1
            indent()
            output.write ('</%s>\n' % (o.classString,))
        output.write ('<?xml version="1.0"?>\n')
        output.write ('<database schema="%d">\n' % (schema_mod.VERSION,))
        indentation = indentation + 1
        for o in db:
            global memory
            memory = set()
            o = objectToSavable (o)
            if o is not None:
                output_object (o)
        indentation = indentation - 1
        output.write ('</database>\n')
        output.close()

    def backupDatabase(self):
        # backs up the database and support directories to a zip file
        # returns the name of the zip file
        logging.info("Attempting to back up database")
        if not self.closed:
            try:
                self.conn.close()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                traceback.print_exc()
        try:
            try:
                tempfilename = os.path.join(tempfile.gettempdir(),("%012ddatabasebackup.zip"%randrange(0,999999999999)))
                zipfile = ZipFile(tempfilename,"w")
                for root, dirs, files in os.walk(config.get(prefs.SUPPORT_DIRECTORY)):
                    if ((os.path.normpath(root) !=
                        os.path.normpath(config.get(prefs.ICON_CACHE_DIRECTORY)))
                        and not os.path.islink(root)):
                        relativeroot = root[len(config.get(prefs.SUPPORT_DIRECTORY)):]
                        while len(relativeroot)>0 and relativeroot[0] in ['/','\\']:
                            relativeroot = relativeroot[1:]
                        for filen in files:
                            if not os.path.islink(os.path.join(root,filen)):
                                zipfile.write(os.path.join(root,filen),
                                              os.path.join(relativeroot, filen).encode('ascii','replace'))
                zipfile.close()
                logging.info("Database backed up to %s" % tempfilename)
                return tempfilename
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                traceback.print_exc()
        finally:
            if not self.closed:
                # have to convert this from a unicode to a utf-8 encoded string because 
                # otherwise sql.connect fails if there are non-ascii characters
                self.conn = sql.connect(self.dbPath.encode("utf-8"), isolation_level=None)
                self.cursor = self.conn.cursor()
        return None

    def handleDatabaseLoadError(self):
        database.confirmDBThread()
        logging.exception ("exception while loading database")
        self.closeInvalidDB()
        self.saveInvalidDB()
        self.saveDatabase()

    def saveInvalidDB(self):
        dir = os.path.dirname(self.dbPath)
        saveName = "corrupt_database"
        i = 0
        while os.path.exists(os.path.join(dir, saveName)):
            i += 1
            saveName = "corrupt_database.%d" % i

        os.rename(self.dbPath, os.path.join(dir, saveName))

    def closeInvalidDB(self):
        database.confirmDBThread()
        self.conn.close()
        self.conn = None

    def upgradeDatabase(self):
        database.confirmDBThread()
        self.updating = True
        self.cursor.execute("BEGIN TRANSACTION")
        try:

            savables = []
            self.cursor.execute("SELECT id, serialized_object FROM dtv_objects")
            for next in self.cursor:
                key, data = next
                try:
                    savable = cPickle.loads(str(data))
                    savables.append(savable)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    logging.info ('Error loading data in upgradeDatabase')
                    raise
            changed = databaseupgrade.upgrade(savables, self.version)
        
            if changed is None:
                self.rewriteDatabase(savables)
            else:
                savables_set = set()
                for o in savables:
                    savables_set.add(o)
                for o in changed:
                    if o in savables_set:
                        data = cPickle.dumps(o,cPickle.HIGHEST_PROTOCOL)
                        self.cursor.execute("REPLACE INTO dtv_objects (id, serialized_object) VALUES (?,?)",(int(o.savedData['id']), buffer(data)))
                    else:
                        self.cursor.execute("DELETE FROM dtv_objects WHERE id=?", (int(o.savedData['id']),))
            self.version = schema_mod.VERSION
            self.cursor.execute("REPLACE INTO dtv_variables (name, serialized_value) VALUES (?,?)",(VERSION_KEY, buffer(cPickle.dumps(self.version,cPickle.HIGHEST_PROTOCOL))))

            objects = savablesToObjects (savables)
            db = database.defaultDatabase
            db.restoreFromObjectList(objects)
        finally:
            self.updating = False
            self.cursor.execute("COMMIT")

    def rewriteDatabase(self, savables):
        """Delete, then rewrite the entire database.  savables is a list of
        SavableObjects that will be in the new database.  WARNING: This method
        will probably take a long time.
        """
        database.confirmDBThread()
        logging.info ("Rewriting database")
        if not self.updating:
            self.cursor.execute("BEGIN TRANSACTION")
        try:
            self.cursor.execute("DELETE FROM dtv_objects")
            for o in savables:
                data = cPickle.dumps(o,cPickle.HIGHEST_PROTOCOL)
                self.cursor.execute("REPLACE INTO dtv_objects (id, serialized_object) VALUES (?,?)",(int(o.savedData['id']), buffer(data)))
        finally:
            if not self.updating:
                self.cursor.execute("COMMIT")

    def loadDatabase(self):
        database.confirmDBThread()
        upgrade = (self.version != schema_mod.VERSION)
        if upgrade:
            return self.upgradeDatabase()
        objects = []
        self.cursor.execute("SELECT id, serialized_object FROM dtv_objects")
        while True:
            next = self.cursor.fetchone()
            if next is None:
                break
            key, data = next
            try:
                savable = cPickle.loads(str(data))
                object = savableToObject(savable)
                objects.append(object)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                logging.info ("Error loading data in loadDatabase")
                raise
        self.cursor.close()
        db = database.defaultDatabase
        db.restoreFromObjectList(objects)

    def saveDatabase(self):
        database.confirmDBThread()
        db = database.defaultDatabase
        self.updating = True
        self.cursor.execute("BEGIN TRANSACTION")
        try:
            self.cursor.execute("DELETE FROM dtv_objects WHERE 1=1")
            for o in db.objects:
                self.update(o[0])
            self.version = schema_mod.VERSION
            self.cursor.execute("REPLACE INTO dtv_variables (name, serialized_value) VALUES (?,?)",(VERSION_KEY, buffer(cPickle.dumps(self.version,cPickle.HIGHEST_PROTOCOL))))
        finally:
            self.updating = False
            self.cursor.execute("COMMIT")

    def sync(self):
        database.confirmDBThread()

    def close(self):
        database.confirmDBThread()
        self.cursor.execute("VACUUM")
        self.runUpdate()
        self.closed = True
        self.cursor.close()
        self.conn.close()

    def runUpdate(self):
        database.confirmDBThread()
        try:
            self.updating = True
            self.cursor.execute("BEGIN TRANSACTION")
            try:
                for object in self.toRemove:
                    # If an object was created and removed between saves, it
                    # won't be in the database to be removed, so catch the
                    # exception
                    try:
                        self.remove (object)
                    except sql.DatabaseError, e:
                        #logging.error("SQL ERROR %s" % e)
                        pass
                for object in self.toUpdate:
                    self.update (object)
            finally:
                self.updating = False
                self.cursor.execute("COMMIT")
            self.toUpdate = set()
            self.toRemove = set()
            if self.errorState:
                title = _("%(appname)s database save succeeded",
                          {"appname": config.get(prefs.SHORT_APP_NAME)})
                description = _(
                    "The database has been successfully saved. It is now safe to quit "
                    "without losing any data."
                )
                dialogs.MessageBoxDialog(title, description).run()
                self.errorState = False
        except sql.DatabaseError, e:
            print e
            if not self.errorState:
                title = _("%(appname)s database save failed",
                          {"appname": config.get(prefs.SHORT_APP_NAME)})
                description = _(
                    "%(appname)s was unable to save its database: Disk Full.\n"
                    "We suggest deleting files from the full disk or simply deleting "
                    "some movies from your collection.\n"
                    "Recent changes may be lost.",
                    {"appname": config.get(prefs.SHORT_APP_NAME)}
                )
                dialogs.MessageBoxDialog(title, description).run()
                self.errorState = True
                self.updating=False
        self.updating=False
        self.dc = eventloop.addTimeout(self.TRANSACTION_TIMEOUT, self.runUpdate, self.TRANSACTION_NAME)
            

    def update (self, object):
        database.confirmDBThread()
        if self.closed:
            return
        if not self.updating:
            self.toUpdate.add (object)
            if self.dc is None:
                self.dc = eventloop.addTimeout(self.TRANSACTION_TIMEOUT, self.runUpdate, self.TRANSACTION_NAME)
        else:
            savable = objectToSavable (object)
            if savable:
                key = int(object.id)
                data = cPickle.dumps(savable,cPickle.HIGHEST_PROTOCOL)
                self.cursor.execute("REPLACE INTO dtv_objects (id, serialized_object) VALUES (?,?)",(int(key), buffer(data)))

    def remove (self, object):
        database.confirmDBThread()
        if self.closed:
            return
        if not self.updating:
            self.toRemove.add (object)
            try:
                self.toUpdate.remove (object)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
            if self.dc is None:
                self.dc = eventloop.addTimeout(self.TRANSACTION_TIMEOUT, self.runUpdate, self.TRANSACTION_NAME)
        else:
            self.cursor.execute("DELETE FROM dtv_objects WHERE id=?", (int(object.id),))

    def checkpoint (self):
        database.confirmDBThread()
        # I don't think we have to do anything here for SQLite
        eventloop.addTimeout(60, self.checkpoint, "Remove Unused Database Logs")
