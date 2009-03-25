from datetime import datetime
import os
import tempfile
import unittest

from miro import database
from miro import databaseupgrade
from miro import item
from miro import feed
from miro import schema
import shutil
from miro import storedatabase

from miro.test.framework import MiroTestCase
# sooo much easier to type...
from miro.schema import SchemaString, SchemaInt, SchemaFloat, SchemaSimpleContainer
from miro.schema import SchemaList, SchemaDict, SchemaObject

# create a dummy schema
class Human:
    def __init__(self, name, age, meters_tall, friends, high_scores = None):
        self.name = name
        self.age = age
        self.meters_tall = meters_tall
        self.friends = friends
        if high_scores is None:
            self.high_scores = {}
        else:
            self.high_scores = high_scores

class RestorableHuman(Human):
    def onRestore(self):
        self.iveBeenRestored = True

class Dog:
    def __init__(self, name, age, owner=None):
        self.name = name
        self.age = age
        self.owner = owner

class House:
    def __init__(self, address, color, occupants, stuff=None):
        self.address = address
        self.color = color
        self.occupants = occupants
        self.stuff = stuff

class PCFProgramer(Human):
    def __init__(self, name, age, meters_tall, friends, position, superpower,
            high_scores = None):
        Human.__init__(self, name, age, meters_tall, friends, high_scores)
        self.position = position
        self.superpower = superpower

class HumanSchema(schema.ObjectSchema):
    klass = Human
    classString = 'human'
    fields = [
        ('name', SchemaString()),
        ('age', SchemaInt()),
        ('meters_tall', SchemaFloat()),
        ('friends', SchemaList(SchemaObject(Human))),
        ('high_scores', SchemaDict(SchemaString(), SchemaInt())),
    ]

class RestorableHumanSchema(HumanSchema):
    klass = RestorableHuman
    classString = 'restorable-human'

class DogSchema(schema.ObjectSchema):
    klass = Dog
    classString = 'dog'
    fields = [
        ('name', SchemaString()),
        ('age', SchemaInt()),
        ('owner', SchemaObject(Human, noneOk=True)),
    ]

class HouseSchema(schema.ObjectSchema):
    klass = House
    classString = 'house'
    fields = [
        ('address', SchemaString()),
        ('color', SchemaString()),
        ('occupants', SchemaList(SchemaObject(Human))),
        ('stuff', SchemaSimpleContainer(noneOk=True)),
    ]

class PCFProgramerSchema(HumanSchema):
    klass = PCFProgramer
    classString = 'pcf-programmer'
    fields = HumanSchema.fields + [
        ('position', SchemaString()),
        ('superpower', SchemaString()),
    ]

testObjectSchemas = [HumanSchema, DogSchema, HouseSchema, PCFProgramerSchema,
    RestorableHumanSchema]

class SchemaTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        storedatabase.skipUpgrade = True
        self.lee = Human(u"lee", 25, 1.4, [], {u'virtual bowling': 212})
        self.joe = Human(u"joe", 14, 1.4, [self.lee])
        self.forbesSt = House(u'45 Forbs St', u'Blue', [self.lee, self.joe],
                {'view': u'pretty', 'next-party': datetime(2005, 4, 5)})
        self.scruffy = Dog(u'Scruffy', 3, self.lee)
        self.spike = Dog(u'Spike', 4, owner=None)
        self.db = [ self.lee, self.joe, self.forbesSt, self.scruffy, 
            self.spike]
        self.savePath = tempfile.mktemp()

    def tearDown(self):
        storedatabase.skipUpgrade = False
        try:
            os.unlink(self.savePath)
        except OSError:
            pass
        MiroTestCase.tearDown(self)

    def addSubclassObjects(self):
        self.ben = PCFProgramer(u'ben', 25, 3.4, [], u'programmer',
                u'Teleportation')
        self.holmes = PCFProgramer(u'ben', 25, 3.4, [], u'co-director', 
                u'Mind Control')
        self.forbesSt.occupants.extend([self.ben, self.holmes])
        self.db.extend([self.ben, self.holmes])

class TestValidation(SchemaTest):
    def assertDbValid(self):
        storedatabase.objectsToSavables(self.db, testObjectSchemas)

    def assertDbInvalid(self):
        self.assertRaises(schema.ValidationError,
                storedatabase.objectsToSavables, self.db, testObjectSchemas)

    def tesntValidDb(self):
        self.assertDbValid()

    def testNoneValues(self):
        self.lee.age = None
        self.assertDbInvalid()
        self.lee.age = 25
        self.scruffy.owner = None
        self.assertDbValid()

    def testIntValidation(self):
        self.lee.age = '25'
        self.assertDbInvalid()
        self.lee.age = 25L
        self.assertDbValid()

    def testStringValidation(self):
        self.lee.name = 133
        self.assertDbInvalid()
        self.lee.name = u'lee'
        self.assertDbValid()

    def testFloatValidation(self):
        self.lee.meters_tall = 3
        self.assertDbInvalid()

    def testListValidation(self):
        self.lee.friends = [u'joe']
        self.assertDbInvalid()

    def testDictValidation(self):
        self.joe.high_scores['pong'] = u"One Million"
        self.assertDbInvalid()
        del self.joe.high_scores['pong']
        self.joe.high_scores[1943] = 1234123
        self.assertDbInvalid()

    def testSubclassValidation(self):
        self.addSubclassObjects()
        self.assertDbValid()
        class HumanSubclassWithoutObjectSchema(Human):
            pass
        jimmy = HumanSubclassWithoutObjectSchema(u"Luc", 23, 3.4, [])
        self.joe.friends.append(jimmy)
        self.assertDbInvalid()

class TestSave(SchemaTest):
    def testSimpleCircularReference(self):
        self.lee.friends = [self.joe]

    def testSaveToDisk(self):
        storedatabase.saveObjectList(self.db, self.savePath,
                testObjectSchemas)

    def testExtraObjectsAreIgnored(self):
        class EpherialObject:
            pass
        self.db.append(EpherialObject())
        storedatabase.objectsToSavables(self.db, testObjectSchemas)

class TestRestore(SchemaTest):
    def testSaveThenRestore(self):
        storedatabase.saveObjectList(self.db, self.savePath,
                testObjectSchemas)
        db2 = storedatabase.restoreObjectList(self.savePath,
                testObjectSchemas)
        # check out the humans
        lee2, joe2, forbesSt2, scruffy2, spike2 = db2
        for attr in 'name', 'age', 'meters_tall', 'high_scores':
            self.assertEquals(getattr(self.lee, attr), getattr(lee2, attr))
            self.assertEquals(getattr(self.joe, attr), getattr(joe2, attr))
        self.assertEquals(joe2.friends, [lee2])
        # check out the house
        self.assertEquals(forbesSt2.address, u'45 Forbs St')
        self.assertEquals(forbesSt2.color, u'Blue')
        self.assertEquals(forbesSt2.occupants, [lee2, joe2])
        self.assertEquals(forbesSt2.stuff,
                {'view': u'pretty', 'next-party': datetime(2005, 4, 5)})
        # check out the dogs
        self.assertEquals(scruffy2.name, u'Scruffy')
        self.assertEquals(scruffy2.age, 3)
        self.assertEquals(spike2.name, u'Spike')
        self.assertEquals(spike2.age, 4)
        self.assertEquals(scruffy2.owner, lee2)
        self.assertEquals(spike2.owner, None)

    def testRestoreSubclasses(self):
        self.addSubclassObjects()
        storedatabase.saveObjectList(self.db, self.savePath, testObjectSchemas)
        db2 = storedatabase.restoreObjectList(self.savePath, testObjectSchemas)
        lee2, joe2, forbesSt2, scruffy2, spike2, ben2, holmes2 = db2
        for attr in ('name', 'age', 'meters_tall', 'high_scores', 'position',
                'superpower'):
            self.assertEquals(getattr(self.ben, attr), getattr(ben2, attr))
            self.assertEquals(getattr(self.holmes, attr), getattr(holmes2,
                attr))
        self.assertEquals(forbesSt2.occupants, [lee2, joe2, ben2, holmes2])

    def testOnRestoreCalled(self):
        resto = RestorableHuman(u'resto', 23, 1.3, [])
        self.db.append(resto)
        storedatabase.saveObjectList(self.db, self.savePath, testObjectSchemas)
        db2 = storedatabase.restoreObjectList(self.savePath, testObjectSchemas)
        lee2, joe2, forbesSt2, scruffy2, spike2, resto2, = db2
        self.assertEquals(resto2.name, u'resto')
        self.assert_(hasattr(resto2, 'iveBeenRestored'))
        self.assertEquals(resto2.iveBeenRestored, True)

class UpgradeTest(SchemaTest):
    def setUp(self):
        super(UpgradeTest, self).setUp()
        # save the actual version and upgrade functions
        self.realSchemaVersion = schema.VERSION
        try:
            self.realUpgrade2 = databaseupgrade.upgrade2
        except AttributeError:
            self.realUpgrade2 = None
        try:
            self.realUpgrade3 = databaseupgrade.upgrade3
        except AttributeError:
            self.realUpgrade3 = None
        # save the database, this is our "old" version
        schema.VERSION = 1
        storedatabase.saveObjectList(self.db, self.savePath,
                testObjectSchemas)
        # install a fake upgrade path
        schema.VERSION = 3
        def upgrade2(objects):
            for o in objects:
                if o.classString == 'human':
                    o.savedData['name'] = "Sir %s" % o.savedData['name']
        def upgrade3(objects):
            for o in objects:
                if o.classString == 'dog':
                    o.savedData['color'] = u"Unknown"
        databaseupgrade.upgrade2 = upgrade2
        databaseupgrade.upgrade3 = upgrade3
        storedatabase.skipUpgrade = False
        class DogSchema2(schema.ObjectSchema):
            klass = Dog
            classString = 'dog'
            fields = [
                ('name', SchemaString()),
                ('age', SchemaInt()),
                ('owner', SchemaObject(Human, noneOk=True)),
                ('color', SchemaString()),
            ]
        self.nextGenObjectSchemas = [ HumanSchema, DogSchema2, HouseSchema,
            PCFProgramerSchema, RestorableHumanSchema ]

    def tearDown(self):
        if self.realUpgrade3 is not None:
            databaseupgrade.upgrade3 = self.realUpgrade3
        else:
            del databaseupgrade.upgrade3
        if self.realUpgrade2 is not None:
            databaseupgrade.upgrade2 = self.realUpgrade2
        else:
            del databaseupgrade.upgrade2
        schema.VERSION = self.realSchemaVersion
        super(UpgradeTest, self).tearDown()

    def testChanges(self):
        newDb = storedatabase.restoreObjectList(self.savePath,
                self.nextGenObjectSchemas)
        for object in newDb:
            if isinstance(object, Human):
                self.assert_(object.name.startswith("Sir "))
            elif isinstance(object, Dog):
                self.assert_('color' in object.__dict__)

    def testRestoreWithNewerVersion(self):
        newDb = storedatabase.restoreObjectList(self.savePath,
                self.nextGenObjectSchemas)
        storedatabase.saveObjectList(newDb, self.savePath,
                testObjectSchemas)
        # saved database is now version 3
        schema.VERSION = 1
        self.assertRaises(databaseupgrade.DatabaseTooNewError,
                storedatabase.restoreObjectList, self.savePath, 
                testObjectSchemas)

    def testSavingUpgradedDb(self):
        newDb = storedatabase.restoreObjectList(self.savePath,
                self.nextGenObjectSchemas)
        storedatabase.saveObjectList(newDb, self.savePath,
                self.nextGenObjectSchemas)
        newDb = storedatabase.restoreObjectList(self.savePath,
                self.nextGenObjectSchemas)

class LiveStorageTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        storedatabase.skipUpgrade = True
        self.savePath = os.path.join(tempfile.gettempdir(),
                'democracy-temp-db')
        self.database = database.defaultDatabase
        self.database.liveStorage = storedatabase.LiveStorage(self.savePath,
                restore=False)

    def tearDown(self):
        storedatabase.skipUpgrade = False
        try:
            self.database.liveStorage.close()
            self.database.liveStorage = None
        except:
            pass
        try:
            shutil.rmtree(self.savePath);
        except:
            pass
        MiroTestCase.tearDown(self)


class TestConstraintChecking(LiveStorageTest):
    def testConstraintCheck(self):
        # test creating an item with an invalid feed id
        self.assertRaises(database.DatabaseConstraintError,
                item.Item, feed_id=123123123, entry={})

    def testConstraintCheck2(self):
        # test changing an item to have an invalid feed id
        f = feed.Feed(u"http://feed.uk")
        i = item.Item({}, feed_id=f.id)
        i.feed_id = 123456789
        self.assertRaises(database.DatabaseConstraintError, i.signalChange)

    def testUpdateAfterRemove(self):
        obj = database.DDBObject()
        obj.remove()
        self.assertRaises(database.DatabaseConstraintError, obj.signalChange)

class TestHighLevelFunctions(LiveStorageTest):
    def setUp(self):
        LiveStorageTest.setUp(self)
        self.f = feed.Feed(u"http://feed.uk")
        i = item.Item({}, feed_id=self.f.id)
        i2 = item.Item({}, feed_id=self.f.id)
        self.objects = [self.f, self.f.actualFeed, self.f.icon_cache,
                i.icon_cache, i, i2.icon_cache, i2 ]

    def checkDatabaseIsTheSame(self):
        self.assertEquals(len(self.objects), len(self.database.objects))

        # We can't directly compare objects, since that would compare their
        # ids.  As a sanity test, compare that we have the same classes coming
        # out and we did going in.
        i = 0
        for newObject, copy in self.database.objects:
            self.assertEquals(newObject.__class__, self.objects[i].__class__)
            self.assertEquals(newObject.id, self.objects[i].id)
            i += 1

    def saveDatabase(self):
        self.database.liveStorage.saveDatabase()

    def restoreDatabase(self):
        database.resetDefaultDatabase()
        self.database.liveStorage = storedatabase.LiveStorage(self.savePath,
                restore=True)

    def testSaveThenRestore(self):
        self.saveDatabase()
        self.restoreDatabase()
        self.checkDatabaseIsTheSame()

    def testUpdateThenRestore(self):
        i3 = item.Item({}, feed_id=self.f.id)
        self.saveDatabase()
        i3.remove()
        i3 = item.Item({}, feed_id=self.f.id)
        self.objects.append(i3.icon_cache)
        self.objects.append(i3)
        self.database.liveStorage.runUpdate()
        self.restoreDatabase()
        self.checkDatabaseIsTheSame()


if __name__ == '__main__':
    unittest.main()
