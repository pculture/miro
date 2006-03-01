from downloader import grabURL
from threading import Thread, Lock
import config
import xml.dom.minidom

_lock = Lock()

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

def checkForUpdates(notifyIfUpToDate=False):
    if _lock.acquire(False):
        thread = Thread(target=lambda: _checkForUpdates(notifyIfUpToDate),
                        name="upgrade notification")
        thread.setDaemon(False)
        thread.start()
    

def _checkForUpdates(notifyIfUpToDate):
    platform = config.get(config.APP_PLATFORM)
    serial = int(config.get(config.APP_SERIAL))
    info = grabURL(config.get(config.AUTOUPDATE_URL))
    updated = False
    if info is not None:
        data = info['file-handle'].read()
        info['file-handle'].close()
        domObj = xml.dom.minidom.parseString(data)
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
    _lock.release()
