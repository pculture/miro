# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

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
import platformutils

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
            elif k == prefs.MOVIES_DIRECTORY.key:
                pydict[k] = platformutils.osFilenameToFilenameType(v)

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
