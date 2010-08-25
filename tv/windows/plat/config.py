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

import os
import _winreg
import cPickle
import logging
import string
import tempfile
import traceback
import shutil

from miro import app
from miro import prefs
from miro import util
from miro import u3info
from miro import fileutil
from miro.plat import proxyfind
from miro.plat import resources
from miro.plat import specialfolders

proxy_info = proxyfind.get_proxy_info()

def _getSupportDirectory():
    if u3info.u3_active:
        path = u3info.APP_DATA_PREFIX
    else:
        # We don't get the publisher and long app name from the config so
        # changing the app name doesn't change the support directory
        path = os.path.join(specialfolders.appDataDirectory,
                            u'Participatory Culture Foundation',
                            u'Miro',
                            u'Support')

    try:
        fileutil.makedirs(path)
    except:
        pass
    return path

def _getConfigFile():
    return fileutil.expand_filename(os.path.join(_getSupportDirectory(), "preferences.bin"))

def load():
    save_file = _getConfigFile()

    # if Miro died while saving the config file, then it's likely there's
    # a save_file.new floating around and that's the one we want to use.
    new_save_file = save_file + ".new"
    if os.path.exists(new_save_file):
        save_file = new_save_file

    if os.path.exists(save_file):
        try:
            return cPickle.load(open(save_file))
        except:
            logging.warn("Error loading config: %s", traceback.format_exc())
    return {}

def save(data):
    # save to a new file and if that's successful then rename it.  this
    # reduces the chance that the user ends up with a hosed preferences
    # file.
    save_file = _getConfigFile()
    new_file = save_file + ".new"
    try:
        f = open(new_file, 'w')
        cPickle.dump(data, f)
        f.close()

        if not os.path.exists(save_file):
            shutil.move(new_file, save_file)
            return

        os.remove(save_file)
        shutil.move(new_file, save_file)
    except:
        raise

def get(descriptor):
    if descriptor == prefs.MOVIES_DIRECTORY:
        return os.path.join(specialfolders.baseMoviesDirectory, app.configfile['shortAppName'])

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        return specialfolders.nonVideoDirectory

    elif descriptor == prefs.GETTEXT_PATHNAME:
        return resources.path("locale")

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        return fileutil.expand_filename(_getSupportDirectory())

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        return os.path.join(_getSupportDirectory(), 'icon-cache')

    elif descriptor == prefs.SQLITE_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(path, 'sqlitedb')

    elif descriptor == prefs.LOG_PATHNAME:
        if u3info.u3_active:
            directory = u3info.app_data_path
        else:
            directory = tempfile.gettempdir()
        return os.path.join(directory, 
                ('%s.log' % app.configfile['shortAppName']))

    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        if u3info.u3_active:
            directory = u3info.app_data_path
        else:
            directory = tempfile.gettempdir()
        return os.path.join(directory,
            ('%s-downloader.log' % app.configfile['shortAppName']))

    elif descriptor == prefs.RUN_AT_STARTUP:
        import logging
        # We use the legacy startup registry key, so legacy versions
        # of Windows have a chance
        # http://support.microsoft.com/?kbid=270035

        try:
            folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,
                                     "Software\Microsoft\Windows\CurrentVersion\Run")
        except WindowsError, e:
            # 2 indicates that the key doesn't exist yet, so
            # RUN_AT_STARTUP is clearly False
            if e.errno == 2:
                logging.exception("=== windowserror kicked up at open key ===")
                return False
            raise
        long_app_name = app.configfile['longAppName']
        count = 0
        while True:
            try:
                name, val, type_ = _winreg.EnumValue(folder, count)
                count += 1
                if name == long_app_name:
                    return True                    
            except WindowsError, e:
                # 22 indicates there are no more items in this folder to
                # iterate through.
                if e.errno == 22:
                    return False
                else:
                    raise
        return False

    elif descriptor == prefs.HTTP_PROXY_ACTIVE:
        return proxy_info.host is not None
    elif descriptor == prefs.HTTP_PROXY_HOST:
        return proxy_info.host
    elif descriptor == prefs.HTTP_PROXY_PORT:
        return proxy_info.port
    elif descriptor == prefs.HTTP_PROXY_IGNORE_HOSTS:
        return proxy_info.ignore_hosts
    # Proxy authorization isn't suppored on windows, so the following keys are
    # ignored:
    # 
    # HTTP_PROXY_AUTHORIZATION_ACTIVE
    # HTTP_PROXY_AUTHORIZATION_USERNAME
    # HTTP_PROXY_AUTHORIZATION_PASSWORD
    else:
        return descriptor.default
