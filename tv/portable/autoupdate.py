import traceback
import xml.dom.minidom

import prefs
import config
import dialogs
import eventloop

from httpclient import grabURL

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

# Trigger the version checking process
def checkForUpdates(notifyIfUpToDate=False):
    grabURL(config.get(prefs.AUTOUPDATE_URL), 
            lambda info: _checkForUpdates(info, notifyIfUpToDate),
            _checkForUpdatesErrback)



def _checkForUpdatesErrback(error):
    print "Warning: HTTP error while checking for updates: ", error
    eventloop.addTimeout (86400, checkForUpdates, "Check for updates")
    
def _checkForUpdates(info, notifyIfUpToDate):
    try:
        platform = config.get(prefs.APP_PLATFORM)
        serial = int(config.get(prefs.APP_SERIAL))
        upToDate = True
        body = info['body']
        try:
            domObj = xml.dom.minidom.parseString(body)
        except:
            print "WARNING: Error parsing autoupdate page"
            traceback.print_exc()
            return
        versions = domObj.getElementsByTagNameNS("http://www.getdemocracy.com/versionfile/1.0","version")
        for version in versions:
            attributes = version.attributes
            if ((attributes['platform'].value == platform) and 
                (int(attributes['serial'].value) > serial)):
                upToDate = False
                ver = attributes['version'].value
                print "DTV: new update '%s' available (have '%s')" % (ver, config.get(prefs.APP_VERSION))
                url = attributes['updateurl'].value
                _handleNewUpdate(url)
                break
        domObj.unlink()
        if upToDate and notifyIfUpToDate:
            _handleUpToDate()
    finally:
        eventloop.addTimeout (86400, checkForUpdates, "Check for updates")

def _handleNewUpdate(url):
    def callback(dialog):
        global delegate
        if dialog.choice == dialogs.BUTTON_DOWNLOAD:
            delegate.openExternalURL(url)
    summary = _("%s Version Alert") % (config.get(prefs.SHORT_APP_NAME), )
    message = _("A new version of %s is available. Would you like to download it now?") % (config.get(prefs.LONG_APP_NAME), )
    dlog = dialogs.ChoiceDialog(summary, message, dialogs.BUTTON_DOWNLOAD, dialogs.BUTTON_CANCEL)
    dlog.run(callback)
    
def _handleUpToDate():
    title = _('%s Version Check') % (config.get(prefs.SHORT_APP_NAME), )
    message = _('%s is up to date.') % (config.get(prefs.LONG_APP_NAME), )
    dialogs.MessageBoxDialog(title, message).run()
