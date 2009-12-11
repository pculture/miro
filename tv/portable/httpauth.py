# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

from miro.download_utils import parse_url
from miro import dialogs
from miro import eventloop
from miro import models

def formatAuthString(auth):
    return "%s %s" % (auth.get_auth_scheme(), auth.get_auth_token())

def find_http_auth(callback, host, path):
    """Find an HTTPAuthPassword object stored in the database.  Callback will
    be called with a string to use for the Authorization header or None if we
    can't find anything in the DB.
    """
    from miro import downloader

    auth = downloader.find_http_auth(host, path)
    if auth is not None:
        auth = formatAuthString(auth)
    eventloop.addIdle(callback, "http auth callback", args=(auth,))

def askForHTTPAuth(callback, url, realm, authScheme):
    """Ask the user for a username and password to login to a site.  Callback
    will be called with a string to use for the Authorization header or None
    if the user clicks cancel.
    """

    scheme, host, port, path = parse_url(url)
    def handleLoginResponse(dialog):
        if dialog.choice == dialogs.BUTTON_OK:
            auth = models.HTTPAuthPassword(dialog.username,
                    dialog.password, host, realm, path, authScheme)
            callback(formatAuthString(auth))
        else:
            callback(None)
    dialogs.HTTPAuthDialog(url, realm).run(handleLoginResponse)
