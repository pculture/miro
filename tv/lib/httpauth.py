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

import re

from miro.download_utils import parse_url
from miro import dialogs
from miro import eventloop
from miro import models

def find_http_auth(callback, url):
    """Find an HTTPAuthPassword object stored in the database

    This method searches the database for already entered passwords.  It
    will find a string to use for the Authorization header or None.

    We use a callback to return the data because that's how we have to do it
    inside the downloader daemon (see dl_daemon/private/httpauth.py).

    :param callback: will be called with a HTTPAuthPassword to use, or None
    :param url: request URL
    """
    from miro import downloader

    scheme, host, port, path = parse_url(url)
    auth = downloader.find_http_auth(host, path)
    eventloop.add_idle(callback, 'find_http_auth callback', args=(auth,))

def decode_auth_header(auth_header):
    def match_group_1(regex):
        m = re.search(regex, auth_header)
        if m is None:
            return None
        else:
            return unicode(m.group(1))
    scheme = match_group_1("^(\w+) ")
    realm = match_group_1("realm\s*=\s*\"(.*?)\"")
    domain = match_group_1("domain\s*=\s*\"(.*?)\"")
    return (scheme, realm, domain)

def ask_for_http_auth(callback, url, auth_header):
    """Ask the user for a username and password to login to a site.

    :param callback: will be called with a HTTPAuthPassword to use, or None
    :param url: URL for the request
    :param auth_header: www-authenticate header we got from the server
    """

    scheme, host, port, path = parse_url(url)
    auth_scheme, realm, domain = decode_auth_header(auth_header)
    if auth_scheme is None:
        raise ValueError("Scheme not present in auth header: %s" %
                auth_header)
    if realm is None:
        raise ValueError("Realm not present in auth header: %s" %
                auth_header)

    def handleLoginResponse(dialog):
        if dialog.choice == dialogs.BUTTON_OK:
            auth = models.HTTPAuthPassword(dialog.username,
                    dialog.password, host, realm, path, auth_scheme)
            callback(auth)
        else:
            callback(None)
    dialogs.HTTPAuthDialog(url, realm).run(handleLoginResponse)
