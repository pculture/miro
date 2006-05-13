from download_utils import grabURLAsync
from threading import Thread
import config
import xml.dom.minidom
import eventloop

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

def checkForUpdates(notifyIfUpToDate=False):
    info = grabURLAsync(_checkForUpdates, config.get(config.AUTOUPDATE_URL), args=(notifyIfUpToDate,))
    

def _checkForUpdates(info, notifyIfUpToDate):
    try:
        platform = config.get(config.APP_PLATFORM)
        serial = int(config.get(config.APP_SERIAL))
        updated = False
        if info is not None:
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
                       (ver, config.get(config.APP_VERSION))
                    delegate.updateAvailable(url)
                    updated = True
                    break
            domObj.unlink()
            if notifyIfUpToDate and not updated:
                delegate.dtvIsUpToDate()
    finally:
        eventloop.addTimeout (86400, checkForUpdates)
