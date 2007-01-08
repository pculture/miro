from AppKit import NSUserDefaults, NSBundle
from PyObjCTools import Conversion

import os
import objc

import util
import prefs
import config
import keychain
import resources

sysconfPath = objc.pathForFramework('/System/Library/Frameworks/SystemConfiguration.framework')
sysconfBundle = NSBundle.bundleWithPath_(sysconfPath)
objc.loadBundleFunctions(sysconfBundle, globals(), ((u'SCDynamicStoreCopyProxies', '@@'), ))

_proxiesInfo = SCDynamicStoreCopyProxies(None)


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
    value = descriptor.default

    if descriptor == prefs.MOVIES_DIRECTORY:
        path = os.path.join(MOVIES_DIRECTORY_PARENT, config.get(prefs.SHORT_APP_NAME))
        try:
            os.makedirs(os.path.join(path,'Incomplete Downloads'))
        except:
            pass
        value = path

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        value = os.path.expanduser('~/Desktop')

    elif descriptor == prefs.GETTEXT_PATHNAME:
        value = os.path.abspath(resources.path("../locale"))

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        path = os.path.join(SUPPORT_DIRECTORY_PARENT, config.get(prefs.SHORT_APP_NAME))
        os.environ['APPDATA'] = path # This is for the Bittorent module
        try:
            os.makedirs(path)
        except:
            pass
        value = path

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        value = _makeSupportFilePath('icon-cache')
    
    elif descriptor == prefs.DB_PATHNAME:
        value = _makeSupportFilePath('tvdump')

    elif descriptor == prefs.BSDDB_PATHNAME:
        value = _makeSupportFilePath('database')

    elif descriptor == prefs.LOG_PATHNAME:
        value = _makeSupportFilePath('dtv-log')

    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        value = _makeSupportFilePath('dtv-downloader-log')

    elif descriptor == prefs.HTTP_PROXY_ACTIVE:
        value = 'HTTPEnable' in _proxiesInfo and _proxiesInfo['HTTPEnable'] == 1
        
    elif descriptor == prefs.HTTP_PROXY_HOST:
        value = _proxiesInfo['HTTPProxy']
        
    elif descriptor == prefs.HTTP_PROXY_PORT:
        value = _proxiesInfo['HTTPPort']
        
    elif descriptor == prefs.HTTP_PROXY_IGNORE_HOSTS:
        value = _proxiesInfo['ExceptionsList']
    
    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_USERNAME:
        authInfo = keychain.getAuthInfo(_proxiesInfo['HTTPProxy'])
        value = authInfo['username']
    
    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_PASSWORD:
        authInfo = keychain.getAuthInfo(_proxiesInfo['HTTPProxy'])
        value = authInfo['password']
    
    return value

def _makeSupportFilePath(filename):
    path = get(prefs.SUPPORT_DIRECTORY)
    path = os.path.join(path, filename)
    return path

###############################################################################
#### Bundle information accessors                                          ####
###############################################################################

def getBundleIdentifier():
    if os.environ.has_key('BUNDLEIDENTIFIER'):
        return os.environ['BUNDLEIDENTIFIER']
    else:
        return NSBundle.mainBundle().bundleIdentifier()

def getBundlePath():
    if os.environ.has_key('BUNDLEPATH'):
        return os.environ['BUNDLEPATH']
    else:
        return NSBundle.mainBundle().bundlePath()

def getBundleResourcePath():
    if os.environ.has_key('RESOURCEPATH'):
        return os.environ['RESOURCEPATH']
    else:
        return NSBundle.mainBundle().resourcePath()

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
    newDomain = getBundleIdentifier()
    newPrefs = '%s.plist' % os.path.join(prefsPath, newDomain)
    oldDomain = newDomain.replace(newAppName, oldAppName)
    oldPrefs = '%s.plist' % os.path.join(prefsPath, oldDomain)
    
    if os.path.exists(oldPrefs):
        print "DTV: Migrating preferences to %s" % newDomain
        os.rename(oldPrefs, newPrefs)
        
    # Migrate Movies and Support folders

    if os.path.exists(oldMoviesFolder):
        if not os.path.exists(newMoviesFolder):
            print "DTV: Migrating movies folder to %s" % newMoviesFolder
            os.rename(oldMoviesFolder, newMoviesFolder)
        else:
            print "DTV: WARNING! Both DTV and Democracy movies folder exist."

    if os.path.exists(oldSupportFolder):
        if not os.path.exists(newSupportFolder):
            print "DTV: Migrating support folder to %s" % newSupportFolder
            os.rename(oldSupportFolder, newSupportFolder)
        else:
            print "DTV: WARNING! Both DTV and Democracy support folder exist."

def ensureMigratedMoviePath(pathname):
    if pathname.startswith(oldMoviesFolder):
        pathname = pathname.replace(oldMoviesFolder, newMoviesFolder)
        print "DTV: Migrating movie to %s" % pathname
    return pathname

if not util.inDownloader:
    migrateToDemocracy()
