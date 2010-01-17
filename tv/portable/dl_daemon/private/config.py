# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

from threading import Event, Lock
from miro import prefs
import miro.plat.config

_data = {}
_dataLock = Lock()

_ready = Event()

__callbacks = set()

def add_change_callback(callback):
    __callbacks.add(callback)

def remove_change_callback(callback):
    __callbacks.discard(callback)

def setDictionary(d):
    global _data
    #print "set initial remote config %s" % repr(d)
    _dataLock.acquire()
    try:
        _data = d
    finally:
        _dataLock.release()
    prefs.APP_SERIAL.key = 'appSerial-%s' % d[prefs.APP_PLATFORM.key]
    _ready.set()

def updateDictionary (key, value):
    _dataLock.acquire()
    try:
        _data[key] = value
    finally:
        _dataLock.release()
    for callback in __callbacks:
        callback(key, value)

def get(descriptor):
    _ready.wait()
    _dataLock.acquire()
    try:
        if descriptor.key in _data:
            return _data[descriptor.key]
        elif descriptor.platformSpecific:
            return miro.plat.config.get(descriptor)
        else:
            return descriptor.default
    finally:
        _dataLock.release()
