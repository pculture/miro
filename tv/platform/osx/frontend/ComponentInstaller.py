import os
import glob
import tempfile

from objc import nil, YES
from AppKit import NSApplication
from Foundation import NSUserDefaults, NSBundle, NSTask, NSFileManager, NSFileHandle

import platformcfg
from UIBackendDelegate import showWarningDialog

###############################################################################

CORE_AUDIO_COMPONENT_BUNDLE_TYPE = 'thngadec'

CORE_AUDIO_COMPONENTS_LOCATIONS = list()
CORE_AUDIO_COMPONENTS_LOCATIONS.append('/Library/Components')
CORE_AUDIO_COMPONENTS_LOCATIONS.append(os.path.expanduser('~/Library/Components'))

QUICKTIME_COMPONENT_BUNDLE_TYPE = 'thngeat '

QUICKTIME_COMPONENTS_LOCATIONS = list()
QUICKTIME_COMPONENTS_LOCATIONS.append('/Library/QuickTime')
QUICKTIME_COMPONENTS_LOCATIONS.append(os.path.expanduser('~/Library/QuickTime'))

ALL_LOCATIONS = CORE_AUDIO_COMPONENTS_LOCATIONS + QUICKTIME_COMPONENTS_LOCATIONS

PATH_TO_TRASH = os.path.expanduser('~/.Trash')

###############################################################################

def run():
    installList = list()
    upgradeList = list()
    installedComponents = list()
    installableComponents = _gatherInstallableComponents()

    for installable in installableComponents:
        installed = _checkInstalledComponent(installable)
        if installed is None:
            installList.append(installable)
        else:
            installedComponents.append(installed)
            installedVersion = _getComponentVersion(installed)
            installableVersion = _getComponentVersion(installable)
            if _installedIsOutdated(installedVersion, installableVersion):
                upgradeList.append((installed, installable))
    _runCompatibilityCheck(installedComponents, installList)

    if _shouldRun():    
        print 'DTV: Running QuickTime Components Installer.'
        _didRun()
        return _performInstallation(installList, upgradeList)
        
    return False

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

def _runCompatibilityCheck(installed, toInstall):
    versionInfo = os.uname()
    versionInfo = versionInfo[2].split('.')
    majorBuildVersion = int(versionInfo[0])
    if majorBuildVersion <= 7:
        print 'DTV: Running Quicktime Components compatibility check for OS X 10.3'
        
        # First check for an already installed Perian component
        installedPerian = None
        for inst in installed:
            if os.path.basename(inst) == 'Perian.component':
                installedPerian = inst
                break            
        if installedPerian is not None:
            title = 'Quicktime Component Incompatibility'
            message = 'The Perian Quicktime Component is installed but is incompatible with Mac OS X 10.3 and is therefore likely to cause crashes. Do you want Democracy to remove it for you ?'
            result = showWarningDialog(title, message, ['Yes', 'No'])
            remove = (result == 0)
            if remove:
                script =  'echo -- Quicktime Components Cleanup --'
                script += _getMoveToTrashCommands(installedPerian)
                _runScript(script, wait=True)
        
        # If the installation step is going to be performed, remove Perian from 
        # the list of components to install
        if _shouldRun():
            unsupportedPerian = None
            for inst in toInstall:
                if os.path.basename(inst) == 'Perian.component':
                    unsupportedPerian = inst
                    break
            if unsupportedPerian is not None:
                print "DTV: Removing Perian from the list of installable components."
                toInstall.remove(unsupportedPerian)

def _performInstallation(installList, upgradeList):
    if len(installList) > 0 or len(upgradeList) > 0:
        message = _buildMessage(installList, upgradeList)
    else:
        print '     nothing to install or upgrade.'
        return False

    appl = NSApplication.sharedApplication()
    if not appl.isActive():
        appl.activateIgnoringOtherApps_(YES)

    dlogTitle = 'QuickTime Components Installation'
    dlogResult = showWarningDialog(dlogTitle, message, ['Install', 'Continue without installing'])
    
    proceedAndRestart = (dlogResult == 0)
    if proceedAndRestart:
        script = 'echo -- QuickTime Components Installation/Upgrade -- \n'
        for install in installList:
            script += _getInstallCommands(install)
        for upgrade in upgradeList:
            script += _getUpgradeCommands(upgrade)
        script += _getRestartCommands()
        _runScript(script)

    return proceedAndRestart

def _buildMessage(installList, upgradeList):
    plugins = [os.path.splitext(os.path.basename(f))[0] for f in installList + upgradeList]
    plugins = ', '.join(plugins)
    total = len(installList) + len(upgradeList)
    
    message = 'Democracy can now install or update '
    if total == 1:
        message += '1 plugin (%s) ' % plugins
    else:        
        message += '%d plugins (%s) ' % (total, plugins)
    message += 'which will allow you to watch lots of additional video formats, including Flash, Divx, and AVI.'
    
    return message

def _getInstallCommands(sourcePath, destinationPath=None):
    if destinationPath is None:
        destinationPath = _getPreferredInstallPath(sourcePath)
    commands =  'echo Installing %s \n' % os.path.basename(sourcePath)
    commands += 'cp -v -R "%s" "%s" \n' % (sourcePath, destinationPath)
    return commands

def _getUpgradeCommands(upgradeInfo):
    commands =  _getMoveToTrashCommands(upgradeInfo[0])
    commands += _getInstallCommands(upgradeInfo[1], os.path.dirname(upgradeInfo[0]))
    return commands

def _getMoveToTrashCommands(path):
    commands =  'echo Moving %s to the trash \n' % path
    commands += 'mv -v "%s" "%s" \n' % (path, PATH_TO_TRASH)
    return commands

def _getRestartCommands():
    commands =  '\n'
    commands += 'echo Sleeping 1s... \n'
    commands += 'sleep 1 \n'
    commands += 'echo Quitting Democracy... \n'
    commands += 'osascript -e "tell application \\\"Democracy\\\" to quit" \n'
    commands += 'echo Sleeping 4s... \n'
    commands += 'sleep 4 \n'
    commands += 'echo Relaunching Democracy... \n'
    commands += 'open %s \n' % NSBundle.mainBundle().bundlePath()
    commands += 'echo Finished. \n'
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

def _getLogFileHandle():
    path = os.path.join(platformcfg.SUPPORT_DIRECTORY_PARENT, 'Democracy', 'dtv-qt-comp-inst-log')
    NSFileManager.defaultManager().createFileAtPath_contents_attributes_(path, nil, nil)
    return NSFileHandle.fileHandleForWritingAtPath_(path)

def _runScript(script, wait=False):
    path = _makeTempScript(script)
    wrapper = 'osascript -e "do shell script \\\"/bin/sh %s\\\" with administrator privileges"\n' % path
    wrapper += 'rm %s\n' % path
    path = _makeTempScript(wrapper)
    task = NSTask.alloc().init()
    task.setLaunchPath_('/bin/sh')
    task.setArguments_([path])
    task.setStandardOutput_(_getLogFileHandle())
    task.launch()
    if wait:
        task.waitUntilExit()

def _makeTempScript(script):
    handle, path = tempfile.mkstemp()
    f = os.fdopen(handle, "w")
    f.write(script)
    f.close()
    return path

###############################################################################
