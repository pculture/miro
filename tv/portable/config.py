# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

from threading import RLock
import os
import traceback

import util
import prefs
import resources
import eventloop
import platformcfg
import urllib
import logging

__appConfig = None
__themeConfig = dict()
__data = None
__lock = RLock()
__callbacks = set()

def addChangeCallback(callback):
    __callbacks.add(callback)

def removeChangeCallback(callback):
    __callbacks.discard(callback)

# The theme parameter is a horrible hack to load the theme before we
# can import other modules. pybridge makes the extra, early call
def load(theme = None):
    global __appConfig
    global __themeConfig
    global __data
    __lock.acquire()
    try:
        if __appConfig is None and __data is None:
            # There's some sleight-of-hand here. The Windows port needs to
            # look up config.LONG_APP_NAME and config.PUBLISHER to compute
            # the path to the data file that is read when load() is
            # called. Setting __appConfig to a true value (and populating
            # it with those keys) before calling load() ensures that (a)
            # the values will be available and (b) we won't get caught in
            # an infinite loop of load()s. But in general, you shouldn't
            # call config.get() or config.set() from platformcfg.load()
            # unless you know exactly what you are doing, and maybe not
            # even then.
            __appConfig = util.readSimpleConfigFile(resources.path('app.config'))

            # Load the preferences
            __data = platformcfg.load()
            if __data is None:
                __data = dict()

            # This is a bit of a hack to automagically get the serial
            # number for this platform
            prefs.APP_SERIAL.key = ('appSerial-%s' % get(prefs.APP_PLATFORM))
        if theme is not None:
            logging.info("Using theme %s" % theme)
            try:
                __themeConfig = util.readSimpleConfigFile(os.path.join(
                    get(prefs.THEME_DIRECTORY),
                    theme,
                    'app.config'))
            except:
                logging.warn("Failed to load theme %s" % theme)
                
    finally:
        __lock.release()

def save():
    __lock.acquire()
    try:
        __checkValidity()
        platformcfg.save( __data )
    finally:
        __lock.release()

def get(descriptor, useThemeData=True):
    __lock.acquire()
    try:
        __checkValidity()

        if __data is not None and descriptor.key in __data:
            return __data[descriptor.key]
        elif descriptor.platformSpecific:
            return platformcfg.get(descriptor)
        elif descriptor.key in __themeConfig and useThemeData:
            return __themeConfig[descriptor.key]
        elif descriptor.key in __appConfig:
            return __appConfig[descriptor.key]
        else:
            return descriptor.default
    finally:
        __lock.release()

def getList(descriptor):
    return [urllib.unquote(i) for i in get(descriptor).split(",") if i]

def getAppConfig():
    __lock.acquire()
    try:
        __checkValidity()
        return __appConfig.copy()
    finally:
        __lock.release()
    
def set(descriptor, value):
    __lock.acquire()
    logging.debug("Setting %s to %s", descriptor.key, value)
    try:
        __checkValidity()
        if descriptor.key not in __data or __data[ descriptor.key ] != value:
            __data[ descriptor.key ] = value
            __notifyListeners(descriptor.key, value)
    finally:
        __lock.release()

def setList(descriptor, value):
    set(descriptor, ','.join ([urllib.quote(i) for i in value]))

def __checkValidity():
    if __appConfig == None:
        load()

def __notifyListeners(key, value):
    for callback in __callbacks:
        eventloop.addIdle(callback, 'config callback: %s' % callback,
                args=(key,value))
