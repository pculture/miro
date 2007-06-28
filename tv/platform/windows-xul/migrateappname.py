import util
import platformcfg
import os
import os.path
import resources
import config
import prefs
import _winreg
from xpcom import components

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
                return
            count += 1
            if (name == oldAppName):
                filename = os.path.join(resources.resourceRoot(),"..",("%s.exe" % templateVars['shortAppName']))
                filename = os.path.normpath(filename)
                writable_folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                                           runSubkey, 0,_winreg.KEY_SET_VALUE)
                _winreg.SetValueEx(writable_folder, newAppName, 0,_winreg.REG_SZ, filename)
                _winreg.DeleteValue(writable_folder, oldAppName)
                return

def migrateVideos(oldAppName, newAppName):
    global migratedSupport
    # we have to wait to import this
    pybridgeCID = "@participatoryculture.org/dtv/pybridge;1"
    pybridge = components.classes[pybridgeCID]. \
                 getService(components.interfaces.pcfIDTVPyBridge)
    if migratedSupport:
        oldDefault = os.path.join(platformcfg._baseMoviesDirectory, oldAppName)
        newDefault = os.path.join(platformcfg._baseMoviesDirectory, newAppName)
        videoDir = config.get(prefs.MOVIES_DIRECTORY)
        if videoDir == newDefault:
            pybridge.changeMoviesDirectory(newDefault, True)
