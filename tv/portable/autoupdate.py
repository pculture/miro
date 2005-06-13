from downloader import grabURL
from threading import Thread

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

def checkForUpdates():
    thread = Thread(target=lambda: _checkForUpdates())
    thread.setDaemon(False)
    thread.start()
    

def _checkForUpdates():
    info = grabURL('http://www.participatoryculture.org/DTV-version.txt')
    if not info is None:
        data = info['file-handle'].read()
        info['file-handle'].close()
        (version, url) = data.split()
        if version != 'CVS-06-12-2005':
            delegate.updateAvailable(url)
