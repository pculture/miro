from httpclient import grabURL
import config
import prefs
import xml.dom.minidom
import eventloop
import util

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

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
        updated = False
        domObj = xml.dom.minidom.parseString(info['body'])
        versions = domObj.getElementsByTagNameNS("http://www.getdemocracy.com/versionfile/1.0","version")
        for version in versions:
            attributes = version.attributes
            if ((attributes['platform'].value == platform) and
                (int(attributes['serial'].value)>serial)):
                ver = attributes['version'].value
                url = attributes['updateurl'].value
                text = ""
                for node in version.childNodes:
                    if node.nodeType == node.TEXT_NODE:
                        text = text + node.data
                print "DTV: new update '%s' available (have '%s')" % \
                   (ver, config.get(prefs.APP_VERSION))
                delegate.updateAvailable(url)
                updated = True
                break
        domObj.unlink()
        if notifyIfUpToDate and not updated:
            delegate.dtvIsUpToDate()
    finally:
        eventloop.addTimeout (86400, checkForUpdates, "Check for updates")
