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

"""
Holds functions that associate Miro with certain protocols
"""

import gconf
from miro.plat.config import gconf_lock

def associate_protocols(command):
    _associate_protocol("magnet", command, False)

def disassociate_protocols(command):
    _disassociate_protocol("magnet", command)

def _associate_protocol(name, command, overwrite_existing=False):
    url_handlers_key = "/desktop/gnome/url-handlers/" + name + "/"
    if not _is_associated(name) or overwrite_existing:
        gconf_lock.acquire()
        try:
            gconf_client = gconf.client_get_default()
            if gconf_client.set_string(url_handlers_key + "command", command):
                gconf_client.set_bool(url_handlers_key + "needs_terminal", False)
                gconf_client.set_bool(url_handlers_key + "enabled", True)
                success = True
            else:
                success = False
        finally:
            gconf_lock.release()
    else:
        success = True
    return success

def _disassociate_protocol(name, command):
    url_handlers_key = "/desktop/gnome/url-handlers/" + name + "/"
    if _is_associated(name, command):
        gconf_lock.acquire()
        try:
            gconf_client = gconf.client_get_default()
            if gconf_client.set_bool(url_handlers_key + "enabled", False):
                success = True
            else:
                success = False
        finally:
            gconf_lock.release()
    else:
        success = True
    return success

def _is_associated(protocol, command=None):
    """ Checks whether a protocol currently is
        associated with the given command, or,
        if none is given, whether the protocol
        is associated with anything at all.
    """
    url_handlers_key = "/desktop/gnome/url-handlers/" + protocol + "/"
    gconf_lock.acquire()
    try:
        gconf_client = gconf.client_get_default()
        key = gconf_client.get(url_handlers_key + "command")
        enabled = gconf_client.get(url_handlers_key + "enabled")
        if command:
            associated = key.get_string() == command and enabled.get_bool()
        else:
            associated = key.get_string() != "" and enabled.get_bool()
    finally:
        gconf_lock.release()
    return associated

