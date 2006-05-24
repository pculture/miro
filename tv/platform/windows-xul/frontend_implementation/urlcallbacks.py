"""Handles installing callbacks for url loads of HTMLDisplay objects.

The way this module is used is HTMLDisplay installs a bunch of callbacks with
installCallback(), then the mycontentpolicy XPCOM object calls runCallback()
when it sees a new URL.  This means that installCallback is called from the
backend event loop, while runCallback is called from the frontend event loop.
"""

import util
from threading import Lock

callbacks = {}
callbacksLock = Lock()

def installCallback(referrer, callback):
    """Install a new URL load callback, callback will be called when we see a
    URL load where the referrer matches referrer.
    Callback should accept a URL as an input and return True if we should
    continue the load, or False if the we shouldn't.
    """
    callbacksLock.acquire()
    try:
        callbacks[referrer] = callback
    finally:
        callbacksLock.release()

def removeCallback(referrer):
    """Remove a callback created with installCallback().  If a callback
    doesn't exist for referrer, a KeyError will be thrown.
    """
    callbacksLock.acquire()
    try:
        del callbacks[referrer]
    finally:
        callbacksLock.release()

def runCallback(referrerURL, url):
    """Try to find an installed callback and run it if there is one.  If this
    method return True, the URL load should continue, if it returns False it
    should stop.
    """

    try:
        callbacksLock.acquire()
        try:
            callback = callbacks[referrerURL]
        finally:
            callbacksLock.release()
    except KeyError:
        return True
    else:
        try:
            rv = callback(url)
            return rv
        except:
            util.failedExn(when="When running URL callback")
            return True
