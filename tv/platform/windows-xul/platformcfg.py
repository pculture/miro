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
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import os
import util
import config
import _winreg
import cPickle
import string
import prefs
import tempfile
import ctypes
import resources

import proxyfind

proxy_info = proxyfind.get_proxy_info()

_specialFolderCSIDLs = {
    'AppData': 0x001a,
    "My Music": 0x000d,
    "My Pictures": 0x0027,
    "My Videos": 0x000e,
    "My Documents": 0x0005,
    "Desktop": 0x0000,
    "Common AppData": 0x0023,
}

def getSpecialFolder(name):
    """Get the location of a special folder.  name should be one of the
    following: 'AppData', 'My Music', 'My Pictures', 'My Videos', 
    'My Documents', 'Desktop'.

    The path to the folder will be returned, or None if the lookup fails

    """

    buf = ctypes.create_unicode_buffer(260)
    buf2 = ctypes.create_unicode_buffer(1024) 
    SHGetSpecialFolderPath = ctypes.windll.shell32.SHGetSpecialFolderPathW
    GetShortPathName = ctypes.windll.kernel32.GetShortPathNameW
    csidl = _specialFolderCSIDLs[name]
    if SHGetSpecialFolderPath(None, buf, csidl, False):
        if GetShortPathName(buf, buf2, 1024):
            return buf2.value
        else:
            return buf.value
    else:
        return None

_appDataDirectory = getSpecialFolder('AppData')
_commonAppDataDirectory = getSpecialFolder("Common AppData")
_baseMoviesDirectory = getSpecialFolder('My Videos')
_nonVideoDirectory = getSpecialFolder('Desktop')

# The "My Videos" folder isn't guaranteed to be listed. If it isn't
# there, we do this hack.
if _baseMoviesDirectory is None:
    _baseMoviesDirectory = os.path.join(getSpecialFolder('My Documents'),'My Videos')

def _getMoviesDirectory():
    path = os.path.join(_baseMoviesDirectory, config.get(prefs.SHORT_APP_NAME))
    try:
        os.makedirs(os.path.join(path, 'Incomplete Downloads'))
    except:
        pass
    return path

def _getSupportDirectory():
    # We don't get the publisher and long app name from the config so
    # changing the app name doesn't change the support directory
    path = os.path.join(_appDataDirectory,
                        u'Participatory Culture Foundation',
                        u'Miro',
                        u'Support')
    try:
        os.makedirs(path)
    except:
        pass
    return path

def _getThemeDirectory():
    # We don't get the publisher and long app name from the config so
    # changing the app name doesn't change the support directory
    path = os.path.join(_commonAppDataDirectory,
                        u'Participatory Culture Foundation',
                        u'Miro',
                        u'Themes')
    try:
        os.makedirs(path)
    except:
        pass
    return path

def _getConfigFile():
    return os.path.join(_getSupportDirectory(), "preferences.bin")

def load():
    try:
        file = _getConfigFile()
        if os.path.exists(file):
            return cPickle.load(open(file))
        else:
            return {}
    except:
        import traceback
        print "Error loading perferences. Resetting prefs."
        traceback.print_exc()
        return {}

def save(data):
    file = _getConfigFile()
    cPickle.dump(data,open(file,'w'))

def get(descriptor):
    if descriptor == prefs.MOVIES_DIRECTORY:
        return _getMoviesDirectory()

    elif descriptor == prefs.THEME_DIRECTORY:
        return _getThemeDirectory()

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        return _nonVideoDirectory

    elif descriptor == prefs.GETTEXT_PATHNAME:
        return resources.path("locale")

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        return _getSupportDirectory()

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        return os.path.join(_getSupportDirectory(), 'icon-cache')
    
    elif descriptor == prefs.DB_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(path, 'tvdump')

    elif descriptor == prefs.BSDDB_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(path, 'database')

    elif descriptor == prefs.SQLITE_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(path, 'sqlitedb')

    elif descriptor == prefs.LOG_PATHNAME:
        return os.path.join(tempfile.gettempdir(), ('%s.log' %config.get(prefs.SHORT_APP_NAME)))

    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        return os.path.join(tempfile.gettempdir(), ('%s-downloader.log'%config.get(prefs.SHORT_APP_NAME)))

    elif descriptor == prefs.RUN_AT_STARTUP:
        # We use the legacy startup registry key, so legacy versions
        # of Windows have a chance
        # http://support.microsoft.com/?kbid=270035

        folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,"Software\Microsoft\Windows\CurrentVersion\Run")
        count = 0
        while True:
            try:
                (name, val, type) = _winreg.EnumValue(folder,count)
                count += 1
                if (name == config.get(prefs.LONG_APP_NAME)):
                    return True                    
            except:
                return False
        return False

    elif descriptor == prefs.HTTP_PROXY_ACTIVE:
        return proxy_info.host is not None
    elif descriptor == prefs.HTTP_PROXY_HOST:
        return proxy_info.host
    elif descriptor == prefs.HTTP_PROXY_PORT:
        return proxy_info.port
    elif descriptor == prefs.HTTP_PROXY_IGNORE_HOSTS:
        return poxy_info.ignore_hosts
    # Proxy authorization isn't suppored on windows, so the following keps are
    # ignored:
    # 
    # HTTP_PROXY_AUTHORIZATION_ACTIVE
    # HTTP_PROXY_AUTHORIZATION_USERNAME
    # HTTP_PROXY_AUTHORIZATION_PASSWORD
    else:
        return descriptor.default
