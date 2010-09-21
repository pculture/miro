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

import base64
import json
import logging
import os
import re
import urlparse

from miro import config
from miro import dialogs
from miro import eventloop
from miro import prefs

def decode_auth_header(auth_header):
    def match_group_1(regex):
        m = re.search(regex, auth_header)
        if m is None:
            return None
        else:
            return m.group(1)
    scheme = match_group_1("^(\w+) ")
    realm = match_group_1("realm\s*=\s*\"(.*?)\"")
    domain = match_group_1("domain\s*=\s*\"(.*?)\"")
    return (scheme, realm, domain)

class HTTPAuthPassword(object):
    def __init__(self, username, password, url, auth_header):
        self.username = username
        self.password = password
        self.url = url
        self.auth_header = auth_header

        self.scheme, self.realm, self.domain = decode_auth_header(auth_header)
        self.scheme = self.scheme.lower()
        if self.scheme not in ('basic', 'digest'):
            raise AssertionError("Unknown HTTPAuth Scheme: %s", self.scheme)
        self.urlparts = urlparse.urlparse(url)
        self.url_dir = os.path.dirname(self.urlparts.path) + "/"
        self.calc_domain_list()

    def calc_domain_list(self):
        if self.domain is None:
            self.domain_list = None
        else:
            # This is slightly weird because RFC 2617 specifies URLs are space
            # separated and RFC 2069 specifies they are comma separated.
            # Guess which one it is by searching for a comma, which is a
            # reserved URL char
            if ',' in self.domain:
                sep = ','
            else:
                sep = ' '
            self.domain_list = []
            for d in self.domain.split(sep):
                d = d.strip()
                if d != '':
                    if '://' not in d:
                        # no domain listed
                        if d.startswith('/'):
                            d = d[1:]
                        d = '%s://%s/%s' % (self.urlparts.scheme,
                                self.urlparts.netloc, d)

                    self.domain_list.append(d)

    def update_auth(self, username, password):
        self.username = username
        self.password = password

    def same_realm(self, other_pw):
        return self.realm == other_pw.realm

    def should_use_for_request(self, url):
        request_parts = urlparse.urlparse(url)
        if url == self.url:
            return True
        if self.scheme == 'basic':
            return (self.urlparts.netloc == request_parts.netloc and
                    request_parts.path.startswith(self.url_dir))
        elif self.scheme == 'digest':
            if self.domain is None:
                return self.urlparts.netloc == request_parts.netloc
            else:
                for domain in self.domain_list:
                    if url.startswith(domain):
                        return True
                return False
        else:
            raise AssertionError("Unknown HTTPAuth Scheme: %s", self.scheme)

class HTTPPasswordList(object):
    def __init__(self):
        self.passwords = []

    def write_to_file(self, path):
        dump_data = []
        for p in self.passwords:
            dump_data.append({
                'username': p.username,
                'password': p.password,
                'url': p.url,
                'auth_header': p.auth_header,
        })
        try:
            f = open(path, 'wt')
            data = json.dumps(dump_data, indent=4)
            f.write(base64.b64encode(data))
            f.close()
        except IOError, e:
            logging.warn("Error writing out HTTP Passwords: %s", e)

    def restore_from_file(self, path):
        if not os.path.exists(path):
            return
        try:
            f = open(path, 'rt')
            data = f.read()
            dump_data = json.loads(base64.b64decode(data))
        except Exception, e:
            logging.warn("Error reading in HTTP Passwords: %s", e)
        else:
            for d in dump_data:
                self.add(d['username'], d['password'], d['url'],
                        d['auth_header'])

    def add(self, user, password, url, auth_header):
        new_pw = HTTPAuthPassword(user, password, url, auth_header)

        # Actually adding the auth is a bit tricky, because we want to remove
        # any old, quite possibly bad, passwords.

        found_index = self._find_password_with_realm(new_pw)
        if found_index < 0:
            # We didn't find any old password to replace, add the new password
            # to the end of the list and we're done
            self.passwords.append(new_pw)
            return new_pw
        else:
            # We found an old password to replace.  Try to pick the best
            # password to use.  This will be the password with the shortest
            # URL.  For domain auth it shouldn't matter, but for basic auth,
            # the shortest URL will match the most URLs in the future
            old_pw = self.passwords[found_index]
            if len(old_pw.url) < len(new_pw.url):
                # old password has the largest domain, update that
                old_pw.update_auth(new_pw.username, new_pw.password)
                final_pw = old_pw
            else:
                # new password has the largest domain, replace the old
                self.passwords[found_index] = new_pw
                final_pw = new_pw
            # for good measure, delete any extra passwords with the same realm
            for i in reversed(xrange(found_index+1, len(self.passwords))):
                if final_pw.same_realm(self.passwords[i]):
                    del self.passwords[i]
            return final_pw

    def _find_password_with_realm(self, pw):
        """Find a password in our current list with the same realm as pw

        :returns: the index of the first password where this is True, or -1
        """

        for i, other_pw in enumerate(self.passwords):
            if pw.same_realm(other_pw):
                return i
        return -1

    def find(self, url):
        for p in self.passwords:
            if p.should_use_for_request(url):
                return p
        return None

    def remove(self, auth):
        try:
            self.passwords.remove(auth)
        except ValueError:
            logging.warn("Trying to remove HTTPAuthPassword that's not in "
                    "the list: %s", auth)

def find_http_auth(callback, url):
    """Find an HTTPAuthPassword object stored in the database

    This method searches the database for already entered passwords.  It
    will find a string to use for the Authorization header or None.

    We use a callback to return the data because that's how we have to do it
    inside the downloader daemon (see dl_daemon/private/httpauth.py).

    :param callback: will be called with a HTTPAuthPassword to use, or None
    :param url: request URL
    """
    global password_list
    auth = password_list.find(url)
    eventloop.add_idle(callback, 'find_http_auth callback', args=(auth,))

class CallbackTracker(object):
    """Used internally to track callbacks for dialogs for ask_for_http_auth().

    This class allows us to to only pop up one dialog for each auth request.
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
    if auth_scheme is None:
        raise ValueError("Scheme not present in auth header: %s" %
                auth_header)
    if realm is None:
        raise ValueError("Realm not present in auth header: %s" %
                auth_header)

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

def init():
    global password_list
    global callback_tracker
    password_list = HTTPPasswordList()
    callback_tracker = CallbackTracker()

def _default_password_file():
    support_dir = config.get(prefs.SUPPORT_DIRECTORY)
    return os.path.join(support_dir, 'httpauth')

def restore_from_file(path=None):
    if path is None:
        path = _default_password_file()
    password_list.restore_from_file(path)

def write_to_file(path=None):
    if path is None:
        path = _default_password_file()
    password_list.write_to_file(path)
