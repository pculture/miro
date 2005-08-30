from AppKit import NSUserDefaults, NSBundle
from PyObjCTools import Conversion

import os

import config

def load():
    domain = NSBundle.mainBundle().bundleIdentifier()
    plist =  NSUserDefaults.standardUserDefaults().persistentDomainForName_(domain)
    return Conversion.pythonCollectionFromPropertyList(plist)

def save(data):
    domain = NSBundle.mainBundle().bundleIdentifier()
    plist = Conversion.propertyListFromPythonCollection(data)
    defaults = NSUserDefaults.standardUserDefaults()
    defaults.setPersistentDomain_forName_(plist, domain)
    defaults.synchronize()

def get(descriptor):
    value = None

    if descriptor == config.MOVIES_DIRECTORY:
        path = os.path.expanduser('~/Movies/DTV')
        try:
            os.makedirs(os.path.join(path,'Incomplete Downloads'))
        except:
            pass
        value = path

    elif descriptor == config.SUPPORT_DIRECTORY:
        path = os.path.expanduser('~/Library/Application Support/DTV')
        os.environ['APPDATA'] = path # This is for the Bittorent module
        try:
            os.makedirs(path)
        except:
            pass
        value = path
    
    elif descriptor == config.DB_PATHNAME:
        path = get(config.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'tvdump')
        value = path
    
    return value
