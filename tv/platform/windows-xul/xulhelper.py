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

from xpcom import components

pcfIDTVPyBridge = components.interfaces.pcfIDTVPyBridge
pcfIDTVJSBridge = components.interfaces.pcfIDTVJSBridge
pcfIDTVVLCRenderer = components.interfaces.pcfIDTVVLCRenderer

proxyManager = components.classes["@mozilla.org/xpcomproxy;1"].createInstance(components.interfaces.nsIProxyObjectManager)

try:
    # XULRunner 1.8 version
    eventQueueService = components.classes["@mozilla.org/event-queue-service;1"].getService(components.interfaces.nsIEventQueueService)
    xulEventQueue = eventQueueService.getSpecialEventQueue(
        components.interfaces.nsIEventQueueService.UI_THREAD_EVENT_QUEUE)
except:
    # XULRunner 1.9 version
    threadMan = components.classes["@mozilla.org/thread-manager;1"].getService(components.interfaces.nsIThreadManager)
    xulEventQueue = threadMan.mainThread

def proxify(obj, iid):
    return proxyManager.getProxyForObject(xulEventQueue, iid, obj,
          components.interfaces.nsIProxyObjectManager.INVOKE_SYNC |
          components.interfaces.nsIProxyObjectManager.FORCE_PROXY_CREATION )

def makeComp(clsid, iid, makeProxy=True):
    """Helper function to get an XPCOM component"""
    obj = components.classes[clsid].createInstance(iid)
    if makeProxy:
        obj = proxify(obj, iid)
    return obj

def makeService(clsid, iid, makeProxy=True):
    """Helper function to get an XPCOM service"""
    obj = components.classes[clsid].getService(iid)
    if makeProxy:
        obj = proxify(obj, iid)
    return obj
