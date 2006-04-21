"""Responsible for upgrading old versions of the database.

NOTE: For really old versions (before the schema.py module, see
olddatabaseupgrade.py)
"""

import schema

def upgrade(savedObjects, saveVersion, upgradeTo=None):
    """Upgrade a list of SavableObjects that were saved using an old version 
    of the database schema.

    This method will call upgradeX for each number X between saveVersion and
    upgradeTo.  For example, if saveVersion is 2 and upgradeTo is 4, this
    method is equivelant to:

        savedObjects = upgrade3(savedObjects)
        savedObjects = upgrade4(savedObjects)
        return savedObjects

    By default, upgradeTo will be the VERSION variable in schema.
    """

    if upgradeTo is None:
        upgradeTo = schema.VERSION

    while saveVersion < upgradeTo:
        upgradeFunc = globals()['upgrade%d' % (saveVersion + 1)]
        savedObjects = upgradeFunc(savedObjects)
        saveVersion += 1
    return savedObjects
