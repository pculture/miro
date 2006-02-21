from downloader import grabURL
from threading import Thread, Lock
import config

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
    info = grabURL(config.get(config.AUTOUPDATE_URL))
    if info is not None:
        try:
            data = info['file-handle'].read()
            info['file-handle'].close()
            (version, url) = data.split()
            if version != config.get(config.UPDATE_KEY):
                print "DTV: new update '%s' available (have '%s')" % \
                    (config.get(config.UPDATE_KEY), version)
                delegate.updateAvailable(url)
            elif notifyIfUpToDate:
                delegate.dtvIsUpToDate()
        except:
            pass
    _lock.release()
