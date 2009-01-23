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

"""miro.plat.config

This module implements configuration persistence for the gtkx11 platform.
Miro persists configuration preferences for gtkx11 platform to gconf.

Preferences are listed in miro.pref and also miro.plat.options.
"""

import os
from miro import prefs
import gconf
import threading
from miro.plat import resources

client = gconf.client_get_default()
gconf_lock = threading.RLock()

def _get_gconf(fullkey, default=None):
    gconf_lock.acquire()
    try:
        value = client.get(fullkey)
        if value != None:
            if value.type == gconf.VALUE_STRING:
                return value.get_string()
            if value.type == gconf.VALUE_INT:
                return value.get_int()
            if value.type == gconf.VALUE_BOOL:
                return value.get_bool()
            if value.type == gconf.VALUE_FLOAT:
                return value.get_float()
        return default
    finally:
        gconf_lock.release()

class GconfDict:
    def get(self, key, default=None):
        if not isinstance(key, str):
            raise TypeError()
        fullkey = '/apps/miro/' + key
        return _get_gconf(fullkey, default)

    def __contains__(self, key):
        gconf_lock.acquire()
        try:
            fullkey = '/apps/miro/' + key
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
        gconf_lock.acquire()
        try:
            if not isinstance(key, str):
                raise TypeError()

            fullkey = '/apps/miro/' + key
            if isinstance(value, str):
                client.set_string(fullkey, value)
            elif isinstance(value, bool):
                client.set_bool(fullkey, value)
            elif isinstance(value, int):
                client.set_int(fullkey, value)
            elif isinstance(value, float):
                client.set_float(fullkey, value)
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
        value = os.path.expanduser('~/Movies/Miro')

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        value = os.path.expanduser('~/Desktop')

    elif descriptor == prefs.GETTEXT_PATHNAME:
        value = resources.path("../../locale")

    elif descriptor == prefs.RUN_AT_STARTUP:
        autostart_dir = resources.get_autostart_dir()
        destination = os.path.join(autostart_dir, "miro.desktop")
        value = os.path.exists(destination)

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        value = os.path.expanduser('~/.miro')

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        value = os.path.expanduser('~/.miro/icon-cache')

    elif descriptor == prefs.DB_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'tvdump')

    elif descriptor == prefs.BSDDB_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'database')

    elif descriptor == prefs.SQLITE_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'sqlitedb')

    elif descriptor == prefs.LOG_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'miro-log')
    
    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        value = get(prefs.SUPPORT_DIRECTORY)
        value = os.path.join(value, 'miro-downloader-log')

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
