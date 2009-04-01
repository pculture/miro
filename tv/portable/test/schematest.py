import datetime
import os
import tempfile
import time
import unittest

from miro import schema
# much easier to type this way..
from miro.schema import SchemaString, SchemaInt, SchemaFloat, SchemaBool
from miro.schema import SchemaDateTime, SchemaList, SchemaDict, SchemaObject
from miro.schema import SchemaReprContainer, ValidationError
from miro.test.framework import MiroTestCase

class TestValidation(MiroTestCase):
    def testModuleVariablesDefined(self):
        self.assert_(hasattr(schema, 'VERSION'))
        self.assert_(hasattr(schema, 'object_schemas'))

    def testNoneValidation(self):
        self.assertRaises(ValidationError, SchemaInt(noneOk=False).validate,
                None)
        self.assertRaises(ValidationError, SchemaInt().validate, None)
        SchemaInt(noneOk=True).validate(None)

    def testBoolValiation(self):
        schemabool = SchemaBool()
        self.assertRaises(ValidationError, schemabool.validate, 1)
        self.assertRaises(ValidationError, schemabool.validate, 0)
        self.assertRaises(ValidationError, schemabool.validate, "True")
        self.assertRaises(ValidationError, schemabool.validate, None)
        schemabool.validate(True)
        schemabool.validate(False)

    def testDateTimeValiation(self):
        schemadatetime = SchemaDateTime()
        self.assertRaises(ValidationError, schemadatetime.validate, 1)
        self.assertRaises(ValidationError, schemadatetime.validate, 0)
        delta = datetime.timedelta(days=40)
        self.assertRaises(ValidationError, schemadatetime.validate, delta)
        schemadatetime.validate(datetime.datetime(1980, 8, 1))

    def testIntValiation(self):
        schemaint = SchemaInt()
        self.assertRaises(ValidationError, schemaint.validate, "One")
        self.assertRaises(ValidationError, schemaint.validate, 1.4)
        schemaint.validate(1)
        schemaint.validate(1L)

    def testFloatValiation(self):
        schemafloat = SchemaFloat()
        self.assertRaises(ValidationError, schemafloat.validate, "One half")
        self.assertRaises(ValidationError, schemafloat.validate, 1)
        schemafloat.validate(1.4)

    def testStringValidation(self):
        schemastring = SchemaString()
        self.assertRaises(ValidationError, schemastring.validate, 10123)
        self.assertRaises(ValidationError, schemastring.validate, "10123")
        schemastring.validate(u"10123")

    def testReprContainerValidation(self):
        schemasimple = SchemaReprContainer()
        schemasimple.validate({1: u"Ben", u"pie": 3.1415})
        schemasimple.validate([1, 1, u"two", u"three", 5])
        schemasimple.validate({u'y2k': datetime.datetime(2000, 1, 1),
                'now': time.localtime()})
        schemasimple.validate({
                'fib': (1, 1, u"two", u"three", 5),
                'square': (1, 4, u"nine", 16),
                'fact': (1, 2.0, 6, u"twenty-four"),
            })
        #make sure circular references doesn't screw it up
        l = []
        d = {}
        l.extend([l, d])
        d['list'] = l
        schemasimple.validate(l)
        schemasimple.validate(d)

        class TestObject(object):
            pass
        self.assertRaises(ValidationError, schemasimple.validate,
                TestObject())
        self.assertRaises(ValidationError, schemasimple.validate,
                [TestObject()])
        self.assertRaises(ValidationError, schemasimple.validate, 
                {'object': TestObject()})

    def testListValidation(self):
        schemalist = SchemaList(SchemaInt())
        self.assertRaises(ValidationError, schemalist.validate,
                1234)
        schemalist.validate([1, 2, 3, 4])

    def testDictValidation(self):
        schemadict = SchemaDict(SchemaInt(), SchemaString())
        self.assertRaises(ValidationError, schemadict.validate,
                1234)
        schemadict.validate({12: u"Buckle my shoe"})

    def testObjectValidation(self):
        class TestObject(object):
            pass
        class ChildObject(TestObject):
            pass

        schemaobject = SchemaObject(TestObject)
        self.assertRaises(ValidationError, schemaobject.validate, 1234)
        schemaobject.validate(TestObject())
        # child objects should work
        schemaobject.validate(ChildObject())
        # the actual class object shouldn't
        self.assertRaises(ValidationError, schemaobject.validate, TestObject)

if __name__ == '__main__':
    unittest.main()
