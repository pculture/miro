# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

from miro import util
import os
import os.path
from miro import app
from miro import config
from miro import prefs
from miro.platform import resources
from miro.platform.specialfolders import baseMoviesDirectory, appDataDirectory
import _winreg
from xpcom import components

def migrateSupport(oldAppName, newAppName):
    global migratedSupport
    migratedSupport = False
    # This gets called before config is set up, so we have to cheat
    oldSupportDir = os.path.join(appDataDirectory, app.configfile['publisher'], oldAppName, 'Support')
    newSupportDir = os.path.join(appDataDirectory, app.configfile['publisher'], newAppName, 'Support')

    # Migrate support
    if os.path.exists(oldSupportDir):
        if not os.path.exists(os.path.join(newSupportDir,"preferences.bin")):
            try:
                for name in os.listdir(oldSupportDir):
                    os.rename(os.path.join(oldSupportDir,name),
                              os.path.join(newSupportDir,name))
                migratedSupport = True
            except:
                pass

    if migratedSupport:
        runSubkey = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        try:
            folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, runSubkey)
        except WindowsError, e:
            if e.errno == 2: # registry key doesn't exist
                folder = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, runSubkey)
            else:
                raise

        count = 0
        while True:
            try:
                (name, val, type) = _winreg.EnumValue(folder,count)
            except:
                return True
            count += 1
            if (name == oldAppName):
                filename = os.path.join(resources.resourceRoot(),"..",("%s.exe" % templateVars['shortAppName']))
                filename = os.path.normpath(filename)
                writable_folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                                           runSubkey, 0,_winreg.KEY_SET_VALUE)
                _winreg.SetValueEx(writable_folder, newAppName, 0,_winreg.REG_SZ, filename)
                _winreg.DeleteValue(writable_folder, oldAppName)
                return True
        return True
    else:
        return False
    
def migrateVideos(oldAppName, newAppName):
    global migratedSupport
    # we have to wait to import this
    pybridgeCID = "@participatoryculture.org/dtv/pybridge;1"
    pybridge = components.classes[pybridgeCID]. \
                 getService(components.interfaces.pcfIDTVPyBridge)
    if migratedSupport:
        oldDefault = os.path.join(baseMoviesDirectory, oldAppName)
        newDefault = os.path.join(baseMoviesDirectory, newAppName)
        videoDir = config.get(prefs.MOVIES_DIRECTORY)
        if videoDir == newDefault:
            pybridge.changeMoviesDirectory(newDefault, True)
