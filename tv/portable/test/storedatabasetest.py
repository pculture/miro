import os
import tempfile
import unittest

import schema
import storedatabase

# sooo much easier to type...
from schema import SchemaString, SchemaInt, SchemaFloat
from schema import SchemaList, SchemaDict, SchemaObject

# create a dummy schemma
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

class Dog:
    def __init__(self, name, age, owner=None):
        self.name = name
        self.age = age
        self.owner = owner

class House:
    def __init__(self, address, color, occupants):
        self.address = address
        self.color = color
        self.occupants = occupants

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
    ]

class PCFProgramerSchema(HumanSchema):
    klass = PCFProgramer
    classString = 'pcf-programmer'
    fields = HumanSchema.fields + [
        ('position', SchemaString()),
        ('superpower', SchemaString()),
    ]

testObjectSchemas = [HumanSchema, DogSchema, HouseSchema, PCFProgramerSchema]

def installDummySchema():
    schema.VERSION = 1
    schema.objectSchemas = testObjectSchemas
    schema.stringsToClasses = dummyStringsToClasses
    schema._makeClassesToStrings()

class SchemaTest(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.lee = Human("lee", 25, 1.4, [], {'virtual bowling': 212})
        self.joe = Human("joe", 14, 1.4, [self.lee])
        self.forbesSt = House('45 Forbs St', 'Blue', [self.lee, self.joe])
        self.scruffy = Dog('Scruffy', 3, self.lee)
        self.spike = Dog('Spike', 4, owner=None)
        self.db = [ self.lee, self.joe, self.forbesSt, self.scruffy, 
            self.spike]
        self.savePath = tempfile.mktemp()

    def tearDown(self):
        try:
            os.unlink(self.savePath)
        except OSError:
            pass
        unittest.TestCase.tearDown(self)

    def addSubclassObjects(self):
        self.ben = PCFProgramer('ben', 25, 3.4, [], 'programmer',
                'Teleportation')
        self.holmes = PCFProgramer('ben', 25, 3.4, [], 'co-director', 
                'Mind Control')
        self.forbesSt.occupants.extend([self.ben, self.holmes])
        self.db.extend([self.ben, self.holmes])

class TestValidation(SchemaTest):
    def assertDbValid(self):
        storedatabase.saveObjectList(self.db, testObjectSchemas)

    def assertDbInvalid(self):
        self.assertRaises(schema.ValidationError,
                storedatabase.saveObjectList, self.db, testObjectSchemas)

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
        self.lee.friends = ['joe']
        self.assertDbInvalid()

    def testDictValidation(self):
        self.joe.high_scores['pong'] = "One Million"
        self.assertDbInvalid()
        del self.joe.high_scores['pong']
        self.joe.high_scores[1943] = 1234123
        self.assertDbInvalid()

    def testSubclassValidation(self):
        self.addSubclassObjects()
        self.assertDbValid()

class TestSave(SchemaTest):
    def testSimpleCircularReference(self):
        self.lee.friends = [self.joe]
        self.joe.friends = [self.lee]
        storedatabase.saveObjectList(self.db, testObjectSchemas)

    def testSaveToDisk(self):
        storedatabase.saveDatabase(self.db, self.savePath, testObjectSchemas)

    def testExtraObjectsAreIgnored(self):
        class EpherialObject:
            pass
        self.db.append(EpherialObject())
        storedatabase.saveObjectList(self.db, testObjectSchemas)

class TestRestore(SchemaTest):
    def testSaveThenRestore(self):
        storedatabase.saveDatabase(self.db, self.savePath, testObjectSchemas)
        db2 = storedatabase.restoreDatabase(self.savePath, testObjectSchemas)
        # check out the humans
        lee2, joe2, forbesSt2, scruffy2, spike2 = db2
        for attr in 'name', 'age', 'meters_tall', 'high_scores':
            self.assertEquals(getattr(self.lee, attr), getattr(lee2, attr))
            self.assertEquals(getattr(self.joe, attr), getattr(joe2, attr))
        self.assertEquals(joe2.friends, [lee2])
        # check out the house
        self.assertEquals(forbesSt2.address, '45 Forbs St')
        self.assertEquals(forbesSt2.color, 'Blue')
        self.assertEquals(forbesSt2.occupants, [lee2, joe2])
        # check out the dogs
        self.assertEquals(scruffy2.name, 'Scruffy')
        self.assertEquals(scruffy2.age, 3)
        self.assertEquals(spike2.name, 'Spike')
        self.assertEquals(spike2.age, 4)
        self.assertEquals(scruffy2.owner, lee2)
        self.assertEquals(spike2.owner, None)

    def testRestoreSubclasses(self):
        self.addSubclassObjects()
        storedatabase.saveDatabase(self.db, self.savePath, testObjectSchemas)
        db2 = storedatabase.restoreDatabase(self.savePath, testObjectSchemas)
        lee2, joe2, forbesSt2, scruffy2, spike2, ben2, holmes2 = db2
        for attr in ('name', 'age', 'meters_tall', 'high_scores', 'position',
                'superpower'):
            self.assertEquals(getattr(self.ben, attr), getattr(ben2, attr))
            self.assertEquals(getattr(self.holmes, attr), getattr(holmes2,
                attr))
        self.assertEquals(forbesSt2.occupants, [lee2, joe2, ben2, holmes2])

if __name__ == '__main__':
    unittest.main()
