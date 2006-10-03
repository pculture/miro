import os
import glob
import tempfile

import platformcfg

from Foundation import NSUserDefaults, NSBundle, NSTask
from UIBackendDelegate import showWarningDialog

###############################################################################

CORE_AUDIO_COMPONENT_BUNDLE_TYPE = 'thngadec'

CORE_AUDIO_COMPONENTS_LOCATIONS = list()
CORE_AUDIO_COMPONENTS_LOCATIONS.append('/Library/Components')
CORE_AUDIO_COMPONENTS_LOCATIONS.append(os.path.expanduser('~/Library/Components'))

QUICKTIME_COMPONENT_BUNDLE_TYPE = 'thngeat '

QUICKTIME_COMPONENTS_LOCATIONS = list()
QUICKTIME_COMPONENTS_LOCATIONS.append('/Library/Quicktime')
QUICKTIME_COMPONENTS_LOCATIONS.append(os.path.expanduser('~/Library/Quicktime'))

ALL_LOCATIONS = CORE_AUDIO_COMPONENTS_LOCATIONS + QUICKTIME_COMPONENTS_LOCATIONS

PATH_TO_TRASH = os.path.expanduser('~/.Trash')

###############################################################################

def run():
    willRestart = False
    if _shouldRun():    
        print 'DTV: running Quicktime Components Installer.'
        _didRun()

        installList = list()
        upgradeList = list()

        installableComponents = _gatherInstallableComponents()
        for installable in installableComponents:
            installed = _checkInstalledComponent(installable)
            if installed is None:
                installList.append(installable)
            else:
                installedVersion = _getComponentVersion(installed)
                installableVersion = _getComponentVersion(installable)
                if _installedIsOutdated(installedVersion, installableVersion):
                    upgradeList.append((installed, installable))

        willRestart = _performInstallation(installList, upgradeList)

    return willRestart

###############################################################################

def _shouldRun():
    defaults = NSUserDefaults.standardUserDefaults()
    done = defaults.boolForKey_('componentInstallerDone')
    return not done

def _didRun():
    defaults = NSUserDefaults.standardUserDefaults()
    defaults.setBool_forKey_(True, 'componentInstallerDone')
    defaults.synchronize()

def _gatherInstallableComponents():
    path = os.path.join(NSBundle.mainBundle().bundlePath(), 'Contents/Components')
    return glob.glob(os.path.join(path, '*.component'))

def _checkInstalledComponent(path):
    for location in ALL_LOCATIONS:
        name = os.path.basename(path)
        installed = os.path.join(location, name)
        if os.path.exists(installed):
            return installed
    return None

def _getComponentVersion(path):
    bundle = NSBundle.bundleWithPath_(path)
    info = bundle.infoDictionary()
    return info.get('CFBundleVersion', '9999')

def _installedIsOutdated(installedVersion, installableVersion):
    return (installedVersion < installableVersion)

def _performInstallation(installList, upgradeList):
    installCount = len(installList)
    upgradeCount = len(upgradeList)
    if installCount > 0 or upgradeCount > 0:
        message = _buildMessage(installCount, upgradeCount)
    else:
        print '     nothing to install or upgrade.'
        return False

    dlogTitle = 'Quicktime Components Installation'
    dlogResult = showWarningDialog(dlogTitle, message, ['Yes', 'No'])
    
    proceedAndRestart = (dlogResult == 0)
    if proceedAndRestart:
        script = ''
        for install in installList:
            script += _getInstallCommands(install)
        for upgrade in upgradeList:
            script += _getUpgradeCommands(upgrade)
        script += _getRestartCommands()
        _runScript(script)

    return proceedAndRestart

def _buildMessage(installCount, upgradeCount):
    installPlural = ''
    if installCount > 1:
        installPlural = 's'
    upgradePlural = ''
    if upgradePlural > 1:
        upgradePlural = 's'

    message = 'Democracy can now '
    if installCount > 0 and upgradeCount == 0:
        message += 'install %d Quicktime component%s.' % (installCount, installPlural)
    elif installCount == 0 and upgradeCount > 0:
        message += 'upgrade %d outdated Quicktime component%s ' % (upgradeCount, upgradePlural)
        message += '(old component%s will be moved to the Trash).' % (upgradePlural,)
    elif installCount > 0 and upgradeCount > 0:
        message += 'install %d Quicktime component%s ' % (installCount, installPlural)
        message += 'and upgrade %d outdated one%s ' % (upgradeCount, upgradePlural)
        message += '(old component%s will be moved to the Trash).' % (upgradePlural,)
    
    message += '\n\nDemocracy will automatically restart itself after this. '
    message += 'Would you like to proceed ?'
    
    return message

def _getInstallCommands(sourcePath, destinationPath=None):
    if destinationPath is None:
        destinationPath = _getPreferredInstallPath(sourcePath)
    return 'cp -r "%s" "%s" \n' % (sourcePath, destinationPath)

def _getUpgradeCommands(upgradeInfo):
    command = 'mv "%s" "%s" \n' % (upgradeInfo[0], PATH_TO_TRASH)
    command += _getInstallCommands(upgradeInfo[1], os.path.dirname(upgradeInfo[0]))
    return command

def _getRestartCommands():
    commands =  '\n'
    commands += 'sleep 1 \n'
    commands += 'osascript -e "tell application \\\"Democracy\\\" to quit" \n'
    commands += 'sleep 4 \n'
    commands += 'open %s \n' % NSBundle.mainBundle().bundlePath()
    return commands

def _getPreferredInstallPath(sourcePath):
    installPath = QUICKTIME_COMPONENTS_LOCATIONS[0]
    bundlePath = NSBundle.bundleWithPath_(sourcePath).bundlePath()
    pkgInfoPath = os.path.join(bundlePath, 'Contents/PkgInfo')

    if os.path.exists(pkgInfoPath):
        try:
            pkgInfoFile = open(pkgInfoPath)
            pkgInfo = pkgInfoFile.read()
            if pkgInfo == CORE_AUDIO_COMPONENT_BUNDLE_TYPE:
                installPath = CORE_AUDIO_COMPONENTS_LOCATIONS[0]
        finally:
            pkgInfoFile.close()
        
    return installPath

def _runScript(script):
    path = _makeTempScript(script)
    wrapper = 'osascript -e "do shell script \\\"/bin/sh %s\\\" with administrator privileges"\n' % path
    wrapper += 'rm %s\n' % path
    path = _makeTempScript(wrapper)
    NSTask.launchedTaskWithLaunchPath_arguments_('/bin/sh', [path])

def _makeTempScript(script):
    handle, path = tempfile.mkstemp()
    f = os.fdopen(handle, "w")
    f.write(script)
    f.close()
    return path

###############################################################################
