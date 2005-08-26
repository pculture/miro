from downloader import grabURL
from threading import Thread, Lock

_lock = Lock()

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

def checkForUpdates(notifyIfUpToDate=False):
    if _lock.acquire(False):
        thread = Thread(target=lambda: _checkForUpdates(notifyIfUpToDate))
        thread.setDaemon(False)
        thread.start()
    

def _checkForUpdates(notifyIfUpToDate):
    info = grabURL('http://www.participatoryculture.org/DTV-version.txt')
    if info is not None:
        try:
            data = info['file-handle'].read()
            info['file-handle'].close()
            (version, url) = data.split()
            if version != 'beta2005-08-25':
                delegate.updateAvailable(url)
            elif notifyIfUpToDate:
                delegate.dtvIsUpToDate()
        except:
            pass
    _lock.release()
