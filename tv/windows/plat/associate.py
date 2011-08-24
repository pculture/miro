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

import _winreg
import logging
from miro import prefs
from miro import app

def associate_extensions(executable_path, icon_path):
    try:
        if not _is_associated():
            _asssociate_extension("Magnet", "Magnet URI", ".magnet",
                                  "application/x-magnet", executable_path,
                                  icon_path, is_protocol=True)
        _register_with_magnet_exe(executable_path, icon_path)
    except WindowsError, e:
        if e.winerror == 5:
            logging.debug("Access denied when trying to associate "
                          "the magnet protocol")
        else:
            raise

def _is_associated(executable_path=None):
    """ Checks whether the magnet protocol currently is
        associated with the given executable path, or,
        if none is given, whether the magnet protocol
        is associated with anything at all.
    """

    sub_key = "magnet\\shell\\open\\command"
    try:
        handle = _winreg.OpenKey(_winreg.HKEY_CLASSES_ROOT, sub_key,
                                 0, _winreg.KEY_QUERY_VALUE)
    except WindowsError, e:
        if e.errno == 2:
            # Key does not exist
            return False
        else:
            raise
    try:
        path = _winreg.QueryValue(_winreg.HKEY_CLASSES_ROOT, sub_key)
        if executable_path:
            is_associated = path.lower() == executable_path
        else:
            is_associated = len(path) > 0
    except ValueError:
        is_associated = False
    return is_associated

def _register_with_magnet_exe(executable_path, icon_path):
    """ Registers Miro with the magnet.exe utlity
    """
    sub_key = ("Software\\magnet\\handlers\\" +
               app.config.get(prefs.SHORT_APP_NAME) + "\\")
    try:
        handle = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, sub_key,
                                 0, _winreg.KEY_SET_VALUE)
    except WindowsError, e:
        if e.errno == 2:
            # Key does not exist
            save_string_HKLM(sub_key, "DefaultIcon", "\"" + icon_path + ", 0\"")
            value = "Download with " + app.config.get(prefs.SHORT_APP_NAME)
            save_string_HKLM(sub_key, "Description", value)
            save_string_HKLM(sub_key, "ShellExecute",
                             "\"" + executable_path + "\" %URL")
            save_word_HKLM(sub_key + "\\Type", "urn:btih", 0)
        elif e.winerror == 5:
            logging.debug("Access denied when trying to register with magnet.exe")
        else:
            raise

def _asssociate_extension(name, description, extension, content_type,
                          executable_path, icon_path, is_protocol):
    prefix = "Software\\Classes\\"
    save_string_HKCU(prefix + extension, "", name)
    save_string_HKCU(prefix + extension, "Content Type", content_type)
    save_string_HKCU(prefix + "MIME\\Database\\Content Type\\" + content_type,
                     "Extension", extension)
    save_string_HKCU(prefix + name, "", description)
    save_string_HKCU(prefix + name + "\\shell", "", "open")
    save_string_HKCU(prefix + name + "\\DefaultIcon", "", icon_path + ", 0")
    sub_key = prefix + name + "\\shell\\open\\command"
    save_string_HKCU(sub_key, "", "\"" + executable_path + "\" \"%1\"")
    save_string_HKCU(prefix + name, "Content Type", content_type)
    if is_protocol:
        save_string_HKCU(prefix + name, "URL Protocol", "")

def save_string_HKLM(sub_key, name, value):
    save_value(_winreg.HKEY_LOCAL_MACHINE, sub_key, name, value,
               _winreg.REG_SZ)

def save_string_HKCU(sub_key, name, value):
    save_value(_winreg.HKEY_CURRENT_USER, sub_key, name, value,
               _winreg.REG_SZ)

def save_word_HKLM(sub_key, name, value):
    save_value(_winreg.HKEY_LOCAL_MACHINE, sub_key, name, value,
               _winreg.REG_DWORD)

def save_word_HKCU(sub_key, name, value):
    save_value(_winreg.HKEY_CURRENT_USER, sub_key, name, value,
               _winreg.REG_DWORD)

def save_value(constant, sub_key, name, value, type_=_winreg.REG_SZ):
    try:
        handle = _winreg.OpenKey(constant, sub_key, 0, _winreg.KEY_SET_VALUE)
    except WindowsError, e:
        if e.errno == 2:
            handle = _winreg.CreateKey(constant, sub_key)
        else:
            raise
    _winreg.SetValueEx(handle, name, 0, type_, value)
