import datetime
import os
import time
import unittest

from miro import schema
from miro.schema import (SchemaString, SchemaInt, SchemaFloat, SchemaBool,
                         SchemaDateTime, SchemaList, SchemaDict, SchemaObject,
                         SchemaReprContainer, ValidationError)
from miro.test.framework import MiroTestCase

class TestValidation(MiroTestCase):
    def test_module_variables_defined(self):
        self.assert_(hasattr(schema, 'VERSION'))
        self.assert_(hasattr(schema, 'object_schemas'))

    def test_none_validation(self):
        self.assertRaises(ValidationError, SchemaInt(noneOk=False).validate,
                          None)
        self.assertRaises(ValidationError, SchemaInt().validate, None)
        SchemaInt(noneOk=True).validate(None)

    def test_bool_validation(self):
        schemabool = SchemaBool()
        self.assertRaises(ValidationError, schemabool.validate, 1)
        self.assertRaises(ValidationError, schemabool.validate, 0)
        self.assertRaises(ValidationError, schemabool.validate, "True")
        self.assertRaises(ValidationError, schemabool.validate, None)
        schemabool.validate(True)
        schemabool.validate(False)

    def test_date_time_validation(self):
        schemadatetime = SchemaDateTime()
        self.assertRaises(ValidationError, schemadatetime.validate, 1)
        self.assertRaises(ValidationError, schemadatetime.validate, 0)
        delta = datetime.timedelta(days=40)
        self.assertRaises(ValidationError, schemadatetime.validate, delta)
        schemadatetime.validate(datetime.datetime(1980, 8, 1))

    def test_int_validation(self):
        schemaint = SchemaInt()
        self.assertRaises(ValidationError, schemaint.validate, "One")
        self.assertRaises(ValidationError, schemaint.validate, 1.4)
        schemaint.validate(1)
        schemaint.validate(1L)

    def test_float_validation(self):
        schemafloat = SchemaFloat()
        self.assertRaises(ValidationError, schemafloat.validate, "One half")
        self.assertRaises(ValidationError, schemafloat.validate, 1)
        schemafloat.validate(1.4)

    def test_string_validation(self):
        schemastring = SchemaString()
        self.assertRaises(ValidationError, schemastring.validate, 10123)
        self.assertRaises(ValidationError, schemastring.validate, "10123")
        schemastring.validate(u"10123")

    def test_repr_container_validatoin(self):
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
        # make sure circular references doesn't screw it up
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

    def test_list_validation(self):
        schemalist = SchemaList(SchemaInt())
        self.assertRaises(ValidationError, schemalist.validate,
                          1234)
        schemalist.validate([1, 2, 3, 4])

    def test_dict_validation(self):
        schemadict = SchemaDict(SchemaInt(), SchemaString())
        self.assertRaises(ValidationError, schemadict.validate,
                1234)
        schemadict.validate({12: u"Buckle my shoe"})

    def test_object_validation(self):
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
