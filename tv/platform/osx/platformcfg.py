from AppKit import NSUserDefaults, NSBundle
from PyObjCTools import Conversion

import os

import util
import config
import resource

MOVIES_DIRECTORY_PARENT = os.path.expanduser('~/Movies')
SUPPORT_DIRECTORY_PARENT = os.path.expanduser('~/Library/Application Support')

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
        path = os.path.join(MOVIES_DIRECTORY_PARENT, config.get(config.SHORT_APP_NAME))
        try:
            os.makedirs(os.path.join(path,'Incomplete Downloads'))
        except:
            pass
        value = path

    elif descriptor == config.SUPPORT_DIRECTORY:
        path = os.path.join(SUPPORT_DIRECTORY_PARENT, config.get(config.SHORT_APP_NAME))
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

    elif descriptor == config.LOG_PATHNAME:
        path = get(config.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'log')
        value = path
    
    return value


###############################################################################
#### Migrate to Democracy                                                  ####
###############################################################################

oldAppName = 'DTV'
newAppName = 'Democracy'

oldMoviesFolder = os.path.join(MOVIES_DIRECTORY_PARENT, oldAppName)
newMoviesFolder = os.path.join(MOVIES_DIRECTORY_PARENT, newAppName)
oldSupportFolder = os.path.join(SUPPORT_DIRECTORY_PARENT, oldAppName)
newSupportFolder = os.path.join(SUPPORT_DIRECTORY_PARENT, newAppName)

def migrateToDemocracy():

    # Migrate preferences
    
    prefsPath = os.path.expanduser('~/Library/Preferences')
    newDomain = NSBundle.mainBundle().bundleIdentifier()
    newPrefs = '%s.plist' % os.path.join(prefsPath, newDomain)
    oldDomain = newDomain.replace(newAppName, oldAppName)
    oldPrefs = '%s.plist' % os.path.join(prefsPath, oldDomain)
    
    if os.path.exists(oldPrefs):
        print "DTV: Migrating preferences to %s" % newDomain
        os.rename(oldPrefs, newPrefs)
        
    # Migrate Movies and Support folders

    if os.path.exists(oldMoviesFolder):
        print "DTV: Migrating movies folder to %s" % newMoviesFolder
        os.rename(oldMoviesFolder, newMoviesFolder)

    if os.path.exists(oldSupportFolder):
        print "DTV: Migrating support folder to %s" % newSupportFolder
        os.rename(oldSupportFolder, newSupportFolder)

def ensureMigratedMoviePath(pathname):
    if pathname.startswith(oldMoviesFolder):
        pathname = pathname.replace(oldMoviesFolder, newMoviesFolder)
        print "DTV: Migrating movie to %s" % pathname
    return pathname


migrateToDemocracy();
