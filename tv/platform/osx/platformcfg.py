from AppKit import NSUserDefaults, NSBundle
from PyObjCTools import Conversion

import os
import objc
import logging

import util
import prefs
import config
import keychain
import resources

sysconfPath = objc.pathForFramework('/System/Library/Frameworks/SystemConfiguration.framework')
sysconfBundle = NSBundle.bundleWithPath_(sysconfPath)
objc.loadBundleFunctions(sysconfBundle, globals(), ((u'SCDynamicStoreCopyProxies', '@@'), ))


MOVIES_DIRECTORY_PARENT = os.path.expanduser('~/Movies')
SUPPORT_DIRECTORY_PARENT = os.path.expanduser('~/Library/Application Support')

def load():
    domain = getBundleIdentifier()
    plist =  NSUserDefaults.standardUserDefaults().persistentDomainForName_(domain)
    try:
        pydict = Conversion.pythonCollectionFromPropertyList(plist)
    except:
        print "WARNING!! Error while converting the preference property list to python dictionary:"
        print plist

    # Sanitize the dictionary we just got, some value might be of type which can
    # cause massive problems when being pickled.
    if pydict is not None:
        for k, v in pydict.iteritems():
            if type(v) is objc._pythonify.OC_PythonFloat:
                pydict[k] = float(v)
            elif type(v) is objc._pythonify.OC_PythonInt:
                pydict[k] = int(v)
            elif type(v) is objc._pythonify.OC_PythonLong:
                pydict[k] = long(v)

    return pydict

def save(data):
    try:
        plist = Conversion.propertyListFromPythonCollection(data)
    except:
        print "WARNING!! Error while converting the settings dictionary to a property list:"
        print data
        raise
    else:
        domain = getBundleIdentifier()
        defaults = NSUserDefaults.standardUserDefaults()
        defaults.setPersistentDomain_forName_(plist, domain)
        defaults.synchronize()

def get(descriptor):
    if descriptor == prefs.MOVIES_DIRECTORY:
        path = os.path.join(MOVIES_DIRECTORY_PARENT, config.get(prefs.SHORT_APP_NAME))
        try:
            os.makedirs(os.path.join(path,'Incomplete Downloads'))
        except:
            pass
        return path

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        return os.path.expanduser('~/Desktop')

    elif descriptor == prefs.GETTEXT_PATHNAME:
        return os.path.abspath(resources.path("../locale"))

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        path = os.path.join(SUPPORT_DIRECTORY_PARENT, config.get(prefs.SHORT_APP_NAME))
        os.environ['APPDATA'] = path # This is for the Bittorent module
        try:
            os.makedirs(path)
        except:
            pass
        return path

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        return _makeSupportFilePath('icon-cache')
    
    elif descriptor == prefs.DB_PATHNAME:
        return _makeSupportFilePath('tvdump')

    elif descriptor == prefs.BSDDB_PATHNAME:
        return _makeSupportFilePath('database')

    elif descriptor == prefs.SQLITE_PATHNAME:
        return _makeSupportFilePath('sqlitedb')

    elif descriptor == prefs.LOG_PATHNAME:
        return _makeSupportFilePath('dtv-log')

    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        return _makeSupportFilePath('dtv-downloader-log')

    elif descriptor == prefs.HTTP_PROXY_ACTIVE:
        return _getProxyInfo('HTTPEnable', 0) == 1
        
    elif descriptor == prefs.HTTP_PROXY_HOST:
        return _getProxyInfo('HTTPProxy')
        
    elif descriptor == prefs.HTTP_PROXY_PORT:
        return _getProxyInfo('HTTPPort', 0)
        
    elif descriptor == prefs.HTTP_PROXY_IGNORE_HOSTS:
        return _getProxyInfo('ExceptionsList', list())
    
    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_USERNAME:
        return _getProxyAuthInfo('username')
    
    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_PASSWORD:
        return _getProxyAuthInfo('password')
    
    return descriptor.default

def _makeSupportFilePath(filename):
    path = get(prefs.SUPPORT_DIRECTORY)
    path = os.path.join(path, filename)
    return path

def _getProxyInfo(key, default=None):
    info = SCDynamicStoreCopyProxies(None)
    if info is None or key not in info:
        return default
    return info[key]

def _getProxyAuthInfo(key, default=None):
    proxy = _getProxyInfo('HTTPProxy')
    if proxy is None:
        return default
    authInfo = keychain.getAuthInfo(proxy)
    if authInfo is None or key not in authInfo:
        return default
    return authInfo[key]

###############################################################################
#### Bundle information accessors                                          ####
###############################################################################

def getBundleIdentifier():
    return unicode(NSBundle.mainBundle().bundleIdentifier())

def getBundlePath():
    return unicode(NSBundle.mainBundle().bundlePath())

def getBundleResourcePath():
    return unicode(NSBundle.mainBundle().resourcePath())

###############################################################################
#### Migrate to new application name                                       ####
###############################################################################

def migrateToNewAppName(oldAppName, newAppName):

    # Migrate preferences
    prefsPath = os.path.expanduser('~/Library/Preferences')
    newDomain = getBundleIdentifier()
    newPrefs = '%s.plist' % os.path.join(prefsPath, newDomain)
    oldDomain = newDomain.replace(newAppName, oldAppName)
    oldPrefs = '%s.plist' % os.path.join(prefsPath, oldDomain)
    
    if os.path.exists(oldPrefs):
        os.rename(oldPrefs, newPrefs)
        print("Migrated preferences to %s" % newPrefs)
        
    # Migrate Movies and Support folders

    oldMoviesFolder = os.path.join(MOVIES_DIRECTORY_PARENT, oldAppName)
    newMoviesFolder = os.path.join(MOVIES_DIRECTORY_PARENT, newAppName)
    if os.path.exists(oldMoviesFolder):
        if not os.path.exists(newMoviesFolder):
            os.rename(oldMoviesFolder, newMoviesFolder)
            print("Migrated movies folder to %s" % newMoviesFolder)
        else:
            print("Both %s and %s movies folder exist." % (oldAppName, newAppName))

    oldSupportFolder = os.path.join(SUPPORT_DIRECTORY_PARENT, oldAppName)
    newSupportFolder = os.path.join(SUPPORT_DIRECTORY_PARENT, newAppName)
    if os.path.exists(oldSupportFolder):
        if not os.path.exists(newSupportFolder):
            os.rename(oldSupportFolder, newSupportFolder)
            print("Migrated support folder to %s" % newSupportFolder)
        else:
            print("Both %s and %s support folder exist." % (oldAppName, newAppName))

def ensureMigratedMoviePath(pathname):
    if pathname.startswith(oldMoviesFolder):
        pathname = pathname.replace(oldMoviesFolder, newMoviesFolder)
        logging.info("Migrating movie to %s" % pathname)
    return pathname

if not util.inDownloader:
    migrateToNewAppName('Democracy', 'Miro')
