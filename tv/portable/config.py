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

"""``miro.config`` -- Configuration and preference related functions.
"""

from threading import RLock

from miro.appconfig import AppConfig
from miro import app
from miro import prefs
from miro.plat import config as platformcfg
import logging

_data = None
_lock = RLock()
_callbacks = set()

def add_change_callback(callback):
    """Attaches change notification callback functions.

    Callback functions should have a signature like
    ``callback_function: key * value -> None``.  Example::

        def callback_function(key, value):
            if key == prefs.PRESERVE_X_GB_FREE:
                blah blah blah
    """
    _callbacks.add(callback)

def remove_change_callback(callback):
    """Removes change notification callback functions.
    """
    _callbacks.discard(callback)

def load(theme=None):
    global _data
    _lock.acquire()
    try:
        app.configfile = AppConfig(theme)
        # Load the preferences
        _data = platformcfg.load()
        if _data is None:
            _data = dict()

        # This is a bit of a hack to automagically get the serial
        # number for this platform
        prefs.APP_SERIAL.key = 'appSerial-%s' % get(prefs.APP_PLATFORM)

    finally:
        _lock.release()

def save():
    _lock.acquire()
    try:
        _check_validity()
        platformcfg.save( _data )
    finally:
        _lock.release()

def get(descriptor, use_theme_data=True):
    _lock.acquire()
    try:
        _check_validity()

        if _data is not None and descriptor.key in _data:
            value = _data[descriptor.key]
            if ((descriptor.possible_values is not None
                 and not value in descriptor.possible_values)):
                logging.warn('bad preference value %s for key %s.  using failsafe: %s',
                             value, descriptor.key, descriptor.failsafe_value)
                return descriptor.failsafe_value
            else:
                return value
        elif descriptor.platformSpecific:
            return platformcfg.get(descriptor)
        if app.configfile.contains(descriptor.key, use_theme_data):
            return app.configfile.get(descriptor.key, use_theme_data)
        else:
            return descriptor.default
    finally:
        _lock.release()

def set(descriptor, value):
    _lock.acquire()
    logging.debug("Setting %s to %s", descriptor.key, value)
    try:
        _check_validity()
        if descriptor.key not in _data or _data[descriptor.key] != value:
            _data[descriptor.key] = value
            _notify_listeners(descriptor.key, value)
    finally:
        _lock.release()

def _check_validity():
    if _data == None:
        load()

def _notify_listeners(key, value):
    from miro import eventloop
    for callback in _callbacks:
        eventloop.addIdle(callback, 'config callback: %s' % callback,
                          args=(key, value))
