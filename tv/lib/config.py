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

import functools
import logging
from threading import RLock

from miro.appconfig import AppConfig
from miro import app
from miro import prefs
from miro import signals
from miro.plat import config as platformcfg

def _with_lock(func):
    """Wrapper function that uses a lock to synchronize access."""
    def lock_wrapper(self, *args, **kwargs):
        self._lock.acquire()
        try:
            func(self, *args, **kwargs)
        finally:
            self._lock.release()
    return functools.update_wrapper(lock_wrapper, func)

class ConfigurationBase(object):
    """Base class for Configuration handling
    """

    def __init__(self):
        self._data = None
        self._lock = RLock()
        self._watchers = set()

        # Load the preferences
        self._data = platformcfg.load()
        if self._data is None:
            self._data = dict()

    @_with_lock
    def _add_watcher(self, watcher):
        """Add a ConfigWatcher to our internal list.
        """
        self._watchers.add(watcher)

    @_with_lock
    def _remove_watcher(self, watcher):
        """Remove a ConfigWatcher from our list.
        """
        self._watchers.discard(watcher)

    @_with_lock
    def get(self, descriptor):
        return self._data[descriptor.key]

    @_with_lock
    def set(self, descriptor, value):
        self.set_key(descriptor.key, value)

    @_with_lock
    def set_key(self, key, value):
        logging.debug("Setting %s to %s", key, value)
        if (key not in self._data or
                self._data[key] != value):
            self._data[key] = value
            self._emit_on_watchers("changed", key, value)

    def _emit_on_watchers(self, signal, *args):
        for watcher in self._watchers:
            watcher.emit(signal, *args)

class Configuration(ConfigurationBase):
    """Configuration class used in the main process

    config.load() sets up the global Configuration object using the app.config
    variable.
    """

    def __init__(self):
        ConfigurationBase.__init__(self)
        # This is a bit of a hack to automagically get the serial
        # number for this platform
        prefs.APP_SERIAL.key = 'appSerial-%s' % self.get(prefs.APP_PLATFORM)

    def get(self, descriptor, use_theme_data=True):
        if descriptor.key in self._data:
            value = self._data[descriptor.key]
            if ((descriptor.possible_values is not None
                 and not value in descriptor.possible_values)):
                logging.warn(
                    'bad preference value %s for key %s.  using failsafe: %s',
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

    @_with_lock
    def save(self):
        platformcfg.save(self._data)

class DownloaderConfig(ConfigurationBase):
    """Configuration class for the downloader
    """

    def __init__(self):
        ConfigurationBase.__init__(self)
        self._initial_config_loaded = False

    def set_dictionary(self, data):
        if self._initial_config_loaded:
            raise AssertionError("set dictionary called twice")
        self._data = data
        self._initial_config_loaded = True

    def get(self, pref):
        if pref.key in self._data:
            return self._data[pref.key]
        elif pref.platformSpecific:
            return platformcfg.get(pref)
        else:
            return pref.default

class TemporaryConfiguration(Configuration):
    """Configuration class for the unit tests"""
    def __init__(self):
        Configuration.__init__(self)
        # make _data a plain dict.  On linux, we don't want this to be a
        # GConfDict, which auto-saves changes
        self._data = {}

    def save(self):
        pass

class ConfigWatcher(signals.SignalEmitter):
    """Emits signals when the config changes.

    Config changes can happen in any thread.  This class allows us to have
    signals handlers always execute in the same thread.

    signals:
        changed(key, value) : a config value changed
    """
    def __init__(self, thread_caller):
        """Construct a ConfigWatcher

        This class needs a function that can call another function in a
        specific thread.  It should input (func, *args), and call func with
        args on the thread.

        Typical Example:
        def thread_caller(func, *args):
            eventloop.add_idle(func, "config callback", args=args)
        app.backend_config_watcher = ConfigWatcher(thread_caller)

        :args thread_caller: function that invoke another function in a
            specific thread.
        """
        signals.SignalEmitter.__init__(self, 'changed')
        self.thread_caller = thread_caller
        app.config._add_watcher(self)

    def emit(self, signal, *args):
        self.thread_caller(signals.SignalEmitter.emit,
                self, signal, *args)

    def destroy(self):
        app.config._remove_watcher(self)

def load(config_obj=None):
    if app.config is not None:
        raise AssertionError("Config already loaded")
    app.configfile = AppConfig(None)
    if config_obj is None:
        app.config = Configuration()
    else:
        app.config = config_obj

def load_temporary():
    """This initializes temporary mode where all configuration
    set calls are temporary.
    """
    app.configfile = AppConfig(None)
    app.config = TemporaryConfiguration()

def set_theme(theme):
    """Setup the theme to get config data from.

    This method exists because we need to create the config object ASAP,
    before we know the theme on some platforms.  Therfore, we create the
    config object, then later on set the theme.
    """
    app.configfile = AppConfig(theme)
