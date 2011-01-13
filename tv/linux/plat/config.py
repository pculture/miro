# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

"""miro.plat.config

This module implements configuration persistence for the linux
platform.  Miro persists configuration preferences for linux platform
to gconf.

Preferences are listed in miro.pref and also miro.plat.options.
"""

import os
import logging
from miro import prefs
import gconf
import threading
from miro.plat import options
from miro.plat import resources

client = gconf.client_get_default()
gconf_lock = threading.RLock()

def _gconf_key(key):
    if options.gconf_name is None:
        options.gconf_name = "miro"
    return '/apps/%s/%s' % (options.gconf_name, key)

def _convert_gconf_value(value):
    if value.type == gconf.VALUE_STRING:
        return value.get_string()
    if value.type == gconf.VALUE_INT:
        return value.get_int()
    if value.type == gconf.VALUE_BOOL:
        return value.get_bool()
    if value.type == gconf.VALUE_FLOAT:
        return value.get_float()
    if value.type == gconf.VALUE_LIST:
        return [_convert_gconf_value(v) for v in value.get_list()]
    raise TypeError("unknown gconf type %s" % value.type)

def _get_gconf(fullkey, default=None):
    gconf_lock.acquire()
    try:
        value = client.get(fullkey)
        if value != None:
            try:
                return _convert_gconf_value(value)
            except TypeError, e:
                logging.warn("type error while getting gconf value %s: %s",
                        fullkey, str(e))
        return default
    finally:
        gconf_lock.release()

class GconfDict:
    def get(self, key, default=None):
        if not isinstance(key, str):
            raise TypeError()

        if "MIRO_%s" % key.upper() in os.environ:
            return os.environ["MIRO_%s" % key.upper()]

        fullkey = _gconf_key(key)
        return _get_gconf(fullkey, default)

    def __contains__(self, key):
        if "MIRO_%s" % key.upper() in os.environ:
            return True

        gconf_lock.acquire()
        try:
            fullkey = _gconf_key(key)
            return client.get(fullkey) is not None
        finally:
            gconf_lock.release()

    def __getitem__(self, key):
        rv = self.get(key)
        if rv is None:
            raise KeyError
        else:
            return rv

    def __setitem__(self, key, value):
        if "MIRO_%s" % key.upper() in os.environ:
            return

        gconf_lock.acquire()
        try:
            if not isinstance(key, str):
                raise TypeError()

            fullkey = _gconf_key(key)
            if isinstance(value, str):
                client.set_string(fullkey, value)
            elif isinstance(value, bool):
                client.set_bool(fullkey, value)
            elif isinstance(value, int):
                client.set_int(fullkey, value)
            elif isinstance(value, float):
                client.set_float(fullkey, value)
            elif isinstance(value, list):
                # this is lame, but there isn't enough information to
                # figure it out another way
                if len(value) == 0 or isinstance(value[0], str):
                    list_type = gconf.VALUE_STRING
                elif isinstance(value[0], int):
                    list_type = gconf.VALUE_INT
                elif isinstance(value[0], float):
                    list_type = gconf.VALUE_FLOAT
                elif isinstance(value[0], bool):
                    list_type = gconf.VALUE_BOOL
                else:
                    raise TypeError("unknown gconf type %s" % type(value[0]))

                client.set_list(fullkey, list_type, value)
            else:
                raise TypeError()
        finally:
            gconf_lock.release()

def load():
    return GconfDict()

def save(data):
    pass

def get(descriptor):
    value = descriptor.default

    if descriptor == prefs.MOVIES_DIRECTORY:
        value = os.path.expanduser(os.path.join(options.user_home, 'Videos/Miro'))

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        value = os.path.expanduser(os.path.join(options.user_home, 'Desktop'))

    elif descriptor == prefs.GETTEXT_PATHNAME:
        value = resources.path("../../locale")

    elif descriptor == prefs.RUN_AT_STARTUP:
        autostart_dir = resources.get_autostart_dir()
        destination = os.path.join(autostart_dir, "miro.desktop")
        value = os.path.exists(destination)

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        value = os.path.expanduser(os.path.join(options.user_home, '.miro'))

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'icon-cache')

    elif descriptor == prefs.SQLITE_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'sqlitedb')

    elif descriptor == prefs.LOG_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'miro.log')
    
    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'miro-downloader.log')

    elif descriptor == prefs.HTTP_PROXY_ACTIVE:
        return _get_gconf("/system/http_proxy/use_http_proxy")

    elif descriptor == prefs.HTTP_PROXY_HOST:
        return _get_gconf("/system/http_proxy/host")

    elif descriptor == prefs.HTTP_PROXY_PORT:
        return _get_gconf("/system/http_proxy/port")

    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_ACTIVE:
        return _get_gconf("/system/http_proxy/use_authentication")

    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_USERNAME:
        return _get_gconf("/system/http_proxy/authentication_user")

    elif descriptor == prefs.HTTP_PROXY_AUTHORIZATION_PASSWORD:
        return _get_gconf("/system/http_proxy/authentication_password")

    elif descriptor == prefs.HTTP_PROXY_IGNORE_HOSTS:
        return _get_gconf("/system/http_proxy/ignore_hosts", [])

    return value
