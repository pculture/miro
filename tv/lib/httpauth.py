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

from miro import app
from miro import dialogs
from miro import prefs

from miro.httpauthtools import HTTPPasswordList, decode_auth_header

def find_http_auth(url, auth_header=None):
    """Find an HTTPAuthPassword object stored in the passwords database.

    This method searches the database for already entered passwords.  It
    will find a string to use for the Authorization header or None.

    :param url: request URL
    :param auth_header: optional www-authenticate header to use to search for.
        This allows us to better match basic auth passwords
    """
    global password_list
    if auth_header is not None:
        auth_scheme, realm, domain = decode_auth_header(auth_header)
    else:
        realm = None
    return password_list.find(url, realm)

class CallbackTracker(object):
    """Used internally to track callbacks for dialogs for ask_for_http_auth().

    This class allows us to only pop up one dialog for each auth request.
    """
    def __init__(self):
        self.callback_map = {}

    def has_callback(self, url, realm):
        key = (url, realm)
        return key in self.callback_map

    def add_callback(self, callback, url, realm):
        key = (url, realm)
        callbacks = self.callback_map.setdefault(key, [])
        callbacks.append(callback)

    def run_callbacks(self, url, realm, username, password, auth_header):
        key = (url, realm)
        auth = password_list.add(username, password, url, auth_header)
        for callback in self.callback_map[key]:
            callback(auth)
        del self.callback_map[key]

    def run_canceled_callbacks(self, url, realm):
        key = (url, realm)
        for callback in self.callback_map[key]:
            callback(None)
        del self.callback_map[key]

def ask_for_http_auth(callback, url, auth_header, location):
    """Ask the user for a username and password to login to a site.

    :param callback: will be called with a HTTPAuthPassword to use, or None
    :param url: URL for the request
    :param auth_header: www-authenticate header we got from the server
    :param location: human readable text of what's requesting authorization
    """
    global password_list

    auth_scheme, realm, domain = decode_auth_header(auth_header)

    def handleLoginResponse(dialog):
        if dialog.choice == dialogs.BUTTON_OK:
            callback_tracker.run_callbacks(url, realm, dialog.username,
                    dialog.password, auth_header)
        else:
            callback_tracker.run_canceled_callbacks(url, realm)

    run_dialog = (not callback_tracker.has_callback(url, realm))
    callback_tracker.add_callback(callback, url, realm)
    if run_dialog:
        dialogs.HTTPAuthDialog(location, realm).run(handleLoginResponse)

def remove(auth):
    global password_list
    password_list.remove(auth)

password_list = None
callback_tracker = None

def init():
    global password_list
    global callback_tracker
    password_list = HTTPPasswordList()
    callback_tracker = CallbackTracker()

def _default_password_file():
    support_dir = app.config.get(prefs.SUPPORT_DIRECTORY)
    return os.path.join(support_dir, 'httpauth')

def restore_from_file(path=None):
    if path is None:
        path = _default_password_file()
    password_list.restore_from_file(path)

def write_to_file(path=None):
    if path is None:
        path = _default_password_file()
    password_list.write_to_file(path)

def all_passwords():
    """Get the current list of all HTTPAuthPassword objects."""
    global password_list
    return password_list.passwords

def add_change_callback(callback):
    """Register to get changes to the list of HTTPAuthPassword objects

    The callback will be called with the entire list of passwords whenever it
    is updated.

    :returns: a callback handle that can be passed to remove_change_callback
    """
    global password_list
    def callback_wrapper(obj, passwords):
        callback(passwords)
    return password_list.connect("passwords-updated", callback_wrapper)

def remove_change_callback(callback_handle):
    global password_list
    password_list.disconnect(callback_handle)
