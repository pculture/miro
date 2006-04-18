# test.py Copyright (c) 2005,2006 Participatory Culture Foundation
#
# Includes all PyUnit unit tests
#

import unittest

testModules = [
    __import__('test.databasetest'),
    __import__('test.templatetest'),
    __import__('test.fasttypestest'),
    __import__('test.schematest'),
    __import__('test.storedatabasetest'),
]

for module in testModules:
    unittest.defaultTestLoader.loadTestsFromModule(module)
