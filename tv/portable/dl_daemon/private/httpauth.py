import itertools

from miro.dl_daemon import command
from miro import eventloop

requestIdGenerator = itertools.count()
waitingHTTPAuthCallbacks = {}

def handleHTTPAuthResponse(id, authHeader):
    callback = waitingHTTPAuthCallbacks.pop(id)
    callback(authHeader)

def findHTTPAuth(callback, host, path):
    id = requestIdGenerator.next()
    waitingHTTPAuthCallbacks[id] = callback
    from miro.dl_daemon import daemon
    c = command.FindHTTPAuthCommand(daemon.lastDaemon, id, host, path)
    c.send()

def askForHTTPAuth(callback, host, path, authScheme):
    id = requestIdGenerator.next()
    waitingHTTPAuthCallbacks[id] = callback
    from miro.dl_daemon import daemon
    c = command.AskForHTTPAuthCommand(daemon.lastDaemon, id, host, path,
            authScheme)
    c.send()
