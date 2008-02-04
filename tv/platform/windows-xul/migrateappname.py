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

import util
import platformcfg
import os
import os.path
import resources
import config
import prefs
import _winreg
from xulhelper import makeService, pcfIDTVPyBridge

def migrateSupport(oldAppName, newAppName):
    global migratedSupport
    migratedSupport = False
    # This gets called before config is set up, so we have to cheat
    templateVars = util.readSimpleConfigFile(resources.path('app.config'))
    appDataDir = platformcfg._appDataDirectory
    oldSupportDir = os.path.join(appDataDir, templateVars['publisher'], oldAppName, 'Support')
    newSupportDir = os.path.join(appDataDir, templateVars['publisher'], newAppName, 'Support')

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
    pybridge = makeService(pybridgeCID,pcfIDTVPyBridge, True, False)
    if migratedSupport:
        oldDefault = os.path.join(platformcfg._baseMoviesDirectory, oldAppName)
        newDefault = os.path.join(platformcfg._baseMoviesDirectory, newAppName)
        videoDir = config.get(prefs.MOVIES_DIRECTORY)
        if videoDir == newDefault:
            pybridge.changeMoviesDirectory(newDefault, True)
