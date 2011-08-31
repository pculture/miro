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

def _get_support_directory():
    if u3info.u3_active:
        path = u3info.APP_DATA_PREFIX
    else:
        # We don't get the publisher and long app name from the config so
        # changing the app name doesn't change the support directory
        path = os.path.join(specialfolders.app_data_directory,
                            u'Participatory Culture Foundation',
                            u'Miro',
                            u'Support')

    try:
        fileutil.makedirs(path)
    except:
        pass
    return path

def _get_config_file():
    return fileutil.expand_filename(
        os.path.join(_get_support_directory(), "preferences.bin"))

def load():
    save_file = _get_config_file()

    # if Miro died while saving the config file, then it's likely there's
    # a save_file.new floating around and that's the one we want to use.
    new_save_file = save_file + ".new"
    if os.path.exists(new_save_file):
        save_file = new_save_file

    if os.path.exists(save_file):
        try:
            return cPickle.load(open(save_file))
        except cPickle.UnpicklingError:
            logging.exception("error loading config")
    return {}

def save(data):
    # save to a new file and if that's successful then rename it.
    # this reduces the chance that the user ends up with a hosed
    # preferences file.
    save_file = _get_config_file()
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
        return os.path.join(
            specialfolders.base_movies_directory,
            app.configfile['shortAppName'])

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        return specialfolders.non_video_directory

    elif descriptor == prefs.GETTEXT_PATHNAME:
        return resources.path("locale")

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        return fileutil.expand_filename(_get_support_directory())

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        return os.path.join(_get_support_directory(), 'icon-cache')

    elif descriptor == prefs.COVER_ART_DIRECTORY:
        return os.path.join(_get_support_directory(), 'cover-art')

    elif descriptor == prefs.SQLITE_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(path, 'sqlitedb')

    elif descriptor == prefs.CRASH_PATHNAME:
        directory = tempfile.gettempdir()
        return os.path.join(directory, "crashes")

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
        # we use the legacy startup registry key, so legacy versions
        # of Windows have a chance
        # http://support.microsoft.com/?kbid=270035

        try:
            folder = _winreg.OpenKey(
                _winreg.HKEY_CURRENT_USER,
                "Software\Microsoft\Windows\CurrentVersion\Run")
        except WindowsError, e:
            # 2 indicates that the key doesn't exist yet, so
            # RUN_AT_STARTUP is clearly False
            if e.errno == 2:
                logging.exception("windowserror kicked up at open key")
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
                # 22 indicates there are no more items in this folder
                # to iterate through.
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
    elif descriptor == prefs.AUTOUPDATE_URL:
        return prefs.get_from_environ('DTV_AUTOUPDATE_URL',
          u'http://www.participatoryculture.org/democracy-appcast-windows.xml')
    elif descriptor == prefs.AUTOUPDATE_BETA_URL:
        return prefs.get_from_environ('DTV_AUTOUPDATE_BETA_URL',
          u'http://www.participatoryculture.org/democracy-appcast-windows-beta.xml')
    # Proxy authorization isn't suppored on windows, so the following
    # keys are ignored:
    #
    # HTTP_PROXY_AUTHORIZATION_ACTIVE
    # HTTP_PROXY_AUTHORIZATION_USERNAME
    # HTTP_PROXY_AUTHORIZATION_PASSWORD
    else:
        return descriptor.default
