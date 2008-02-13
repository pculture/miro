# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""Handles installing callbacks for url loads of HTMLDisplay objects.

The way this module is used is HTMLDisplay installs a bunch of callbacks with
installCallback(), then the mycontentpolicy XPCOM object calls runCallback()
when it sees a new URL.  This means that installCallback is called from the
backend event loop, while runCallback is called from the frontend event loop.
"""

from miro import config
from miro import prefs
from miro import signals
from threading import Lock

callbacks = {}
mainDisplayCallback = None
# We assume all urls that don't begin with file:// go to the mainDisplay
# FIXME: we may want a cleaner way to do this.
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

def installMainDisplayCallback(callback):
    """Install a callback for urls where the referrerer is any channel guide
    page.  """
    global mainDisplayCallback
    callbacksLock.acquire()
    try:
        mainDisplayCallback = callback
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

    callbacksLock.acquire()
    try:
        try:
            callback = callbacks[referrerURL]
        except KeyError:
            if (not url.startswith("file://") and 
                    mainDisplayCallback is not None):
                callback = mainDisplayCallback
            else:
                return True
    finally:
        callbacksLock.release()
    try:
        rv = callback(url)
        return rv
    except:
        signals.system.failedExn(when="When running URL callback")
        return True
